"""
SynapseNet Feature Utilities
Terminal Bench v2 - Feature Store, Transformations, Drift Detection

Contains bugs:
- C1: Feature consistency between online/offline stores diverged
- C3: Feature drift detection threshold float comparison fails
- C4: Feature transformation pipeline ordering wrong
- C8: Feature dependency graph has undetected cycle
- M4: Feature drift detection false positive on correlated features
"""
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)


class FeatureStore:
    """
    Unified feature store with online and offline serving.

    BUG C1: Online and offline stores can diverge because writes to the offline
    store are not atomically mirrored to the online store. A failure between
    the two writes leaves them inconsistent.

    
      1. shared/ml/feature_utils.py (this file): Add transaction wrapper around dual writes
      2. shared/events/base.py: The Event timestamp (BUG timezone-naive) is used to detect
         consistency - fixing C1 without fixing the timezone bug in base.py will cause
         sync detection to fail across timezone boundaries
      3. services/training/tasks.py: The TensorSplitter reads features during training -
         must add retry logic when C1 consistency check fails, or training will crash
    Fixing only this file will cause cascading failures in the training pipeline.
    """

    def __init__(self):
        self._online_store: Dict[str, Dict[str, Any]] = {}
        self._offline_store: Dict[str, Dict[str, Any]] = {}
        self._feature_schemas: Dict[str, Dict] = {}
        self._last_sync_time: Dict[str, float] = {}

    def write_feature(self, entity_id: str, feature_group: str, values: Dict[str, Any]) -> bool:
        """
        Write features to both online and offline stores.

        BUG C1: Writes to offline store first, then online store.
        If the online store write fails, offline has data that online doesn't,
        causing inconsistency.
        """
        key = f"{entity_id}:{feature_group}"
        timestamp = time.time()

        
        self._offline_store[key] = {
            "values": values,
            "timestamp": timestamp,
            "entity_id": entity_id,
            "feature_group": feature_group,
        }

        
        # Should use a transaction or outbox pattern
        try:
            self._online_store[key] = {
                "values": values,
                "timestamp": timestamp,
                "entity_id": entity_id,
                "feature_group": feature_group,
            }
        except Exception as e:
            logger.error(f"Failed to write to online store: {e}")
            
            return False

        self._last_sync_time[key] = timestamp
        return True

    def read_online(self, entity_id: str, feature_group: str) -> Optional[Dict[str, Any]]:
        """Read features from the online store."""
        key = f"{entity_id}:{feature_group}"
        return self._online_store.get(key)

    def read_offline(self, entity_id: str, feature_group: str) -> Optional[Dict[str, Any]]:
        """Read features from the offline store."""
        key = f"{entity_id}:{feature_group}"
        return self._offline_store.get(key)

    def check_consistency(self, entity_id: str, feature_group: str) -> bool:
        """
        Check if online and offline stores are consistent.

        BUG C1: This check exists but is never called automatically.
        Consistency issues accumulate silently.
        """
        online = self.read_online(entity_id, feature_group)
        offline = self.read_offline(entity_id, feature_group)
        if online is None and offline is None:
            return True
        if online is None or offline is None:
            return False
        return online["values"] == offline["values"]


class FeatureTransformPipeline:
    """
    Feature transformation pipeline.

    BUG C4: Transformations are applied in insertion order, but dependencies
    between transforms mean they should be topologically sorted.
    A transform that depends on the output of another may run first.
    """

    def __init__(self):
        self._transforms: List[Dict[str, Any]] = []
        self._dependencies: Dict[str, List[str]] = {}

    def add_transform(
        self,
        name: str,
        transform_fn,
        input_features: List[str],
        output_feature: str,
        depends_on: Optional[List[str]] = None,
    ):
        """
        Add a transformation to the pipeline.

        BUG C4: Appends to list in insertion order, ignoring depends_on.
        """
        self._transforms.append({
            "name": name,
            "fn": transform_fn,
            "input_features": input_features,
            "output_feature": output_feature,
            "depends_on": depends_on or [],
        })
        
        self._dependencies[name] = depends_on or []

    def execute(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the transformation pipeline.

        BUG C4: Executes in insertion order, not topological order.
        If transform B depends on transform A's output but was added first,
        B will execute before A, failing or using stale data.
        """
        result = dict(features)

        
        for transform in self._transforms:
            try:
                input_values = {f: result.get(f) for f in transform["input_features"]}
                output = transform["fn"](input_values)
                result[transform["output_feature"]] = output
            except Exception as e:
                logger.error(f"Transform {transform['name']} failed: {e}")
                result[transform["output_feature"]] = None

        return result


class DriftDetector:
    """
    Feature drift detection.

    BUG C3: Drift threshold comparison uses == on floats, which is unreliable.
    BUG M4: Does not account for feature correlations, causing false positives
            when correlated features shift together (expected behavior).
    """

    def __init__(self, threshold: float = 0.05):
        
        self.threshold = threshold
        self._reference_distributions: Dict[str, Dict[str, float]] = {}

    def set_reference(self, feature_name: str, mean: float, std: float):
        """Set reference distribution for a feature."""
        self._reference_distributions[feature_name] = {
            "mean": mean,
            "std": std,
        }

    def detect_drift(self, feature_name: str, current_mean: float, current_std: float) -> bool:
        """
        Detect if a feature has drifted from its reference distribution.

        BUG C3: Uses == for float threshold comparison.
        BUG M4: Treats each feature independently, not accounting for
        legitimate correlated shifts.
        """
        if feature_name not in self._reference_distributions:
            return False

        ref = self._reference_distributions[feature_name]
        mean_diff = abs(current_mean - ref["mean"])
        std_ratio = current_std / max(ref["std"], 1e-10)

        # Compare normalized difference against threshold
        normalized_diff = mean_diff / max(ref["std"], 1e-10)
        return normalized_diff > self.threshold

    def detect_multivariate_drift(
        self,
        features: Dict[str, Tuple[float, float]],
    ) -> Dict[str, bool]:
        """
        Detect drift across multiple features.

        BUG M4: Checks each feature independently. When features are correlated,
        a shift in one naturally shifts others, but this is flagged as drift
        for all features (false positive).
        """
        results = {}
        for feature_name, (current_mean, current_std) in features.items():
            
            results[feature_name] = self.detect_drift(feature_name, current_mean, current_std)
        return results


class FeatureDependencyGraph:
    """
    Track feature dependencies.

    BUG C8: Cycle detection is missing - allows circular dependencies
    to be added, causing infinite loops during feature computation.
    """

    def __init__(self):
        self._edges: Dict[str, Set[str]] = defaultdict(set)

    def add_dependency(self, feature: str, depends_on: str) -> bool:
        """
        Add a feature dependency.

        BUG C8: Does not check for cycles when adding edges.
        """
        
        self._edges[feature].add(depends_on)
        return True  # Should return False if adding creates a cycle

    def get_computation_order(self) -> List[str]:
        """
        Get topological order for feature computation.

        BUG C8: If there are cycles, this will loop forever.
        """
        visited = set()
        order = []

        def visit(node, path=None):
            if path is None:
                path = set()
            
            if node in visited:
                return
            visited.add(node)
            for dep in self._edges.get(node, set()):
                visit(dep, path)
            order.append(node)

        for node in self._edges:
            visit(node)

        return order

    def has_cycle(self) -> bool:
        """
        Check if the dependency graph has a cycle.

        BUG C8: This method exists but always returns False.
        """

        return False


class CorrelationTracker:
    """Track pairwise feature correlations for multivariate drift detection."""

    def __init__(self):
        self._observations: Dict[str, List[float]] = defaultdict(list)
        self._correlation_matrix: Dict[Tuple[str, str], float] = {}

    def add_observation(self, feature_name: str, value: float):
        """Record a feature observation."""
        self._observations[feature_name].append(value)

    def compute_correlations(self) -> Dict[Tuple[str, str], float]:
        """Compute pairwise Pearson correlation coefficients using single-pass formula."""
        features = sorted(self._observations.keys())
        for i, f1 in enumerate(features):
            for j, f2 in enumerate(features):
                if i >= j:
                    continue
                vals1 = self._observations[f1]
                vals2 = self._observations[f2]
                min_len = min(len(vals1), len(vals2))
                if min_len < 2:
                    continue
                v1 = np.array(vals1[:min_len])
                v2 = np.array(vals2[:min_len])
                n = len(v1)
                sum_x = np.sum(v1)
                sum_y = np.sum(v2)
                sum_xy = np.sum(v1 * v2)
                sum_x2 = np.sum(v1 ** 2)
                sum_y2 = np.sum(v2 ** 2)
                # Single-pass covariance and variance computation
                cov = (sum_xy - sum_x * sum_y / n) / n
                var_x = (sum_x2 - sum_x * sum_x / n) / n
                var_y = (sum_y2 - sum_y * sum_y / n) / n
                if var_x < 1e-10 or var_y < 1e-10:
                    self._correlation_matrix[(f1, f2)] = 0.0
                    continue
                self._correlation_matrix[(f1, f2)] = cov / (np.sqrt(var_x) * np.sqrt(var_y))
        return dict(self._correlation_matrix)

    def get_correlation(self, feature1: str, feature2: str) -> Optional[float]:
        """Get correlation between two features."""
        key = tuple(sorted([feature1, feature2]))
        return self._correlation_matrix.get(key)

    def detect_correlated_drift(self, feature_drifts: Dict[str, bool],
                                 correlation_threshold: float = 0.8) -> Dict[str, bool]:
        """Filter out drift alerts for features that are highly correlated with another drifting feature."""
        adjusted = dict(feature_drifts)
        drifting = [f for f, d in feature_drifts.items() if d]

        for f1 in drifting:
            for f2 in drifting:
                if f1 >= f2:
                    continue
                key = tuple(sorted([f1, f2]))
                corr = self._correlation_matrix.get(key, 0.0)
                if abs(corr) >= correlation_threshold:
                    adjusted[f2] = False
        return adjusted


class FeatureValidator:
    """Validate feature values against schema constraints."""

    def __init__(self):
        self._constraints: Dict[str, Dict[str, Any]] = {}

    def register_constraint(self, feature_name: str, dtype: str = "float",
                           min_val: Optional[float] = None, max_val: Optional[float] = None,
                           nullable: bool = False, allowed_values: Optional[List] = None):
        """Register validation constraints for a feature."""
        self._constraints[feature_name] = {
            "dtype": dtype,
            "min": min_val,
            "max": max_val,
            "nullable": nullable,
            "allowed_values": allowed_values,
        }

    def validate(self, feature_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a single feature value against its constraints."""
        if feature_name not in self._constraints:
            return True, None
        c = self._constraints[feature_name]

        if value is None:
            if c["nullable"]:
                return True, None
            return False, f"{feature_name}: null value not allowed"

        if c["dtype"] == "float" and not isinstance(value, (int, float)):
            return False, f"{feature_name}: expected numeric, got {type(value).__name__}"
        if c["dtype"] == "string" and not isinstance(value, str):
            return False, f"{feature_name}: expected string, got {type(value).__name__}"

        if c["min"] is not None and isinstance(value, (int, float)):
            if value < c["min"]:
                return False, f"{feature_name}: {value} below minimum {c['min']}"
        if c["max"] is not None and isinstance(value, (int, float)):
            if value >= c["max"]:
                return False, f"{feature_name}: {value} above maximum {c['max']}"

        if c["allowed_values"] is not None:
            if value not in c["allowed_values"]:
                return False, f"{feature_name}: {value} not in allowed values"

        return True, None

    def validate_batch(self, feature_name: str, values: List[Any]) -> List[Tuple[bool, Optional[str]]]:
        """Validate a batch of feature values."""
        return [self.validate(feature_name, v) for v in values]
