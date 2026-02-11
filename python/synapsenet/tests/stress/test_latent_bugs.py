"""
SynapseNet Latent Bug Tests
Tests for bugs that don't directly cause obvious failures but corrupt state
or produce subtly wrong results under specific conditions.
"""
import os
import sys
import time
import copy
import threading
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestEMAParameterAveraging:
    """Test ExponentialMovingAverage correctly tracks parameter history."""

    def test_ema_high_decay_barely_moves(self):
        """With high decay, a single update should barely change the shadow value."""
        from shared.ml.model_loader import ExponentialMovingAverage

        ema = ExponentialMovingAverage(decay=0.999)
        initial = np.array([1.0, 1.0, 1.0])
        ema.register("param", initial)

        new_value = np.array([2.0, 2.0, 2.0])
        ema.update("param", new_value)

        result = ema.get_averaged("param")
        # With high decay, the result should barely change after one update
        assert np.allclose(result, 1.001, atol=0.01), (
            "result should barely change after one update with high decay"
        )

    def test_ema_convergence(self):
        """After many updates with same value, EMA should converge to that value."""
        from shared.ml.model_loader import ExponentialMovingAverage

        ema = ExponentialMovingAverage(decay=0.9)
        ema.register("param", np.array([0.0]))

        target = np.array([10.0])
        for _ in range(200):
            ema.update("param", target)

        result = ema.get_averaged("param")
        assert np.allclose(result, target, atol=0.1), (
            "EMA should converge to target value after many repeated updates"
        )

    def test_ema_high_decay_slow_tracking(self):
        """High decay means slow tracking of changes."""
        from shared.ml.model_loader import ExponentialMovingAverage

        ema = ExponentialMovingAverage(decay=0.99)
        ema.register("w", np.array([0.0]))

        ema.update("w", np.array([100.0]))
        result = ema.get_averaged("w")
        # A single update from 0 to 100 with high decay should stay near 0
        assert result[0] < 5.0, (
            "result should remain close to original value after one update with high decay"
        )

    def test_ema_low_decay_fast_tracking(self):
        """Low decay means fast tracking of changes."""
        from shared.ml.model_loader import ExponentialMovingAverage

        ema = ExponentialMovingAverage(decay=0.1)
        ema.register("w", np.array([0.0]))

        ema.update("w", np.array([100.0]))
        result = ema.get_averaged("w")
        # With low decay, the result should move quickly toward the new value
        assert result[0] > 50.0, (
            "result should move quickly toward new value with low decay"
        )

    def test_ema_decay_direction_multi_step(self):
        """Multiple steps should show gradual convergence proportional to decay."""
        from shared.ml.model_loader import ExponentialMovingAverage

        ema = ExponentialMovingAverage(decay=0.999)
        ema.register("p", np.array([0.0]))

        # After 10 updates to 100.0, with high decay the value should still be small
        for _ in range(10):
            ema.update("p", np.array([100.0]))

        result = ema.get_averaged("p")
        # After 10 steps with decay=0.999, result should be approximately 0 + 10*0.001*100 ~ 1.0
        # (rough approximation; exact is slightly different due to compounding)
        assert result[0] < 5.0, (
            "result should still be near original after few updates with very high decay"
        )


class TestGradientClipperNormType:
    """Test that GradientClipper uses the correct norm computation."""

    def test_single_parameter_l2_norm(self):
        """L2 norm of a single parameter should match manual calculation."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=10.0, norm_type="l2")
        grads = {"layer": np.array([3.0, 4.0])}

        norm = clipper.compute_norm(grads)
        expected = np.sqrt(3.0**2 + 4.0**2)  # 5.0
        assert abs(norm - expected) < 0.01, (
            "gradient norm should match manual calculation for single parameter"
        )

    def test_multi_parameter_l2_norm_is_global(self):
        """Global L2 norm across multiple parameters should be sqrt(sum of all squared elements)."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=100.0, norm_type="l2")
        grads = {
            "layer1": np.array([3.0, 4.0]),
            "layer2": np.array([5.0, 6.0]),
        }

        norm = clipper.compute_norm(grads)
        # Global L2 norm = sqrt(3^2 + 4^2 + 5^2 + 6^2) = sqrt(9+16+25+36) = sqrt(86)
        expected_global = np.sqrt(3.0**2 + 4.0**2 + 5.0**2 + 6.0**2)
        assert abs(norm - expected_global) < 0.01, (
            "global L2 norm should combine all parameters into a single norm computation"
        )

    def test_l1_norm_computation(self):
        """L1 norm should be sum of absolute values."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=10.0, norm_type="l1")
        grads = {"layer": np.array([3.0, -4.0])}

        norm = clipper.compute_norm(grads)
        expected_l1 = 3.0 + 4.0  # = 7.0
        assert abs(norm - expected_l1) < 0.01, (
            "L1 norm should equal the sum of absolute values"
        )

    def test_clipping_preserves_direction(self):
        """After clipping, gradient direction should be preserved."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=1.0, norm_type="l2")
        grads = {"layer": np.array([30.0, 40.0])}

        clipped = clipper.clip(grads)
        original_direction = grads["layer"] / np.linalg.norm(grads["layer"])
        clipped_direction = clipped["layer"] / np.linalg.norm(clipped["layer"])

        assert np.allclose(original_direction, clipped_direction, atol=0.01), (
            "clipping should preserve gradient direction"
        )

    def test_clipping_respects_max_norm(self):
        """After clipping, total norm should be at most max_norm."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=1.0, norm_type="l2")
        grads = {
            "layer1": np.array([30.0, 40.0]),
            "layer2": np.array([10.0, 20.0]),
        }

        clipped = clipper.clip(grads)
        total_norm = np.sqrt(sum(np.sum(g**2) for g in clipped.values()))
        assert total_norm <= 1.0 + 0.01, (
            "total norm after clipping should not exceed max_norm"
        )

    def test_no_clipping_when_below_threshold(self):
        """Gradients below max_norm should not be modified."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=100.0, norm_type="l2")
        grads = {"layer": np.array([3.0, 4.0])}

        clipped = clipper.clip(grads)
        assert np.allclose(clipped["layer"], grads["layer"]), (
            "gradients below max_norm should remain unchanged"
        )

    def test_multi_parameter_norm_not_sum_of_individual_norms(self):
        """Global L2 norm should not be the sum of individual per-parameter L2 norms."""
        from shared.ml.model_loader import GradientClipper

        clipper = GradientClipper(max_norm=100.0, norm_type="l2")
        grads = {
            "a": np.array([3.0, 0.0]),
            "b": np.array([0.0, 4.0]),
        }

        norm = clipper.compute_norm(grads)
        # Global L2: sqrt(9 + 16) = 5.0
        # Sum-of-L2s: 3.0 + 4.0 = 7.0
        # The norm should be 5.0, not 7.0
        assert abs(norm - 5.0) < 0.01, (
            "multi-parameter norm should be computed globally, not as sum of individual norms"
        )


class TestFeatureNormalizerDdof:
    """Test FeatureNormalizer uses consistent statistics for transform and inverse."""

    def test_sample_std_used_for_normalization(self):
        """Normalizer should use sample std (ddof=1) for transform."""
        from shared.ml.model_loader import FeatureNormalizer

        normalizer = FeatureNormalizer()
        values = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        normalizer.fit("feature_a", values)

        stats = normalizer.get_stats("feature_a")
        expected_std = float(np.std(values, ddof=1))
        assert abs(stats["std"] - expected_std) < 0.01, (
            "stored standard deviation should match the sample standard deviation"
        )

    def test_roundtrip_small_dataset(self):
        """transform followed by inverse_transform should recover original values on a small dataset."""
        from shared.ml.model_loader import FeatureNormalizer

        normalizer = FeatureNormalizer()
        # Small dataset where ddof=0 vs ddof=1 difference is pronounced
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        normalizer.fit("f1", values)

        normalized = normalizer.transform("f1", values)
        recovered = normalizer.inverse_transform("f1", normalized)

        assert np.allclose(values, recovered, atol=0.01), (
            "roundtrip transform then inverse_transform should recover original values"
        )

    def test_roundtrip_three_elements(self):
        """Roundtrip should work even with very small datasets where ddof matters most."""
        from shared.ml.model_loader import FeatureNormalizer

        normalizer = FeatureNormalizer()
        values = np.array([10.0, 20.0, 30.0])
        normalizer.fit("small", values)

        normalized = normalizer.transform("small", values)
        recovered = normalizer.inverse_transform("small", normalized)

        assert np.allclose(values, recovered, atol=0.01), (
            "roundtrip should be exact even for a 3-element dataset"
        )

    def test_normalized_distribution(self):
        """Normalized values should have mean approximately 0 and std approximately 1."""
        from shared.ml.model_loader import FeatureNormalizer

        normalizer = FeatureNormalizer()
        np.random.seed(42)
        values = np.random.normal(loc=50, scale=10, size=1000)
        normalizer.fit("f1", values)

        normalized = normalizer.transform("f1", values)
        assert abs(np.mean(normalized)) < 0.1, (
            "normalized mean should be approximately zero"
        )
        assert abs(np.std(normalized) - 1.0) < 0.1, (
            "normalized standard deviation should be approximately one"
        )


class TestFeatureValidatorBoundary:
    """Test FeatureValidator handles boundary conditions correctly."""

    def test_max_value_inclusive(self):
        """Maximum value should be inclusive (value == max is valid)."""
        from shared.ml.feature_utils import FeatureValidator

        validator = FeatureValidator()
        validator.register_constraint("score", dtype="float", min_val=0.0, max_val=1.0)

        valid, msg = validator.validate("score", 1.0)
        assert valid, (
            f"value exactly at max boundary should be accepted, got rejection: {msg}"
        )

    def test_min_value_inclusive(self):
        """Minimum value should be inclusive."""
        from shared.ml.feature_utils import FeatureValidator

        validator = FeatureValidator()
        validator.register_constraint("score", dtype="float", min_val=0.0, max_val=1.0)

        valid, msg = validator.validate("score", 0.0)
        assert valid, f"value at min boundary should be accepted, got rejection: {msg}"

    def test_just_above_max(self):
        """Value just above max should be invalid."""
        from shared.ml.feature_utils import FeatureValidator

        validator = FeatureValidator()
        validator.register_constraint("score", dtype="float", min_val=0.0, max_val=1.0)

        valid, msg = validator.validate("score", 1.001)
        assert not valid, "value above max should be rejected"


class TestCorrelationTrackerAccuracy:
    """Test CorrelationTracker computes correct Pearson correlation."""

    def test_perfect_positive_correlation(self):
        """Perfectly correlated features should have correlation near 1.0."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        for i in range(100):
            tracker.add_observation("x", float(i))
            tracker.add_observation("y", float(i * 2 + 1))

        correlations = tracker.compute_correlations()
        key = ("x", "y")
        assert key in correlations, "correlation should be computed for the feature pair"
        assert abs(correlations[key] - 1.0) < 0.01, (
            "perfectly linearly related features should have correlation near 1.0"
        )

    def test_perfect_negative_correlation(self):
        """Anti-correlated features should have correlation near -1.0."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        for i in range(100):
            tracker.add_observation("a", float(i))
            tracker.add_observation("b", float(-i))

        correlations = tracker.compute_correlations()
        key = ("a", "b")
        assert key in correlations
        assert abs(correlations[key] - (-1.0)) < 0.01, (
            "inversely related features should have correlation near -1.0"
        )

    def test_uncorrelated_features(self):
        """Uncorrelated features should have correlation near 0."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        np.random.seed(42)
        for i in range(1000):
            tracker.add_observation("x", float(np.random.randn()))
            tracker.add_observation("y", float(np.random.randn()))

        correlations = tracker.compute_correlations()
        key = ("x", "y")
        assert key in correlations
        assert abs(correlations[key]) < 0.1, (
            "independent random features should have correlation near zero"
        )

    def test_correlated_drift_filtering(self):
        """Should filter out drift alerts for highly correlated features."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        for i in range(100):
            x = float(i)
            tracker.add_observation("feature_a", x)
            tracker.add_observation("feature_b", x * 2 + 0.01)
            tracker.add_observation("feature_c", float(np.random.randn()))

        tracker.compute_correlations()

        drifts = {"feature_a": True, "feature_b": True, "feature_c": False}
        adjusted = tracker.detect_correlated_drift(drifts, correlation_threshold=0.8)

        drifting_count = sum(1 for v in adjusted.values() if v)
        assert drifting_count < 3, (
            "highly correlated drifting features should be deduplicated"
        )


class TestIdempotencyTrackerKeyGeneration:
    """Test IdempotencyTracker generates correct dedup keys."""

    def test_same_event_detected_as_duplicate(self):
        """Processing same event twice should be detected."""
        from shared.events.base import IdempotencyTracker, Event

        tracker = IdempotencyTracker()
        event = Event(event_id="evt-001", event_type="model.trained",
                      source_service="training")

        assert tracker.check_and_mark(event) == True, "first processing should succeed"
        assert tracker.check_and_mark(event) == False, "duplicate should be detected"

    def test_similar_ids_tracked_independently(self):
        """Events with similar IDs should be independently tracked."""
        from shared.events.base import IdempotencyTracker, Event

        tracker = IdempotencyTracker()

        # Mark evt-10 as processed
        evt10 = Event(event_id="evt-10", event_type="model.trained",
                      source_service="training")
        tracker.check_and_mark(evt10)

        # evt-1 has never been seen, so it should NOT be a duplicate
        assert not tracker.is_duplicate("evt-1"), (
            "events with similar IDs should be independently tracked"
        )

    def test_substring_id_not_confused(self):
        """An ID that is a substring of a processed ID should not be flagged as duplicate."""
        from shared.events.base import IdempotencyTracker, Event

        tracker = IdempotencyTracker()

        # Mark "evt-100" as processed
        evt100 = Event(event_id="evt-100", event_type="test.event",
                       source_service="svc")
        tracker.check_and_mark(evt100)

        # "evt-10" and "evt-1" should not be considered duplicates
        assert not tracker.is_duplicate("evt-10"), (
            "a shorter ID should not match a longer processed ID"
        )
        assert not tracker.is_duplicate("evt-1"), (
            "a prefix ID should not match a longer processed ID"
        )

    def test_is_duplicate_matches_check_and_mark(self):
        """is_duplicate should agree with what check_and_mark tracks."""
        from shared.events.base import IdempotencyTracker, Event

        tracker = IdempotencyTracker()
        event = Event(event_id="evt-002", event_type="model.deployed",
                      source_service="inference")

        assert not tracker.is_duplicate("evt-002")

        tracker.check_and_mark(event)

        assert tracker.is_duplicate("evt-002"), (
            "is_duplicate should detect events that were previously marked"
        )

    def test_different_events_not_confused(self):
        """Different events should not be confused as duplicates."""
        from shared.events.base import IdempotencyTracker, Event

        tracker = IdempotencyTracker()
        e1 = Event(event_id="evt-001", event_type="model.trained",
                    source_service="training")
        e2 = Event(event_id="evt-002", event_type="model.deployed",
                    source_service="inference")

        tracker.check_and_mark(e1)
        assert tracker.check_and_mark(e2) == True, (
            "distinct events should be tracked independently"
        )


class TestEventReplayDeduplication:
    """Test that event replay doesn't cause duplicate processing."""

    def test_replay_all_sends_all_events(self):
        """replay_all should send all stored events."""
        from shared.events.base import EventBus, EventReplayManager, Event

        bus = EventBus(service_name="test")
        replay = EventReplayManager(bus)

        for i in range(5):
            event = Event(event_id=f"evt-{i}", event_type="test.event")
            replay.store_for_replay(event)

        count = replay.replay_all("test-topic")
        assert count == 5

    def test_double_replay_should_not_double_publish(self):
        """Calling replay_all twice should not double the number of published events."""
        from shared.events.base import EventBus, EventReplayManager, Event

        bus = EventBus(service_name="test")
        replay = EventReplayManager(bus)

        for i in range(3):
            event = Event(event_id=f"replay-evt-{i}", event_type="test.event")
            replay.store_for_replay(event)

        replay.replay_all("topic-a")
        count_after_first = len(bus.get_published_events())

        replay.replay_all("topic-a")
        count_after_second = len(bus.get_published_events())

        assert count_after_second == count_after_first, (
            "replaying events a second time should not produce additional published events"
        )

    def test_single_event_replay_idempotent(self):
        """Replaying a single event multiple times should only publish it once."""
        from shared.events.base import EventBus, EventReplayManager, Event

        bus = EventBus(service_name="test")
        replay = EventReplayManager(bus)

        event = Event(event_id="evt-single", event_type="test.event")
        replay.store_for_replay(event)

        replay.replay_all("topic-a")
        initial_published = len(bus.get_published_events())

        replay.replay_all("topic-a")
        final_published = len(bus.get_published_events())

        assert final_published == initial_published, (
            "repeated replay should be idempotent and not re-send events"
        )


class TestDeadLetterQueueRetryLogic:
    """Test dead letter queue retry counting."""

    def test_retry_count_increments(self):
        """Each push should increment the retry count."""
        from shared.events.base import DeadLetterQueue, Event

        dlq = DeadLetterQueue(max_retries=3)
        event = Event(event_id="evt-fail-1", event_type="test.failed")

        dlq.push(event, "connection_timeout")
        assert dlq.get_retry_count("evt-fail-1") == 1

        dlq.push(event, "connection_timeout")
        assert dlq.get_retry_count("evt-fail-1") == 2

    def test_max_retries_enforced(self):
        """Events exceeding max retries should not be retryable."""
        from shared.events.base import DeadLetterQueue, Event

        dlq = DeadLetterQueue(max_retries=2)
        event = Event(event_id="evt-fail-2", event_type="test.failed")

        dlq.push(event, "error1")
        dlq.push(event, "error2")

        assert not dlq.can_retry("evt-fail-2"), (
            "event at max retries should not be retryable"
        )

    def test_can_retry_unknown_event(self):
        """Unknown event IDs should be retryable."""
        from shared.events.base import DeadLetterQueue

        dlq = DeadLetterQueue(max_retries=3)
        assert dlq.can_retry("never-seen"), "unknown events should be retryable"


class TestShallowCopyLatentBugs:
    """Test that parameter server returns independent copies."""

    def test_parameter_server_returns_independent_copy(self):
        """Modifying returned parameters should not affect server state."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weights": [1.0, 2.0, 3.0]}

        params = ps.get_parameters()
        params["weights"].append(999.0)

        # The server's internal state should not be modified
        internal = ps.get_parameters()
        assert len(internal["weights"]) == 3, (
            "modifying returned parameters should not affect server state"
        )

    def test_parameter_server_mutation_isolation(self):
        """Mutating nested structures in returned params should be isolated from server."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"config": {"lr": 0.01, "layers": [64, 128]}}

        params = ps.get_parameters()
        params["config"]["lr"] = 999.0
        params["config"]["layers"].append(256)

        internal = ps.get_parameters()
        assert internal["config"]["lr"] == 0.01, (
            "modifying nested dict values should not propagate to server"
        )
        assert len(internal["config"]["layers"]) == 2, (
            "modifying nested list values should not propagate to server"
        )

    def test_gradient_accumulator_returns_independent_copy(self):
        """Accumulated gradients should be independent of internal state."""
        from shared.ml.model_loader import GradientAccumulator

        acc = GradientAccumulator(accumulation_steps=1)
        grad = {"layer": np.array([1.0, 2.0, 3.0])}
        acc.accumulate(grad)

        result = acc.get_accumulated()
        result["layer"][0] = 999.0

        # Reset and accumulate again
        acc.reset()
        acc.accumulate({"layer": np.array([4.0, 5.0, 6.0])})
        result2 = acc.get_accumulated()

        assert result2["layer"][0] == 4.0, (
            "modifying returned gradients should not corrupt accumulator state"
        )


class TestGradientNormalizerNormType:
    """Test GradientNormalizer applies normalization correctly across parameters."""

    def test_single_parameter_normalization(self):
        """Single parameter normalization should produce target norm."""
        from shared.utils.distributed import GradientNormalizer

        normalizer = GradientNormalizer(target_norm=1.0)
        grads = {"param": np.array([3.0, 4.0])}

        normalized = normalizer.normalize(grads)
        result_norm = float(np.sqrt(np.sum(normalized["param"] ** 2)))

        assert abs(result_norm - 1.0) < 0.01, (
            "normalized single parameter should have the target norm"
        )

    def test_multi_parameter_total_norm_equals_target(self):
        """Total gradient norm after normalization should equal target_norm, not target_norm * num_params."""
        from shared.utils.distributed import GradientNormalizer

        normalizer = GradientNormalizer(target_norm=1.0)
        grads = {
            "p1": np.array([1.0, 0.0]),
            "p2": np.array([0.0, 1.0]),
        }

        normalized = normalizer.normalize(grads)
        total_norm = float(np.sqrt(
            sum(np.sum(g ** 2) for g in normalized.values())
        ))

        assert abs(total_norm - 1.0) < 0.01, (
            "total gradient norm across all parameters should equal target_norm"
        )

    def test_multi_parameter_norm_not_scaled_by_count(self):
        """With 3 parameters, total norm should still be target_norm, not 3x target_norm."""
        from shared.utils.distributed import GradientNormalizer

        normalizer = GradientNormalizer(target_norm=2.0)
        grads = {
            "a": np.array([1.0, 1.0]),
            "b": np.array([1.0, 1.0]),
            "c": np.array([1.0, 1.0]),
        }

        normalized = normalizer.normalize(grads)
        total_norm = float(np.sqrt(
            sum(np.sum(g ** 2) for g in normalized.values())
        ))

        # Should be 2.0, not 6.0 (2.0 * 3 params)
        assert abs(total_norm - 2.0) < 0.1, (
            "total gradient norm should equal target_norm regardless of parameter count"
        )

    def test_normalize_preserves_direction(self):
        """Normalization should preserve gradient direction within each parameter."""
        from shared.utils.distributed import GradientNormalizer

        normalizer = GradientNormalizer(target_norm=2.0)
        grads = {"p1": np.array([1.0, 0.0]), "p2": np.array([0.0, 1.0])}

        normalized = normalizer.normalize(grads)
        if np.linalg.norm(normalized["p1"]) > 1e-10:
            direction_original = grads["p1"] / np.linalg.norm(grads["p1"])
            direction_normalized = normalized["p1"] / np.linalg.norm(normalized["p1"])
            assert np.allclose(direction_original, direction_normalized, atol=0.01), (
                "normalization should preserve the direction of each parameter's gradient"
            )

    def test_gradient_stats_norm_computation(self):
        """compute_gradient_stats should report correct per-parameter norm."""
        from shared.utils.distributed import GradientNormalizer

        normalizer = GradientNormalizer()
        grads = {"param": np.array([3.0, 4.0])}

        stats = normalizer.compute_gradient_stats(grads)
        assert abs(stats["param"]["norm"] - 5.0) < 0.01, (
            "gradient stats should report correct norm for each parameter"
        )
