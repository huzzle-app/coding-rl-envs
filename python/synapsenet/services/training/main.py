"""
SynapseNet Training Service
Terminal Bench v2 - Training Job Orchestration (Celery/FastAPI)

Contains bugs:
- M2: Gradient accumulation overflow
- M5: Training data not shuffled between epochs
- M8: Mixed-precision NaN propagation
- M9: Data augmentation seed not set
- A1: Parameter server race (via shared.utils.distributed)
"""
import os
import time
import uuid
import logging
import random
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)


class TrainingDataIterator:
    """
    Training data iterator.

    BUG M5: Data is not shuffled between epochs. The model sees the same
    order every epoch, leading to poor generalization.
    BUG M9: Random seed for data augmentation not set, so augmentations
    are not reproducible across runs.
    """

    def __init__(self, dataset: List[Dict[str, Any]], batch_size: int = 32):
        self.dataset = dataset
        self.batch_size = batch_size
        self._index = 0
        self._epoch = 0

    def __iter__(self):
        return self

    def __next__(self) -> List[Dict[str, Any]]:
        if self._index >= len(self.dataset):
            self._epoch += 1
            self._index = 0
            
            # Should: random.shuffle(self.dataset)
            raise StopIteration

        batch = self.dataset[self._index:self._index + self.batch_size]
        self._index += self.batch_size
        return batch

    def reset(self):
        """Reset iterator for new epoch."""
        self._index = 0
        self._epoch += 1
        


class LearningRateScheduler:
    """
    Learning rate scheduler.

    BUG M6: Off-by-one error in step counting. The scheduler counts
    from 0, but the warmup period check uses > instead of >=,
    so the first post-warmup step uses warmup LR.
    """

    def __init__(self, base_lr: float = 0.001, warmup_steps: int = 100, decay_factor: float = 0.1):
        self.base_lr = base_lr
        self.warmup_steps = warmup_steps
        self.decay_factor = decay_factor
        self._step = 0

    def step(self) -> float:
        """
        Get learning rate for current step and advance.

        BUG M6: Off-by-one - warmup period extends one step too long.
        """
        self._step += 1

        if self._step < self.warmup_steps:
            # Linear warmup
            lr = self.base_lr * (self._step / self.warmup_steps)
        elif self._step > self.warmup_steps:  
            # Decay after warmup
            decay_steps = self._step - self.warmup_steps
            lr = self.base_lr * (self.decay_factor ** (decay_steps / 1000))
        else:
            
            lr = self.base_lr * (self._step / self.warmup_steps)

        return lr

    def get_step(self) -> int:
        return self._step


class DataAugmenter:
    """
    Data augmentation for training.

    BUG M9: Does not set random seed, so augmentations are non-reproducible.
    """

    def __init__(self, seed: Optional[int] = None):
        
        self.seed = seed
        

    def augment(self, data: np.ndarray) -> np.ndarray:
        """
        Apply data augmentation.

        BUG M9: Uses random without seed, producing different results each run.
        """
        
        noise = np.random.randn(*data.shape) * 0.01
        return data + noise

    def augment_batch(self, batch: List[np.ndarray]) -> List[np.ndarray]:
        """Augment a batch of data."""
        return [self.augment(item) for item in batch]


class TrainingOrchestrator:
    """
    Orchestrate training jobs.

    BUG M2: No gradient clipping during accumulation.
    BUG M8: Mixed precision scaling wrong.
    """

    def __init__(self):
        self._active_jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(
        self,
        model_id: str,
        dataset_id: str,
        hyperparameters: Dict[str, Any],
    ) -> str:
        """Create a new training job."""
        job_id = str(uuid.uuid4())
        self._active_jobs[job_id] = {
            "job_id": job_id,
            "model_id": model_id,
            "dataset_id": dataset_id,
            "hyperparameters": hyperparameters,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {},
        }
        return job_id

    def run_training_step(
        self,
        job_id: str,
        batch_data: np.ndarray,
        use_mixed_precision: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a single training step.

        BUG M2: Gradients are accumulated without clipping.
        BUG M8: Mixed precision loss scale is wrong.
        """
        job = self._active_jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Simulate gradient computation
        gradients = np.random.randn(*batch_data.shape) * batch_data

        
        # Should clip: gradients = np.clip(gradients, -1.0, 1.0)

        if use_mixed_precision:
            
            loss_scale = 1.0  # Should be 65536.0
            gradients = gradients * loss_scale

        loss = float(np.mean(gradients ** 2))
        job["metrics"]["last_loss"] = loss
        job["status"] = "running"

        return {
            "job_id": job_id,
            "loss": loss,
            "gradients_norm": float(np.linalg.norm(gradients)),
        }

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get training job status."""
        return self._active_jobs.get(job_id)


class EarlyStopping:
    """Early stopping to prevent overfitting during training."""

    def __init__(self, patience: int = 10, min_delta: float = 0.001, mode: str = "min"):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self._best_value = None
        self._counter = 0
        self._stopped = False

    def step(self, value: float) -> bool:
        """Record a metric value and return True if training should stop."""
        if self._stopped:
            return True

        if self._best_value is None:
            self._best_value = value
            return False

        if self.mode == "min":
            improved = value < self._best_value - self.min_delta
        else:
            improved = value > self._best_value + self.min_delta

        if improved:
            self._best_value = value
            self._counter = 0
        else:
            self._counter += 1

        if self._counter > self.patience:
            self._stopped = True
            return True

        return False

    def get_best(self) -> Optional[float]:
        return self._best_value

    def is_stopped(self) -> bool:
        return self._stopped

    def reset(self):
        self._best_value = None
        self._counter = 0
        self._stopped = False


class MetricTracker:
    """Track training metrics across epochs with smoothing."""

    def __init__(self, smoothing: float = 0.9):
        self.smoothing = smoothing
        self._raw: Dict[str, List[float]] = {}
        self._smoothed: Dict[str, float] = {}

    def update(self, name: str, value: float):
        """Record a metric value."""
        if name not in self._raw:
            self._raw[name] = []
            self._smoothed[name] = 0.0
        self._raw[name].append(value)
        self._smoothed[name] = self.smoothing * self._smoothed[name] + (1 - self.smoothing) * value

    def get_current(self, name: str) -> Optional[float]:
        """Get the latest raw value."""
        values = self._raw.get(name, [])
        return values[-1] if values else None

    def get_smoothed(self, name: str) -> Optional[float]:
        """Get the exponentially smoothed value."""
        return self._smoothed.get(name)

    def get_best(self, name: str, mode: str = "min") -> Optional[float]:
        """Get the best value for a metric."""
        values = self._raw.get(name, [])
        if not values:
            return None
        return min(values) if mode == "min" else max(values)

    def get_history(self, name: str) -> List[float]:
        """Get full history for a metric."""
        return list(self._raw.get(name, []))

    def compute_moving_average(self, name: str, window: int = 10) -> Optional[float]:
        """Compute a simple moving average over the last window values."""
        values = self._raw.get(name, [])
        if not values:
            return None
        window_vals = values[-window:]
        return sum(window_vals) / len(window_vals)


orchestrator = TrainingOrchestrator()

app = {
    "service": "training",
    "port": 8004,
    "orchestrator": orchestrator,
}
