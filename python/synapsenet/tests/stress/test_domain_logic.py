"""
SynapseNet Domain Logic Tests
Tests requiring understanding of ML/AI domain concepts - not just operator swaps.
"""
import os
import sys
import time
import math
import threading
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestCosineAnnealingScheduler:
    """Test cosine annealing with warm restarts follows correct mathematical formula."""

    def test_initial_lr_is_base_lr(self):
        """First step should return base_lr (top of cosine)."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.01, min_lr=0.0001, period=100)
        lr = scheduler.step()
        assert abs(lr - 0.01) < 0.001, "LR at first step should be near base_lr"

    def test_mid_period_lr(self):
        """At half period, LR should be midpoint between base and min."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.01, min_lr=0.0, period=100)
        for _ in range(50):
            lr = scheduler.step()
        assert abs(lr - 0.005) < 0.001, "LR at half period should be near midpoint"

    def test_end_of_period_lr(self):
        """At end of period, LR should be at min_lr."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.01, min_lr=0.0001, period=100)
        for _ in range(99):
            lr = scheduler.step()
        assert lr < 0.001, "LR near end of period should approach min_lr"

    def test_warm_restart_at_exact_period_boundary(self):
        """At exactly step=period, the warm restart should happen and LR should jump back to base_lr."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.01, min_lr=0.0001,
                                              period=10, period_mult=1.0)
        # Step through the entire first period (steps 1 through 10)
        for i in range(10):
            lr = scheduler.step()

        # At step 10 (which equals the period), a restart should have occurred.
        # The LR at step=period should reflect the restart, not linger at min_lr for an extra step.
        restart_count_after_period = scheduler.get_restart_count()
        assert restart_count_after_period >= 1, "warm restart should occur at the period boundary"

        # The LR returned at the period boundary step should be near base_lr
        # (i.e., the restart happened at step=period, not step=period+1)
        # If the restart is delayed by one step, the LR at step=period would be near min_lr
        # and the LR at step=period+1 would be near base_lr.
        lr_at_boundary = lr  # This is the LR from step 10
        lr_next = scheduler.step()  # This is step 11

        # One of these should be near base_lr. The correct behavior is that step 10
        # triggers the restart, so either lr_at_boundary reflects the restart
        # or lr_next is the first step of the new period.
        # With the off-by-one bug (> instead of >=), the restart happens at step 11
        # instead of step 10, meaning lr_at_boundary is still near min_lr.
        assert lr_at_boundary > 0.008 or restart_count_after_period == 1, (
            "LR should restart at period boundary, not one step after"
        )

    def test_warm_restart_resets_lr(self):
        """After warm restart, LR should jump back to base_lr."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.01, min_lr=0.0001,
                                              period=10, period_mult=1.0)
        # Run through first period
        for _ in range(10):
            scheduler.step()

        # First step of second period should be near base_lr
        lr = scheduler.step()
        assert lr > 0.008, "LR should jump back near base_lr after warm restart"

    def test_restart_happens_at_period_not_period_plus_one(self):
        """Verify restart count increments at step=period, not at step=period+1."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.1, min_lr=0.001,
                                              period=5, period_mult=1.0)
        # Take exactly 'period' steps
        for _ in range(5):
            scheduler.step()

        assert scheduler.get_restart_count() == 1, (
            "restart count should be 1 after exactly period steps"
        )

        # Take another 'period' steps
        for _ in range(5):
            scheduler.step()

        assert scheduler.get_restart_count() == 2, (
            "restart count should be 2 after exactly 2*period steps"
        )

    def test_period_doubling(self):
        """With period_mult=2, second period should be twice as long."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.01, min_lr=0.0,
                                              period=10, period_mult=2.0)
        # First period: 10 steps
        lrs_period1 = []
        for _ in range(10):
            lrs_period1.append(scheduler.step())

        assert scheduler.get_restart_count() == 1

        # Second period: 20 steps
        lrs_period2 = []
        for _ in range(20):
            lrs_period2.append(scheduler.step())

        assert scheduler.get_restart_count() == 2, (
            "should have 2 restarts after first period plus doubled second period"
        )

    def test_lr_values_form_cosine_curve_within_period(self):
        """LR values within a period should decrease monotonically (cosine from 1 to -1)."""
        from shared.ml.model_loader import CosineAnnealingScheduler

        scheduler = CosineAnnealingScheduler(base_lr=0.1, min_lr=0.0, period=20, period_mult=1.0)
        lrs = []
        for _ in range(20):
            lrs.append(scheduler.step())

        # LR should generally decrease throughout the period
        # Check that the first quarter has higher LR than the last quarter
        first_quarter_avg = sum(lrs[:5]) / 5
        last_quarter_avg = sum(lrs[15:]) / 5
        assert first_quarter_avg > last_quarter_avg, (
            "LR should decrease over the period following a cosine curve"
        )


class TestEarlyStoppingLogic:
    """Test early stopping handles min/max mode correctly."""

    def test_min_mode_stops_on_plateau(self):
        """In min mode, should stop when metric stops decreasing."""
        from services.training.main import EarlyStopping

        es = EarlyStopping(patience=3, min_delta=0.01, mode="min")

        # Decreasing loss
        assert not es.step(1.0)
        assert not es.step(0.9)
        assert not es.step(0.8)

        # Plateau - should stop after exactly patience (3) non-improving steps
        assert not es.step(0.8)  # non-improving step 1
        assert not es.step(0.8)  # non-improving step 2
        assert es.step(0.8), "training should stop after patience epochs without improvement"

    def test_max_mode_stops_on_plateau(self):
        """In max mode, should stop when metric stops increasing."""
        from services.training.main import EarlyStopping

        es = EarlyStopping(patience=3, min_delta=0.01, mode="max")

        # Increasing accuracy
        assert not es.step(0.5)
        assert not es.step(0.6)
        assert not es.step(0.7)

        # Plateau - should stop after exactly patience (3) non-improving steps
        assert not es.step(0.7)  # non-improving step 1
        assert not es.step(0.7)  # non-improving step 2
        assert es.step(0.7), "training should stop after patience epochs without improvement"

    def test_patience_boundary_exact_count(self):
        """With patience=N, training should stop after exactly N non-improving steps, not N+1."""
        from services.training.main import EarlyStopping

        for patience_val in [1, 2, 3, 5]:
            es = EarlyStopping(patience=patience_val, min_delta=0.001, mode="min")
            es.step(1.0)  # initial best

            stopped_at = None
            for i in range(1, patience_val + 5):
                if es.step(1.0):  # no improvement
                    stopped_at = i
                    break

            assert stopped_at == patience_val, (
                f"with patience={patience_val}, training should stop after exactly "
                f"{patience_val} non-improving steps, not {stopped_at}"
            )

    def test_max_mode_patience_exact_count(self):
        """In max mode, patience should also trigger after exactly N non-improving steps."""
        from services.training.main import EarlyStopping

        es = EarlyStopping(patience=2, min_delta=0.001, mode="max")

        es.step(0.9)  # initial best
        assert not es.step(0.9)  # non-improving step 1
        assert es.step(0.9), (
            "with patience=2, training should stop after 2 non-improving steps"
        )

    def test_max_mode_recognizes_improvement(self):
        """In max mode, a higher value should reset patience counter."""
        from services.training.main import EarlyStopping

        es = EarlyStopping(patience=2, min_delta=0.001, mode="max")

        es.step(0.5)
        es.step(0.5)  # No improvement, counter = 1
        es.step(0.6)  # Improvement! Counter should reset
        es.step(0.6)  # No improvement, counter = 1
        result = es.step(0.6)  # No improvement, counter = 2

        assert result, "training should stop after patience non-improving steps"
        assert es.get_best() == 0.6

    def test_improvement_resets_counter(self):
        """Any improvement within patience window should reset the counter."""
        from services.training.main import EarlyStopping

        es = EarlyStopping(patience=3, min_delta=0.0, mode="min")

        es.step(1.0)
        es.step(1.0)  # counter=1
        es.step(1.0)  # counter=2
        es.step(0.5)  # improvement, counter should reset
        es.step(0.5)  # counter=1
        es.step(0.5)  # counter=2
        result = es.step(0.5)  # counter=3 -> should stop

        assert result, "training should stop after patience non-improving steps following a reset"


class TestMetricTrackerSmoothing:
    """Test metric tracker exponential smoothing."""

    def test_first_smoothed_value_reflects_actual_input(self):
        """After the first update, smoothed value should reflect the actual input, not be biased toward zero."""
        from services.training.main import MetricTracker

        tracker = MetricTracker(smoothing=0.9)
        tracker.update("loss", 5.0)

        smoothed = tracker.get_smoothed("loss")
        # If initialized to 0.0, smoothed = 0.9 * 0.0 + 0.1 * 5.0 = 0.5, heavily biased toward zero
        # If initialized to the first value, smoothed = 5.0
        assert smoothed is not None
        assert abs(smoothed - 5.0) < 1.0, (
            "first smoothed value should reflect actual input, not be biased toward zero"
        )

    def test_first_update_not_biased_toward_zero(self):
        """Smoothed value after first update should be close to the input value, not near zero."""
        from services.training.main import MetricTracker

        tracker = MetricTracker(smoothing=0.95)
        tracker.update("metric", 100.0)

        smoothed = tracker.get_smoothed("metric")
        # If initialized to 0: smoothed = 0.95 * 0 + 0.05 * 100 = 5.0 (way off)
        # If initialized correctly: smoothed = 100.0
        assert smoothed > 50.0, (
            "first smoothed value should not be biased toward zero"
        )

    def test_high_smoothing_preserves_initial_value(self):
        """With high smoothing factor, early values should still be reasonable, not near zero."""
        from services.training.main import MetricTracker

        tracker = MetricTracker(smoothing=0.99)
        tracker.update("loss", 10.0)
        tracker.update("loss", 10.0)
        tracker.update("loss", 10.0)

        smoothed = tracker.get_smoothed("loss")
        # If init to 0: after 3 updates with s=0.99, smoothed ~ 0.297
        # If init correctly: smoothed ~ 10.0
        assert smoothed > 5.0, (
            "smoothed value should converge near actual values, not stay near zero"
        )

    def test_smoothing_dampens_noise(self):
        """Smoothed values should be less noisy than raw values."""
        from services.training.main import MetricTracker

        tracker = MetricTracker(smoothing=0.9)

        np.random.seed(42)
        true_trend = np.linspace(1.0, 0.1, 50)
        noisy = true_trend + np.random.randn(50) * 0.2

        for v in noisy:
            tracker.update("loss", float(v))

        raw_history = tracker.get_history("loss")
        smoothed_final = tracker.get_smoothed("loss")

        assert smoothed_final is not None
        assert abs(smoothed_final - 0.1) < abs(raw_history[-1] - 0.1) + 0.5, (
            "smoothed value should be closer to the true trend than raw"
        )

    def test_moving_average_window(self):
        """Moving average should only consider last N values."""
        from services.training.main import MetricTracker

        tracker = MetricTracker()
        for v in [100.0, 100.0, 100.0, 1.0, 1.0, 1.0]:
            tracker.update("loss", v)

        ma = tracker.compute_moving_average("loss", window=3)
        assert abs(ma - 1.0) < 0.01, (
            "moving average of last 3 values should reflect only those values"
        )


class TestGradientAccumulationMixedPrecision:
    """Test gradient accumulation with mixed precision scaling."""

    def test_mixed_precision_accumulation_scaling(self):
        """Mixed precision should scale then unscale gradients correctly."""
        from shared.ml.model_loader import GradientAccumulator

        acc = GradientAccumulator(accumulation_steps=2, use_mixed_precision=True)

        grad1 = {"layer": np.array([0.1, 0.2])}
        grad2 = {"layer": np.array([0.3, 0.4])}

        acc.accumulate(grad1)
        acc.accumulate(grad2)

        result = acc.get_accumulated()
        expected = np.array([0.2, 0.3])

        assert np.allclose(result["layer"], expected, atol=0.5), (
            "accumulated mixed precision gradients should be properly unscaled"
        )


class TestBatchNormTrainingEvalIsolation:
    """Test that batch norm stats are isolated between training and eval modes."""

    def test_eval_mode_freezes_running_stats(self):
        """In eval mode, running statistics should NOT be updated."""
        from shared.ml.model_loader import BatchNormTracker

        bn = BatchNormTracker(num_features=3, momentum=0.1)

        # Train mode: update stats
        bn.set_training(True)
        bn.update_statistics(
            np.array([1.0, 2.0, 3.0]),
            np.array([0.5, 0.5, 0.5])
        )
        training_mean = bn.running_mean.copy()

        # Eval mode: stats should be frozen
        bn.set_training(False)
        bn.update_statistics(
            np.array([100.0, 200.0, 300.0]),
            np.array([50.0, 50.0, 50.0])
        )
        eval_mean = bn.running_mean.copy()

        assert np.allclose(training_mean, eval_mean), (
            "running stats should be frozen in eval mode"
        )


class TestFeatureTransformPipelineDependencies:
    """Test feature transform pipeline handles dependencies correctly."""

    def test_dependent_transforms_order(self):
        """Transforms with dependencies should execute in correct order."""
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()

        # B depends on A's output, but add B first
        pipeline.add_transform(
            name="transform_B",
            transform_fn=lambda inputs: inputs.get("feature_A_out", 0) * 2,
            input_features=["feature_A_out"],
            output_feature="feature_B_out",
            depends_on=["transform_A"],
        )
        pipeline.add_transform(
            name="transform_A",
            transform_fn=lambda inputs: 10,
            input_features=["raw_input"],
            output_feature="feature_A_out",
            depends_on=[],
        )

        result = pipeline.execute({"raw_input": 5})

        assert result["feature_A_out"] == 10, "upstream transform should produce expected output"
        assert result["feature_B_out"] == 20, (
            "dependent transform should receive upstream output in correct order"
        )

    def test_none_propagation_in_pipeline(self):
        """A failed transform should not silently poison downstream transforms."""
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()

        def failing_transform(inputs):
            raise ValueError("Data validation failed")

        pipeline.add_transform(
            name="failing",
            transform_fn=failing_transform,
            input_features=["input"],
            output_feature="intermediate",
        )
        pipeline.add_transform(
            name="downstream",
            transform_fn=lambda inputs: inputs["intermediate"] + 1 if inputs.get("intermediate") is not None else -1,
            input_features=["intermediate"],
            output_feature="output",
        )

        result = pipeline.execute({"input": 5})

        assert result.get("output") != 1, (
            "downstream transform should not silently coerce None from a failed upstream to zero"
        )


class TestDriftDetectorThreshold:
    """Test drift detector handles threshold semantics correctly."""

    def test_drift_at_exact_threshold(self):
        """Drift at exact threshold boundary should be consistently handled."""
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.5)
        detector.set_reference("feature_x", mean=10.0, std=2.0)

        # normalized_diff = |11.0 - 10.0| / 2.0 = 0.5
        is_drifted = detector.detect_drift("feature_x", current_mean=11.0, current_std=2.0)
        assert is_drifted, "drift at exact threshold boundary should be detected"

    def test_small_shift_not_flagged_at_low_threshold(self):
        """With threshold=0.05 interpreted as p-value, a small shift should NOT trigger drift."""
        from shared.ml.feature_utils import DriftDetector

        # threshold=0.05 is documented as a p-value (significance level)
        # At 5% significance, you need z > 1.96 to reject the null hypothesis
        # A shift of 0.1 standard deviations from the mean is NOT statistically significant
        detector = DriftDetector(threshold=0.05)
        detector.set_reference("feature_a", mean=50.0, std=10.0)

        # Current mean is 50.5, which is 0.05 std devs from reference mean
        # This tiny shift should NOT be flagged as drift at 5% significance
        is_drifted = detector.detect_drift("feature_a", current_mean=50.5, current_std=10.0)
        assert not is_drifted, (
            "small drift should not trigger detection at 5% significance level"
        )

    def test_small_shift_within_noise_not_flagged(self):
        """A shift of 0.1 standard deviations should not be flagged at conventional significance."""
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("feature_b", mean=100.0, std=20.0)

        # Shift of 2.0 units = 0.1 std devs, well within normal variation
        is_drifted = detector.detect_drift("feature_b", current_mean=102.0, current_std=20.0)
        assert not is_drifted, (
            "shift of 0.1 standard deviations should not be flagged as significant drift"
        )

    def test_large_shift_flagged(self):
        """A shift of several standard deviations should always be detected as drift."""
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        detector.set_reference("feature_c", mean=50.0, std=10.0)

        # Shift of 3 standard deviations (z=3.0), clearly significant
        is_drifted = detector.detect_drift("feature_c", current_mean=80.0, current_std=10.0)
        assert is_drifted, "large shift of multiple standard deviations should be detected"


class TestCorrelationTrackerAccuracy:
    """Test correlation tracker handles numerical precision correctly."""

    def test_correlation_zero_centered_data(self):
        """Correlation should be accurate for zero-centered data."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        np.random.seed(42)
        n = 200
        x = np.random.randn(n)
        y = x * 0.8 + np.random.randn(n) * 0.2  # highly correlated

        for i in range(n):
            tracker.add_observation("feat_a", float(x[i]))
            tracker.add_observation("feat_b", float(y[i]))

        corrs = tracker.compute_correlations()
        key = ("feat_a", "feat_b")
        assert key in corrs
        assert abs(corrs[key] - np.corrcoef(x, y)[0, 1]) < 0.05, (
            "correlation should be accurate for zero-centered data"
        )

    def test_correlation_large_offset_data(self):
        """Correlation should be accurate for features with large mean offsets."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        np.random.seed(123)
        n = 200
        # Data centered at 1000 (large offset)
        x = 1000.0 + np.random.randn(n)
        y = 1000.0 + x - 1000.0 + np.random.randn(n) * 0.3  # correlated but large mean

        for i in range(n):
            tracker.add_observation("big_a", float(x[i]))
            tracker.add_observation("big_b", float(y[i]))

        corrs = tracker.compute_correlations()
        key = ("big_a", "big_b")
        expected_corr = float(np.corrcoef(x, y)[0, 1])

        assert key in corrs
        assert abs(corrs[key] - expected_corr) < 0.1, (
            "correlation should be accurate for features with large mean offsets"
        )

    def test_correlation_catastrophic_cancellation(self):
        """Single-pass correlation formula should not suffer from catastrophic cancellation."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        np.random.seed(99)
        n = 500
        # Very large means with small variance - worst case for catastrophic cancellation
        base = 1e6
        x = base + np.random.randn(n) * 0.01
        y = base + x - base + np.random.randn(n) * 0.005  # nearly perfect correlation

        for i in range(n):
            tracker.add_observation("huge_a", float(x[i]))
            tracker.add_observation("huge_b", float(y[i]))

        corrs = tracker.compute_correlations()
        key = ("huge_a", "huge_b")
        expected = float(np.corrcoef(x, y)[0, 1])

        assert key in corrs
        computed = corrs[key]
        # With catastrophic cancellation, the computed value may be wildly wrong
        # (e.g., NaN, negative when it should be positive, or >1)
        assert not math.isnan(computed), "correlation should not be NaN due to numerical issues"
        assert -1.0 <= computed <= 1.0, "correlation should be in valid range [-1, 1]"
        assert abs(computed - expected) < 0.2, (
            "correlation should be accurate even with large mean offsets"
        )

    def test_uncorrelated_data_near_zero(self):
        """Uncorrelated features should have correlation near zero regardless of offset."""
        from shared.ml.feature_utils import CorrelationTracker

        tracker = CorrelationTracker()
        np.random.seed(77)
        n = 500
        x = 5000.0 + np.random.randn(n)
        y = 5000.0 + np.random.randn(n)  # independent

        for i in range(n):
            tracker.add_observation("ind_a", float(x[i]))
            tracker.add_observation("ind_b", float(y[i]))

        corrs = tracker.compute_correlations()
        key = ("ind_a", "ind_b")
        assert key in corrs
        assert abs(corrs[key]) < 0.15, (
            "uncorrelated features should have correlation near zero"
        )


class TestHyperparameterComparison:
    """Test hyperparameter float comparison handles edge cases."""

    def test_float_precision_comparison(self):
        """Should correctly compare floats that differ by precision errors."""
        from shared.utils.time import compare_hyperparameters

        hp1 = {"learning_rate": 0.1 + 0.2}
        hp2 = {"learning_rate": 0.3}

        result = compare_hyperparameters(hp1, hp2)
        assert result, "float comparison should handle precision errors"


class TestConsistentHashRingDistribution:
    """Test consistent hash ring distributes keys evenly."""

    def test_even_distribution(self):
        """Keys should be roughly evenly distributed across nodes."""
        from shared.utils.distributed import ConsistentHashRing

        ring = ConsistentHashRing(["node-1", "node-2", "node-3"])
        counts = {"node-1": 0, "node-2": 0, "node-3": 0}

        for i in range(3000):
            node = ring.get_node(f"key-{i}")
            counts[node] += 1

        for node, count in counts.items():
            assert 500 < count < 1500, (
                f"each node should receive a roughly equal share of keys"
            )

    def test_replication_returns_distinct_nodes(self):
        """Replication nodes should all be different physical nodes."""
        from shared.utils.distributed import ConsistentHashRing

        ring = ConsistentHashRing(["node-1", "node-2", "node-3"])
        nodes = ring.get_replication_nodes("test-key", replicas=3)

        assert len(nodes) == 3, "should return the requested number of replicas"
        assert len(set(nodes)) == 3, "all replication nodes should be distinct"

    def test_node_removal_minimal_disruption(self):
        """Removing a node should only reassign that node's keys."""
        from shared.utils.distributed import ConsistentHashRing

        ring = ConsistentHashRing(["node-1", "node-2", "node-3"])
        original = {}
        for i in range(1000):
            original[f"key-{i}"] = ring.get_node(f"key-{i}")

        ring.remove_node("node-2")
        changed = 0
        for i in range(1000):
            new_node = ring.get_node(f"key-{i}")
            if original[f"key-{i}"] != new_node:
                changed += 1
                assert original[f"key-{i}"] == "node-2", (
                    "only keys from the removed node should be reassigned"
                )

        assert changed > 0, "some keys should have moved after node removal"


class TestDataQualityChecks:
    """Test data quality checker handles edge cases."""

    def test_null_rate_check(self):
        """Should correctly compute null rate."""
        from services.pipeline.main import DataQualityChecker

        checker = DataQualityChecker()
        checker.add_rule("no_nulls", column="value", check_type="not_null", threshold=0.0)

        data = [{"value": 1}, {"value": None}, {"value": 3}]
        results = checker.check(data)

        assert not results["no_nulls"]["passed"], (
            "data with nulls should fail a zero-null threshold"
        )

    def test_uniqueness_check(self):
        """Should detect duplicate values."""
        from services.pipeline.main import DataQualityChecker

        checker = DataQualityChecker()
        checker.add_rule("unique_ids", column="id", check_type="unique", threshold=1.0)

        data = [{"id": "a"}, {"id": "b"}, {"id": "a"}]
        results = checker.check(data)

        assert not results["unique_ids"]["passed"], (
            "data with duplicates should fail uniqueness check"
        )

    def test_empty_dataset(self):
        """Empty dataset should pass quality checks."""
        from services.pipeline.main import DataQualityChecker

        checker = DataQualityChecker()
        checker.add_rule("check1", column="val", check_type="not_null")
        results = checker.check([])
        assert results["check1"]["passed"]


class TestSLOTrackerComputation:
    """Test SLO tracker correctly computes error budgets."""

    def test_slo_compliance(self):
        """Should correctly compute SLO compliance rate."""
        from services.monitoring.main import SLOTracker

        tracker = SLOTracker()
        tracker.define_slo("latency_p99", target=0.99, window_seconds=3600)

        for i in range(99):
            tracker.record("latency_p99", 0.05, is_good=True)
        tracker.record("latency_p99", 2.0, is_good=False)

        status = tracker.get_slo_status("latency_p99")
        assert abs(status["compliance"] - 0.99) < 0.01

    def test_slo_breach(self):
        """Should detect when SLO is breached."""
        from services.monitoring.main import SLOTracker

        tracker = SLOTracker()
        tracker.define_slo("availability", target=0.999, window_seconds=3600)

        for i in range(990):
            tracker.record("availability", 200, is_good=True)
        for i in range(10):
            tracker.record("availability", 500, is_good=False)

        status = tracker.get_slo_status("availability")
        assert not status["meeting_target"], "compliance below target should be a breach"

    def test_error_budget_remaining_full_compliance(self):
        """Error budget should be 1.0 when compliance is 100% and target is below 100%."""
        from services.monitoring.main import SLOTracker

        tracker = SLOTracker()
        tracker.define_slo("test_slo", target=0.95, window_seconds=3600)

        # 100% good
        for _ in range(100):
            tracker.record("test_slo", 1.0, is_good=True)

        status = tracker.get_slo_status("test_slo")
        # Compliance = 1.0, target = 0.95
        # Correct formula: (compliance - target) / (1 - target) = 0.05 / 0.05 = 1.0
        # Wrong formula:   (compliance - target) / target = 0.05 / 0.95 ~ 0.053
        assert abs(status["error_budget_remaining"] - 1.0) < 0.01, (
            "error budget should be 1.0 when compliance is 100% with a sub-100% target"
        )

    def test_error_budget_at_exact_target(self):
        """Error budget should be 0.0 when compliance exactly meets the target."""
        from services.monitoring.main import SLOTracker

        tracker = SLOTracker()
        tracker.define_slo("exact_slo", target=0.95, window_seconds=3600)

        # 95% good, 5% bad
        for _ in range(95):
            tracker.record("exact_slo", 1.0, is_good=True)
        for _ in range(5):
            tracker.record("exact_slo", 1.0, is_good=False)

        status = tracker.get_slo_status("exact_slo")
        assert abs(status["error_budget_remaining"] - 0.0) < 0.01, (
            "error budget should be 0.0 when compliance exactly equals the target"
        )

    def test_error_budget_high_target(self):
        """Error budget should use (1-target) denominator for high SLO targets."""
        from services.monitoring.main import SLOTracker

        tracker = SLOTracker()
        tracker.define_slo("strict_slo", target=0.999, window_seconds=3600)

        # 100% compliance
        for _ in range(1000):
            tracker.record("strict_slo", 1.0, is_good=True)

        status = tracker.get_slo_status("strict_slo")
        # (1.0 - 0.999) / (1.0 - 0.999) = 1.0
        # Wrong formula gives: (1.0 - 0.999) / 0.999 = ~0.001
        assert status["error_budget_remaining"] > 0.5, (
            "full compliance with high target should show substantial error budget remaining"
        )

    def test_error_budget_partial_consumption(self):
        """Error budget should reflect partial consumption proportionally."""
        from services.monitoring.main import SLOTracker

        tracker = SLOTracker()
        tracker.define_slo("partial_slo", target=0.90, window_seconds=3600)

        # 95% good -> used half of 10% error budget
        for _ in range(95):
            tracker.record("partial_slo", 1.0, is_good=True)
        for _ in range(5):
            tracker.record("partial_slo", 1.0, is_good=False)

        status = tracker.get_slo_status("partial_slo")
        # (0.95 - 0.90) / (1.0 - 0.90) = 0.05 / 0.10 = 0.5
        assert abs(status["error_budget_remaining"] - 0.5) < 0.05, (
            "error budget should reflect proportional consumption of the budget"
        )
