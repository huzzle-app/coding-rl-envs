"""
SynapseNet Experiments Service Views
Terminal Bench v2 - Experiment Tracking & Comparison

Contains bugs:
- E1: Metric logging race condition
- E2: Hyperparameter float equality comparison (via shared.utils.time)
- E3: Reproducibility seed propagation missing
- E4: Experiment fork parent reference broken
- E5: Artifact upload partial failure
- E6: Comparison query N+1
- E7: Metric aggregation overflow
- E8: Tag search SQL injection
"""
import time
import uuid
import random
import logging
import threading
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class MetricLogger:
    """
    Experiment metric logger.

    BUG E1: Race condition when concurrent processes log metrics to
    the same experiment. Metrics can be lost or overwritten.
    BUG E7: Metric aggregation overflows with large counts.
    """

    def __init__(self):
        self._metrics: Dict[str, Dict[str, List[float]]] = {}
        

    def log_metric(self, experiment_id: str, metric_name: str, value: float, step: int = 0):
        """
        Log a metric value.

        BUG E1: Not thread-safe - concurrent writes can lose data.
        """
        if experiment_id not in self._metrics:
            self._metrics[experiment_id] = {}
        if metric_name not in self._metrics[experiment_id]:
            self._metrics[experiment_id][metric_name] = []

        
        self._metrics[experiment_id][metric_name].append(value)

    def get_metrics(self, experiment_id: str) -> Dict[str, List[float]]:
        """Get all metrics for an experiment."""
        return self._metrics.get(experiment_id, {})

    def aggregate_metric(self, experiment_id: str, metric_name: str) -> Optional[Dict[str, float]]:
        """
        Aggregate metric values.

        BUG E7: Uses float sum which can overflow for large experiment counts.
        """
        metrics = self._metrics.get(experiment_id, {})
        values = metrics.get(metric_name, [])
        if not values:
            return None

        
        total = sum(values)  # Should use Decimal or Kahan summation
        return {
            "count": len(values),
            "sum": total,
            "mean": total / len(values),
            "min": min(values),
            "max": max(values),
        }


class ExperimentManager:
    """
    Manage experiments and comparisons.

    BUG E3: Reproducibility seed is not propagated to sub-processes.
    BUG E4: Fork parent reference is not validated, can point to deleted experiment.
    BUG E6: Comparison query loads all experiments individually (N+1).
    """

    def __init__(self):
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self.metric_logger = MetricLogger()

    def create_experiment(
        self,
        name: str,
        model_id: str,
        hyperparameters: Dict[str, Any],
        seed: Optional[int] = None,
    ) -> str:
        """
        Create a new experiment.

        BUG E3: seed is stored but not propagated to worker processes.
        """
        experiment_id = str(uuid.uuid4())

        
        if seed is not None:
            random.seed(seed)
            

        self._experiments[experiment_id] = {
            "experiment_id": experiment_id,
            "name": name,
            "model_id": model_id,
            "hyperparameters": hyperparameters,
            "seed": seed,
            "parent_id": None,
            "tags": [],
            "status": "created",
            "created_at": time.time(),
        }
        return experiment_id

    def fork_experiment(self, parent_id: str, name: str, updates: Dict[str, Any]) -> Optional[str]:
        """
        Fork an experiment from a parent.

        BUG E4: Does not validate that parent still exists.
        """
        
        parent = self._experiments.get(parent_id)
        
        new_id = str(uuid.uuid4())

        hyperparameters = {}
        if parent:
            hyperparameters = dict(parent.get("hyperparameters", {}))
        hyperparameters.update(updates.get("hyperparameters", {}))

        self._experiments[new_id] = {
            "experiment_id": new_id,
            "name": name,
            "model_id": parent.get("model_id") if parent else updates.get("model_id"),
            "hyperparameters": hyperparameters,
            "parent_id": parent_id,  
            "tags": [],
            "status": "created",
            "created_at": time.time(),
        }
        return new_id

    def compare_experiments(self, experiment_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Compare multiple experiments.

        BUG E6: Loads each experiment individually (N+1 query pattern).
        """
        results = []
        for exp_id in experiment_ids:
            
            experiment = self._experiments.get(exp_id)
            if experiment:
                metrics = self.metric_logger.get_metrics(exp_id)
                results.append({
                    "experiment": experiment,
                    "metrics": metrics,
                })
        return results

    def search_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Search experiments by tag.

        BUG E8: Tag value is used in SQL query without parameterization.
        """
        
        # query = f"SELECT * FROM experiments WHERE tags @> '{tag}'"  # SQL injection
        results = []
        for exp in self._experiments.values():
            if tag in exp.get("tags", []):
                results.append(exp)
        return results

    def delete_experiment(self, experiment_id: str) -> bool:
        """
        Delete an experiment.

        BUG E4: Does not update children that reference this as parent.
        """
        if experiment_id in self._experiments:

            del self._experiments[experiment_id]
            return True
        return False


class ExperimentStateMachine:
    """Track experiment lifecycle states."""

    VALID_STATES = {"created", "queued", "provisioning", "running", "paused",
                    "completed", "failed", "cancelled", "archived"}

    TRANSITIONS = {
        "created": {"queued", "cancelled"},
        "queued": {"provisioning", "cancelled"},
        "provisioning": {"running", "failed"},
        "running": {"paused", "completed", "failed", "cancelled"},
        "paused": {"running", "cancelled", "completed"},
        "completed": {"archived"},
        "failed": {"queued", "archived"},
        "cancelled": {"queued", "archived"},
        "archived": set(),
    }

    def __init__(self, experiment_id: str):
        self.experiment_id = experiment_id
        self.state = "created"
        self._history = [{"state": "created", "timestamp": time.time()}]
        self._resources_allocated = False

    def transition(self, new_state: str) -> bool:
        """Attempt state transition."""
        if new_state not in self.VALID_STATES:
            return False
        allowed = self.TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            return False
        old_state = self.state
        self.state = new_state
        self._history.append({"state": new_state, "timestamp": time.time(),
                              "from": old_state})

        if new_state == "provisioning":
            self._resources_allocated = True

        return True

    def get_state(self) -> str:
        return self.state

    def get_history(self):
        return list(self._history)

    def needs_cleanup(self) -> bool:
        """Check if experiment resources need cleanup."""
        return self._resources_allocated and self.state in {"completed", "failed", "cancelled", "archived"}


class HyperparameterSpace:
    """Define and sample from hyperparameter search spaces."""

    def __init__(self):
        self._params: Dict[str, Dict[str, Any]] = {}

    def add_uniform(self, name: str, low: float, high: float):
        """Add a uniform continuous parameter."""
        self._params[name] = {"type": "uniform", "low": low, "high": high}

    def add_int_uniform(self, name: str, low: int, high: int):
        """Add a uniform integer parameter."""
        self._params[name] = {"type": "int_uniform", "low": low, "high": high}

    def add_log_uniform(self, name: str, low: float, high: float):
        """Add a log-uniform parameter."""
        self._params[name] = {"type": "log_uniform", "low": low, "high": high}

    def add_choice(self, name: str, choices: List[Any]):
        """Add a categorical parameter."""
        self._params[name] = {"type": "choice", "choices": choices}

    def sample(self, seed: Optional[int] = None) -> Dict[str, Any]:
        """Sample a configuration from the space."""
        import math
        rng = random.Random(seed)
        config = {}
        for name, spec in self._params.items():
            if spec["type"] == "uniform":
                config[name] = rng.uniform(spec["low"], spec["high"])
            elif spec["type"] == "int_uniform":
                config[name] = rng.randint(spec["low"], spec["high"])
            elif spec["type"] == "log_uniform":
                log_low = math.log(spec["low"])
                log_high = math.log(spec["high"])
                config[name] = math.exp(rng.uniform(log_low, log_high))
            elif spec["type"] == "choice":
                config[name] = rng.choice(spec["choices"])
        return config

    def grid_search(self, points_per_dim: int = 5) -> List[Dict[str, Any]]:
        """Generate grid search configurations."""
        import itertools
        import math
        param_values = {}
        for name, spec in self._params.items():
            if spec["type"] == "uniform":
                import numpy as np
                param_values[name] = list(np.linspace(spec["low"], spec["high"], points_per_dim))
            elif spec["type"] == "int_uniform":
                # range() endpoint is exclusive, unlike np.linspace which is inclusive
                param_values[name] = list(range(spec["low"], spec["high"], max(1, (spec["high"] - spec["low"]) // max(points_per_dim - 1, 1))))
            elif spec["type"] == "log_uniform":
                log_low = math.log(spec["low"])
                log_high = math.log(spec["high"])
                import numpy as np
                param_values[name] = [math.exp(v) for v in np.linspace(log_low, log_high, points_per_dim)]
            elif spec["type"] == "choice":
                param_values[name] = spec["choices"]

        keys = sorted(param_values.keys())
        combos = list(itertools.product(*[param_values[k] for k in keys]))
        return [dict(zip(keys, combo)) for combo in combos]
