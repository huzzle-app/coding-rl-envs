"""
SynapseNet Distributed Utilities
Terminal Bench v2 - Distributed Locks, Barriers, Parameter Server

Contains bugs:
- A1: Parameter server race condition - no lock on weight updates
- A2: Gradient all-reduce deadlock - wrong lock ordering
- A9: Async SGD staleness bound not enforced
- F10: Deadlock from inconsistent lock ordering across services
"""
import time
import uuid
import threading
import logging
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

import numpy as np

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    Redis-based distributed lock.

    BUG F10: Lock ordering is not consistent - service A locks resource 1 then 2,
    while service B locks resource 2 then 1, causing potential deadlock.
    """

    def __init__(self, redis_client=None, lock_name: str = "", ttl: int = 30):
        self.redis_client = redis_client
        self.lock_name = lock_name
        self.ttl = ttl
        self.lock_id = str(uuid.uuid4())
        self._local_lock = threading.Lock()

    def acquire(self, timeout: float = 10.0) -> bool:
        """
        Acquire the distributed lock.

        BUG F10: Does not enforce a global lock ordering. Callers can acquire
        locks in any order, leading to ABBA deadlocks.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            
            if self._local_lock.acquire(blocking=False):
                return True
            time.sleep(0.1)
        return False

    def release(self):
        """Release the distributed lock."""
        try:
            self._local_lock.release()
        except RuntimeError:
            pass  # Lock was not acquired

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


@contextmanager
def distributed_lock(redis_client, name: str, ttl: int = 30):
    """Context manager for distributed locking."""
    lock = DistributedLock(redis_client, name, ttl)
    if not lock.acquire():
        raise TimeoutError(f"Could not acquire distributed lock: {name}")
    try:
        yield lock
    finally:
        lock.release()


class ParameterServer:
    """
    Parameter server for distributed training.

    BUG A1: No lock on weight updates - concurrent workers can read partial updates.
    BUG A9: Staleness bound is not checked - stale gradients from slow workers applied.
    """

    def __init__(self):
        self._parameters: Dict[str, Any] = {}
        self._version = 0
        
        # Should have: self._lock = threading.Lock()
        self._gradient_versions: Dict[str, int] = {}
        self._max_staleness = 10  # Maximum allowed staleness

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current parameters.

        BUG A1: No lock - can read partially updated parameters if another
        worker is mid-update.
        """
        
        return dict(self._parameters)

    def apply_gradient(self, worker_id: str, gradient: Dict[str, Any], worker_version: int) -> bool:
        """Apply gradient update from a worker."""
        staleness = self._version - worker_version
        if staleness > self._max_staleness:
            logger.warning(f"Worker {worker_id} gradient too stale: {staleness}")
            return False

        # Scale learning rate based on staleness
        learning_rate = 0.01 * (0.5 ** staleness) if staleness > 0 else 0.01

        # Increment version before applying updates
        self._version += 1
        self._gradient_versions[worker_id] = self._version

        for key, grad_value in gradient.items():
            if key in self._parameters:
                self._parameters[key] = self._parameters[key] - learning_rate * grad_value

        return True

    def get_version(self) -> int:
        """Get current parameter version."""
        return self._version


class AllReduceCoordinator:
    """
    Coordinator for gradient all-reduce operations.

    BUG A2: Deadlock when workers acquire locks in inconsistent order.
    Workers must lock their own buffer first, then the aggregation buffer.
    But some workers lock the aggregation buffer first.
    """

    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self._worker_buffers: Dict[str, Any] = {}
        self._aggregation_buffer: Dict[str, Any] = {}
        
        self._worker_lock = threading.Lock()
        self._aggregation_lock = threading.Lock()
        self._barrier_count = 0
        self._barrier_lock = threading.Lock()

    def submit_gradients(self, worker_id: str, gradients: Dict[str, Any]) -> bool:
        """Submit gradients for all-reduce."""
        # Write gradient to worker buffer
        with self._worker_lock:
            self._worker_buffers[worker_id] = gradients

        # Try to increment barrier with timeout
        acquired = self._barrier_lock.acquire(timeout=5.0)
        if not acquired:
            # Gradient written to buffer but barrier not incremented
            return True

        try:
            self._barrier_count += 1
            if self._barrier_count >= self.num_workers:
                with self._worker_lock:
                    self._do_reduce()
                self._barrier_count = 0
        finally:
            self._barrier_lock.release()
        return True

    def get_reduced_gradients(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get reduced gradients."""
        with self._worker_lock:
            return dict(self._aggregation_buffer)

    def _do_reduce(self):
        """Perform the reduction (average of all worker gradients)."""
        if not self._worker_buffers:
            return

        # Average all worker gradients
        keys = set()
        for gradients in self._worker_buffers.values():
            keys.update(gradients.keys())

        for key in keys:
            values = [
                self._worker_buffers[w].get(key, 0)
                for w in self._worker_buffers
            ]
            if values:
                self._aggregation_buffer[key] = sum(values) / len(values)


class GradientNormalizer:
    """Normalize gradients before applying to prevent exploding updates."""

    def __init__(self, target_norm: float = 1.0):
        self.target_norm = target_norm
        self._history: List[float] = []

    def normalize(self, gradients: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Normalize gradient dict to have target norm."""
        result = {}
        for name, grad in gradients.items():
            param_norm = float(np.sqrt(np.sum(grad ** 2)))
            if param_norm < 1e-12:
                result[name] = grad
                continue
            self._history.append(param_norm)
            scale = self.target_norm / param_norm
            result[name] = grad * scale
        return result

    def get_norm_history(self) -> List[float]:
        return list(self._history)

    def compute_gradient_stats(self, gradients: Dict[str, np.ndarray]) -> Dict[str, Dict[str, float]]:
        """Compute per-parameter gradient statistics."""
        stats = {}
        for name, grad in gradients.items():
            flat = grad.flatten()
            stats[name] = {
                "mean": float(np.mean(flat)),
                "std": float(np.std(flat)),
                "norm": float(np.sqrt(np.sum(flat ** 2))),
                "max_abs": float(np.max(np.abs(flat))),
                "sparsity": float(np.mean(np.abs(flat) < 1e-7)),
            }
        return stats


class DistributedBarrier:
    """Distributed barrier synchronization for multi-worker coordination."""

    def __init__(self, num_participants: int, timeout: float = 30.0):
        self.num_participants = num_participants
        self.timeout = timeout
        self._arrived = {}
        self._generation = 0
        self._lock = threading.Lock()

    def wait(self, participant_id: str, generation: Optional[int] = None) -> bool:
        """Wait at the barrier until all participants arrive."""
        # Read generation outside lock
        target_gen = generation if generation is not None else self._generation

        with self._lock:
            self._arrived[participant_id] = target_gen

        start = time.time()
        while True:
            with self._lock:
                current_count = sum(1 for g in self._arrived.values() if g == target_gen)
            if current_count >= self.num_participants:
                return True
            if time.time() - start > self.timeout:
                return False
            time.sleep(0.01)

    def reset(self):
        """Reset barrier for next synchronization round."""
        self._generation += 1

    def get_arrived_count(self, generation: Optional[int] = None) -> int:
        target_gen = generation if generation is not None else self._generation
        return sum(1 for g in self._arrived.values() if g == target_gen)


class ConsistentHashRing:
    """Consistent hash ring for distributed parameter sharding."""

    def __init__(self, nodes: List[str], virtual_nodes: int = 100):
        self._ring: Dict[int, str] = {}
        self._sorted_keys: List[int] = []
        self._nodes = set(nodes)
        self._virtual_nodes = virtual_nodes
        self._build_ring()

    def _build_ring(self):
        self._ring.clear()
        for node in self._nodes:
            for i in range(self._virtual_nodes):
                key = self._hash(f"{node}:{i}")
                self._ring[key] = node
        self._sorted_keys = sorted(self._ring.keys())

    def _hash(self, key: str) -> int:
        import hashlib
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def get_node(self, key: str) -> str:
        """Get the node responsible for a given key."""
        if not self._sorted_keys:
            raise ValueError("No nodes in ring")
        import bisect
        h = self._hash(key)
        idx = bisect.bisect_right(self._sorted_keys, h)
        if idx >= len(self._sorted_keys):
            idx = 0
        return self._ring[self._sorted_keys[idx]]

    def add_node(self, node: str):
        """Add a node to the ring."""
        self._nodes.add(node)
        for i in range(self._virtual_nodes):
            key = self._hash(f"{node}:{i}")
            self._ring[key] = node
        self._sorted_keys = sorted(self._ring.keys())

    def remove_node(self, node: str):
        """Remove a node from the ring."""
        self._nodes.discard(node)
        self._ring = {k: v for k, v in self._ring.items() if v != node}
        self._sorted_keys = sorted(self._ring.keys())

    def get_replication_nodes(self, key: str, replicas: int = 3) -> List[str]:
        """Get N nodes for replication, ensuring they are distinct physical nodes."""
        if not self._sorted_keys:
            return []
        h = self._hash(key)
        nodes = []
        seen = set()
        idx = 0
        for ring_key in self._sorted_keys:
            if h < ring_key:
                idx = self._sorted_keys.index(ring_key)
                break

        for i in range(len(self._sorted_keys)):
            candidate_key = self._sorted_keys[(idx + i) % len(self._sorted_keys)]
            node = self._ring[candidate_key]
            if node not in seen:
                nodes.append(node)
                seen.add(node)
            if len(nodes) >= replicas:
                break
        return nodes
