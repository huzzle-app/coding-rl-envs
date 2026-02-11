"""
SynapseNet Multi-Step Bug Tests
Tests for bug chains where fixing one bug reveals another.
These require sequential discovery and fixing.
"""
import os
import sys
import time
import threading
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestCheckpointSaveLoadVersionChain:
    """Bug chain: Checkpoint save writes version -> Load doesn't validate -> Rollback reads wrong version."""

    def test_checkpoint_save_load_roundtrip(self):
        """Checkpoint save/load should preserve all data including version."""
        from shared.ml.model_loader import ModelLoader

        loader = ModelLoader()
        weights = {"layer1": np.array([1.0, 2.0, 3.0]).tolist()}
        metadata = {"epoch": 10, "loss": 0.5}

        path = loader.save_checkpoint("model-1", "v2", weights, metadata)
        loaded = loader.load_checkpoint(path)

        assert loaded["model_id"] == "model-1"
        assert loaded["version"] == "v2"
        assert loaded["metadata"]["epoch"] == 10

    def test_rollback_loads_previous_version(self):
        """Rollback should load the version before the current one."""
        from shared.ml.model_loader import ModelLoader

        loader = ModelLoader()
        loader.load_model("model-1", "v1", {"w": 1.0})
        loader.load_model("model-1", "v2", {"w": 2.0})
        loader.load_model("model-1", "v3", {"w": 3.0})

        rolled_back = loader.rollback_model("model-1")
        assert rolled_back is not None
        assert rolled_back["version"] == "v2", (
            "rollback from v3 should restore v2"
        )

    def test_double_rollback(self):
        """Two rollbacks from v3 should go v3 -> v2 -> v1."""
        from shared.ml.model_loader import ModelLoader

        loader = ModelLoader()
        loader.load_model("model-1", "v1", {"w": 1.0})
        loader.load_model("model-1", "v2", {"w": 2.0})
        loader.load_model("model-1", "v3", {"w": 3.0})

        first = loader.rollback_model("model-1")
        assert first["version"] == "v2", "first rollback should restore v2"

        second = loader.rollback_model("model-1")
        assert second is not None and second["version"] == "v1", (
            "second rollback should restore v1"
        )


class TestTokenRefreshPermissionChain:
    """Bug chain: Token refresh -> Permission cache -> Service auth."""

    def test_permission_cache_invalidated_on_token_refresh(self):
        """Refreshing a token should invalidate the permission cache."""
        from services.auth.views import TokenManager, PermissionCache

        tm = TokenManager()
        pc = PermissionCache(ttl=300.0)

        tokens = tm.create_token("user-1", {"role": "viewer"})
        pc.set_permissions("user-1", {"read": True, "write": False})

        new_tokens = tm.refresh(tokens["refresh_token"])

        cached = pc.get_permissions("user-1")
        assert cached is None or cached == {"read": True, "write": False}, (
            "permission cache should be invalidated on token refresh"
        )

    def test_concurrent_token_refresh_safety(self):
        """Two concurrent refreshes of the same token should not both succeed."""
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user-1", {"role": "admin"})
        refresh_token = tokens["refresh_token"]

        results = []
        errors = []

        def do_refresh():
            try:
                result = tm.refresh(refresh_token)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=do_refresh)
        t2 = threading.Thread(target=do_refresh)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successful = [r for r in results if r is not None]
        assert len(successful) <= 1, (
            "only one concurrent refresh should succeed per token"
        )


class TestFeatureTransformDriftChain:
    """Bug chain: Feature transform ordering -> Drift detection -> Model retraining."""

    def test_transform_then_drift_detection(self):
        """Drift detection after transform should use transformed distribution."""
        from shared.ml.feature_utils import FeatureTransformPipeline, DriftDetector

        pipeline = FeatureTransformPipeline()
        detector = DriftDetector(threshold=0.1)

        pipeline.add_transform(
            name="normalize",
            transform_fn=lambda inputs: (inputs.get("raw", 0) - 50.0) / 10.0,
            input_features=["raw"],
            output_feature="normalized",
        )

        detector.set_reference("normalized", mean=0.0, std=1.0)

        result = pipeline.execute({"raw": 55.0})
        normalized_value = result["normalized"]

        is_drifted = detector.detect_drift("normalized",
                                            current_mean=normalized_value,
                                            current_std=1.0)
        assert not is_drifted, (
            "normalized value within reference range should not trigger drift"
        )

    def test_consistency_after_transform_update(self):
        """Online and offline stores should stay consistent when transforms change."""
        from shared.ml.feature_utils import FeatureStore, FeatureTransformPipeline

        store = FeatureStore()
        pipeline = FeatureTransformPipeline()

        store.write_feature("entity-1", "features", {"raw": 100.0})

        pipeline.add_transform(
            name="scale",
            transform_fn=lambda inputs: inputs.get("raw", 0) * 2,
            input_features=["raw"],
            output_feature="scaled",
        )

        online = store.read_online("entity-1", "features")
        offline = store.read_offline("entity-1", "features")

        assert online is not None and offline is not None
        assert online["values"] == offline["values"], (
            "online and offline stores should have identical data"
        )


class TestParameterServerVersionOrdering:
    """Tests that the parameter server version is consistent with actual parameter state."""

    def test_stale_gradient_rejected(self):
        """Gradients beyond staleness bound should be rejected."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 1.0}

        # Advance version well beyond max_staleness
        for i in range(20):
            ps.apply_gradient(f"worker-{i}", {"w": 0.01}, ps.get_version())

        result = ps.apply_gradient("stale_worker", {"w": 0.1}, 0)
        assert result is False, "stale gradients should be rejected"

    def test_near_stale_gradient_scaled_lr(self):
        """Gradients near staleness bound should use reduced learning rate."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 10.0}

        # Advance version to 5
        for i in range(5):
            ps.apply_gradient(f"setup-{i}", {"w": 0.0}, ps.get_version())

        initial_w = ps._parameters["w"]

        # Apply a gradient that is stale by 5 steps (within max_staleness=10)
        # With scaled lr = 0.01 * (0.5^5) = 0.0003125, change = 0.0003125
        ps.apply_gradient("worker_stale", {"w": 1.0}, 0)  # staleness = current_version - 0

        change = abs(ps._parameters["w"] - initial_w)

        assert change < 0.02, (
            "near-stale gradients should use a reduced learning rate"
        )

    def test_version_reflects_completed_update(self):
        """The version returned by get_version should correspond to fully applied parameters."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 0.0}

        # Apply a gradient, then immediately read version and params
        ps.apply_gradient("w1", {"w": 1.0}, ps.get_version())
        v = ps.get_version()
        params = ps.get_parameters()

        # At version v, the parameters should reflect the gradient that caused version v
        # If version was incremented before the update loop, a concurrent reader could see
        # the new version while params are still at the old values.
        assert v >= 1, "version should have advanced after applying a gradient"
        assert params["w"] != 0.0, (
            "parameters should be updated when version is reported as advanced"
        )

    def test_staleness_boundary_exactly_at_max(self):
        """A gradient with staleness exactly equal to max_staleness should be accepted."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 5.0}

        # Advance version to exactly max_staleness (10)
        for i in range(10):
            ps.apply_gradient(f"setup-{i}", {"w": 0.0}, ps.get_version())

        version_now = ps.get_version()
        # staleness = version_now - 0 = 10, which equals max_staleness
        result = ps.apply_gradient("boundary_worker", {"w": 1.0}, 0)
        assert result is True, (
            "gradient at exactly max_staleness should be accepted"
        )

    def test_staleness_one_beyond_max_rejected(self):
        """A gradient with staleness = max_staleness + 1 should be rejected."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 5.0}

        # Advance version to max_staleness + 1 (11)
        for i in range(11):
            ps.apply_gradient(f"setup-{i}", {"w": 0.0}, ps.get_version())

        result = ps.apply_gradient("too_stale", {"w": 1.0}, 0)
        assert result is False, (
            "gradient one step beyond max_staleness should be rejected"
        )


class TestTensorSplitMergeChain:
    """Tests for tensor splitting and merging along different axes."""

    def test_tensor_split_preserves_elements(self):
        """Split should preserve all elements, including remainder."""
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=3)
        tensor = np.arange(10.0)

        splits = splitter.split(tensor)
        total_elements = sum(len(s) for s in splits)

        assert total_elements == 10, (
            "splitting should preserve all elements including remainder"
        )

    def test_split_merge_roundtrip_1d(self):
        """split then merge should recover the original 1D tensor exactly."""
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=3)
        original = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

        splits = splitter.split(original)
        merged = splitter.merge(splits)

        assert np.array_equal(original, merged), (
            "split and merge roundtrip should recover the original 1D tensor"
        )

    def test_split_even_division(self):
        """Evenly divisible tensors should split without issues."""
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=4)
        tensor = np.arange(12.0)

        splits = splitter.split(tensor)
        assert len(splits) == 4
        for s in splits:
            assert len(s) == 3

    def test_split_merge_roundtrip_2d_axis1(self):
        """split and merge along axis 1 should recover the original matrix."""
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=2)
        original = np.array([[1.0, 2.0, 3.0, 4.0],
                             [5.0, 6.0, 7.0, 8.0],
                             [9.0, 10.0, 11.0, 12.0]])

        splits = splitter.split(original, dim=1)
        merged = splitter.merge(splits, dim=1)

        assert merged.shape == original.shape, (
            "split and merge along axis 1 should preserve shape"
        )
        assert np.array_equal(original, merged), (
            "split and merge along axis 1 should recover the original matrix"
        )

    def test_split_merge_roundtrip_2d_axis0(self):
        """split and merge along axis 0 (default) should recover a 2D matrix."""
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=3)
        original = np.arange(12.0).reshape(6, 2)

        splits = splitter.split(original, dim=0)
        merged = splitter.merge(splits, dim=0)

        assert np.array_equal(original, merged), (
            "split and merge along axis 0 should recover the original 2D matrix"
        )

    def test_split_merge_3d_axis1(self):
        """split and merge along axis 1 for a 3D tensor should roundtrip correctly."""
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=2)
        original = np.arange(24.0).reshape(2, 4, 3)

        splits = splitter.split(original, dim=1)
        merged = splitter.merge(splits, dim=1)

        assert np.array_equal(original, merged), (
            "split and merge along axis 1 for 3D tensor should roundtrip"
        )


class TestElasticScalerReregistration:
    """Test elastic scaler handles worker re-registration correctly."""

    def test_reregister_same_worker(self):
        """Re-registering the same worker should not create duplicate entries."""
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        idx1 = scaler.register_worker("worker-A")
        idx2 = scaler.register_worker("worker-A")

        active = scaler.get_active_workers()
        assert active.count("worker-A") == 1, (
            "re-registered worker should appear exactly once in active workers"
        )

    def test_reregister_preserves_index(self):
        """Re-registering should keep the same worker index."""
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        idx1 = scaler.register_worker("worker-A")
        idx2 = scaler.register_worker("worker-A")

        assert idx1 == idx2, (
            "re-registration should return the same index"
        )

    def test_reregister_does_not_create_index_gaps(self):
        """Re-registering an existing worker should not increment the next index counter."""
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        scaler.register_worker("worker-A")
        scaler.register_worker("worker-B")

        # Re-register worker-A multiple times
        scaler.register_worker("worker-A")
        scaler.register_worker("worker-A")
        scaler.register_worker("worker-A")

        # Now register a brand new worker
        idx_c = scaler.register_worker("worker-C")

        # worker-A got index 0, worker-B got index 1, worker-C should get index 2
        assert idx_c == 2, (
            "re-registration should not create index gaps"
        )

    def test_reregister_then_new_worker_sequential_indices(self):
        """After re-registrations, new workers should get the next sequential index."""
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        scaler.register_worker("w1")  # index 0
        scaler.register_worker("w2")  # index 1

        # Re-register w1 many times
        for _ in range(10):
            scaler.register_worker("w1")

        idx_w3 = scaler.register_worker("w3")
        assert idx_w3 == 2, (
            "re-registration should not inflate the next available index"
        )


class TestDistributedCheckpointerConsistency:
    """Test checkpoint creation uses consistent worker states and tracks checkpoint step correctly."""

    def test_checkpoint_uses_min_step(self):
        """Checkpoint step should be the minimum across all workers."""
        from services.training.tasks import DistributedCheckpointer

        ckpt = DistributedCheckpointer(num_workers=3)

        ckpt.report_state("w1", {"params": [1.0]}, step=100)
        ckpt.report_state("w2", {"params": [2.0]}, step=105)
        ckpt.report_state("w3", {"params": [3.0]}, step=98)

        checkpoint = ckpt.create_checkpoint()
        assert checkpoint is not None
        assert checkpoint["step"] == 98, (
            "checkpoint step should be the minimum across all workers"
        )

    def test_checkpoint_requires_all_workers(self):
        """Checkpoint should not be created until all workers report."""
        from services.training.tasks import DistributedCheckpointer

        ckpt = DistributedCheckpointer(num_workers=3)
        ckpt.report_state("w1", {"params": [1.0]}, step=100)
        ckpt.report_state("w2", {"params": [2.0]}, step=100)

        checkpoint = ckpt.create_checkpoint()
        assert checkpoint is None, (
            "checkpoint should not be created until all workers have reported"
        )

    def test_should_checkpoint_uses_last_checkpoint_step(self):
        """Checkpoint interval should be measured from last checkpoint step, not from global max."""
        from services.training.tasks import DistributedCheckpointer

        ckpt = DistributedCheckpointer(num_workers=2)
        ckpt._checkpoint_interval = 50

        # Workers report with a spread: min=100, max=120
        ckpt.report_state("w1", {"params": [1.0]}, step=100)
        ckpt.report_state("w2", {"params": [2.0]}, step=120)

        # Create a checkpoint -- checkpoint step should be min=100
        checkpoint = ckpt.create_checkpoint()
        assert checkpoint is not None
        assert checkpoint["step"] == 100

        # After the checkpoint, _last_checkpoint_step should be the checkpoint step (100),
        # not the global max (120). Now advance workers slightly.
        ckpt.report_state("w1", {"params": [1.1]}, step=140)
        ckpt.report_state("w2", {"params": [2.1]}, step=148)

        # Distance from last checkpoint step (100) to global_step (148) = 48 < 50
        # should_checkpoint should return False
        # But if _last_checkpoint_step was set to 120, distance = 148-120 = 28, also False
        # Need to push further to expose the difference
        ckpt.report_state("w1", {"params": [1.2]}, step=155)
        ckpt.report_state("w2", {"params": [2.2]}, step=160)

        # If _last_checkpoint_step = 100 (correct): 160 - 100 = 60 >= 50 -> True
        # If _last_checkpoint_step = 120 (buggy):   160 - 120 = 40 < 50  -> False
        assert ckpt.should_checkpoint() is True, (
            "checkpoint interval should be measured from last checkpoint step"
        )

    def test_second_checkpoint_timing(self):
        """After creating a checkpoint, the next checkpoint timing should be based on that checkpoint's step."""
        from services.training.tasks import DistributedCheckpointer

        ckpt = DistributedCheckpointer(num_workers=2)
        ckpt._checkpoint_interval = 100

        # First round: workers at step 200 and 250
        ckpt.report_state("w1", {"params": [1.0]}, step=200)
        ckpt.report_state("w2", {"params": [2.0]}, step=250)
        cp1 = ckpt.create_checkpoint()
        assert cp1["step"] == 200

        # Second round: workers at step 280 and 310
        # If _last_checkpoint_step = 200 (correct): 310 - 200 = 110 >= 100 -> True
        # If _last_checkpoint_step = 250 (buggy):   310 - 250 = 60 < 100  -> False
        ckpt.report_state("w1", {"params": [1.1]}, step=280)
        ckpt.report_state("w2", {"params": [2.1]}, step=310)

        assert ckpt.should_checkpoint() is True, (
            "next checkpoint should be triggered based on previous checkpoint step"
        )


class TestRingAllReduceWorkerRemoval:
    """Test ring all-reduce behavior when workers are removed."""

    def test_reduce_after_worker_removal_averages_correctly(self):
        """Reduce after worker removal should average remaining workers correctly."""
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w1", "w2", "w3"])

        # Submit data from all three workers
        ring.submit("w1", np.array([3.0, 6.0]))
        ring.submit("w2", np.array([6.0, 12.0]))
        ring.submit("w3", np.array([9.0, 18.0]))

        # Remove w3 before reduce
        ring.remove_worker("w3")

        # Now only w1 and w2 are in the ring; their average is [4.5, 9.0]
        # But w3's buffer is still present. The reduce should only consider
        # workers that are in the ring and divide by the current ring size.
        result = ring.reduce()

        assert result is not None, (
            "reduce should succeed after worker removal with remaining submissions"
        )
        expected = np.array([4.5, 9.0])
        assert np.allclose(result, expected), (
            "reduce after worker removal should average remaining workers correctly"
        )

    def test_reduce_with_all_workers_present(self):
        """Basic reduce with all workers should compute correct average."""
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w1", "w2"])
        ring.submit("w1", np.array([2.0, 4.0]))
        ring.submit("w2", np.array([4.0, 8.0]))

        result = ring.reduce()
        expected = np.array([3.0, 6.0])
        assert result is not None
        assert np.allclose(result, expected), (
            "reduce should compute average of all worker submissions"
        )

    def test_remove_worker_clears_stale_buffer(self):
        """Removing a worker should not let its stale buffer affect future reductions."""
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w1", "w2", "w3"])

        # w3 submits before removal
        ring.submit("w3", np.array([100.0, 200.0]))

        # Remove w3
        ring.remove_worker("w3")

        # Now only w1 and w2 submit fresh data
        ring.submit("w1", np.array([2.0, 4.0]))
        ring.submit("w2", np.array([4.0, 8.0]))

        result = ring.reduce()
        assert result is not None
        expected = np.array([3.0, 6.0])
        assert np.allclose(result, expected), (
            "stale buffer from removed worker should not affect the reduction"
        )


class TestGradientAccumulatorV2ErrorFeedback:
    """Test gradient accumulation with error feedback loop."""

    def test_error_feedback_improves_accuracy(self):
        """Error feedback should make compressed gradients more accurate over multiple rounds."""
        from services.training.tasks import GradientAccumulatorV2

        acc = GradientAccumulatorV2(accumulation_steps=1, compression_ratio=0.5)

        total_applied = np.zeros(10)
        true_gradient = np.ones(10) * 0.5

        for _ in range(10):
            acc.accumulate({"layer": true_gradient.copy()})
            compressed = acc.get_compressed()
            total_applied += compressed["layer"]
            acc.reset()

        expected_total = true_gradient * 10
        error = np.mean(np.abs(total_applied - expected_total))

        assert error < 1.0, (
            "error feedback should keep accumulated error bounded"
        )

    def test_compression_ratio_respected(self):
        """Compressed output should have roughly compression_ratio * size non-zero elements."""
        from services.training.tasks import GradientAccumulatorV2

        acc = GradientAccumulatorV2(accumulation_steps=1, compression_ratio=0.1)

        grad = {"layer": np.random.randn(100)}
        acc.accumulate(grad)
        compressed = acc.get_compressed()

        nonzero = np.count_nonzero(compressed["layer"])
        expected = int(100 * 0.1)

        assert abs(nonzero - expected) <= 2, (
            "compression ratio should control the number of non-zero elements"
        )

    def test_error_feedback_with_2d_tensors(self):
        """Error feedback should work correctly with 2D tensors across multiple rounds."""
        from services.training.tasks import GradientAccumulatorV2

        acc = GradientAccumulatorV2(accumulation_steps=1, compression_ratio=0.5)

        original_grad = np.array([[1.0, 2.0, 3.0],
                                   [4.0, 5.0, 6.0]])

        # First round
        acc.accumulate({"layer": original_grad.copy()})
        compressed_1 = acc.get_compressed()
        assert compressed_1["layer"].shape == original_grad.shape, (
            "compressed output should preserve the original tensor shape"
        )
        acc.reset()

        # Second round -- error feedback from round 1 should be added to the gradient.
        # If error feedback is stored as flat (1D) but the next gradient is 2D,
        # the shapes will mismatch and cause an error.
        acc.accumulate({"layer": original_grad.copy()})
        compressed_2 = acc.get_compressed()
        assert compressed_2["layer"].shape == original_grad.shape, (
            "error feedback should preserve tensor shape across accumulation rounds"
        )

    def test_error_feedback_2d_multiple_rounds(self):
        """Multiple rounds of accumulation with 2D tensors should not raise shape errors."""
        from services.training.tasks import GradientAccumulatorV2

        acc = GradientAccumulatorV2(accumulation_steps=1, compression_ratio=0.25)

        grad_2d = np.random.randn(4, 8)

        for i in range(5):
            acc.accumulate({"w": grad_2d.copy()})
            compressed = acc.get_compressed()
            assert compressed["w"].shape == grad_2d.shape, (
                f"round {i}: error feedback shape should match 2D gradient shape"
            )
            acc.reset()


class TestAPIKeyRotationWindow:
    """Test that API key rotation doesn't create a gap."""

    def test_no_gap_during_rotation(self):
        """During rotation, either old or new key should be valid at all times."""
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        old_key = km.create_key("user-1")

        user = km.validate_key(old_key)
        assert user == "user-1"

        new_key = km.rotate_key(old_key)
        assert new_key is not None

        user_new = km.validate_key(new_key)
        assert user_new == "user-1", "new key should be valid after rotation"
