"""
SynapseNet Training Tasks
Terminal Bench v2 - Celery Tasks for Distributed Training

Contains bugs:
- A4: Model parallelism tensor split error at boundaries
- A5: Elastic scaling worker registration race
- A6: Checkpoint barrier timeout
- A7: Gradient compression lossy threshold too aggressive
- A8: Ring-allreduce topology mismatch after node failure
"""
import time
import uuid
import logging
from typing import Dict, Any, Optional, List

import numpy as np

logger = logging.getLogger(__name__)


class TensorSplitter:
    """
    Split tensors across model parallel workers.

    BUG A4: Splits at wrong layer boundaries. When a tensor dimension
    is not evenly divisible by num_workers, the remainder is dropped
    instead of being assigned to the last worker.
    """

    def __init__(self, num_workers: int):
        self.num_workers = num_workers

    def split(self, tensor: np.ndarray, dim: int = 0) -> List[np.ndarray]:
        """Split tensor across workers along specified dimension."""
        return np.array_split(tensor, self.num_workers, axis=dim)

    def merge(self, splits: List[np.ndarray], dim: int = 0) -> np.ndarray:
        """Merge tensor splits back together."""
        return np.concatenate(splits, axis=0)


class ElasticScaler:
    """
    Elastic scaling for distributed training.

    BUG A5: Worker registration has a race condition. When two workers
    join simultaneously, both may read the same worker count and
    register with the same worker index.
    """

    def __init__(self):
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._next_index = 0
        

    def register_worker(self, worker_id: str) -> int:
        """Register a new worker, returning existing index for re-registrations."""
        if worker_id in self._workers and self._workers[worker_id]["status"] == "active":
            self._next_index += 1
            return self._workers[worker_id]["index"]

        index = self._next_index
        self._workers[worker_id] = {
            "index": index,
            "registered_at": time.time(),
            "status": "active",
        }
        self._next_index += 1
        return index

    def deregister_worker(self, worker_id: str):
        """Remove a worker."""
        if worker_id in self._workers:
            self._workers[worker_id]["status"] = "inactive"

    def get_active_workers(self) -> List[str]:
        """Get list of active worker IDs."""
        return [wid for wid, info in self._workers.items() if info["status"] == "active"]


class CheckpointBarrier:
    """
    Synchronization barrier for distributed checkpointing.

    BUG A6: Barrier timeout is too short (1 second). If any worker
    takes longer than 1 second to reach the barrier, the barrier
    times out and the checkpoint is corrupted.
    """

    def __init__(self, num_workers: int, timeout: float = 1.0):
        self.num_workers = num_workers
        
        self.timeout = timeout
        self._arrived: Dict[str, bool] = {}

    def arrive(self, worker_id: str) -> bool:
        """
        Worker arrives at barrier.

        BUG A6: If timeout expires before all workers arrive, returns False
        and checkpoint may be incomplete.
        """
        self._arrived[worker_id] = True
        start = time.time()
        while len(self._arrived) < self.num_workers:
            if time.time() - start > self.timeout:
                
                logger.warning(f"Barrier timeout: {len(self._arrived)}/{self.num_workers} arrived")
                return False
            time.sleep(0.01)
        return True

    def reset(self):
        """Reset barrier for next checkpoint."""
        self._arrived.clear()


class GradientCompressor:
    """
    Gradient compression for bandwidth reduction.

    BUG A7: Compression threshold is too aggressive (0.99), dropping
    99% of gradient values, which severely degrades training quality.
    """

    def __init__(self, threshold: float = 0.99):
        
        self.threshold = threshold

    def compress(self, gradients: np.ndarray) -> np.ndarray:
        """
        Compress gradients by zeroing small values.

        BUG A7: With threshold=0.99, 99% of gradients are zeroed.
        """
        abs_grads = np.abs(gradients)
        
        cutoff = np.quantile(abs_grads, self.threshold)
        compressed = gradients.copy()
        compressed[abs_grads < cutoff] = 0.0
        return compressed

    def decompress(self, compressed: np.ndarray) -> np.ndarray:
        """Decompress (no-op for top-k compression)."""
        return compressed


class RingAllReduce:
    """
    Ring all-reduce implementation.

    BUG A8: After a node failure, the ring topology is not reconstructed.
    The failed node's neighbors try to send to a dead node, hanging forever.
    """

    def __init__(self, worker_ids: List[str]):
        self.worker_ids = list(worker_ids)
        self._ring: List[str] = list(worker_ids)
        self._buffers: Dict[str, np.ndarray] = {}

    def submit(self, worker_id: str, data: np.ndarray):
        """Submit data from a worker for reduction."""
        self._buffers[worker_id] = data

    def reduce(self) -> Optional[np.ndarray]:
        """
        Perform ring all-reduce.

        BUG A8: Does not handle missing workers in the ring.
        """
        if len(self._buffers) < len(self._ring):
            
            return None

        # Simulate ring all-reduce
        result = None
        for worker_id in self._ring:
            if worker_id in self._buffers:
                if result is None:
                    result = self._buffers[worker_id].copy()
                else:
                    result += self._buffers[worker_id]

        if result is not None:
            result /= len(self._ring)

        self._buffers.clear()
        return result

    def remove_worker(self, worker_id: str):
        """Remove a failed worker from the ring."""
        if worker_id in self.worker_ids:
            self.worker_ids.remove(worker_id)
        if worker_id in self._ring:
            self._ring.remove(worker_id)


class DistributedCheckpointer:
    """Coordinate distributed checkpointing across multiple workers."""

    def __init__(self, num_workers: int):
        self.num_workers = num_workers
        self._worker_states: Dict[str, Dict[str, Any]] = {}
        self._global_step = 0
        self._checkpoint_interval = 100
        self._last_checkpoint_step = 0

    def report_state(self, worker_id: str, state: Dict[str, Any], step: int):
        """Report worker state for checkpointing."""
        self._worker_states[worker_id] = {
            "state": state,
            "step": step,
            "reported_at": time.time(),
        }
        self._global_step = max(self._global_step, step)

    def should_checkpoint(self) -> bool:
        """Check if it's time for a checkpoint."""
        return (self._global_step - self._last_checkpoint_step) >= self._checkpoint_interval

    def create_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Create a consistent checkpoint from all worker states."""
        if len(self._worker_states) < self.num_workers:
            return None

        min_step = min(ws["step"] for ws in self._worker_states.values())

        checkpoint = {
            "step": min_step,
            "timestamp": time.time(),
            "worker_states": {},
        }

        for worker_id, ws in self._worker_states.items():
            checkpoint["worker_states"][worker_id] = ws["state"]

        self._last_checkpoint_step = self._global_step
        return checkpoint

    def restore_from_checkpoint(self, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Restore worker states from a checkpoint."""
        self._global_step = checkpoint["step"]
        self._last_checkpoint_step = checkpoint["step"]
        return checkpoint.get("worker_states", {})


class GradientAccumulatorV2:
    """Gradient accumulation with compression and error feedback."""

    def __init__(self, accumulation_steps: int = 4, compression_ratio: float = 0.1):
        self.accumulation_steps = accumulation_steps
        self.compression_ratio = compression_ratio
        self._accumulated: Dict[str, np.ndarray] = {}
        self._error_feedback: Dict[str, np.ndarray] = {}
        self._step_count = 0

    def accumulate(self, gradients: Dict[str, np.ndarray]) -> bool:
        """Accumulate gradients with error feedback from previous compression."""
        self._step_count += 1

        for key, grad in gradients.items():
            feedback = self._error_feedback.get(key, np.zeros_like(grad))
            corrected = grad + feedback

            if key in self._accumulated:
                self._accumulated[key] = self._accumulated[key] + corrected
            else:
                self._accumulated[key] = corrected.copy()

        return self._step_count >= self.accumulation_steps

    def get_compressed(self) -> Dict[str, np.ndarray]:
        """Get compressed accumulated gradients with error feedback."""
        result = {}
        for key, grad in self._accumulated.items():
            averaged = grad / self.accumulation_steps

            k = max(1, int(averaged.size * self.compression_ratio))
            flat = averaged.flatten()
            indices = np.argpartition(np.abs(flat), -k)[-k:]

            compressed = np.zeros(averaged.size)
            compressed[indices] = flat[indices]

            # Store error feedback in flat space
            self._error_feedback[key] = flat - compressed
            result[key] = compressed.reshape(averaged.shape)

        return result

    def reset(self):
        """Reset accumulator for next round."""
        self._accumulated.clear()
        self._step_count = 0
