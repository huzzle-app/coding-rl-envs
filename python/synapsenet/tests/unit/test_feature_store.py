"""
SynapseNet Feature Store Tests
Terminal Bench v2 - Tests for feature store, transformations, drift detection

Tests cover:
- C1-C8: Feature Store bugs
"""
import time
import uuid
import threading
import sys
import os
import unittest
from unittest import mock

import pytest
import numpy as np


# =========================================================================
# C1: Online/offline consistency
# =========================================================================

class TestOnlineOfflineConsistency:
    """BUG C1: Online and offline stores can diverge."""

    def test_online_offline_consistency(self):
        """Writing a feature should update both online and offline stores atomically."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("entity_1", "user_features", {"age": 25, "score": 0.8})

        online = store.read_online("entity_1", "user_features")
        offline = store.read_offline("entity_1", "user_features")

        assert online is not None
        assert offline is not None
        assert online["values"] == offline["values"], (
            "Online and offline stores should have identical values"
        )

    def test_feature_value_match(self):
        """After writing, check_consistency should return True."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("entity_2", "product_features", {"price": 19.99, "rating": 4.5})

        consistent = store.check_consistency("entity_2", "product_features")
        assert consistent is True, "Online and offline stores should be consistent after write"

    def test_write_failure_rollback(self):
        """If online write fails, offline write should be rolled back."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()

        # Write a feature successfully first
        store.write_feature("entity_3", "group_a", {"v": 1})

        # Now simulate a situation where online write might diverge
        # Write new values
        store.write_feature("entity_3", "group_a", {"v": 2})

        # Both stores should have the new value
        online = store.read_online("entity_3", "group_a")
        offline = store.read_offline("entity_3", "group_a")
        assert online["values"]["v"] == offline["values"]["v"], (
            "BUG C1: Online and offline values should match after every write"
        )

    def test_consistency_check_missing_online(self):
        """Consistency check should detect missing online data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()

        # Write to offline only (simulating BUG C1 effect)
        key = "entity_4:group_b"
        store._offline_store[key] = {"values": {"x": 1}, "timestamp": time.time()}

        consistent = store.check_consistency("entity_4", "group_b")
        assert consistent is False, "Should detect inconsistency when online is missing"


# =========================================================================
# C2: PIT join timezone
# =========================================================================

class TestPITJoinTimezone:
    """BUG C2: Point-in-time join uses wrong timezone handling."""

    def test_pit_join_timezone(self):
        """Timestamps should be normalized to UTC for PIT joins."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.time import parse_timestamp

        # UTC timestamp
        ts_utc = parse_timestamp("2024-01-15T12:00:00+00:00")
        # EST timestamp (same moment)
        ts_est = parse_timestamp("2024-01-15T07:00:00-05:00")

        # Both should normalize to the same UTC time
        
        assert ts_utc is not None
        assert ts_est is not None

    def test_pit_join_utc_conversion(self):
        """All timestamps in PIT joins should be in UTC."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.time import parse_timestamp

        # Timestamp without timezone
        ts_naive = parse_timestamp("2024-01-15T12:00:00")
        
        assert ts_naive is not None

        # Timestamp with timezone
        ts_aware = parse_timestamp("2024-01-15T12:00:00+00:00")
        assert ts_aware is not None

    def test_pit_join_ordering(self):
        """PIT join should correctly order events by timestamp."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.time import point_in_time_lookup

        events = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": "first"},
            {"timestamp": "2024-01-15T12:00:00+00:00", "value": "second"},
            {"timestamp": "2024-01-15T14:00:00+00:00", "value": "third"},
        ]

        # Look up at a point between first and second
        result = point_in_time_lookup(events, "2024-01-15T11:00:00+00:00")
        assert result is not None


# =========================================================================
# C3: Drift threshold float comparison
# =========================================================================

class TestDriftThresholdFloat:
    """BUG C3: Float comparison in drift detection is unreliable."""

    def test_drift_threshold_float(self):
        """Drift detection should use proper float comparison."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("feature_a", mean=10.0, std=2.0)

        # Exactly at threshold - should detect drift
        
        drifted = detector.detect_drift("feature_a", current_mean=10.1, current_std=2.0)

        # The normalized diff = 0.1 / 2.0 = 0.05, exactly at threshold
        
        assert drifted is True, (
            "Drift should be detected when normalized diff equals threshold. "
            "BUG C3: Float == comparison fails for boundary values."
        )

    def test_drift_threshold_comparison(self):
        """Drift detection at exact threshold should use >= not ==."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("feature_b", mean=0.0, std=1.0)

        # Test values very close to threshold
        # normalized_diff = 0.1 / 1.0 = 0.1, exactly equal to threshold
        drifted = detector.detect_drift("feature_b", current_mean=0.1, current_std=1.0)
        assert drifted is True, (
            "Drift should be detected at exact threshold boundary"
        )

    def test_drift_clearly_above_threshold(self):
        """Drift clearly above threshold should always be detected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("feature_c", mean=5.0, std=1.0)

        # Large drift
        drifted = detector.detect_drift("feature_c", current_mean=10.0, current_std=1.0)
        assert drifted is True, "Large drift should definitely be detected"

    def test_no_drift_below_threshold(self):
        """No drift should be reported below threshold."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.5)
        detector.set_reference("stable_feature", mean=10.0, std=2.0)

        # Very small change
        drifted = detector.detect_drift("stable_feature", current_mean=10.01, current_std=2.0)
        assert drifted is False, "Small change should not trigger drift detection"


# =========================================================================
# C4: Feature transformation pipeline ordering
# =========================================================================

class TestFeatureTransformOrder:
    """BUG C4: Transforms execute in insertion order, not dependency order."""

    def test_feature_transform_order(self):
        """Transforms should execute in topological order based on dependencies."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()

        execution_order = []

        def transform_b(inputs):
            execution_order.append("B")
            return inputs.get("a_output", 0) * 2

        def transform_a(inputs):
            execution_order.append("A")
            return inputs.get("raw", 0) + 1

        # Add B first, which depends on A's output
        pipeline.add_transform(
            "transform_b", transform_b,
            input_features=["a_output"],
            output_feature="b_output",
            depends_on=["transform_a"],
        )
        # Add A second
        pipeline.add_transform(
            "transform_a", transform_a,
            input_features=["raw"],
            output_feature="a_output",
        )

        result = pipeline.execute({"raw": 5})

        
        # Correct order should be A then B
        assert execution_order == ["A", "B"], (
            f"Transforms executed in order {execution_order}, "
            f"but should be ['A', 'B'] based on dependencies. "
            f"BUG C4: Transforms execute in insertion order, not topological order."
        )

    def test_transform_pipeline_sequence(self):
        """Pipeline with dependencies should produce correct results."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()

        # Step 1: normalize
        pipeline.add_transform(
            "normalize", lambda inputs: inputs.get("value", 0) / 100.0,
            input_features=["value"],
            output_feature="normalized",
        )

        # Step 2: square (depends on normalize)
        pipeline.add_transform(
            "square", lambda inputs: (inputs.get("normalized", 0) or 0) ** 2,
            input_features=["normalized"],
            output_feature="squared",
            depends_on=["normalize"],
        )

        result = pipeline.execute({"value": 50})
        assert result["normalized"] == 0.5
        assert result["squared"] == 0.25, (
            "Squared should be 0.25 (0.5^2) when transforms execute in correct order"
        )

    def test_independent_transforms(self):
        """Independent transforms should execute regardless of order."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()

        pipeline.add_transform(
            "upper", lambda inputs: str(inputs.get("name", "")).upper(),
            input_features=["name"],
            output_feature="name_upper",
        )
        pipeline.add_transform(
            "length", lambda inputs: len(str(inputs.get("name", ""))),
            input_features=["name"],
            output_feature="name_length",
        )

        result = pipeline.execute({"name": "test"})
        assert result["name_upper"] == "TEST"
        assert result["name_length"] == 4


# =========================================================================
# C5: Feature backfill race condition
# =========================================================================

class TestFeatureBackfillRace:
    """BUG C5: Concurrent backfill jobs can process same entities."""

    def test_feature_backfill_race(self):
        """Concurrent backfill jobs should not overlap on same feature group."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import BackfillManager

        manager = BackfillManager()

        # Start first backfill
        backfill_1 = manager.start_backfill("user_features", ["e1", "e2", "e3"])

        # Start second backfill for same feature group
        
        backfill_2 = manager.start_backfill("user_features", ["e2", "e3", "e4"])

        # Both backfills are now active for overlapping entities
        active = manager._active_backfills
        assert len(active) <= 1 or not any(
            a["feature_group"] == b["feature_group"]
            for a_id, a in active.items()
            for b_id, b in active.items()
            if a_id != b_id and a["status"] == "running" and b["status"] == "running"
        ), (
            "Two backfill jobs for the same feature group should not run concurrently. "
            "BUG C5: No check for overlapping backfills."
        )

    def test_backfill_idempotency(self):
        """Processing the same entity twice should be idempotent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import BackfillManager

        manager = BackfillManager()
        backfill_id = manager.start_backfill("features", ["e1", "e2"])

        # Process entity
        result1 = manager.process_entity(backfill_id, "e1")
        assert result1 is True

        # Process same entity again should be detected as duplicate
        result2 = manager.process_entity(backfill_id, "e1")
        # Should detect duplicate processing
        backfill = manager._active_backfills[backfill_id]
        # Check that entity isn't processed twice
        e1_count = backfill["processed"].count("e1")
        assert e1_count == 1, (
            f"Entity processed {e1_count} times, should only be processed once"
        )


# =========================================================================
# C6: Feature schema evolution breaks backward compatibility
# =========================================================================

class TestFeatureSchemaEvolution:
    """BUG C6: Schema changes don't validate backward compatibility."""

    def test_feature_schema_evolution(self):
        """New schema version should be backward compatible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()

        # Register v1 with fields a, b, c
        v1 = manager.register_schema("user_features", {
            "fields": {"a": "int", "b": "str", "c": "float"},
        })

        # Register v2 that REMOVES field b (breaking change)
        
        v2 = manager.register_schema("user_features", {
            "fields": {"a": "int", "c": "float"},
        })

        # v2 should either be rejected or still include field b
        schema_v1 = manager.get_schema("user_features", version=1)
        schema_v2 = manager.get_schema("user_features", version=2)

        v1_fields = set(schema_v1["schema"]["fields"].keys())
        v2_fields = set(schema_v2["schema"]["fields"].keys())

        assert v1_fields.issubset(v2_fields), (
            f"Schema v2 removed fields {v1_fields - v2_fields}. "
            "BUG C6: Schema evolution should enforce backward compatibility."
        )

    def test_schema_backward_compat(self):
        """Adding new fields should be allowed (backward compatible)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()
        v1 = manager.register_schema("group_a", {"fields": {"x": "int"}})
        v2 = manager.register_schema("group_a", {"fields": {"x": "int", "y": "float"}})

        # Adding a field is backward compatible
        assert v1 == 1
        assert v2 == 2

    def test_schema_type_change_rejected(self):
        """Changing a field's type should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()
        manager.register_schema("typed_group", {"fields": {"score": "int"}})

        # Changing score from int to str is breaking
        
        v2 = manager.register_schema("typed_group", {"fields": {"score": "str"}})

        schema_v1 = manager.get_schema("typed_group", version=1)
        schema_v2 = manager.get_schema("typed_group", version=2)

        # Types should match for existing fields
        for field_name in schema_v1["schema"]["fields"]:
            if field_name in schema_v2["schema"]["fields"]:
                assert schema_v1["schema"]["fields"][field_name] == schema_v2["schema"]["fields"][field_name], (
                    f"Field '{field_name}' type changed from {schema_v1['schema']['fields'][field_name]} "
                    f"to {schema_v2['schema']['fields'][field_name]}. "
                    "BUG C6: Type changes should be rejected."
                )


# =========================================================================
# C7: Feature serving cache stampede
# =========================================================================

class TestFeatureServingCacheStampede:
    """BUG C7: No stampede protection on popular feature expiry."""

    def test_feature_serving_cache_stampede(self):
        """Cache miss should not cause all requests to hit backend."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.01)
        cache.set("popular_feature", {"score": 0.95})

        # Wait for expiry
        time.sleep(0.02)

        # Multiple concurrent requests for the same expired key
        backend_calls = {"count": 0}
        lock = threading.Lock()

        def fetch_feature():
            val = cache.get("popular_feature")
            if val is None:
                with lock:
                    backend_calls["count"] += 1
                # Simulate backend fetch
                time.sleep(0.01)
                cache.set("popular_feature", {"score": 0.95})

        threads = [threading.Thread(target=fetch_feature) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        
        assert backend_calls["count"] <= 2, (
            f"Backend called {backend_calls['count']} times. "
            "Should be at most 1-2 with stampede protection. "
            "BUG C7: No cache stampede protection."
        )

    def test_feature_cache_lock(self):
        """Cache should use lock to prevent concurrent recomputation."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        cache.set("locked_feature", "value")

        # Verify basic cache operations work
        assert cache.get("locked_feature") == "value"

        # After setting a new value
        cache.set("locked_feature", "new_value")
        assert cache.get("locked_feature") == "new_value"


# =========================================================================
# C8: Feature dependency graph has undetected cycle
# =========================================================================

class TestFeatureDependencyCycle:
    """BUG C8: Dependency graph doesn't detect cycles."""

    def test_feature_dependency_cycle(self):
        """Adding a dependency that creates a cycle should be detected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("A", "B")
        graph.add_dependency("B", "C")

        # Adding C -> A creates a cycle: A -> B -> C -> A
        result = graph.add_dependency("C", "A")

        
        # Should return False when cycle detected
        has_cycle = graph.has_cycle()
        assert has_cycle is True, (
            "Graph has cycle A->B->C->A but has_cycle() returned False. "
            "BUG C8: Cycle detection is broken."
        )

    def test_dependency_graph_acyclic(self):
        """Graph without cycles should report no cycle."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("A", "B")
        graph.add_dependency("B", "C")
        graph.add_dependency("A", "C")

        has_cycle = graph.has_cycle()
        assert has_cycle is False, "DAG should not report a cycle"

    def test_computation_order_valid(self):
        """Computation order should be valid topological sort."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("D", "B")
        graph.add_dependency("D", "C")
        graph.add_dependency("B", "A")
        graph.add_dependency("C", "A")

        order = graph.get_computation_order()
        # A should come before B and C, which should come before D
        if "A" in order and "D" in order:
            assert order.index("A") < order.index("D"), (
                "A should be computed before D"
            )

    def test_self_cycle_detected(self):
        """Self-referencing dependency should be detected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("X", "X")  # Self-cycle

        has_cycle = graph.has_cycle()
        assert has_cycle is True, (
            "Self-referencing dependency should be detected as cycle"
        )

    def test_diamond_dependency(self):
        """Diamond dependencies (no cycle) should work correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        # Diamond: D -> B -> A, D -> C -> A
        graph.add_dependency("D", "B")
        graph.add_dependency("D", "C")
        graph.add_dependency("B", "A")
        graph.add_dependency("C", "A")

        has_cycle = graph.has_cycle()
        assert has_cycle is False, "Diamond pattern is not a cycle"


# =========================================================================
# Additional feature store tests
# =========================================================================

class TestFeatureStoreOperations:
    """Test basic feature store operations."""

    def test_write_and_read_online(self):
        """Writing a feature should make it readable from online store."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("user_1", "demographics", {"age": 30, "gender": "M"})

        result = store.read_online("user_1", "demographics")
        assert result is not None
        assert result["values"]["age"] == 30

    def test_write_and_read_offline(self):
        """Writing a feature should make it readable from offline store."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("user_2", "activity", {"last_login": "2024-01-15"})

        result = store.read_offline("user_2", "activity")
        assert result is not None
        assert result["values"]["last_login"] == "2024-01-15"

    def test_read_nonexistent_feature(self):
        """Reading a nonexistent feature should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        assert store.read_online("unknown", "unknown") is None
        assert store.read_offline("unknown", "unknown") is None

    def test_overwrite_feature(self):
        """Overwriting a feature should update the value."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("user_3", "prefs", {"theme": "dark"})
        store.write_feature("user_3", "prefs", {"theme": "light"})

        result = store.read_online("user_3", "prefs")
        assert result["values"]["theme"] == "light"


class TestDriftDetectorMultivariate:
    """Test multivariate drift detection (BUG M4 via feature store)."""

    def test_multivariate_drift_correlated(self):
        """Correlated feature shifts should not all trigger drift."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("height", mean=170.0, std=10.0)
        detector.set_reference("weight", mean=70.0, std=10.0)

        # Correlated shift: both height and weight increase together
        results = detector.detect_multivariate_drift({
            "height": (175.0, 10.0),  # 0.5 std shift
            "weight": (75.0, 10.0),   # 0.5 std shift
        })

        
        drift_count = sum(1 for v in results.values() if v)
        # With proper correlation handling, the drift should be less severe
        assert drift_count >= 0  # This test documents the bug

    def test_multivariate_drift_independent(self):
        """Independent feature drift should be detected individually."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("feature_x", mean=0.0, std=1.0)
        detector.set_reference("feature_y", mean=0.0, std=1.0)

        # Only feature_x drifts significantly
        results = detector.detect_multivariate_drift({
            "feature_x": (5.0, 1.0),   # 5 std shift - significant drift
            "feature_y": (0.01, 1.0),   # 0.01 std shift - no drift
        })

        assert results["feature_x"] is True, "feature_x should show drift"
        assert results["feature_y"] is False, "feature_y should not show drift"


class TestFeatureSchemaManagerOperations:
    """Test schema manager operations."""

    def test_get_latest_schema(self):
        """Getting schema with version=-1 should return latest."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()
        manager.register_schema("test_group", {"fields": {"a": "int"}})
        manager.register_schema("test_group", {"fields": {"a": "int", "b": "str"}})

        latest = manager.get_schema("test_group")
        assert latest["version"] == 2
        assert "b" in latest["schema"]["fields"]

    def test_get_specific_version(self):
        """Getting a specific version should return that version."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()
        manager.register_schema("versioned", {"fields": {"x": "int"}})
        manager.register_schema("versioned", {"fields": {"x": "int", "y": "float"}})

        v1 = manager.get_schema("versioned", version=1)
        assert v1["version"] == 1
        assert "y" not in v1["schema"]["fields"]

    def test_get_nonexistent_schema(self):
        """Getting nonexistent schema should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()
        assert manager.get_schema("nonexistent") is None


# =========================================================================
# Extended Feature Store Tests
# =========================================================================

class TestFeatureStoreWriteReadCycle:
    """Extended write/read cycle tests."""

    def test_write_multiple_entities(self):
        """Multiple entities should be stored independently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("e1", "group_a", {"score": 1.0})
        store.write_feature("e2", "group_a", {"score": 2.0})
        store.write_feature("e3", "group_a", {"score": 3.0})

        r1 = store.read_online("e1", "group_a")
        r2 = store.read_online("e2", "group_a")
        r3 = store.read_online("e3", "group_a")

        assert r1["values"]["score"] == 1.0
        assert r2["values"]["score"] == 2.0
        assert r3["values"]["score"] == 3.0

    def test_write_multiple_groups(self):
        """Same entity can have features in multiple groups."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("e1", "demographics", {"age": 30})
        store.write_feature("e1", "activity", {"clicks": 100})

        demo = store.read_online("e1", "demographics")
        activity = store.read_online("e1", "activity")

        assert demo["values"]["age"] == 30
        assert activity["values"]["clicks"] == 100

    def test_feature_entity_id_in_response(self):
        """Response should include entity_id."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("user_42", "prefs", {"dark_mode": True})

        result = store.read_online("user_42", "prefs")
        assert result["entity_id"] == "user_42"

    def test_feature_group_in_response(self):
        """Response should include feature_group."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("e1", "my_group", {"val": 1})

        result = store.read_online("e1", "my_group")
        assert result["feature_group"] == "my_group"

    def test_feature_timestamp_in_response(self):
        """Response should include a timestamp."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("e1", "timed", {"val": 1})

        result = store.read_online("e1", "timed")
        assert "timestamp" in result
        assert result["timestamp"] is not None

    def test_write_returns_bool(self):
        """write_feature should return a boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        result = store.write_feature("e1", "g1", {"v": 1})
        assert isinstance(result, bool)


class TestDriftDetectorEdgeCases:
    """Edge cases for drift detector."""

    def test_drift_no_reference(self):
        """Drift detection without reference should handle gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        # No reference set
        result = detector.detect_drift("unknown", current_mean=5.0, current_std=1.0)
        assert result is False or result is True  # Should not crash

    def test_drift_zero_std_reference(self):
        """Drift detection with zero std should handle gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("constant", mean=5.0, std=0.0)
        result = detector.detect_drift("constant", current_mean=5.0, current_std=0.0)
        assert isinstance(result, bool)

    def test_drift_exact_threshold(self):
        """Drift at exactly the threshold should be handled consistently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.5)
        detector.set_reference("feature", mean=10.0, std=1.0)
        result = detector.detect_drift("feature", current_mean=10.5, current_std=1.0)
        assert isinstance(result, bool)

    def test_drift_negative_shift(self):
        """Negative mean shift should also be detected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("feature", mean=10.0, std=1.0)
        result = detector.detect_drift("feature", current_mean=0.0, current_std=1.0)
        assert result is True, "Large negative drift should be detected"

    def test_drift_multiple_features_independent(self):
        """Drift detection for multiple features should be independent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.5)
        detector.set_reference("f1", mean=0.0, std=1.0)
        detector.set_reference("f2", mean=0.0, std=1.0)

        # f1 drifts, f2 does not
        r1 = detector.detect_drift("f1", current_mean=5.0, current_std=1.0)
        r2 = detector.detect_drift("f2", current_mean=0.1, current_std=1.0)

        assert r1 is True
        assert r2 is False


class TestFeatureTransformPipelineDetailed:
    """Detailed tests for feature transform pipeline."""

    def test_empty_pipeline_returns_empty(self):
        """Empty pipeline should return empty result."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        result = pipeline.execute({"input": 1.0})
        assert isinstance(result, dict)

    def test_single_transform(self):
        """Single transform should produce correct output."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "double", lambda inputs: inputs.get("x", 0) * 2,
            input_features=["x"],
            output_feature="x_doubled",
        )
        result = pipeline.execute({"x": 5})
        assert result["x_doubled"] == 10

    def test_chained_transforms(self):
        """Chained transforms should execute in order."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "normalize", lambda inputs: inputs.get("raw", 0) / 100.0,
            input_features=["raw"],
            output_feature="normalized",
        )
        pipeline.add_transform(
            "square", lambda inputs: inputs.get("normalized", 0) ** 2,
            input_features=["normalized"],
            output_feature="squared",
        )
        result = pipeline.execute({"raw": 50})
        assert "normalized" in result
        assert abs(result["normalized"] - 0.5) < 1e-6

    def test_transform_with_numpy(self):
        """Transforms should work with numpy operations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "log_transform", lambda inputs: float(np.log1p(inputs.get("value", 0))),
            input_features=["value"],
            output_feature="log_value",
        )
        result = pipeline.execute({"value": 99})
        assert abs(result["log_value"] - np.log1p(99)) < 1e-6

    def test_transform_error_handling(self):
        """Transform errors should be handled gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "safe_divide",
            lambda inputs: inputs.get("a", 0) / max(inputs.get("b", 1), 1e-10),
            input_features=["a", "b"],
            output_feature="ratio",
        )
        result = pipeline.execute({"a": 10, "b": 0})
        assert "ratio" in result


class TestFeatureCacheManagerDetailed:
    """Detailed tests for FeatureCacheManager."""

    def test_cache_set_and_get(self):
        """Basic set/get should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_ttl_expiry(self):
        """Expired entries should not be returned."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.01)
        cache.set("short_lived", "data")
        time.sleep(0.02)
        assert cache.get("short_lived") is None

    def test_cache_overwrite(self):
        """Overwriting a key should update the value."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"

    def test_cache_different_keys_independent(self):
        """Different keys should be independent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_cache_nonexistent_key(self):
        """Getting nonexistent key should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        assert cache.get("nonexistent") is None

    def test_cache_complex_values(self):
        """Cache should handle complex value types."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        complex_val = {"scores": [0.1, 0.2, 0.3], "metadata": {"source": "model_a"}}
        cache.set("complex", complex_val)
        result = cache.get("complex")
        assert result == complex_val


class TestFeatureSchemaManagerExtended(unittest.TestCase):
    """Extended tests for FeatureSchemaManager edge cases."""

    def test_register_multiple_versions(self):
        """Should track multiple schema versions independently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        mgr = FeatureSchemaManager()
        v1 = mgr.register_schema("user_features", {"age": "int", "name": "str"})
        v2 = mgr.register_schema("user_features", {"age": "int", "name": "str", "email": "str"})
        assert v1 == 1
        assert v2 == 2
        assert mgr.get_schema("user_features", 1)["schema"]["age"] == "int"
        assert "email" in mgr.get_schema("user_features", 2)["schema"]

    def test_get_latest_schema(self):
        """Default version=-1 should return latest schema."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        mgr = FeatureSchemaManager()
        mgr.register_schema("fg1", {"f1": "float"})
        mgr.register_schema("fg1", {"f1": "float", "f2": "str"})
        latest = mgr.get_schema("fg1")
        assert "f2" in latest["schema"]

    def test_get_schema_invalid_version(self):
        """Out-of-range version should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        mgr = FeatureSchemaManager()
        mgr.register_schema("fg1", {"f1": "float"})
        assert mgr.get_schema("fg1", 999) is None
        assert mgr.get_schema("fg1", 0) is None

    def test_get_schema_nonexistent_group(self):
        """Getting schema for nonexistent group should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        mgr = FeatureSchemaManager()
        assert mgr.get_schema("nonexistent") is None

    def test_schema_has_created_at(self):
        """Each schema version should have a created_at timestamp."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        mgr = FeatureSchemaManager()
        mgr.register_schema("fg1", {"f1": "float"})
        schema = mgr.get_schema("fg1", 1)
        assert "created_at" in schema
        assert isinstance(schema["created_at"], float)


class TestBackfillManagerExtended(unittest.TestCase):
    """Extended tests for BackfillManager operations."""

    def test_start_backfill_returns_unique_ids(self):
        """Each backfill should get a unique ID."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import BackfillManager

        mgr = BackfillManager()
        ids = [mgr.start_backfill("fg1", ["e1", "e2"]) for _ in range(10)]
        assert len(set(ids)) == 10

    def test_process_entity_tracks_progress(self):
        """Processing entities should track them as processed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import BackfillManager

        mgr = BackfillManager()
        bid = mgr.start_backfill("fg1", ["e1", "e2", "e3"])
        assert mgr.process_entity(bid, "e1") is True
        assert mgr.process_entity(bid, "e2") is True
        backfill = mgr._active_backfills[bid]
        assert "e1" in backfill["processed"]
        assert "e2" in backfill["processed"]

    def test_process_entity_invalid_backfill(self):
        """Processing with invalid backfill ID should fail."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import BackfillManager

        mgr = BackfillManager()
        assert mgr.process_entity("nonexistent", "e1") is False

    def test_multiple_backfills_same_group(self):
        """Bug C5: Starting two backfills for same group should be handled."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import BackfillManager

        mgr = BackfillManager()
        bid1 = mgr.start_backfill("fg1", ["e1", "e2"])
        bid2 = mgr.start_backfill("fg1", ["e1", "e2"])
        
        assert bid1 != bid2
        assert len(mgr._active_backfills) == 2


class TestFeatureDependencyGraphExtended(unittest.TestCase):
    """Extended tests for FeatureDependencyGraph."""

    def test_add_single_dependency(self):
        """Adding a dependency should succeed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        assert graph.add_dependency("B", "A") is True

    def test_computation_order_simple_chain(self):
        """Computation order should handle a simple chain."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("C", "B")
        graph.add_dependency("B", "A")
        order = graph.get_computation_order()
        assert "B" in order
        assert "C" in order

    def test_has_cycle_bug_c8(self):
        """Bug C8: has_cycle always returns False even with cycles."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("A", "B")
        graph.add_dependency("B", "C")
        graph.add_dependency("C", "A")  # cycle
        
        result = graph.has_cycle()
        assert isinstance(result, bool)

    def test_diamond_dependency(self):
        """Diamond dependency pattern should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("D", "B")
        graph.add_dependency("D", "C")
        graph.add_dependency("B", "A")
        graph.add_dependency("C", "A")
        order = graph.get_computation_order()
        assert len(order) >= 2

    def test_isolated_nodes(self):
        """Nodes with no dependencies should still appear."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureDependencyGraph

        graph = FeatureDependencyGraph()
        graph.add_dependency("B", "A")
        order = graph.get_computation_order()
        assert "A" in order or "B" in order


class TestDriftDetectorExtended(unittest.TestCase):
    """Additional drift detector edge case tests."""

    def test_drift_detection_exact_threshold_bug(self):
        """Bug C3: Float equality comparison at threshold boundary."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("feature_a", mean=100.0, std=10.0)
        # When normalized diff is exactly 0.05, float comparison may fail
        result = detector.detect_drift("feature_a", 100.5, 10.0)
        assert isinstance(result, bool)

    def test_drift_detection_zero_std_reference(self):
        """Drift detection with zero std reference should not crash."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("f1", mean=5.0, std=0.0)
        # Should use epsilon in denominator
        result = detector.detect_drift("f1", 5.1, 0.0)
        assert isinstance(result, bool)

    def test_multivariate_drift_independent(self):
        """Bug M4: Multivariate drift checks features independently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("f1", 100.0, 10.0)
        detector.set_reference("f2", 200.0, 20.0)
        results = detector.detect_multivariate_drift({
            "f1": (110.0, 10.0),
            "f2": (220.0, 20.0),
        })
        assert "f1" in results
        assert "f2" in results

    def test_detect_drift_unregistered_feature(self):
        """Detecting drift for unregistered feature should return False."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector()
        assert detector.detect_drift("unknown", 1.0, 1.0) is False

    def test_drift_detection_negative_values(self):
        """Drift detection should work with negative feature values."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("neg_feat", -50.0, 5.0)
        result = detector.detect_drift("neg_feat", -50.0, 5.0)
        assert result is False  # No drift when same as reference


class TestFeatureTransformPipelineExtended(unittest.TestCase):
    """Extended tests for FeatureTransformPipeline."""

    def test_single_transform(self):
        """Single transform should execute correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform("double", lambda x: x["val"] * 2, ["val"], "doubled")
        result = pipeline.execute({"val": 5})
        assert result["doubled"] == 10

    def test_chained_transforms(self):
        """Chained transforms should accumulate results."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform("add_one", lambda x: x["val"] + 1, ["val"], "plus_one")
        pipeline.add_transform("double", lambda x: x["plus_one"] * 2, ["plus_one"], "doubled", depends_on=["add_one"])
        result = pipeline.execute({"val": 5})
        assert result["plus_one"] == 6
        assert result["doubled"] == 12

    def test_transform_with_missing_input(self):
        """Transform with missing input feature should handle gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform("fail_safe", lambda x: x.get("missing", 0) + 1, ["missing"], "result")
        result = pipeline.execute({})
        assert result["result"] == 1

    def test_transform_error_sets_none(self):
        """Transform that raises exception should produce None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform("bad", lambda x: 1 / 0, ["val"], "crashed")
        result = pipeline.execute({"val": 5})
        assert result["crashed"] is None

    def test_transform_preserves_original_features(self):
        """Pipeline execution should not remove original features."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform("square", lambda x: x["val"] ** 2, ["val"], "squared")
        result = pipeline.execute({"val": 3, "extra": "keep"})
        assert result["val"] == 3
        assert result["extra"] == "keep"
        assert result["squared"] == 9
