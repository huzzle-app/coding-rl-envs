"""
Integration tests for event pipeline operations.

These tests cover Kafka-based event publishing, consumption,
dead letter queues, retry logic, schema validation, and related
event-driven architecture patterns. No bug-mapped tests in this file.
"""
import pytest
import threading
import time
import json
import hashlib
import random
from unittest.mock import MagicMock, patch
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from uuid import uuid4


class TestEventPublishing:
    """Tests for event publishing to Kafka topics."""

    def test_event_routed_to_correct_topic(self):
        """Test that events are routed to the correct Kafka topic."""
        topic_routing = {
            "order_created": "orders.events",
            "order_filled": "orders.events",
            "trade_executed": "trades.events",
            "user_registered": "users.events",
            "risk_alert": "risk.events",
        }

        event = {"type": "order_created", "payload": {"order_id": "o-1"}}
        target_topic = topic_routing.get(event["type"])

        assert target_topic == "orders.events", \
            "order_created should route to orders.events topic"

    def test_unknown_event_type_rejected(self):
        """Test that unknown event types are not silently dropped."""
        known_types = {"order_created", "trade_executed", "user_registered"}
        event = {"type": "unknown_event", "payload": {}}

        is_known = event["type"] in known_types
        assert not is_known, "Unknown event type should be rejected"

    def test_event_partition_selection_by_key(self):
        """Test that events are partitioned by their partition key."""
        num_partitions = 6

        def get_partition(key, num_parts):
            return hash(key) % num_parts

        # Same key always goes to same partition
        user_id = "user-123"
        p1 = get_partition(user_id, num_partitions)
        p2 = get_partition(user_id, num_partitions)
        assert p1 == p2, "Same key must always map to same partition"

        # Different keys may go to different partitions
        other_user = "user-456"
        p3 = get_partition(other_user, num_partitions)
        # (not guaranteed to be different, but the mechanism should be deterministic)
        assert isinstance(p3, int) and 0 <= p3 < num_partitions

    def test_event_includes_required_metadata(self):
        """Test that published events contain all required metadata fields."""
        required_fields = {"event_id", "type", "timestamp", "source", "payload"}

        event = {
            "event_id": str(uuid4()),
            "type": "order_created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "orders-service",
            "payload": {"order_id": "o-1"},
        }

        missing = required_fields - set(event.keys())
        assert len(missing) == 0, f"Event missing required fields: {missing}"


class TestEventConsumption:
    """Tests for event consumption patterns."""

    def test_consumer_group_assignment(self):
        """Test that partitions are assigned across consumer group members."""
        partitions = list(range(6))
        consumers = ["consumer-1", "consumer-2", "consumer-3"]

        # Round-robin assignment
        assignments = defaultdict(list)
        for i, partition in enumerate(partitions):
            consumer = consumers[i % len(consumers)]
            assignments[consumer].append(partition)

        # Each consumer should have 2 partitions
        for consumer in consumers:
            assert len(assignments[consumer]) == 2, \
                f"{consumer} should have 2 partitions"

        # All partitions should be assigned
        all_assigned = []
        for parts in assignments.values():
            all_assigned.extend(parts)
        assert sorted(all_assigned) == partitions, "All partitions must be assigned"

    def test_offset_commit_after_processing(self):
        """Test that offsets are committed only after successful processing."""
        committed_offsets = {}
        messages = [
            {"offset": 0, "value": "msg-0"},
            {"offset": 1, "value": "msg-1"},
            {"offset": 2, "value": "msg-2"},
        ]

        processed = []
        for msg in messages:
            # Process message
            processed.append(msg["value"])
            # Commit offset after processing
            committed_offsets["partition-0"] = msg["offset"] + 1

        assert committed_offsets["partition-0"] == 3, \
            "Committed offset should be last processed + 1"

    def test_offset_not_committed_on_failure(self):
        """Test that offsets are not committed when processing fails."""
        committed_offset = 0

        messages = [
            {"offset": 0, "value": "good"},
            {"offset": 1, "value": "bad"},  # will fail
            {"offset": 2, "value": "good"},
        ]

        for msg in messages:
            try:
                if msg["value"] == "bad":
                    raise ValueError("Processing failed")
                committed_offset = msg["offset"] + 1
            except ValueError:
                break  # Stop processing, don't commit

        assert committed_offset == 1, \
            "Offset should only advance up to last successful message"


class TestDeadLetterQueue:
    """Tests for dead letter queue handling."""

    def test_failed_message_sent_to_dlq(self):
        """Test that messages failing max retries are sent to DLQ."""
        max_retries = 3
        dlq = []

        message = {"id": "msg-1", "value": "poison", "retry_count": 0}

        while message["retry_count"] < max_retries:
            # Simulate processing failure
            message["retry_count"] += 1

        # After max retries, send to DLQ
        if message["retry_count"] >= max_retries:
            dlq.append(message)

        assert len(dlq) == 1, "Failed message should be in DLQ"
        assert dlq[0]["retry_count"] == max_retries

    def test_dlq_preserves_original_message(self):
        """Test that DLQ entry preserves the original message and error context."""
        original = {"id": "msg-1", "type": "order_created", "payload": {"order_id": "o-1"}}
        error = "Deserialization error: invalid field 'amount'"

        dlq_entry = {
            "original_message": json.dumps(original),
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": 3,
            "source_topic": "orders.events",
        }

        recovered = json.loads(dlq_entry["original_message"])
        assert recovered == original, "DLQ should preserve original message"
        assert dlq_entry["error"] == error, "DLQ should preserve error context"

    def test_dlq_messages_can_be_replayed(self):
        """Test that DLQ messages can be replayed to original topic."""
        dlq = [
            {"original_message": '{"id": "msg-1"}', "source_topic": "orders.events"},
            {"original_message": '{"id": "msg-2"}', "source_topic": "trades.events"},
        ]

        replayed = []
        for entry in dlq:
            replayed.append({
                "topic": entry["source_topic"],
                "message": json.loads(entry["original_message"]),
            })

        assert len(replayed) == 2
        assert replayed[0]["topic"] == "orders.events"
        assert replayed[1]["message"]["id"] == "msg-2"


class TestEventRetryWithBackoff:
    """Tests for event retry with exponential backoff."""

    def test_exponential_backoff_delays(self):
        """Test that retry delays follow exponential backoff."""
        base_delay = 1.0
        max_delay = 60.0
        retries = 5

        delays = []
        for attempt in range(retries):
            delay = min(base_delay * (2 ** attempt), max_delay)
            delays.append(delay)

        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0], \
            "Delays should follow exponential backoff"

    def test_backoff_with_jitter(self):
        """Test that backoff includes jitter to prevent thundering herd."""
        base_delay = 1.0
        random.seed(42)  # deterministic for testing

        delays = []
        for attempt in range(3):
            delay = base_delay * (2 ** attempt)
            jitter = random.uniform(0, delay * 0.5)
            delays.append(delay + jitter)

        # Delays should all be greater than base exponential values
        assert delays[0] >= 1.0
        assert delays[1] >= 2.0
        assert delays[2] >= 4.0

        # Jitter means delays are not exact powers of 2
        assert delays[0] != 1.0 or delays[1] != 2.0, \
            "At least some delays should include jitter"

    def test_max_retry_reached(self):
        """Test that retries stop after maximum attempts."""
        max_retries = 3
        attempts = 0
        success = False

        while attempts < max_retries and not success:
            attempts += 1
            # Always fails in this test
            success = False

        assert attempts == max_retries, "Should stop after max retries"
        assert not success, "Should report failure after exhausting retries"


class TestEventSchemaValidation:
    """Tests for event schema validation at service boundaries."""

    def test_valid_event_passes_schema(self):
        """Test that events matching the schema are accepted."""
        schema = {
            "required": ["event_id", "type", "timestamp", "payload"],
            "types": {"event_id": str, "type": str, "timestamp": str, "payload": dict},
        }

        event = {
            "event_id": str(uuid4()),
            "type": "order_created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"order_id": "o-1"},
        }

        # Validate required fields
        missing = [f for f in schema["required"] if f not in event]
        assert len(missing) == 0, "Valid event should pass schema validation"

        # Validate types
        type_errors = [
            f for f in schema["types"]
            if f in event and not isinstance(event[f], schema["types"][f])
        ]
        assert len(type_errors) == 0, "All fields should match expected types"

    def test_invalid_event_rejected_at_boundary(self):
        """Test that events missing required fields are rejected."""
        schema_required = {"event_id", "type", "timestamp", "payload"}

        invalid_event = {
            "type": "order_created",
            # Missing event_id, timestamp, payload
        }

        missing = schema_required - set(invalid_event.keys())
        assert len(missing) == 3, "Should detect 3 missing required fields"

    def test_extra_fields_tolerated(self):
        """Test that extra fields in events are tolerated (forward compatibility)."""
        schema_required = {"event_id", "type"}

        event = {
            "event_id": "e-1",
            "type": "order_created",
            "new_field_v2": "extra_data",  # Added in schema v2
        }

        missing = schema_required - set(event.keys())
        assert len(missing) == 0, "Required fields present"
        # Extra fields should not cause validation failure
        extra = set(event.keys()) - schema_required
        assert "new_field_v2" in extra, "Extra fields should be tolerated"


class TestCrossServiceEventCorrelation:
    """Tests for cross-service event correlation."""

    def test_correlation_id_propagated(self):
        """Test that correlation ID is propagated across service events."""
        correlation_id = str(uuid4())

        events = [
            {"service": "orders", "type": "order_created", "correlation_id": correlation_id},
            {"service": "matching", "type": "order_matched", "correlation_id": correlation_id},
            {"service": "settlement", "type": "trade_settled", "correlation_id": correlation_id},
        ]

        # All events should share the same correlation ID
        ids = {e["correlation_id"] for e in events}
        assert len(ids) == 1, "All events should share correlation ID"
        assert correlation_id in ids

    def test_causation_chain_tracking(self):
        """Test that causation chains are maintained across events."""
        event_a = {"event_id": "e-1", "causation_id": None, "type": "order_created"}
        event_b = {"event_id": "e-2", "causation_id": "e-1", "type": "order_matched"}
        event_c = {"event_id": "e-3", "causation_id": "e-2", "type": "trade_settled"}

        # Build causation chain by walking backward from event_c
        events = {"e-1": event_a, "e-2": event_b, "e-3": event_c}
        chain = []

        current = event_c
        while current["causation_id"]:
            chain.insert(0, current["causation_id"])
            current = events.get(current["causation_id"], {"causation_id": None})

        # Chain traces back from event_c's causes to root
        assert chain == ["e-1", "e-2"], "Causation chain should trace back to root"


class TestEventOrderingGuarantees:
    """Tests for event ordering guarantees per partition."""

    def test_same_key_maintains_order(self):
        """Test that events with same partition key maintain order."""
        partition_log = defaultdict(list)

        events = [
            {"key": "order-1", "seq": 1, "type": "created"},
            {"key": "order-1", "seq": 2, "type": "matched"},
            {"key": "order-1", "seq": 3, "type": "settled"},
        ]

        for event in events:
            partition_log[event["key"]].append(event["seq"])

        # Within same key, order should be preserved
        seqs = partition_log["order-1"]
        assert seqs == sorted(seqs), "Events should maintain order per key"

    def test_cross_partition_no_ordering_guarantee(self):
        """Test that events across partitions have no ordering guarantee."""
        partitions = {0: [], 1: []}

        events = [
            {"key": "user-A", "partition": 0, "seq": 1},
            {"key": "user-B", "partition": 1, "seq": 2},
            {"key": "user-A", "partition": 0, "seq": 3},
        ]

        for e in events:
            partitions[e["partition"]].append(e["seq"])

        # Each partition is ordered internally
        assert partitions[0] == [1, 3], "Partition 0 should be ordered"
        assert partitions[1] == [2], "Partition 1 should be ordered"
        # But no guarantee across partitions


class TestConsumerLagMonitoring:
    """Tests for consumer lag monitoring."""

    def test_consumer_lag_calculation(self):
        """Test that consumer lag is calculated correctly."""
        latest_offset = 1000
        consumer_offset = 950

        lag = latest_offset - consumer_offset
        assert lag == 50, "Lag should be difference between latest and consumer offsets"

    def test_lag_threshold_alert(self):
        """Test that alerts fire when lag exceeds threshold."""
        lag_threshold = 100
        partition_lags = {"partition-0": 50, "partition-1": 150, "partition-2": 30}

        alerting_partitions = [
            p for p, lag in partition_lags.items() if lag > lag_threshold
        ]

        assert len(alerting_partitions) == 1
        assert "partition-1" in alerting_partitions, \
            "Partition-1 should trigger lag alert"


class TestEventDeduplication:
    """Tests for event deduplication at consumer."""

    def test_duplicate_event_detected(self):
        """Test that duplicate events are detected and skipped."""
        seen_ids = set()
        processed = []

        events = [
            {"event_id": "e-1", "value": "A"},
            {"event_id": "e-2", "value": "B"},
            {"event_id": "e-1", "value": "A"},  # duplicate
            {"event_id": "e-3", "value": "C"},
        ]

        for event in events:
            if event["event_id"] in seen_ids:
                continue  # skip duplicate
            seen_ids.add(event["event_id"])
            processed.append(event["value"])

        assert processed == ["A", "B", "C"], "Duplicates should be skipped"
        assert len(processed) == 3

    def test_dedup_window_expiry(self):
        """Test that deduplication window expires old entries."""
        dedup_window_seconds = 300  # 5 minutes
        now = time.time()

        dedup_cache = {
            "e-1": now - 400,  # older than window
            "e-2": now - 100,  # within window
        }

        # Clean expired entries
        active = {
            eid: ts for eid, ts in dedup_cache.items()
            if now - ts < dedup_window_seconds
        }

        assert "e-1" not in active, "Expired entry should be purged"
        assert "e-2" in active, "Recent entry should remain"


class TestBatchEventProcessing:
    """Tests for batch event processing."""

    def test_batch_processing_commits_atomically(self):
        """Test that batch of events is committed atomically."""
        batch = [
            {"event_id": f"e-{i}", "value": f"v-{i}"}
            for i in range(10)
        ]

        processed = []
        committed = False

        try:
            for event in batch:
                processed.append(event["event_id"])
            committed = True
        except Exception:
            processed.clear()

        assert committed, "Batch should commit successfully"
        assert len(processed) == 10, "All events in batch should be processed"

    def test_batch_size_limits(self):
        """Test that batch sizes are bounded."""
        max_batch_size = 100
        incoming = list(range(250))

        batches = []
        for i in range(0, len(incoming), max_batch_size):
            batches.append(incoming[i:i + max_batch_size])

        assert len(batches) == 3, "Should split into 3 batches"
        assert len(batches[0]) == 100
        assert len(batches[1]) == 100
        assert len(batches[2]) == 50


class TestEventFilteringAndRouting:
    """Tests for event filtering and routing rules."""

    def test_event_filtering_by_type(self):
        """Test that consumers can filter events by type."""
        subscribed_types = {"order_created", "order_filled"}

        events = [
            {"type": "order_created", "payload": {}},
            {"type": "user_registered", "payload": {}},
            {"type": "order_filled", "payload": {}},
            {"type": "risk_alert", "payload": {}},
        ]

        filtered = [e for e in events if e["type"] in subscribed_types]
        assert len(filtered) == 2, "Should only receive subscribed event types"

    def test_content_based_routing(self):
        """Test content-based routing to different handlers."""
        handlers_called = defaultdict(int)

        def route_event(event):
            if event["payload"].get("priority") == "high":
                handlers_called["fast_lane"] += 1
            else:
                handlers_called["normal"] += 1

        events = [
            {"type": "order_created", "payload": {"priority": "high"}},
            {"type": "order_created", "payload": {"priority": "normal"}},
            {"type": "order_created", "payload": {"priority": "high"}},
        ]

        for event in events:
            route_event(event)

        assert handlers_called["fast_lane"] == 2
        assert handlers_called["normal"] == 1


class TestPoisonMessageHandling:
    """Tests for poison message handling."""

    def test_poison_message_isolated(self):
        """Test that a poison message doesn't block the consumer."""
        processed = []
        errors = []

        messages = [
            {"id": "m-1", "value": "good"},
            {"id": "m-2", "value": None},  # poison: will cause error
            {"id": "m-3", "value": "good"},
        ]

        for msg in messages:
            try:
                if msg["value"] is None:
                    raise TypeError("Cannot process None value")
                processed.append(msg["id"])
            except TypeError as e:
                errors.append({"id": msg["id"], "error": str(e)})

        assert processed == ["m-1", "m-3"], \
            "Good messages should be processed despite poison message"
        assert len(errors) == 1, "Poison message should be captured"

    def test_poison_message_sent_to_dlq_after_retries(self):
        """Test that poison messages end up in DLQ after retry exhaustion."""
        max_retries = 3
        dlq = []

        def process_with_retries(msg, max_r):
            for attempt in range(max_r):
                try:
                    if msg.get("poison"):
                        raise ValueError("Unprocessable")
                    return True
                except ValueError:
                    continue
            return False

        msg = {"id": "m-poison", "poison": True}
        success = process_with_retries(msg, max_retries)

        if not success:
            dlq.append(msg)

        assert not success, "Poison message should fail all retries"
        assert len(dlq) == 1, "Poison message should be in DLQ"


class TestConsumerRebalancing:
    """Tests for consumer rebalancing scenarios."""

    def test_rebalance_reassigns_partitions(self):
        """Test that partitions are reassigned when consumers join/leave."""
        partitions = [0, 1, 2, 3, 4, 5]

        # Initially 2 consumers
        consumers_2 = ["c-1", "c-2"]
        assignment_2 = defaultdict(list)
        for i, p in enumerate(partitions):
            assignment_2[consumers_2[i % len(consumers_2)]].append(p)

        assert len(assignment_2["c-1"]) == 3
        assert len(assignment_2["c-2"]) == 3

        # Consumer c-2 leaves, rebalance to 1 consumer
        consumers_1 = ["c-1"]
        assignment_1 = defaultdict(list)
        for i, p in enumerate(partitions):
            assignment_1[consumers_1[i % len(consumers_1)]].append(p)

        assert len(assignment_1["c-1"]) == 6, \
            "Single consumer should take all partitions"

    def test_no_message_loss_during_rebalance(self):
        """Test that no messages are lost during consumer rebalance."""
        # Before rebalance: consumer A owns partitions [0,1,2]
        consumer_a_offsets = {0: 100, 1: 200, 2: 300}

        # Consumer A commits offsets before rebalance
        committed_offsets = dict(consumer_a_offsets)

        # After rebalance: consumer B gets partition 2
        consumer_b_start_offset = committed_offsets[2]

        assert consumer_b_start_offset == 300, \
            "New consumer should start from committed offset"


class TestEventCompression:
    """Tests for event compression."""

    def test_compressed_event_smaller_than_original(self):
        """Test that compression reduces event payload size."""
        import zlib

        payload = json.dumps({
            "orders": [{"id": f"o-{i}", "symbol": "AAPL", "quantity": 100}
                       for i in range(100)]
        }).encode()

        compressed = zlib.compress(payload)

        assert len(compressed) < len(payload), \
            "Compressed payload should be smaller"
        # Verify roundtrip
        decompressed = zlib.decompress(compressed)
        assert decompressed == payload, "Decompression should recover original"

    def test_compression_codec_negotiation(self):
        """Test that producer and consumer agree on compression codec."""
        supported_codecs = {"gzip", "snappy", "lz4", "zstd"}
        producer_codec = "lz4"

        assert producer_codec in supported_codecs, \
            "Producer codec must be in supported set"


class TestEventTtlAndExpiry:
    """Tests for event TTL and expiry."""

    def test_expired_event_discarded(self):
        """Test that events past their TTL are discarded."""
        now = time.time()
        events = [
            {"id": "e-1", "created_at": now - 7200, "ttl": 3600},  # expired
            {"id": "e-2", "created_at": now - 1800, "ttl": 3600},  # still valid
            {"id": "e-3", "created_at": now - 100, "ttl": 3600},   # still valid
        ]

        valid = [
            e for e in events
            if (now - e["created_at"]) < e["ttl"]
        ]

        assert len(valid) == 2, "Only non-expired events should be processed"
        valid_ids = [e["id"] for e in valid]
        assert "e-1" not in valid_ids, "Expired event should be discarded"

    def test_ttl_based_compaction(self):
        """Test that expired events are cleaned up during compaction."""
        log = {
            "key-A": [
                {"offset": 0, "value": "v1", "expired": True},
                {"offset": 5, "value": "v2", "expired": False},
            ],
            "key-B": [
                {"offset": 1, "value": "v1", "expired": True},
            ],
        }

        # Compaction: keep only latest non-expired per key
        compacted = {}
        for key, entries in log.items():
            live = [e for e in entries if not e["expired"]]
            if live:
                compacted[key] = live[-1]

        assert "key-A" in compacted, "Key-A has live entries"
        assert compacted["key-A"]["value"] == "v2"
        assert "key-B" not in compacted, "Key-B has no live entries"


class TestTransactionalOutboxIntegration:
    """Tests for transactional outbox pattern integration with Kafka."""

    def test_outbox_relay_publishes_to_kafka(self):
        """Test that outbox relay reads from DB and publishes to Kafka."""
        outbox_table = [
            {"id": "ob-1", "topic": "orders.events", "payload": '{"type":"created"}',
             "published": False},
            {"id": "ob-2", "topic": "trades.events", "payload": '{"type":"executed"}',
             "published": False},
        ]

        kafka_published = []

        # Relay process
        for entry in outbox_table:
            if not entry["published"]:
                kafka_published.append({
                    "topic": entry["topic"],
                    "message": entry["payload"],
                })
                entry["published"] = True

        assert len(kafka_published) == 2, "All outbox entries should be published"
        assert all(e["published"] for e in outbox_table), \
            "All outbox entries should be marked published"

    def test_outbox_idempotent_relay(self):
        """Test that replaying outbox relay doesn't create duplicates."""
        outbox_table = [
            {"id": "ob-1", "published": True},  # already published
            {"id": "ob-2", "published": False},  # pending
        ]

        published_count = 0
        for entry in outbox_table:
            if not entry["published"]:
                published_count += 1
                entry["published"] = True

        assert published_count == 1, "Only unpublished entries should be relayed"


class TestEventReplayFromOffset:
    """Tests for event replay from a specific offset."""

    def test_replay_from_specific_offset(self):
        """Test that replay starts from the specified offset."""
        topic_log = [
            {"offset": 0, "value": "a"},
            {"offset": 1, "value": "b"},
            {"offset": 2, "value": "c"},
            {"offset": 3, "value": "d"},
            {"offset": 4, "value": "e"},
        ]

        replay_from = 2
        replayed = [msg for msg in topic_log if msg["offset"] >= replay_from]

        assert len(replayed) == 3, "Should replay from offset 2 onwards"
        assert replayed[0]["value"] == "c"
        assert replayed[-1]["value"] == "e"

    def test_replay_produces_consistent_state(self):
        """Test that replaying all events produces the same aggregate state."""
        events = [
            {"type": "created", "balance": 0},
            {"type": "deposited", "amount": 100},
            {"type": "withdrawn", "amount": 30},
            {"type": "deposited", "amount": 50},
        ]

        def apply_events(event_list):
            balance = 0
            for e in event_list:
                if e["type"] == "deposited":
                    balance += e["amount"]
                elif e["type"] == "withdrawn":
                    balance -= e["amount"]
            return balance

        # Full replay
        balance = apply_events(events)
        assert balance == 120, "Replay should produce consistent state"

        # Partial replay from snapshot
        snapshot_balance = 100  # after first deposit
        remaining = events[2:]  # withdrawn + deposited
        partial_balance = snapshot_balance
        for e in remaining:
            if e["type"] == "deposited":
                partial_balance += e["amount"]
            elif e["type"] == "withdrawn":
                partial_balance -= e["amount"]

        assert partial_balance == balance, \
            "Snapshot + partial replay should equal full replay"
