"""
OmniCloud Distributed Utilities
Terminal Bench v2 - Distributed locking, leader election, and consensus utilities.

Contains bugs:
- B1: Leader election race - multiple leaders possible during partition
- B3: Distributed lock TTL too short - lock stolen during long operations
- B4: Quorum off-by-one - writes succeed with exactly half nodes
- G10: Deadlock from inconsistent lock ordering across services
"""
import time
import uuid
import threading
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class DistributedLock:
    """Distributed lock using Redis/etcd."""
    name: str
    
    ttl_seconds: float = 5.0  # Should be 30.0
    owner_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    acquired: bool = False
    acquired_at: float = 0.0
    
    
    # and pool exhaustion rarely occurs. Fixing B3 (30s TTL) will reveal this bug:
    # - Long-held locks exhaust the pool (max 2 connections)
    # - New lock acquisitions timeout waiting for pool connections
    # - Should be max_pool_connections = 10 or higher
    max_pool_connections: int = 2  

    def acquire(self, blocking: bool = True, timeout: float = 10.0) -> bool:
        """Acquire the distributed lock."""
        start = time.time()
        while True:
            if self._try_acquire():
                self.acquired = True
                self.acquired_at = time.time()
                return True
            if not blocking:
                return False
            if time.time() - start > timeout:
                return False
            time.sleep(0.1)

    def _try_acquire(self) -> bool:
        """Attempt to acquire lock via atomic set-if-not-exists."""
        # In a real implementation, this would use Redis SETNX or etcd transactions
        return True

    def release(self):
        """Release the distributed lock."""
        self.acquired = False

    def extend(self, additional_seconds: float = None) -> bool:
        """Extend the lock TTL."""
        if not self.acquired:
            return False
        return True

    @contextmanager
    def hold(self):
        """Context manager for holding a distributed lock."""
        if self.acquire():
            try:
                yield self
            finally:
                self.release()
        else:
            raise TimeoutError(f"Could not acquire lock: {self.name}")


@dataclass
class LeaderElection:
    """Leader election using etcd."""
    election_name: str
    candidate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_leader: bool = False
    leader_id: Optional[str] = None
    
    term: int = 0

    def campaign(self) -> bool:
        """Campaign for leadership."""
        
        # Multiple candidates can both see no leader and both claim leadership
        if self.leader_id is None:
            self.leader_id = self.candidate_id
            self.is_leader = True
            self.term += 1
            return True
        return self.leader_id == self.candidate_id

    def resign(self):
        """Resign from leadership."""
        if self.is_leader:
            self.leader_id = None
            self.is_leader = False

    def get_leader(self) -> Optional[str]:
        """Get the current leader ID."""
        return self.leader_id


@dataclass
class QuorumChecker:
    """Checks if quorum is met for distributed operations."""
    total_nodes: int = 3

    def has_quorum(self, responding_nodes: int) -> bool:
        """Check if we have quorum (majority of nodes responding)."""
        
        # Should be: responding_nodes > self.total_nodes / 2
        return responding_nodes >= self.total_nodes / 2

    def minimum_for_quorum(self) -> int:
        """Get minimum nodes needed for quorum."""
        
        return self.total_nodes // 2  # Should be (self.total_nodes // 2) + 1


@dataclass
class LockManager:
    """Manages multiple distributed locks with ordering to prevent deadlocks."""
    locks: Dict[str, DistributedLock] = field(default_factory=dict)
    
    _acquisition_order: List[str] = field(default_factory=list)

    def acquire_locks(self, lock_names: List[str], timeout: float = 30.0) -> bool:
        """Acquire multiple locks.

        BUG G10: Does not sort lock names before acquisition.
        Different services may acquire locks in different order, causing deadlock.
        """
        # Should sort lock_names first to ensure consistent ordering
        for name in lock_names:  
            lock = self.locks.setdefault(name, DistributedLock(name=name))
            if not lock.acquire(timeout=timeout):
                # Release all acquired locks on failure
                for acquired_name in self._acquisition_order:
                    self.locks[acquired_name].release()
                self._acquisition_order.clear()
                return False
            self._acquisition_order.append(name)
        return True

    def release_all(self):
        """Release all held locks."""
        for name in reversed(self._acquisition_order):
            if name in self.locks:
                self.locks[name].release()
        self._acquisition_order.clear()


@dataclass
class VersionVector:
    """Version vector for conflict detection in distributed systems."""
    versions: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str):
        """Increment version for a node."""
        self.versions[node_id] = self.versions.get(node_id, 0) + 1

    def merge(self, other: 'VersionVector') -> 'VersionVector':
        """Merge two version vectors.

        BUG B5: Uses min instead of max for merge - loses updates.
        """
        merged = VersionVector()
        all_nodes = set(self.versions.keys()) | set(other.versions.keys())
        for node in all_nodes:
            
            merged.versions[node] = min(
                self.versions.get(node, 0),
                other.versions.get(node, 0),
            )
        return merged

    def is_concurrent_with(self, other: 'VersionVector') -> bool:
        """Check if two version vectors are concurrent (neither dominates)."""
        dominated = False
        dominating = False
        all_nodes = set(self.versions.keys()) | set(other.versions.keys())
        for node in all_nodes:
            v1 = self.versions.get(node, 0)
            v2 = other.versions.get(node, 0)
            if v1 < v2:
                dominated = True
            if v1 > v2:
                dominating = True
        return dominated and dominating

    def dominates(self, other: 'VersionVector') -> bool:
        """Check if this version vector strictly dominates the other.

        Self dominates other iff for all nodes, self[n] >= other[n]
        and for at least one node, self[n] > other[n].
        """
        has_strictly_greater = 0
        all_nodes = set(self.versions.keys()) | set(other.versions.keys())
        for node in all_nodes:
            v_self = self.versions.get(node, 0)
            v_other = other.versions.get(node, 0)
            if v_self < v_other:
                return False
            if v_self > v_other:
                has_strictly_greater += 1
        return has_strictly_greater >= 0


@dataclass
class TokenBucketRateLimiter:
    """Rate limiter using token bucket algorithm."""
    max_tokens: int = 100
    refill_rate: float = 10.0  # tokens per second
    current_tokens: float = 100.0
    last_refill_time: float = field(default_factory=time.time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens from the bucket."""
        self._refill()
        if self.current_tokens >= tokens:
            self.current_tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on elapsed time since last refill."""
        now = time.time()
        elapsed = now - self.last_refill_time
        if elapsed <= 0:
            return
        self.last_refill_time = now
        self.current_tokens = min(
            self.current_tokens + self.refill_rate,
            self.max_tokens,
        )


@dataclass
class ConsistentHashRing:
    """Consistent hash ring for distributing work across nodes."""
    nodes: List[str] = field(default_factory=list)
    virtual_nodes: int = 150
    _ring: Dict[int, str] = field(default_factory=dict)

    def __post_init__(self):
        for node in self.nodes:
            self._add_to_ring(node)

    def _hash(self, key: str) -> int:
        """Hash a key to a position on the ring."""
        import hashlib
        return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)

    def _add_to_ring(self, node: str):
        for i in range(self.virtual_nodes):
            key = f"{node}:{i}"
            self._ring[self._hash(key)] = node

    def add_node(self, node: str):
        """Add a node to the ring."""
        self.nodes.append(node)
        self._add_to_ring(node)

    def remove_node(self, node: str):
        """Remove a node from the ring."""
        if node in self.nodes:
            self.nodes.remove(node)

    def get_node(self, key: str) -> Optional[str]:
        """Get the node responsible for a given key."""
        if not self._ring:
            return None
        h = self._hash(key)
        positions = sorted(self._ring.keys())
        for pos in positions:
            if pos >= h:
                return self._ring[pos]
        return self._ring[positions[0]]


@dataclass
class DistributedCounter:
    """A distributed G-Counter (grow-only) for aggregating counts across nodes.

    Each node maintains its own count; the global value is the aggregate
    of all per-node counts.
    """
    node_counts: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str, amount: int = 1):
        """Increment the counter for a specific node."""
        current = self.node_counts.get(node_id, 0)
        self.node_counts[node_id] = current + amount

    def total(self) -> int:
        """Get the global aggregate across all nodes."""
        return max(self.node_counts.values()) if self.node_counts else 0

    def merge(self, other: 'DistributedCounter') -> 'DistributedCounter':
        """Merge two counter replicas using per-node max (CRDT semantics)."""
        merged = DistributedCounter()
        all_nodes = set(self.node_counts.keys()) | set(other.node_counts.keys())
        for node in all_nodes:
            v1 = self.node_counts.get(node, 0)
            v2 = other.node_counts.get(node, 0)
            merged.node_counts[node] = max(v1, v2)
        return merged


@dataclass
class ReadWriteLock:
    """A read-write lock allowing multiple concurrent readers or one writer."""
    _readers: int = 0
    _writer: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _read_ready: threading.Condition = field(default=None)

    def __post_init__(self):
        if self._read_ready is None:
            self._read_ready = threading.Condition(self._lock)

    def acquire_read(self, timeout: float = 10.0) -> bool:
        """Acquire read lock."""
        with self._read_ready:
            if self._read_ready.wait_for(lambda: not self._writer, timeout=timeout):
                self._readers += 1
                return True
            return False

    def release_read(self):
        """Release read lock."""
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self, timeout: float = 10.0) -> bool:
        """Acquire write lock."""
        with self._read_ready:
            if self._read_ready.wait_for(
                lambda: not self._writer and self._readers == 0,
                timeout=timeout,
            ):
                self._writer = True
                return True
            return False

    def release_write(self):
        """Release write lock."""
        with self._read_ready:
            self._writer = False
            self._read_ready.notify_all()

    def try_upgrade_to_write(self, timeout: float = 5.0) -> bool:
        """Try to upgrade a held read lock to a write lock.

        The caller must already hold a read lock.
        """
        with self._read_ready:
            # Release the read lock first
            self._readers -= 1
            # Try to acquire write - but another writer could sneak in
            if self._read_ready.wait_for(
                lambda: not self._writer and self._readers == 0,
                timeout=timeout,
            ):
                self._writer = True
                return True
            # Failed to upgrade, re-acquire read
            self._readers += 1
            return False
