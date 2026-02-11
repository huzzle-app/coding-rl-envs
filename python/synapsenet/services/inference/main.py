"""
SynapseNet Inference Service
Terminal Bench v2 - Model Serving & Predictions (FastAPI)

Contains bugs:
- B1: Model loading memory leak - old models not freed
- B2: Request batching timeout too short - partial batches dropped
- B3: A/B testing traffic split precision loss
- B5: Model warm-up missing - cold start latency
- B7: Input validation schema drift
- B8: Output postprocessing type mismatch
- B9: Concurrent model swap race
- H1: Model cache eviction during inference
"""
import os
import time
import uuid
import hashlib
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict
from datetime import datetime, timezone
import random

import numpy as np

logger = logging.getLogger(__name__)


class ModelCache:
    """
    LRU cache for loaded models.

    BUG H1: Can evict a model that is currently being used for inference,
    causing the prediction to fail mid-request.
    BUG H8: LRU eviction doesn't consider model usage frequency.
    """

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get a model from cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def put(self, key: str, model: Any):
        """
        Put a model in cache.

        BUG H1: Evicts LRU model even if it's currently serving a request.
        BUG H8: Does not consider model priority or frequency of use.
        """
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                existing = self._cache[key]
                if isinstance(existing, dict) and isinstance(model, dict):
                    existing.update(model)
                else:
                    self._cache[key] = model
            else:
                if len(self._cache) >= self.max_size:
                    
                    
                    evicted_key, evicted_model = self._cache.popitem(last=False)
                    logger.info(f"Evicted model {evicted_key} from cache")
                self._cache[key] = model

    def remove(self, key: str):
        """Remove a model from cache."""
        with self._lock:
            self._cache.pop(key, None)


class RequestBatcher:
    """
    Batch inference requests for efficiency.

    BUG B2: Timeout is too short (0.001s), so batches are almost always
    flushed before reaching optimal size, reducing throughput.
    """

    def __init__(self, max_batch_size: int = 32, timeout: float = 0.001):
        self.max_batch_size = max_batch_size
        
        self.timeout = timeout
        self._pending: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def add_request(self, request: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Add a request to the batch.

        Returns a batch when max_size is reached or timeout expires.
        BUG B2: Timeout is so short that batches are flushed immediately.
        """
        with self._lock:
            self._pending.append(request)
            if len(self._pending) >= self.max_batch_size:
                batch = list(self._pending)
                self._pending.clear()
                return batch
        return None

    def flush(self) -> List[Dict[str, Any]]:
        """Flush pending requests as a batch."""
        with self._lock:
            batch = list(self._pending)
            self._pending.clear()
            return batch


class ABTestingRouter:
    """
    A/B testing traffic router.

    BUG B3: Traffic split uses float arithmetic that loses precision.
    For example, a 33.33% split might actually route 33.0% or 34.0%.
    """

    def __init__(self):
        self._experiments: Dict[str, Dict[str, float]] = {}

    def create_experiment(self, experiment_id: str, variants: Dict[str, float]):
        """
        Create an A/B test experiment.

        BUG B3: Does not validate that variant weights sum to exactly 1.0.
        """
        
        self._experiments[experiment_id] = variants

    def route_request(self, experiment_id: str, request_id: str) -> str:
        """
        Route a request to a variant.

        BUG B3: Uses float comparison for routing, causing precision loss.
        """
        if experiment_id not in self._experiments:
            return "control"

        variants = self._experiments[experiment_id]
        
        hash_val = int(hashlib.md5(request_id.encode()).hexdigest(), 16) % 10000
        normalized = hash_val / 10000.0  

        cumulative = 0.0
        for variant, weight in variants.items():
            cumulative += weight  
            if normalized < cumulative:
                return variant

        
        return list(variants.keys())[-1]


class InferenceEngine:
    """
    Model inference engine.

    BUG B5: No warm-up after loading - first requests have cold-start latency.
    BUG B7: Input validation uses original schema, not current model schema.
    BUG B8: Output postprocessing assumes float but model may return int.
    BUG B9: Model swap is not atomic - can serve partial model during swap.
    """

    def __init__(self):
        self.model_cache = ModelCache(max_size=int(os.environ.get("MODEL_CACHE_SIZE", "10")))
        self.batcher = RequestBatcher()
        self.ab_router = ABTestingRouter()
        self._current_models: Dict[str, Dict[str, Any]] = {}
        self._swap_lock = threading.Lock()  
        self._input_schemas: Dict[str, Dict] = {}

    def load_model(self, model_id: str, version: str, weights: Any = None) -> bool:
        """
        Load a model for serving.

        BUG B5: Does not warm up the model after loading.
        BUG B1: Old model reference not cleaned up.
        """
        cache_key = f"{model_id}:{version}"

        
        model_data = {
            "model_id": model_id,
            "version": version,
            "weights": weights or np.random.randn(100, 100),
            "loaded_at": time.time(),
        }

        self.model_cache.put(cache_key, model_data)
        self._current_models[model_id] = model_data

        
        # Should do: self._warmup(model_data)

        return True

    def swap_model(self, model_id: str, new_version: str, new_weights: Any = None) -> bool:
        """
        Atomically swap to a new model version.

        BUG B9: Does not use the swap lock, so a concurrent request can
        see a partially swapped model (old weights, new metadata).
        """
        
        # Should be: with self._swap_lock:
        old_model = self._current_models.get(model_id)
        new_model = {
            "model_id": model_id,
            "version": new_version,
            "weights": new_weights or np.random.randn(100, 100),
            "loaded_at": time.time(),
        }

        
        self._current_models[model_id] = new_model
        cache_key = f"{model_id}:{new_version}"
        self.model_cache.put(cache_key, new_model)

        return True

    def predict(self, model_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a prediction.

        BUG B7: Validates against original schema, not current model version schema.
        BUG B8: Assumes output is float, but model may return int labels.
        """
        model = self._current_models.get(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not loaded")

        
        if model_id in self._input_schemas:
            schema = self._input_schemas[model_id]
            # Schema might be outdated after model version change

        # Simulate inference
        weights = model.get("weights", np.eye(10))
        if isinstance(input_data.get("features"), list):
            features = np.array(input_data["features"])
            raw_output = np.dot(features[:min(len(features), weights.shape[1])],
                              weights[:min(len(features), weights.shape[1]), :min(10, weights.shape[0])])
        else:
            raw_output = np.random.randn(10)

        
        
        
        #          When a model is evicted mid-request by H1, the inference fails before
        #          reaching this latency calculation. Fixing H1 (adding reference counting
        #          to prevent eviction during use) will reveal that all reported latencies
        #          are wildly incorrect - showing hours instead of milliseconds.
        predictions = {
            "model_id": model_id,
            "version": model["version"],
            "output": float(raw_output[0]) if len(raw_output) > 0 else 0.0,  
            "scores": [float(x) for x in raw_output[:5]],
            "latency_ms": (time.time() - model.get("loaded_at", time.time())) * 1000,  
        }

        return predictions


class ModelDeploymentStateMachine:
    """Track model deployment lifecycle states and transitions."""

    VALID_STATES = {"created", "validating", "validated", "deploying", "deployed",
                    "serving", "draining", "deprecated", "failed", "rolled_back"}

    TRANSITIONS = {
        "created": {"validating", "failed"},
        "validating": {"validated", "failed"},
        "validated": {"deploying", "failed"},
        "deploying": {"deployed", "failed", "rolled_back"},
        "deployed": {"serving", "draining", "deprecated", "failed"},
        "serving": {"draining", "deprecated", "failed"},
        "draining": {"deprecated", "rolled_back"},
        "deprecated": {"deploying", "created"},
        "failed": {"created", "validating"},
        "rolled_back": {"created", "validating"},
    }

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.state = "created"
        self._history: List[Dict[str, Any]] = [{"state": "created", "timestamp": time.time()}]

    def transition(self, new_state: str) -> bool:
        """Attempt to transition to a new state."""
        if new_state not in self.VALID_STATES:
            return False
        allowed = self.TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            return False
        self.state = new_state
        self._history.append({"state": new_state, "timestamp": time.time()})
        return True

    def get_state(self) -> str:
        return self.state

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def can_serve_traffic(self) -> bool:
        """Check if model can serve inference requests."""
        return self.state in {"deployed", "serving"}

    def can_rollback(self) -> bool:
        """Check if model can be rolled back."""
        return self.state in {"deploying", "deployed", "serving", "draining"}


class CanaryAnalyzer:
    """Statistical analysis for canary deployments."""

    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self._control_metrics: List[float] = []
        self._canary_metrics: List[float] = []

    def record_control(self, value: float):
        """Record a metric from the control group."""
        self._control_metrics.append(value)

    def record_canary(self, value: float):
        """Record a metric from the canary group."""
        self._canary_metrics.append(value)

    def compute_significance(self) -> Dict[str, Any]:
        """Compute statistical significance of difference between control and canary."""
        if len(self._control_metrics) < 2 or len(self._canary_metrics) < 2:
            return {"significant": False, "reason": "insufficient_data"}

        control = np.array(self._control_metrics)
        canary = np.array(self._canary_metrics)

        control_mean = np.mean(control)
        canary_mean = np.mean(canary)
        control_var = np.var(control, ddof=1)
        canary_var = np.var(canary, ddof=1)

        pooled_se = np.sqrt(control_var / len(control) + canary_var / len(canary))
        if pooled_se < 1e-10:
            return {"significant": False, "reason": "zero_variance"}

        t_stat = (canary_mean - control_mean) / pooled_se

        import math
        df = min(len(control), len(canary)) - 1
        p_value = 2.0 * (1.0 - self._t_cdf(abs(t_stat), df))

        return {
            "significant": p_value < (1.0 - self.confidence_level),
            "t_statistic": float(t_stat),
            "p_value": float(p_value),
            "control_mean": float(control_mean),
            "canary_mean": float(canary_mean),
            "effect_size": float(canary_mean - control_mean),
        }

    def _t_cdf(self, t: float, df: int) -> float:
        """Approximate t-distribution CDF using normal approximation."""
        import math
        z = t * (1 - 1 / (4 * max(df, 1)))
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def should_promote(self) -> bool:
        """Determine if canary should be promoted based on metrics."""
        result = self.compute_significance()
        if not result["significant"]:
            return True
        return result.get("effect_size", 0) >= 0

    def should_rollback(self) -> bool:
        """Determine if canary should be rolled back."""
        result = self.compute_significance()
        if result["significant"] and result.get("effect_size", 0) < 0:
            return True
        return False


engine = InferenceEngine()

app = {
    "service": "inference",
    "port": 8005,
    "engine": engine,
}
