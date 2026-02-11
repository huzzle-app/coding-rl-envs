"""
Distributed systems utilities.
"""
import asyncio
import time
import logging
from typing import Optional, Callable, Any
from uuid import uuid4
import redis
import consul

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    Distributed lock using Redis.

    BUG A3: Lock timeout too short for long operations
    BUG D10: Inconsistent lock ordering can cause deadlocks
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_name: str,
        
        timeout: float = 5.0,
        retry_interval: float = 0.1,
        max_retries: int = 50,
    ):
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.lock_id = str(uuid4())
        self._acquired = False

    async def acquire(self) -> bool:
        """
        Acquire the distributed lock.

        BUG A3: Lock can be stolen if operation takes longer than timeout
        """
        for attempt in range(self.max_retries):
            # Try to set the lock with NX (only if not exists)
            acquired = self.redis.set(
                self.lock_name,
                self.lock_id,
                nx=True,
                ex=int(self.timeout),  
            )

            if acquired:
                self._acquired = True
                logger.debug(f"Acquired lock {self.lock_name}")
                return True

            # Wait before retry
            await asyncio.sleep(self.retry_interval)

        logger.warning(f"Failed to acquire lock {self.lock_name} after {self.max_retries} attempts")
        return False

    async def release(self) -> bool:
        """
        Release the distributed lock.

        BUG A3: Lock might have been stolen, releasing wrong lock
        """
        if not self._acquired:
            return False

        
        # Another process might have stolen it after timeout
        current_value = self.redis.get(self.lock_name)

        if current_value and current_value.decode() == self.lock_id:
            
            self.redis.delete(self.lock_name)
            self._acquired = False
            return True
        else:
            logger.warning(f"Lock {self.lock_name} was stolen or expired")
            self._acquired = False
            return False

    async def extend(self, additional_time: float) -> bool:
        """Extend the lock timeout."""
        if not self._acquired:
            return False

        current_value = self.redis.get(self.lock_name)
        if current_value and current_value.decode() == self.lock_id:
            self.redis.expire(self.lock_name, int(self.timeout + additional_time))
            return True
        return False

    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise Exception(f"Could not acquire lock {self.lock_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


async def acquire_multiple_locks(
    redis_client: redis.Redis,
    lock_names: list,
    timeout: float = 5.0,
) -> list:
    """
    Acquire multiple locks.

    BUG D10: Locks acquired in arbitrary order - can cause deadlocks
    """
    locks = []

    
    for name in lock_names:  # Should be: sorted(lock_names)
        lock = DistributedLock(redis_client, name, timeout=timeout)
        if await lock.acquire():
            locks.append(lock)
        else:
            # Release all acquired locks on failure
            for acquired_lock in locks:
                await acquired_lock.release()
            raise Exception(f"Failed to acquire lock {name}")

    return locks


class LeaderElection:
    """
    Leader election using Consul.

    BUG A2: Race condition during failover
    """

    def __init__(
        self,
        consul_client: consul.Consul,
        service_name: str,
        node_id: str,
        session_ttl: int = 10,
    ):
        self.consul = consul_client
        self.service_name = service_name
        self.node_id = node_id
        self.session_ttl = session_ttl
        self.session_id: Optional[str] = None
        self._is_leader = False

    async def start_election(self) -> bool:
        """
        Start participating in leader election.

        BUG A2: Session creation and key acquisition not atomic
        """
        # Create session
        self.session_id = self.consul.session.create(
            name=f"{self.service_name}-{self.node_id}",
            ttl=self.session_ttl,
            behavior='delete',  # Delete key when session expires
        )

        
        # Another node could become leader in this window

        # Try to acquire leadership
        key = f"service/{self.service_name}/leader"
        acquired = self.consul.kv.put(
            key,
            self.node_id,
            acquire=self.session_id,
        )

        self._is_leader = acquired
        return acquired

    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._is_leader

    async def renew_session(self) -> bool:
        """Renew the Consul session."""
        if self.session_id:
            try:
                self.consul.session.renew(self.session_id)
                return True
            except Exception as e:
                logger.error(f"Failed to renew session: {e}")
                self._is_leader = False
                return False
        return False

    async def resign(self) -> None:
        """Resign from leadership."""
        if self.session_id:
            self.consul.session.destroy(self.session_id)
            self.session_id = None
            self._is_leader = False


def get_leader_id(consul_client: consul.Consul, service_name: str) -> Optional[str]:
    """
    Get the current leader ID.

    BUG A2: Might return stale data during failover
    """
    key = f"service/{service_name}/leader"
    index, data = consul_client.kv.get(key)

    
    if data:
        return data['Value'].decode()
    return None
