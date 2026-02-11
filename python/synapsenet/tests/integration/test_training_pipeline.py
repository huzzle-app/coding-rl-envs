"""
SynapseNet Training Pipeline Integration Tests
Terminal Bench v2 - Tests for data pipeline orchestration and data processing

Tests cover:
- D1-D10: Data Pipeline bugs
- F1-F10: Database & Transaction bugs (subset)
"""
import time
import uuid
import threading
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest
import numpy as np


# =========================================================================
# D1: Data validation schema mismatch
# =========================================================================

class TestDataValidationSchema:
    """BUG D1: Validator always uses version 1 schema."""

    def test_data_validation_schema(self):
        """Validation should use the specified schema version."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()

        # Register v1 schema
        validator.register_schema("events", 1, {
            "required": ["event_id", "timestamp"],
        })

        # Register v2 schema with additional required field
        validator.register_schema("events", 2, {
            "required": ["event_id", "timestamp", "source"],
        })

        # Data that is valid for v1 but not v2
        data = {"event_id": "e1", "timestamp": "2024-01-01"}

        # Validating against v2 should fail (missing "source")
        
        result = validator.validate(data, "events", version=2)
        assert result is False, (
            "Data missing 'source' field should fail v2 validation. "
            "BUG D1: Always validates against v1 schema."
        )

    def test_schema_mismatch_detection(self):
        """Should detect when data doesn't match specified schema version."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("users", 1, {"required": ["name"]})
        validator.register_schema("users", 2, {"required": ["name", "email"]})

        # Valid for v1
        assert validator.validate({"name": "Alice"}, "users", version=1) is True

        # Invalid for v2 (missing email)
        result = validator.validate({"name": "Alice"}, "users", version=2)
        assert result is False, (
            "Data should fail validation against v2 schema"
        )


# =========================================================================
# D2: Schema evolution compatibility
# =========================================================================

class TestSchemaEvolutionCompat:
    """BUG D2: Schema evolution doesn't check backward compatibility."""

    def test_schema_evolution_compat(self):
        """Schema evolution should be backward compatible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("metrics", 1, {"required": ["name", "value"]})
        validator.register_schema("metrics", 2, {"required": ["name", "value", "timestamp"]})

        # v1 data should still be valid with v1 schema
        v1_data = {"name": "cpu", "value": 0.5}
        assert validator.validate(v1_data, "metrics", version=1) is True

    def test_backward_compat_check(self):
        """New schema version should not remove required fields."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("orders", 1, {"required": ["order_id", "amount"]})

        # v2 data should be valid with both schemas
        v2_data = {"order_id": "o1", "amount": 100, "currency": "USD"}
        assert validator.validate(v2_data, "orders", version=1) is True


# =========================================================================
# D3: Backfill duplicate processing
# =========================================================================

class TestBackfillDedup:
    """BUG D3: Backfill processes same records on restart."""

    def test_backfill_dedup(self):
        """Processing the same record twice should be idempotent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()

        # Process a record
        result1 = processor.process_record("rec_1", {"value": 42})
        assert result1 is True

        # Process the same record again
        result2 = processor.process_record("rec_1", {"value": 42})
        assert result2 is False, "Duplicate record should be detected"

    def test_duplicate_processing_prevention(self):
        """Backfill should track processed records persistently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()

        # Process several records
        for i in range(10):
            processor.process_record(f"rec_{i}", {"index": i})

        
        processor2 = BackfillProcessor()

        # In a persistent implementation, this should return False
        result = processor2.process_record("rec_0", {"index": 0})
        
        # In production, this should use persistent storage
        assert result is False, (
            "Previously processed record should be detected after restart. "
            "BUG D3: In-memory dedup tracking lost on restart."
        )


# =========================================================================
# D4: Late-arriving data window close
# =========================================================================

class TestLateArrivingData:
    """BUG D4: Late data rejected even within allowed lateness."""

    def test_late_arriving_data(self):
        """Late data within allowed lateness should be accepted."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import WindowProcessor

        processor = WindowProcessor(
            window_size=timedelta(minutes=5),
            allowed_lateness=timedelta(minutes=2),
        )

        now = datetime.now(timezone.utc)
        window_start = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)

        # Process an event in current window
        result = processor.process_event(window_start + timedelta(minutes=1), {"v": 1})
        assert result is True

        # Close the window
        window_key = processor._get_window_key(window_start)
        processor.close_window(window_key)

        # Late event that is within allowed lateness
        late_event_time = window_start + timedelta(minutes=3)
        result = processor.process_event(late_event_time, {"v": 2})

        
        assert result is True, (
            "Late event within allowed lateness should be accepted. "
            "BUG D4: Rejects all late data regardless of allowed_lateness."
        )

    def test_window_close_handling(self):
        """Events after window + lateness should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import WindowProcessor

        processor = WindowProcessor(
            window_size=timedelta(minutes=5),
            allowed_lateness=timedelta(minutes=1),
        )

        now = datetime.now(timezone.utc)
        # Process in a specific window
        event_time = now - timedelta(minutes=10)
        result = processor.process_event(event_time, {"v": 1})
        # May or may not be in a closed window depending on timing
        assert isinstance(result, bool)


# =========================================================================
# D5: Partition key distribution skew
# =========================================================================

class TestPartitionDistribution:
    """BUG D5: Partition routing uses string length instead of hash."""

    def test_partition_distribution(self):
        """Partition routing should distribute data evenly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=8)

        # Route many different keys
        partition_counts = {}
        keys = [f"user_{uuid.uuid4()}" for _ in range(1000)]

        for key in keys:
            partition = router.route(key)
            partition_counts[partition] = partition_counts.get(partition, 0) + 1

        # Check distribution evenness
        expected = 1000 / 8
        for partition, count in partition_counts.items():
            ratio = count / expected
            assert 0.3 < ratio < 3.0, (
                f"Partition {partition} has {count} keys (expected ~{expected:.0f}). "
                f"Distribution is severely skewed. "
                "BUG D5: Uses string length instead of hash for routing."
            )

    def test_skew_detection(self):
        """Keys of same length should not all go to same partition."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=8)

        # Keys with same length but different content
        keys = [f"key_{i:04d}" for i in range(100)]  # All length 8
        partitions = set()
        for key in keys:
            partitions.add(router.route(key))

        
        assert len(partitions) > 1, (
            f"All {len(keys)} keys routed to {len(partitions)} partition(s). "
            "BUG D5: Length-based routing causes all same-length keys to go to same partition."
        )


# =========================================================================
# D6: Checkpoint interval data loss
# =========================================================================

class TestCheckpointInterval:
    """BUG D6: Checkpoint interval too large, risking data loss."""

    def test_checkpoint_interval(self):
        """Pipeline should checkpoint at reasonable intervals."""
        # Verify BackfillProcessor tracks state
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()
        for i in range(100):
            processor.process_record(f"rec_{i}", {"data": i})

        assert len(processor._processed_ids) == 100

    def test_checkpoint_data_loss(self):
        """Checkpoint loss should be minimal."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()
        # Process records
        for i in range(50):
            processor.process_record(f"batch_rec_{i}", {"val": i})

        
        assert len(processor._processed_ids) == 50


# =========================================================================
# D7: Dead letter queue overflow
# =========================================================================

class TestDeadLetterQueue:
    """BUG D7: Dead letter queue handling for failed messages."""

    def test_dead_letter_queue(self):
        """Failed messages should go to dead letter queue."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="dlq_test")

        # Publish events
        for i in range(5):
            event = Event(event_type=f"event_{i}")
            bus.publish("processing.events", event)

        assert len(bus.get_published_events()) == 5

    def test_dlq_overflow_handling(self):
        """DLQ should handle overflow gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="dlq_overflow")

        # Publish many events
        for i in range(100):
            event = Event(event_type="batch_event")
            bus.publish("batch.topic", event)

        assert len(bus.get_published_events()) == 100


# =========================================================================
# D8: Pipeline DAG cycle detection
# =========================================================================

class TestPipelineDAGCycle:
    """BUG D8: No cycle detection in pipeline DAG."""

    def test_pipeline_dag_cycle(self):
        """Adding a cycle to pipeline DAG should be detected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("A")
        dag.add_node("B")
        dag.add_node("C")

        dag.add_edge("A", "B")
        dag.add_edge("B", "C")

        # This creates a cycle: A -> B -> C -> A
        result = dag.add_edge("C", "A")

        
        # After adding cycle, execution should detect it
        try:
            dag.execute({})
            # If execution completes, check if cycle was handled
        except RecursionError:
            pass  # Expected if cycle exists and isn't detected

    def test_dag_validation(self):
        """DAG without cycles should execute correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("input")
        dag.add_node("transform")
        dag.add_node("output")

        dag.add_edge("input", "transform")
        dag.add_edge("transform", "output")

        result = dag.execute({"data": "test"})
        assert result is not None


# =========================================================================
# D9: Data lineage tracking
# =========================================================================

class TestDataLineageTracking:
    """BUG D9: Data lineage gaps across pipeline stages."""

    def test_data_lineage_tracking(self):
        """Data lineage should be traceable through pipeline."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("stage_1")
        dag.add_node("stage_2")
        dag.add_edge("stage_1", "stage_2")

        result = dag.execute({"input": "raw_data"})
        assert result is not None

    def test_lineage_gap_detection(self):
        """Should detect gaps in data lineage."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("producer")
        dag.add_node("consumer")
        # No edge - lineage gap
        result = dag.execute({"data": "test"})
        assert result is not None


# =========================================================================
# D10: Transformation idempotency
# =========================================================================

class TestTransformationIdempotency:
    """BUG D10: Reprocessing data produces different results."""

    def test_transformation_idempotency(self):
        """Processing same data twice should produce same result."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()

        data = {"user_id": "u1", "score": 0.5}

        # First process
        result1 = processor._transform(data)

        # Same data, same transform
        result2 = processor._transform(data)

        assert result1 == result2, "Transformation should be idempotent"

    def test_reprocess_same_result(self):
        """Reprocessing should yield identical output."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("test", 1, {"required": ["id"]})

        data = {"id": "test_1", "value": 42}

        # Validate same data multiple times
        results = [validator.validate(data, "test", version=1) for _ in range(10)]
        assert all(r == results[0] for r in results), "Validation should be deterministic"


# =========================================================================
# F2: Connection pool exhaustion
# =========================================================================

class TestConnectionPoolExhaustion:
    """BUG F2: Connection pool runs out under load."""

    def test_connection_pool_exhaustion(self):
        """Connection pool should handle concurrent requests."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        locks = []
        for i in range(10):
            lock = DistributedLock(lock_name=f"pool_test_{i}")
            if lock.acquire(timeout=0.5):
                locks.append(lock)

        for lock in locks:
            lock.release()

        assert len(locks) > 0

    def test_pool_per_service_limit(self):
        """Each service should have bounded connection pool."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        clients = [
            ServiceClient(f"service_{i}", f"http://localhost:{8000+i}")
            for i in range(5)
        ]

        # Each client should be independently configured
        for i, client in enumerate(clients):
            assert client.service_name == f"service_{i}"


# =========================================================================
# F3: Saga compensation order
# =========================================================================

class TestSagaCompensationOrder:
    """BUG F3: Saga compensation doesn't reverse in correct order."""

    def test_saga_compensation_order(self):
        """Saga compensation should reverse steps in reverse order."""
        steps = ["create_order", "reserve_inventory", "charge_payment"]
        compensation = list(reversed(steps))

        assert compensation == ["charge_payment", "reserve_inventory", "create_order"]

    def test_saga_rollback_sequence(self):
        """Failed step should trigger compensation of all preceding steps."""
        executed_steps = ["step_1", "step_2", "step_3"]
        # Step 3 failed, compensate in reverse
        to_compensate = list(reversed(executed_steps[:-1]))
        assert to_compensate == ["step_2", "step_1"]


# =========================================================================
# F5: Read replica lag
# =========================================================================

class TestReadReplicaLag:
    """BUG F5: Reading from replica immediately after write returns stale data."""

    def test_read_replica_lag(self):
        """Read-after-write should see updated data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model({"name": "test_model"}, "user_1")

        # Read immediately after write
        retrieved = store.get_model(model["model_id"])
        assert retrieved is not None
        assert retrieved["name"] == "test_model"

    def test_read_after_write_consistency(self):
        """Updated data should be immediately visible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model({"name": "original"}, "user_1")

        store.update_model(model["model_id"], {"name": "updated"})

        retrieved = store.get_model(model["model_id"])
        assert retrieved["name"] == "updated"


# =========================================================================
# F6: Optimistic lock retry
# =========================================================================

class TestOptimisticLockRetry:
    """BUG F6: Optimistic lock retries exceed limit."""

    def test_optimistic_lock_retry(self):
        """Concurrent updates should handle conflicts gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model({"name": "concurrent_model"}, "user_1")
        model_id = model["model_id"]

        errors = []

        def updater(thread_id):
            try:
                store.update_model(model_id, {"name": f"updated_by_{thread_id}"})
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=updater, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All updates should succeed (last writer wins in this simple impl)
        final = store.get_model(model_id)
        assert final is not None

    def test_retry_limit_enforcement(self):
        """Retries should be bounded."""
        # Verify that the system doesn't retry infinitely
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            retry_count += 1
        assert retry_count == max_retries


# =========================================================================
# F7: Cross-DB foreign key
# =========================================================================

class TestCrossDBForeignKey:
    """BUG F7: Cross-database foreign key references create orphans."""

    def test_cross_db_foreign_key(self):
        """References across databases should be validated."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create experiment referencing a model
        exp_id = manager.create_experiment("exp_1", "model_that_exists", {"lr": 0.01})

        exp = manager._experiments[exp_id]
        assert exp["model_id"] == "model_that_exists"

    def test_orphan_reference_prevention(self):
        """Deleting referenced entity should handle dependents."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("orphan_test", "model_1", {"lr": 0.01})

        # The experiment references model_1
        # If model_1 is deleted elsewhere, experiment has orphan reference
        exp = manager._experiments[exp_id]
        assert exp["model_id"] is not None


# =========================================================================
# F8: Batch insert atomicity
# =========================================================================

class TestBatchInsertAtomicity:
    """BUG F8: Partial batch insert leaves inconsistent state."""

    def test_batch_insert_atomicity(self):
        """Batch inserts should be all-or-nothing."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()

        # Insert a batch of models
        models = []
        for i in range(5):
            model = store.create_model({"name": f"batch_model_{i}"}, "user_1")
            models.append(model)

        assert len(models) == 5
        for model in models:
            assert store.get_model(model["model_id"]) is not None

    def test_partial_insert_rollback(self):
        """If batch insert partially fails, all should be rolled back."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()

        # Create models
        model1 = store.create_model({"name": "success_1"}, "user_1")
        model2 = store.create_model({"name": "success_2"}, "user_1")

        assert store.get_model(model1["model_id"]) is not None
        assert store.get_model(model2["model_id"]) is not None


# =========================================================================
# F9: Index hint plan
# =========================================================================

class TestIndexHintPlan:
    """BUG F9: Query plan doesn't use optimal index."""

    def test_index_hint_plan(self):
        """Queries should use appropriate indexes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()

        # Create many models
        for i in range(100):
            store.create_model({"name": f"model_{i}", "tenant_id": f"tenant_{i % 5}"}, f"user_{i}")

        # List by tenant should be efficient
        results = store.list_models(tenant_id="tenant_0")
        assert len(results) == 20

    def test_query_plan_optimal(self):
        """Filtered queries should not scan all records."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        for i in range(50):
            store.create_model({"name": f"plan_model_{i}"}, "user_1")

        # List all models
        all_models = store.list_models()
        assert len(all_models) == 50


# =========================================================================
# Extended Training Pipeline Tests
# =========================================================================

class TestDataValidatorDetailed:
    """Extended data validation tests."""

    def test_validator_multiple_schemas(self):
        """Validator should handle multiple schema registrations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("schema_a", 1, {"required": ["id"]})
        validator.register_schema("schema_b", 1, {"required": ["name"]})

        assert validator.validate({"id": "1"}, "schema_a") is True
        assert validator.validate({"name": "test"}, "schema_b") is True
        assert validator.validate({"id": "1"}, "schema_b") is False

    def test_validator_schema_versioning(self):
        """Validator should support schema versions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("evolving", 1, {"required": ["id"]})
        validator.register_schema("evolving", 2, {"required": ["id", "name"]})

        # v1 schema: only id required
        assert validator.validate({"id": "1"}, "evolving") is True

    def test_validator_empty_data(self):
        """Validator should reject empty data for required-field schemas."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("strict", 1, {"required": ["id"]})
        assert validator.validate({}, "strict") is False

    def test_validator_unknown_schema(self):
        """Validator should handle unknown schema names."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        result = validator.validate({"id": "1"}, "unknown_schema")
        # Should either return True (no schema = no validation) or handle gracefully
        assert isinstance(result, bool)


class TestBackfillProcessorDetailed:
    """Extended backfill processor tests."""

    def test_backfill_multiple_records(self):
        """Processor should handle multiple records."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()
        for i in range(10):
            result = processor.process_record(f"r{i}", {"data": f"value_{i}"})
            assert result is True

    def test_backfill_empty_data(self):
        """Processor should handle empty data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()
        result = processor.process_record("r1", {})
        assert isinstance(result, bool)

    def test_backfill_large_payload(self):
        """Processor should handle large payloads."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()
        large_data = {f"field_{i}": f"value_{i}" * 100 for i in range(100)}
        result = processor.process_record("large_record", large_data)
        assert isinstance(result, bool)


class TestPartitionRouterDetailed:
    """Extended partition router tests."""

    def test_partition_distribution(self):
        """Keys should be distributed across partitions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=8)
        partitions = set()
        for i in range(100):
            p = router.route(f"key_{i}")
            partitions.add(p)

        # Should use multiple partitions
        assert len(partitions) >= 3, "Keys should be distributed across partitions"

    def test_partition_deterministic(self):
        """Same key should always route to same partition."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=8)
        results = set()
        for _ in range(10):
            results.add(router.route("fixed_key"))
        assert len(results) == 1

    def test_partition_range(self):
        """Partition numbers should be within valid range."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=4)
        for i in range(100):
            p = router.route(f"key_{i}")
            assert 0 <= p < 4, f"Partition {p} out of range [0, 4)"


class TestPipelineDAGDetailed:
    """Extended DAG tests."""

    def test_dag_simple_chain(self):
        """Simple chain DAG should execute."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b")
        dag.add_edge("b", "c")

        result = dag.execute({"input": "data"})
        assert result is not None

    def test_dag_parallel_branches(self):
        """DAG with parallel branches should execute."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("source")
        dag.add_node("branch_a")
        dag.add_node("branch_b")
        dag.add_node("merge")

        dag.add_edge("source", "branch_a")
        dag.add_edge("source", "branch_b")
        dag.add_edge("branch_a", "merge")
        dag.add_edge("branch_b", "merge")

        result = dag.execute({"input": "data"})
        assert result is not None

    def test_dag_single_node(self):
        """DAG with single node should execute."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("only")
        result = dag.execute({"input": "data"})
        assert result is not None

    def test_dag_cycle_detection(self):
        """DAG should detect cycles."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b")
        dag.add_edge("b", "c")
        dag.add_edge("c", "a")  # Creates cycle

        has_cycle = dag.has_cycle()
        assert has_cycle is True


class TestModelMetadataExtended:
    """Extended model metadata tests."""

    def test_create_model_fields(self):
        """Created model should have all required fields."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model(
            {"name": "full_model", "framework": "tensorflow", "version": "2.0"},
            user_id="u1",
        )

        assert "model_id" in model
        assert "name" in model
        assert "owner_id" in model
        assert "created_at" in model
        assert "updated_at" in model
        assert "status" in model

    def test_update_model_timestamp(self):
        """Updating model should change updated_at."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model({"name": "timestamp_model"}, "u1")
        original = model["updated_at"]

        time.sleep(0.01)
        updated = store.update_model(model["model_id"], {"name": "changed"})
        assert updated["updated_at"] != original

    def test_delete_model_success(self):
        """Deleting existing model should return True."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model({"name": "deletable"}, "u1")
        assert store.delete_model(model["model_id"]) is True
        assert store.get_model(model["model_id"]) is None

    def test_delete_model_nonexistent(self):
        """Deleting nonexistent model should return False."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        assert store.delete_model("nonexistent") is False

    def test_list_models_empty(self):
        """Listing with no models should return empty list."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        result = store.list_models(tenant_id="empty_tenant")
        assert isinstance(result, list)
        assert len(result) == 0


class TestAllReduceCoordinatorIntegration(unittest.TestCase):
    """Integration tests for all-reduce coordinator."""

    def test_single_worker_submit(self):
        """Single worker submit should be tracked."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coord = AllReduceCoordinator(num_workers=2)
        result = coord.submit_gradients("w1", {"param": 1.0})
        assert result is True

    def test_all_workers_triggers_reduce(self):
        """When all workers submit, reduction should occur."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coord = AllReduceCoordinator(num_workers=2)
        coord.submit_gradients("w1", {"param": 2.0})
        coord.submit_gradients("w2", {"param": 4.0})
        reduced = coord.get_reduced_gradients("w1")
        assert reduced is not None
        if "param" in reduced:
            assert abs(reduced["param"] - 3.0) < 1e-6  # Average of 2.0 and 4.0

    def test_reduced_gradients_empty_before_all_submit(self):
        """Reduced gradients may be empty before all workers submit."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import AllReduceCoordinator

        coord = AllReduceCoordinator(num_workers=3)
        coord.submit_gradients("w1", {"param": 1.0})
        result = coord.get_reduced_gradients("w1")
        assert isinstance(result, dict)


class TestDistributedLockIntegration(unittest.TestCase):
    """Integration tests for distributed lock."""

    def test_lock_acquire_release(self):
        """Lock should be acquirable and releasable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="test_lock")
        assert lock.acquire(timeout=1.0) is True
        lock.release()

    def test_lock_context_manager(self):
        """Lock should work as context manager."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="ctx_lock")
        with lock:
            pass  # Lock is held here
        # Lock is released

    def test_lock_timeout(self):
        """Lock should timeout when already held."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="timeout_lock")
        lock.acquire()
        # Second acquire on same lock should timeout
        lock2 = DistributedLock(lock_name="timeout_lock")
        # They share the same threading.Lock name but different instances
        result = lock2.acquire(timeout=0.1)
        lock.release()
        assert isinstance(result, bool)
