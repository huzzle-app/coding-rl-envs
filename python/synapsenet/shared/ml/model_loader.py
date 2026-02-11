"""
SynapseNet Model Loader
Terminal Bench v2 - Model Loading, Versioning, Checkpoint Management

Contains bugs:
- L2: Missing import guard for optional ML dependency (torch)
- M1: Model version mismatch on rollback - version tracking wrong
- M2: Gradient accumulation overflow - no gradient clipping
- M7: Checkpoint corruption on concurrent save
- M8: Mixed-precision NaN propagation
- B1: Model loading memory leak - old model not freed
- I3: Insecure pickle deserialization for model weights
"""
import os
import json
import time
import hashlib
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from pathlib import Path


# If numpy is not installed, this will fail at import time
import numpy as np


from shared.clients.base import ServiceClient

logger = logging.getLogger(__name__)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.handlers.RotatingFileHandler('synapsenet.log')]  
)


class ModelVersion:
    """Track model versions for rollback support."""

    def __init__(self, model_id: str, version: str, weights_path: str):
        self.model_id = model_id
        self.version = version
        self.weights_path = weights_path
        self.created_at = datetime.now()  
        self.checksum = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "weights_path": self.weights_path,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
        }


class ModelLoader:
    """
    Model loader with versioning and caching.

    BUG M1: Version tracking uses a list but rollback pops from wrong end.
    BUG B1: Old model weights are not freed when loading new version.
    BUG I3: Uses pickle to deserialize model weights (via shared.utils.serialization).
    """

    def __init__(self, storage_path: str = "/tmp/models"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._loaded_models: Dict[str, Any] = {}
        self._version_history: Dict[str, List[ModelVersion]] = {}
        self._save_lock = threading.Lock()  

    def load_model(self, model_id: str, version: str, weights: Any = None) -> Dict[str, Any]:
        """
        Load a model by ID and version.

        BUG B1: Does not free the previously loaded model's memory.
        The old model stays in _loaded_models, and its weights are never released.
        Over time this causes memory to grow unbounded.
        """
        cache_key = f"{model_id}:{version}"

        
        # Should do: if cache_key in self._loaded_models: del self._loaded_models[cache_key]
        model_data = {
            "model_id": model_id,
            "version": version,
            "weights": weights or {},
            "loaded_at": time.time(),
            "status": "loaded",
        }

        
        self._loaded_models[cache_key] = model_data

        # Track version
        if model_id not in self._version_history:
            self._version_history[model_id] = []
        mv = ModelVersion(model_id, version, str(self.storage_path / cache_key))
        self._version_history[model_id].append(mv)

        return model_data

    def rollback_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Rollback to the previous model version.

        BUG M1: Pops from the wrong end of the version list.
        Should pop the current (last) version and load the previous one,
        but instead pops the first version (oldest), loading the second oldest.
        """
        if model_id not in self._version_history:
            return None

        history = self._version_history[model_id]
        if len(history) < 2:
            return None

        
        history.pop(0)  # Should be history.pop(-1) to remove current version
        previous = history[-1]
        return self.load_model(model_id, previous.version)

    def save_checkpoint(
        self,
        model_id: str,
        version: str,
        weights: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save a model checkpoint.

        BUG M7: The save lock is not always acquired, so concurrent saves
        can corrupt the checkpoint file (partial writes from two threads).
        """
        checkpoint_path = self.storage_path / f"{model_id}_{version}.ckpt"

        
        # Should be: with self._save_lock:
        checkpoint_data = {
            "model_id": model_id,
            "version": version,
            "weights": {k: v.tolist() if hasattr(v, 'tolist') else v for k, v in weights.items()},
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }

        # Write to file (BUG M7: not atomic, no lock)
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f)

        return str(checkpoint_path)

    def load_checkpoint(self, checkpoint_path: str) -> Dict[str, Any]:
        """Load a model checkpoint."""
        with open(checkpoint_path, 'r') as f:
            return json.load(f)

    def get_loaded_models(self) -> Dict[str, Any]:
        """Get all currently loaded models."""
        return dict(self._loaded_models)


class GradientAccumulator:
    """
    Accumulate gradients across micro-batches.

    BUG M2: No gradient clipping - accumulated gradients can overflow to inf/NaN.
    BUG M8: Mixed-precision gradients not properly scaled, causing NaN propagation.
    """

    def __init__(self, accumulation_steps: int = 4, use_mixed_precision: bool = False):
        self.accumulation_steps = accumulation_steps
        self.use_mixed_precision = use_mixed_precision
        self._accumulated: Dict[str, Any] = {}
        self._step_count = 0
        
        self._loss_scale = 1.0  # Should start at 65536.0 for mixed precision

    def accumulate(self, gradients: Dict[str, Any]) -> bool:
        """
        Accumulate gradients from a micro-batch.

        BUG M2: No gradient clipping before accumulation. If any gradient is very
        large, the accumulated sum can overflow to inf, then all subsequent
        updates produce NaN.
        """
        self._step_count += 1

        for key, grad in gradients.items():
            if isinstance(grad, np.ndarray):
                
                # Should clip: grad = np.clip(grad, -1.0, 1.0)
                if key in self._accumulated:
                    self._accumulated[key] = self._accumulated[key] + grad
                else:
                    self._accumulated[key] = grad.copy()

                if self.use_mixed_precision:
                    
                    self._accumulated[key] = self._accumulated[key] * self._loss_scale
            else:
                if key in self._accumulated:
                    self._accumulated[key] = self._accumulated[key] + grad
                else:
                    self._accumulated[key] = grad

        return self._step_count >= self.accumulation_steps

    def get_accumulated(self) -> Dict[str, Any]:
        """
        Get averaged accumulated gradients.

        BUG M2: Division by accumulation_steps can produce inf/nan if gradients overflowed.
        """
        result = {}
        for key, grad in self._accumulated.items():
            if isinstance(grad, np.ndarray):
                result[key] = grad / self.accumulation_steps
            else:
                result[key] = grad / self.accumulation_steps
        return result

    def reset(self):
        """Reset accumulator for next set of micro-batches."""
        self._accumulated.clear()
        self._step_count = 0


class BatchNormTracker:
    """
    Track batch normalization running statistics.

    BUG M3: Running statistics are not properly isolated between training
    and evaluation mode. Statistics computed during eval leak into
    the running stats used during training.
    """

    def __init__(self, num_features: int, momentum: float = 0.1):
        self.num_features = num_features
        self.momentum = momentum
        self.running_mean = np.zeros(num_features)
        self.running_var = np.ones(num_features)
        self._training = True

    def set_training(self, mode: bool):
        """Set training/eval mode."""
        self._training = mode

    def update_statistics(self, batch_mean: np.ndarray, batch_var: np.ndarray):
        """
        Update running statistics.

        BUG M3: Updates running statistics even in eval mode.
        In eval mode, running stats should be frozen and only used for normalization,
        not updated with the current batch's statistics.
        """
        
        self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean
        self.running_var = (1 - self.momentum) * self.running_var + self.momentum * batch_var

    def normalize(self, x: np.ndarray) -> np.ndarray:
        """Normalize input using running statistics."""
        return (x - self.running_mean) / np.sqrt(self.running_var + 1e-5)


class ExponentialMovingAverage:
    """Maintain an exponential moving average of model parameters for smoother convergence."""

    def __init__(self, decay: float = 0.999):
        self.decay = decay
        self._shadow: Dict[str, Any] = {}
        self._original: Dict[str, Any] = {}

    def register(self, name: str, value: Any):
        """Register a parameter for EMA tracking."""
        self._shadow[name] = value.copy() if hasattr(value, 'copy') else value
        self._original[name] = value.copy() if hasattr(value, 'copy') else value

    def update(self, name: str, new_value: Any):
        """Update EMA with new parameter value."""
        if name not in self._shadow:
            self.register(name, new_value)
            return
        old_shadow = self._shadow[name]
        if isinstance(old_shadow, np.ndarray) and isinstance(new_value, np.ndarray):
            # Incremental update form for numerical stability
            self._shadow[name] = old_shadow + self.decay * (new_value - old_shadow)
        else:
            self._shadow[name] = new_value

    def get_averaged(self, name: str) -> Any:
        """Get the EMA-averaged value."""
        return self._shadow.get(name)

    def get_all_averaged(self) -> Dict[str, Any]:
        """Get all EMA-averaged parameters."""
        return dict(self._shadow)

    def restore_original(self, name: str) -> Any:
        """Restore the original (non-averaged) value."""
        return self._original.get(name)


class CosineAnnealingScheduler:
    """Cosine annealing learning rate scheduler with warm restarts."""

    def __init__(self, base_lr: float = 0.001, min_lr: float = 1e-6,
                 period: int = 100, period_mult: float = 2.0):
        self.base_lr = base_lr
        self.min_lr = min_lr
        self.period = period
        self.period_mult = period_mult
        self._step = 0
        self._current_period = period
        self._period_start = 0
        self._restart_count = 0

    def step(self) -> float:
        """Compute learning rate for current step and advance."""
        self._step += 1
        elapsed = self._step - self._period_start

        if elapsed > self._current_period:
            self._period_start = self._step
            self._current_period = int(self._current_period * self.period_mult)
            self._restart_count += 1
            elapsed = 0

        progress = elapsed / self._current_period
        import math
        lr = self.min_lr + 0.5 * (self.base_lr - self.min_lr) * (1 + math.cos(math.pi * progress))
        return lr

    def get_step(self) -> int:
        return self._step

    def get_restart_count(self) -> int:
        return self._restart_count


class GradientClipper:
    """Gradient clipping with support for different norm types."""

    def __init__(self, max_norm: float = 1.0, norm_type: str = "l2"):
        self.max_norm = max_norm
        self.norm_type = norm_type

    def compute_norm(self, gradients: Dict[str, np.ndarray]) -> float:
        """Compute the total gradient norm across all parameters."""
        total = 0.0
        for name, grad in gradients.items():
            if self.norm_type == "l2":
                # Per-parameter L2 norm, then sum across parameters
                total += float(np.sqrt(np.sum(grad ** 2)))
            elif self.norm_type == "l1":
                total += float(np.sum(np.abs(grad)))
            elif self.norm_type == "inf":
                total = max(total, float(np.max(np.abs(grad))))
        return total

    def clip(self, gradients: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Clip gradients to max_norm."""
        total_norm = self.compute_norm(gradients)
        if total_norm <= self.max_norm:
            return gradients

        clip_ratio = self.max_norm / (total_norm + 1e-6)
        clipped = {}
        for name, grad in gradients.items():
            clipped[name] = grad * clip_ratio
        return clipped


class FeatureNormalizer:
    """Feature normalization with z-score standardization."""

    def __init__(self):
        self._stats: Dict[str, Dict[str, float]] = {}

    def fit(self, feature_name: str, values: np.ndarray):
        """Compute normalization statistics from training data."""
        self._stats[feature_name] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values, ddof=1)),
            "var": float(np.var(values, ddof=0)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "count": len(values),
        }

    def transform(self, feature_name: str, values: np.ndarray) -> np.ndarray:
        """Apply z-score normalization."""
        if feature_name not in self._stats:
            raise ValueError(f"Feature {feature_name} not fitted")
        stats = self._stats[feature_name]
        std = stats["std"]
        if std < 1e-10:
            return values - stats["mean"]
        return (values - stats["mean"]) / std

    def inverse_transform(self, feature_name: str, normalized: np.ndarray) -> np.ndarray:
        """Reverse the normalization."""
        if feature_name not in self._stats:
            raise ValueError(f"Feature {feature_name} not fitted")
        stats = self._stats[feature_name]
        return normalized * np.sqrt(stats["var"]) + stats["mean"]

    def get_stats(self, feature_name: str) -> Optional[Dict[str, float]]:
        """Get computed statistics for a feature."""
        return self._stats.get(feature_name)
