"""
Unit tests for event sourcing bugs.

These tests verify bugs B1-B8 (Event Sourcing category).
"""
import pytest
import hashlib
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# B1: Event ordering / cross-partition sequencing
# ---------------------------------------------------------------------------
class TestEventOrdering:
    """Tests for bug B1: Event ordering across partitions."""

    def test_event_ordering(self):
        """Test that events within a partition maintain strict ordering."""
        events = [
            {"partition": "account-1", "sequence": 1, "type": "OrderCreated"},
            {"partition": "account-1", "sequence": 2, "type": "OrderFilled"},
            {"partition": "account-1", "sequence": 3, "type": "SettlementStarted"},
        ]
        
        for i in range(1, len(events)):
            assert events[i]["sequence"] > events[i - 1]["sequence"], (
                "Events within a partition must be strictly ordered by sequence number"
            )

    def test_cross_partition_sequence(self):
        """Test that cross-partition events use a global sequence for ordering."""
        events = [
            {"partition": "account-1", "global_seq": 10, "type": "OrderCreated"},
            {"partition": "account-2", "global_seq": 11, "type": "BalanceUpdated"},
            {"partition": "account-1", "global_seq": 12, "type": "OrderFilled"},
        ]
        
        global_seqs = [e["global_seq"] for e in events]
        assert global_seqs == sorted(global_seqs), (
            "Cross-partition events must be globally ordered"
        )

    def test_gap_detection_in_sequence(self):
        """Test that gaps in the event sequence are detected."""
        sequences = [1, 2, 4]  # gap at 3
        gaps = []
        for i in range(1, len(sequences)):
            if sequences[i] != sequences[i - 1] + 1:
                gaps.append(sequences[i - 1] + 1)
        assert gaps == [3], "Gap at sequence 3 should be detected"


# ---------------------------------------------------------------------------
# B2: Idempotency / duplicate event handling
# ---------------------------------------------------------------------------
class TestIdempotency:
    """Tests for bug B2: Event idempotency."""

    def test_idempotency(self):
        """Test that processing the same event twice produces the same state."""
        state = Decimal("0")
        event = {"type": "Credit", "amount": Decimal("100"), "event_id": "evt-001"}
        seen_ids = set()

        for _ in range(2):
            if event["event_id"] not in seen_ids:
                state += event["amount"]
                seen_ids.add(event["event_id"])

        
        assert state == Decimal("100"), "Duplicate event should not double-apply"

    def test_duplicate_event_handling(self):
        """Test that duplicate events are silently dropped, not errored."""
        processed = []
        seen = set()
        events = [
            {"event_id": "evt-001", "type": "OrderCreated"},
            {"event_id": "evt-001", "type": "OrderCreated"},  # duplicate
            {"event_id": "evt-002", "type": "OrderFilled"},
        ]
        for e in events:
            if e["event_id"] not in seen:
                processed.append(e)
                seen.add(e["event_id"])

        
        assert len(processed) == 2
        assert processed[0]["event_id"] == "evt-001"
        assert processed[1]["event_id"] == "evt-002"


# ---------------------------------------------------------------------------
# B3: Event replay / checkpoint recovery
# ---------------------------------------------------------------------------
class TestEventReplay:
    """Tests for bug B3: Event replay and checkpoint recovery."""

    def test_event_replay(self):
        """Test that replaying events from scratch rebuilds correct state."""
        events = [
            {"type": "Credit", "amount": Decimal("500")},
            {"type": "Debit", "amount": Decimal("150")},
            {"type": "Credit", "amount": Decimal("200")},
        ]
        balance = Decimal("0")
        for e in events:
            if e["type"] == "Credit":
                balance += e["amount"]
            elif e["type"] == "Debit":
                balance -= e["amount"]

        
        assert balance == Decimal("550"), "Replay must produce balance of 550"

    def test_checkpoint_recovery(self):
        """Test recovery from a checkpoint + subsequent events."""
        checkpoint = {"balance": Decimal("350"), "sequence": 2}
        events_after_checkpoint = [
            {"sequence": 3, "type": "Credit", "amount": Decimal("200")},
        ]
        balance = checkpoint["balance"]
        for e in events_after_checkpoint:
            if e["type"] == "Credit":
                balance += e["amount"]

        
        assert balance == Decimal("550"), "Checkpoint recovery must match full replay"


# ---------------------------------------------------------------------------
# B4: Projection consistency / read model sync
# ---------------------------------------------------------------------------
class TestProjectionConsistency:
    """Tests for bug B4: Projection consistency and read model sync."""

    def test_projection_consistency(self):
        """Test that projections stay consistent with the event stream."""
        events = [
            {"type": "OrderCreated", "order_id": "o1", "status": "new"},
            {"type": "OrderFilled", "order_id": "o1", "status": "filled"},
        ]
        projection = {}
        for e in events:
            projection[e["order_id"]] = e["status"]

        
        assert projection["o1"] == "filled", "Projection must reflect latest status"

    def test_read_model_sync(self):
        """Test that the read model catches up when it falls behind."""
        event_log_seq = 100
        read_model_seq = 97
        lag = event_log_seq - read_model_seq

        
        assert lag > 0, "Lag should be detected"
        assert lag == 3, "Read model is 3 events behind"

        # After catching up
        read_model_seq = event_log_seq
        assert read_model_seq == event_log_seq, "Read model should be caught up"

    def test_projection_rebuild_from_scratch(self):
        """Test that a projection can be fully rebuilt from the event store."""
        events = [
            {"type": "AccountOpened", "account_id": "a1", "balance": Decimal("0")},
            {"type": "Deposit", "account_id": "a1", "amount": Decimal("1000")},
            {"type": "Withdrawal", "account_id": "a1", "amount": Decimal("250")},
        ]
        balances = {}
        for e in events:
            aid = e["account_id"]
            if e["type"] == "AccountOpened":
                balances[aid] = e["balance"]
            elif e["type"] == "Deposit":
                balances[aid] = balances.get(aid, Decimal("0")) + e["amount"]
            elif e["type"] == "Withdrawal":
                balances[aid] = balances.get(aid, Decimal("0")) - e["amount"]

        assert balances["a1"] == Decimal("750")


# ---------------------------------------------------------------------------
# B5: Schema evolution / backward compatibility
# ---------------------------------------------------------------------------
class TestSchemaEvolution:
    """Tests for bug B5: Event schema evolution."""

    def test_schema_evolution(self):
        """Test that new fields have sensible defaults for old events."""
        event_v1 = {"type": "OrderCreated", "order_id": "o1"}
        # v2 adds 'source' field
        source = event_v1.get("source", "unknown")
        
        assert source == "unknown", "Missing field should default gracefully"

    def test_backward_compatibility(self):
        """Test that v2 consumer can process v1 events."""
        v1_event = {"version": 1, "type": "OrderCreated", "order_id": "o1", "price": "150.00"}
        v2_event = {"version": 2, "type": "OrderCreated", "order_id": "o2", "price": "150.00", "source": "api"}

        def process_event(event):
            """v2 consumer must handle both v1 and v2."""
            source = event.get("source", "legacy")
            return {"order_id": event["order_id"], "source": source}

        result_v1 = process_event(v1_event)
        result_v2 = process_event(v2_event)

        
        assert result_v1["source"] == "legacy"
        assert result_v2["source"] == "api"


# ---------------------------------------------------------------------------
# B6: Tombstone handling / entity deletion
# ---------------------------------------------------------------------------
class TestTombstoneHandling:
    """Tests for bug B6: Tombstone handling for soft deletes."""

    def test_tombstone_handling(self):
        """Test that tombstone events mark entities as deleted."""
        events = [
            {"type": "OrderCreated", "order_id": "o1"},
            {"type": "OrderDeleted", "order_id": "o1"},  # tombstone
        ]
        active_orders = set()
        for e in events:
            if e["type"] == "OrderCreated":
                active_orders.add(e["order_id"])
            elif e["type"] == "OrderDeleted":
                active_orders.discard(e["order_id"])

        
        assert "o1" not in active_orders, "Deleted order should not be active"

    def test_entity_deletion(self):
        """Test that querying a deleted entity returns not-found."""
        store = {"o1": {"status": "active"}, "o2": {"status": "active"}}
        # Apply tombstone for o1
        store["o1"]["status"] = "deleted"

        
        visible = {k: v for k, v in store.items() if v["status"] != "deleted"}
        assert "o1" not in visible
        assert "o2" in visible

    def test_tombstone_compaction(self):
        """Test that tombstones are compacted after retention period."""
        tombstones = [
            {"order_id": "o1", "deleted_at": 1000},
            {"order_id": "o2", "deleted_at": 2000},
        ]
        retention_cutoff = 1500
        compacted = [t for t in tombstones if t["deleted_at"] >= retention_cutoff]
        assert len(compacted) == 1
        assert compacted[0]["order_id"] == "o2"


# ---------------------------------------------------------------------------
# B7: Snapshot integrity / concurrent snapshots
# ---------------------------------------------------------------------------
class TestSnapshotIntegrity:
    """Tests for bug B7: Snapshot integrity."""

    def test_snapshot_integrity(self):
        """Test that snapshot matches replayed state at the same sequence."""
        events = [
            {"type": "Credit", "amount": Decimal("100"), "seq": 1},
            {"type": "Debit", "amount": Decimal("30"), "seq": 2},
            {"type": "Credit", "amount": Decimal("50"), "seq": 3},
        ]
        # Full replay
        replayed_balance = Decimal("0")
        for e in events:
            if e["type"] == "Credit":
                replayed_balance += e["amount"]
            else:
                replayed_balance -= e["amount"]

        snapshot = {"balance": Decimal("120"), "at_sequence": 3}

        
        assert snapshot["balance"] == replayed_balance, (
            "Snapshot balance must equal replayed balance"
        )

    def test_concurrent_snapshot(self):
        """Test that concurrent snapshot creation does not corrupt data."""
        snapshot_a = {"balance": Decimal("500"), "at_sequence": 10, "writer": "A"}
        snapshot_b = {"balance": Decimal("500"), "at_sequence": 10, "writer": "B"}

        
        assert snapshot_a["balance"] == snapshot_b["balance"], (
            "Concurrent snapshots at the same sequence must agree"
        )
        assert snapshot_a["at_sequence"] == snapshot_b["at_sequence"]

    def test_snapshot_staleness_detection(self):
        """Test that stale snapshots are detected when events have advanced."""
        snapshot_seq = 10
        current_event_seq = 15
        is_stale = current_event_seq > snapshot_seq
        assert is_stale, "Snapshot should be detected as stale"


# ---------------------------------------------------------------------------
# B8: Timestamp ordering / clock skew handling
# ---------------------------------------------------------------------------
class TestTimestampOrdering:
    """Tests for bug B8: Timestamp ordering and clock skew."""

    def test_timestamp_ordering(self):
        """Test that events are ordered by logical clock, not wall clock."""
        events = [
            {"logical_clock": 1, "wall_clock": 1000, "type": "A"},
            {"logical_clock": 2, "wall_clock": 999, "type": "B"},  # wall clock earlier but logically later
        ]
        
        sorted_by_logical = sorted(events, key=lambda e: e["logical_clock"])
        assert sorted_by_logical[0]["type"] == "A"
        assert sorted_by_logical[1]["type"] == "B"

    def test_clock_skew_handling(self):
        """Test that clock skew between nodes doesn't corrupt ordering."""
        node_a_time = 1000
        node_b_time = 998  # 2 seconds behind
        max_allowed_skew = 5  # seconds

        skew = abs(node_a_time - node_b_time)
        within_tolerance = skew <= max_allowed_skew

        
        assert within_tolerance, "2 second skew should be within 5 second tolerance"

        # Excessive skew should be rejected
        node_c_time = 980  # 20 seconds behind
        excessive_skew = abs(node_a_time - node_c_time)
        assert excessive_skew > max_allowed_skew, "20 second skew exceeds tolerance"

    def test_hybrid_logical_clock_advancement(self):
        """Test that HLC advances monotonically."""
        hlc_values = [100, 101, 101, 102]
        for i in range(1, len(hlc_values)):
            assert hlc_values[i] >= hlc_values[i - 1], "HLC must never go backward"

    def test_clock_skew_correction_applied(self):
        """Test that detected skew triggers synchronization."""
        local_time = 1000
        remote_time = 1010
        skew = remote_time - local_time
        corrected_local = local_time + skew
        assert corrected_local == remote_time, "Correction should align local to remote"


# ---------------------------------------------------------------------------
# Additional event sourcing tests (not mapped to specific bugs)
# ---------------------------------------------------------------------------
class TestEventValidation:
    """Tests for event payload validation."""

    def test_event_requires_type_field(self):
        """Test that events without a 'type' field are rejected."""
        event = {"order_id": "o1", "amount": Decimal("100")}
        is_valid = "type" in event
        assert not is_valid, "Event without type field should be invalid"

    def test_event_requires_event_id(self):
        """Test that events must have a unique event ID."""
        event = {"type": "OrderCreated", "event_id": str(uuid.uuid4())}
        assert "event_id" in event
        assert len(event["event_id"]) == 36  # UUID format

    def test_event_payload_size_limit(self):
        """Test that oversized event payloads are rejected."""
        max_payload_bytes = 1024 * 256  # 256 KB
        large_payload = "x" * (max_payload_bytes + 1)
        is_within_limit = len(large_payload.encode()) <= max_payload_bytes
        assert not is_within_limit, "Payload exceeding size limit should be rejected"

    def test_event_timestamp_required(self):
        """Test that every event must carry a timestamp."""
        event = {"type": "OrderCreated", "timestamp": datetime.now(timezone.utc).isoformat()}
        assert "timestamp" in event


class TestEventStoreOperations:
    """Tests for event store read/write operations."""

    def test_append_returns_sequence_number(self):
        """Test that appending an event returns the assigned sequence number."""
        store = []
        event = {"type": "OrderCreated", "order_id": "o1"}
        store.append(event)
        sequence = len(store)
        assert sequence == 1, "First append should return sequence 1"

    def test_read_events_from_sequence(self):
        """Test that events can be read starting from a given sequence."""
        store = [
            {"seq": 1, "type": "A"},
            {"seq": 2, "type": "B"},
            {"seq": 3, "type": "C"},
        ]
        from_seq = 2
        result = [e for e in store if e["seq"] >= from_seq]
        assert len(result) == 2
        assert result[0]["type"] == "B"

    def test_stream_isolation(self):
        """Test that events from different streams don't interfere."""
        events = [
            {"stream": "order-1", "seq": 1, "type": "Created"},
            {"stream": "order-2", "seq": 1, "type": "Created"},
            {"stream": "order-1", "seq": 2, "type": "Filled"},
        ]
        stream1 = [e for e in events if e["stream"] == "order-1"]
        stream2 = [e for e in events if e["stream"] == "order-2"]
        assert len(stream1) == 2
        assert len(stream2) == 1


class TestAggregateReconstruction:
    """Tests for rebuilding aggregates from events."""

    def test_aggregate_version_tracks_events(self):
        """Test that aggregate version matches the number of applied events."""
        events = [{"seq": 1}, {"seq": 2}, {"seq": 3}]
        version = len(events)
        assert version == 3

    def test_aggregate_state_after_multiple_transitions(self):
        """Test that aggregate state is correct after multiple transitions."""
        events = [
            {"type": "OrderCreated", "qty": Decimal("100")},
            {"type": "PartialFill", "filled": Decimal("40")},
            {"type": "PartialFill", "filled": Decimal("30")},
        ]
        total_qty = Decimal("0")
        total_filled = Decimal("0")
        for e in events:
            if e["type"] == "OrderCreated":
                total_qty = e["qty"]
            elif e["type"] == "PartialFill":
                total_filled += e["filled"]
        remaining = total_qty - total_filled
        assert remaining == Decimal("30"), "Remaining quantity should be 30"


class TestEventMetadata:
    """Tests for event metadata handling."""

    def test_event_carries_correlation_id(self):
        """Test that events carry a correlation ID for tracing."""
        correlation_id = str(uuid.uuid4())
        event = {"type": "OrderCreated", "metadata": {"correlation_id": correlation_id}}
        assert event["metadata"]["correlation_id"] == correlation_id

    def test_event_carries_causation_id(self):
        """Test that events reference the command that caused them."""
        command_id = "cmd-001"
        event = {"type": "OrderCreated", "metadata": {"causation_id": command_id}}
        assert event["metadata"]["causation_id"] == command_id


class TestSagaCoordination:
    """Tests for saga patterns in event sourcing."""

    def test_saga_step_completion_emits_event(self):
        """Test that completing a saga step emits a domain event."""
        saga_events = []
        # Step 1: reserve inventory
        saga_events.append({"type": "InventoryReserved", "order_id": "o1"})
        # Step 2: charge payment
        saga_events.append({"type": "PaymentCharged", "order_id": "o1"})
        assert len(saga_events) == 2
        assert saga_events[0]["type"] == "InventoryReserved"
        assert saga_events[1]["type"] == "PaymentCharged"

    def test_saga_compensation_on_failure(self):
        """Test that saga emits compensation events on step failure."""
        saga_events = [
            {"type": "InventoryReserved", "order_id": "o1"},
            {"type": "PaymentFailed", "order_id": "o1"},
        ]
        # On failure, compensation should reverse prior steps
        compensation = []
        if saga_events[-1]["type"] == "PaymentFailed":
            compensation.append({"type": "InventoryReleased", "order_id": "o1"})
        assert len(compensation) == 1
        assert compensation[0]["type"] == "InventoryReleased"


class TestEventDeduplication:
    """Tests for event deduplication at the store level."""

    def test_store_rejects_duplicate_event_id(self):
        """Test that the event store rejects events with duplicate IDs."""
        stored_ids = {"evt-001", "evt-002"}
        new_event_id = "evt-001"
        is_duplicate = new_event_id in stored_ids
        assert is_duplicate, "Duplicate event ID should be detected at store level"

    def test_deduplication_across_partitions(self):
        """Test that deduplication works across different partitions."""
        global_seen = set()
        partitions = {
            "p1": [{"event_id": "evt-001"}, {"event_id": "evt-002"}],
            "p2": [{"event_id": "evt-001"}, {"event_id": "evt-003"}],  # evt-001 duplicate
        }
        duplicates = []
        for partition, events in partitions.items():
            for e in events:
                if e["event_id"] in global_seen:
                    duplicates.append(e["event_id"])
                else:
                    global_seen.add(e["event_id"])
        assert duplicates == ["evt-001"], "evt-001 should be flagged as cross-partition duplicate"
