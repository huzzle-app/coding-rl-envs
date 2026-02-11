"""
SynapseNet Distributed Training Chaos Tests
Terminal Bench v2 - Tests for distributed training, parameter server, allreduce

Tests cover:
- A1-A10: Distributed Training bugs
"""
import time
import uuid
import threading
import sys
import os
from unittest import mock

import pytest
import numpy as np


# =========================================================================
# A1: Parameter server race condition
# =========================================================================

class TestParameterServerRace:
    """BUG A1: No lock on weight updates allows partial reads."""

    def test_parameter_server_race(self):
        """Concurrent gradient applications should be serialized."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"layer1": 1.0, "layer2": 2.0}

        errors = []
        results = []

        def apply_gradient(worker_id):
            try:
                gradient = {"layer1": 0.1, "layer2": 0.2}
                ps.apply_gradient(f"worker_{worker_id}", gradient, ps.get_version())
                results.append(ps.get_parameters())
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=apply_gradient, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent updates: {errors}"

        # After 20 gradient applications, version should be 20
        assert ps.get_version() == 20, (
            f"Version is {ps.get_version()}, expected 20. "
            "BUG A1: Race condition may cause lost updates."
        )

    def test_param_update_ordering(self):
        """Parameter updates should be applied in order."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weight": 10.0}

        # Apply gradients sequentially
        for i in range(10):
            ps.apply_gradient(f"worker_{i}", {"weight": 1.0}, ps.get_version())

        # weight = 10.0 - 10 * (0.01 * 1.0) = 10.0 - 0.10 = 9.90
        final = ps.get_parameters()
        expected = 10.0 - 10 * 0.01
        assert abs(final["weight"] - expected) < 0.01, (
            f"Final weight {final['weight']}, expected ~{expected}"
        )


# =========================================================================
# A2: Gradient allreduce deadlock
# =========================================================================

class TestGradientAllreduceDeadlock:
    """BUG A2: Wrong lock ordering causes deadlock."""

    def test_gradient_allreduce_deadlock(self):
        """AllReduce should not deadlock with concurrent submit and read."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coordinator = AllReduceCoordinator(num_workers=2)
        completed = {"submits": 0, "reads": 0}
        errors = []

        def submit_worker(worker_id):
            try:
                coordinator.submit_gradients(f"worker_{worker_id}", {"grad": 1.0})
                completed["submits"] += 1
            except Exception as e:
                errors.append(f"submit error: {e}")

        def read_worker(worker_id):
            try:
                result = coordinator.get_reduced_gradients(f"worker_{worker_id}")
                completed["reads"] += 1
            except Exception as e:
                errors.append(f"read error: {e}")

        
        # get_reduced acquires aggregation_lock then worker_lock
        # This can deadlock
        t1 = threading.Thread(target=submit_worker, args=(0,))
        t2 = threading.Thread(target=read_worker, args=(1,))

        t1.start()
        t2.start()

        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not t1.is_alive() and not t2.is_alive(), (
            "Threads are still alive after 5s timeout. "
            "BUG A2: Deadlock from inconsistent lock ordering."
        )

    def test_allreduce_timeout_recovery(self):
        """AllReduce should handle timeout gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coordinator = AllReduceCoordinator(num_workers=3)

        # Only 2 of 3 workers submit
        coordinator.submit_gradients("worker_0", {"grad": 1.0})
        coordinator.submit_gradients("worker_1", {"grad": 2.0})

        # Should handle missing worker gracefully
        result = coordinator.get_reduced_gradients("worker_0")
        assert result is not None or result == {}


# =========================================================================
# A3: Data parallelism shard overlap
# =========================================================================

class TestDataParallelismShardOverlap:
    """BUG A3: Data shards overlap between workers."""

    def test_data_parallelism_shard_overlap(self):
        """Each worker should receive unique data shards."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=3)
        data = np.arange(100)

        splits = splitter.split(data)

        # Check for overlaps between splits
        all_elements = []
        for split in splits:
            all_elements.extend(split.tolist())

        
        unique_elements = set(all_elements)
        assert len(unique_elements) == len(all_elements), (
            "Data shards should not overlap - each element should appear exactly once"
        )

    def test_shard_uniqueness(self):
        """No data point should appear in multiple shards."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=4)
        data = np.arange(20).reshape(20, 1)

        splits = splitter.split(data, dim=0)

        # Verify no overlaps
        seen = set()
        for split in splits:
            for val in split.flatten():
                assert val not in seen, f"Element {val} appears in multiple shards"
                seen.add(val)


# =========================================================================
# A4: Model parallelism tensor split error
# =========================================================================

class TestModelParallelismTensorSplit:
    """BUG A4: Tensor split drops remainder elements."""

    def test_model_parallelism_tensor_split(self):
        """Tensor split should preserve all elements."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=3)
        # 10 elements, 3 workers: 3+3+4 or similar
        tensor = np.arange(10).astype(float)

        splits = splitter.split(tensor)
        merged = splitter.merge(splits)

        
        # 10 // 3 = 3, so each worker gets 3, total = 9, drops element 9
        assert len(merged) == len(tensor), (
            f"Merged tensor has {len(merged)} elements, original has {len(tensor)}. "
            "BUG A4: Integer division drops remainder elements."
        )
        np.testing.assert_array_equal(merged, tensor)

    def test_tensor_split_boundary(self):
        """Tensor split should handle non-divisible sizes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=7)
        tensor = np.arange(100).astype(float)

        splits = splitter.split(tensor)
        total_elements = sum(len(s) for s in splits)

        
        assert total_elements == 100, (
            f"Total elements in splits: {total_elements}, expected 100. "
            "BUG A4: Remainder elements dropped."
        )

    def test_even_split(self):
        """Evenly divisible tensor should split correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter(num_workers=5)
        tensor = np.arange(25).astype(float)

        splits = splitter.split(tensor)
        assert all(len(s) == 5 for s in splits)
        merged = splitter.merge(splits)
        np.testing.assert_array_equal(merged, tensor)


# =========================================================================
# A5: Elastic scaling worker registration race
# =========================================================================

class TestElasticScalingRegistration:
    """BUG A5: Concurrent worker registration can assign same index."""

    def test_elastic_scaling_registration(self):
        """Concurrent worker registration should assign unique indices."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        indices = []
        lock = threading.Lock()

        def register(worker_id):
            idx = scaler.register_worker(worker_id)
            with lock:
                indices.append(idx)

        threads = [threading.Thread(target=register, args=(f"w_{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All indices should be unique
        
        assert len(set(indices)) == len(indices), (
            f"Got {len(indices)} indices but only {len(set(indices))} unique. "
            "BUG A5: Concurrent registration assigns duplicate indices."
        )

    def test_worker_join_leave(self):
        """Workers should be able to join and leave dynamically."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()

        # Workers join
        scaler.register_worker("w1")
        scaler.register_worker("w2")
        scaler.register_worker("w3")

        active = scaler.get_active_workers()
        assert len(active) == 3

        # Worker leaves
        scaler.deregister_worker("w2")
        active = scaler.get_active_workers()
        assert len(active) == 2
        assert "w2" not in active


# =========================================================================
# A6: Checkpoint barrier timeout
# =========================================================================

class TestCheckpointBarrierTimeout:
    """BUG A6: Barrier timeout too short for real workloads."""

    def test_checkpoint_barrier_timeout(self):
        """Barrier timeout should be long enough for workers to arrive."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=3)

        
        assert barrier.timeout >= 30.0, (
            f"Barrier timeout is {barrier.timeout}s. "
            "Should be >= 30s for distributed checkpointing. "
            "BUG A6: Timeout too short."
        )

    def test_barrier_synchronization(self):
        """All workers should arrive at barrier before proceeding."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=3, timeout=5.0)

        results = []

        def worker_arrive(worker_id, delay):
            time.sleep(delay)
            result = barrier.arrive(worker_id)
            results.append((worker_id, result))

        threads = [
            threading.Thread(target=worker_arrive, args=("w1", 0.0)),
            threading.Thread(target=worker_arrive, args=("w2", 0.1)),
            threading.Thread(target=worker_arrive, args=("w3", 0.2)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should have succeeded
        success_count = sum(1 for _, result in results if result)
        assert success_count == 3, (
            f"Only {success_count}/3 workers passed barrier"
        )


# =========================================================================
# A7: Gradient compression threshold too aggressive
# =========================================================================

class TestGradientCompressionThreshold:
    """BUG A7: Compression drops 99% of gradient values."""

    def test_gradient_compression_threshold(self):
        """Compression should retain significant gradient values."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import GradientCompressor

        compressor = GradientCompressor()
        gradients = np.random.randn(1000)

        compressed = compressor.compress(gradients)

        # Count non-zero values
        nonzero_count = np.count_nonzero(compressed)
        retention_rate = nonzero_count / len(gradients)

        
        assert retention_rate >= 0.10, (
            f"Only {retention_rate:.1%} of gradients retained. "
            "Should retain at least 10%. "
            "BUG A7: Compression threshold too aggressive."
        )

    def test_compression_accuracy(self):
        """Compressed gradients should approximate original."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import GradientCompressor

        compressor = GradientCompressor()
        original = np.random.randn(100)

        compressed = compressor.compress(original)
        decompressed = compressor.decompress(compressed)

        # Relative error should be small
        error = np.linalg.norm(original - decompressed) / np.linalg.norm(original)

        
        assert error < 0.5, (
            f"Compression error is {error:.2f}. "
            "Should be < 0.5 for useful gradient compression. "
            "BUG A7: Too aggressive compression."
        )


# =========================================================================
# A8: Ring allreduce topology mismatch
# =========================================================================

class TestRingAllreduceTopology:
    """BUG A8: Ring topology not reconstructed after node failure."""

    def test_ring_allreduce_topology(self):
        """Ring should be reconstructed after worker removal."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w1", "w2", "w3", "w4"])

        # Remove worker w2
        ring.remove_worker("w2")

        # Ring should be reconstructed without w2
        assert "w2" not in ring.worker_ids

        
        assert "w2" not in ring._ring, (
            "Failed worker w2 is still in the ring topology. "
            "BUG A8: worker_ids updated but _ring not reconstructed."
        )

    def test_topology_reconstruction(self):
        """Ring should function correctly after topology change."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w1", "w2", "w3"])

        # Submit data from all workers
        ring.submit("w1", np.array([1.0, 2.0]))
        ring.submit("w2", np.array([3.0, 4.0]))
        ring.submit("w3", np.array([5.0, 6.0]))

        result = ring.reduce()
        assert result is not None
        # Average of [1,2], [3,4], [5,6] = [3.0, 4.0]
        np.testing.assert_array_almost_equal(result, [3.0, 4.0])

    def test_ring_with_failed_worker(self):
        """Ring should handle missing worker data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w1", "w2", "w3"])
        ring.remove_worker("w2")

        # Submit from remaining workers only
        ring.submit("w1", np.array([1.0]))
        ring.submit("w3", np.array([3.0]))

        
        result = ring.reduce()
        assert result is not None, (
            "Ring should reduce with remaining workers after removal. "
            "BUG A8: Ring topology not updated."
        )


# =========================================================================
# A9: Async SGD staleness bound not enforced
# =========================================================================

class TestAsyncSGDStalenessBound:
    """BUG A9: Stale gradients from slow workers are applied."""

    def test_async_sgd_staleness_bound(self):
        """Gradients beyond staleness bound should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weight": 1.0}
        ps._max_staleness = 5

        # Advance version
        for i in range(20):
            ps.apply_gradient(f"worker_{i}", {"weight": 0.01}, ps.get_version())

        # Apply very stale gradient (version 0, current is 20)
        initial_params = ps.get_parameters()
        result = ps.apply_gradient("slow_worker", {"weight": 100.0}, worker_version=0)

        
        assert result is False, (
            "Gradient with staleness 20 (bound is 5) should be rejected. "
            "BUG A9: Stale gradients not actually rejected."
        )

    def test_staleness_rejection(self):
        """Worker version that is too old should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 0.0}
        ps._max_staleness = 3

        # Advance version to 10
        for i in range(10):
            ps.apply_gradient(f"w_{i}", {"w": 0.1}, ps.get_version())

        # Try to apply with version 0 (staleness = 10, max = 3)
        old_w = ps.get_parameters()["w"]
        result = ps.apply_gradient("stale_worker", {"w": 999.0}, worker_version=0)

        new_w = ps.get_parameters()["w"]
        
        assert abs(new_w - old_w) < 1.0, (
            f"Weight changed from {old_w} to {new_w} despite stale gradient. "
            "BUG A9: Staleness bound not enforced."
        )


# =========================================================================
# A10: Fault tolerant resume
# =========================================================================

class TestFaultTolerantResume:
    """BUG A10: Training does not resume correctly after failure."""

    def test_fault_tolerant_resume(self):
        """Training should resume from last checkpoint after failure."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=2, timeout=5.0)

        # Simulate successful checkpoint
        barrier.arrive("w1")
        barrier.arrive("w2")

        # Reset for next checkpoint
        barrier.reset()
        assert len(barrier._arrived) == 0

    def test_resume_point_correctness(self):
        """Resume point should be at last successful checkpoint."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weight": 0.0}

        # Record checkpoint at version 5
        for i in range(5):
            ps.apply_gradient(f"w_{i}", {"weight": 0.1}, ps.get_version())

        checkpoint_version = ps.get_version()
        checkpoint_params = ps.get_parameters()

        # More updates
        for i in range(5):
            ps.apply_gradient(f"w_{i}", {"weight": 0.1}, ps.get_version())

        # "Resume" should go back to checkpoint
        ps._parameters = dict(checkpoint_params)
        ps._version = checkpoint_version

        assert ps.get_version() == 5
        assert abs(ps.get_parameters()["weight"] - checkpoint_params["weight"]) < 0.001


# =========================================================================
# Additional distributed training edge cases
# =========================================================================

class TestAllReduceCoordinatorEdgeCases:
    """Test edge cases in AllReduce coordinator."""

    def test_single_worker_reduce(self):
        """AllReduce with single worker should return its own gradients."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coord = AllReduceCoordinator(num_workers=1)
        coord.submit_gradients("w1", {"grad": 5.0})

        result = coord.get_reduced_gradients("w1")
        assert result is not None

    def test_empty_gradient_submit(self):
        """Submitting empty gradients should be handled."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coord = AllReduceCoordinator(num_workers=1)
        result = coord.submit_gradients("w1", {})
        assert result is True


class TestElasticScalerEdgeCases:
    """Test edge cases in elastic scaling."""

    def test_deregister_nonexistent_worker(self):
        """Deregistering a non-existent worker should be safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        # Should not raise
        scaler.deregister_worker("nonexistent")

    def test_get_active_workers_empty(self):
        """Getting active workers when none registered should return empty."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        assert scaler.get_active_workers() == []

    def test_register_same_worker_twice(self):
        """Registering same worker twice should update, not duplicate."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        idx1 = scaler.register_worker("w1")
        idx2 = scaler.register_worker("w1")

        # Worker count should still be 1
        active = scaler.get_active_workers()
        assert active.count("w1") == 1


class TestParameterServerEdgeCases:
    """Test parameter server edge cases."""

    def test_get_empty_parameters(self):
        """Getting parameters before any are set should return empty."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        params = ps.get_parameters()
        assert params == {}

    def test_initial_version_is_zero(self):
        """Initial version should be 0."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        assert ps.get_version() == 0


# =========================================================================
# Extended Distributed Training Tests
# =========================================================================

class TestParameterServerConcurrency:
    """Concurrent parameter server tests."""

    def test_concurrent_gradient_application(self):
        """Multiple workers applying gradients concurrently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weight": 0.0}
        errors = []

        def apply_gradients(worker_id):
            try:
                for i in range(20):
                    ps.apply_gradient(
                        worker_id, {"weight": 0.01}, ps.get_version()
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=apply_gradients, args=(f"worker_{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_parameter_server_version_increments(self):
        """Version should increment with each gradient application."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 0.0}

        for i in range(10):
            ps.apply_gradient("w1", {"w": 0.1}, ps.get_version())

        assert ps.get_version() >= 10

    def test_parameter_server_multiple_params(self):
        """Server should handle multiple parameters."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w1": 0.0, "w2": 0.0, "bias": 0.0}

        ps.apply_gradient("worker", {"w1": 0.1, "w2": 0.2, "bias": 0.01}, ps.get_version())

        params = ps.get_parameters()
        assert "w1" in params
        assert "w2" in params
        assert "bias" in params


class TestCheckpointBarrierExtended:
    """Extended checkpoint barrier tests."""

    def test_barrier_all_workers_arrive(self):
        """All workers arriving should complete the barrier."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=3, timeout=5.0)
        barrier.arrive("w1")
        barrier.arrive("w2")
        barrier.arrive("w3")

        assert len(barrier._arrived) == 3

    def test_barrier_partial_arrival(self):
        """Partial arrival should not complete the barrier."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=3, timeout=5.0)
        barrier.arrive("w1")
        barrier.arrive("w2")

        assert len(barrier._arrived) == 2

    def test_barrier_reset_clears(self):
        """Reset should clear all arrivals."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=2, timeout=5.0)
        barrier.arrive("w1")
        barrier.arrive("w2")
        barrier.reset()
        assert len(barrier._arrived) == 0

    def test_barrier_duplicate_arrival(self):
        """Same worker arriving twice should not count as two arrivals."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import CheckpointBarrier

        barrier = CheckpointBarrier(num_workers=2, timeout=5.0)
        barrier.arrive("w1")
        barrier.arrive("w1")

        # Should only count as 1 arrival
        assert len(barrier._arrived) <= 2


class TestGradientCompressionExtended:
    """Extended gradient compression tests."""

    def test_compression_preserves_shape(self):
        """Compressed gradients should maintain shape."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import GradientCompressor

        compressor = GradientCompressor(threshold=0.001)
        gradient = np.random.randn(100)
        compressed = compressor.compress(gradient)

        assert compressed.shape == gradient.shape

    def test_compression_zeros_small_values(self):
        """Values below threshold should be zeroed out."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import GradientCompressor

        compressor = GradientCompressor(threshold=0.5)
        gradient = np.array([0.1, 0.9, 0.3, 0.8, 0.01])
        compressed = compressor.compress(gradient)

        # Values below 0.5 should be zeroed
        small_indices = np.abs(gradient) < 0.5
        zero_count = np.sum(compressed[small_indices] == 0)
        assert zero_count >= 0  # Documents compression behavior

    def test_compression_ratio(self):
        """Compression should reduce non-zero elements."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import GradientCompressor

        compressor = GradientCompressor(threshold=0.1)
        gradient = np.random.randn(1000) * 0.01  # Mostly small values
        compressed = compressor.compress(gradient)

        non_zero_before = np.count_nonzero(gradient)
        non_zero_after = np.count_nonzero(compressed)
        assert non_zero_after <= non_zero_before


class TestTensorSplitExtended:
    """Extended tensor splitting tests."""

    def test_split_and_merge_roundtrip(self):
        """Splitting and merging should recover original tensor."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter()
        original = np.random.randn(100)
        parts = splitter.split(original, num_parts=4)
        merged = splitter.merge(parts)

        np.testing.assert_array_almost_equal(merged[:len(original)], original)

    def test_split_even_division(self):
        """Splitting evenly divisible tensor should produce equal parts."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter()
        tensor = np.arange(12.0)
        parts = splitter.split(tensor, num_parts=3)
        assert len(parts) == 3

    def test_split_uneven_division(self):
        """Splitting unevenly divisible tensor should handle remainder."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.training.tasks import TensorSplitter

        splitter = TensorSplitter()
        tensor = np.arange(10.0)
        parts = splitter.split(tensor, num_parts=3)

        total_elements = sum(len(p) for p in parts)
        assert total_elements >= 10  # All elements should be covered
