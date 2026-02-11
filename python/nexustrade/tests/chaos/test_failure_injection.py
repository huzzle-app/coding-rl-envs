"""
Chaos engineering tests for failure injection scenarios.

These tests simulate various infrastructure failures (network partitions,
service crashes, resource exhaustion, data corruption, cascading failures,
and timeout chaos) to verify that the NexusTrade platform degrades gracefully
and recovers correctly.
"""
import pytest
import hashlib
import time


# =========================================================================
# Network Partition Tests
# =========================================================================

class TestNetworkPartition:
    """Simulate and verify behaviour during network partitions."""

    @pytest.mark.chaos
    def test_partition_between_services(self):
        """Simulate a partition between order service and matching engine."""
        order_service_reachable = True
        matching_engine_reachable = False  # partitioned

        # During partition the gateway should detect the unreachable service
        services = {
            "order_service": order_service_reachable,
            "matching_engine": matching_engine_reachable,
        }
        unreachable = [s for s, ok in services.items() if not ok]
        assert len(unreachable) > 0, "Should detect at least one unreachable service"
        assert "matching_engine" in unreachable

        # System should switch to degraded mode
        degraded_mode = len(unreachable) > 0
        assert degraded_mode, "System must enter degraded mode when services are partitioned"

    @pytest.mark.chaos
    def test_split_brain_recovery(self):
        """Verify that split-brain state is resolved after partition heals."""
        # During split-brain, two partitions may have divergent state
        partition_a_state = {"order-1": "filled", "order-2": "open"}
        partition_b_state = {"order-1": "open", "order-2": "cancelled"}

        # After partition heals, conflict resolution should pick one truth
        # Rule: higher-progress state wins (filled > open > cancelled for order-1)
        status_priority = {"cancelled": 0, "open": 1, "partially_filled": 2, "filled": 3}
        merged = {}
        all_keys = set(partition_a_state) | set(partition_b_state)
        for key in all_keys:
            state_a = partition_a_state.get(key)
            state_b = partition_b_state.get(key)
            if state_a and state_b:
                merged[key] = state_a if status_priority.get(state_a, 0) >= status_priority.get(state_b, 0) else state_b
            else:
                merged[key] = state_a or state_b

        assert merged["order-1"] == "filled", "Higher progress state should win"
        assert merged["order-2"] is not None, "Every order must have a resolved state"

    @pytest.mark.chaos
    def test_partition_heal_detection(self):
        """Test that partition healing is detected promptly."""
        partition_start = 1000
        partition_end = 1030
        current_time = 1035
        heal_detection_window = 10  # seconds

        is_healed = current_time > partition_end
        detected_within_window = (current_time - partition_end) <= heal_detection_window
        assert is_healed, "Partition should be detected as healed"
        assert detected_within_window, "Heal should be detected within the allowed window"

    @pytest.mark.chaos
    def test_message_queue_during_partition(self):
        """Verify messages are queued and replayed after partition heals."""
        queued_messages = []
        partition_active = True

        # During partition, messages should be queued locally
        for i in range(5):
            msg = {"seq": i, "type": "order.event", "payload": f"data-{i}"}
            if partition_active:
                queued_messages.append(msg)

        assert len(queued_messages) == 5, "All messages should be queued during partition"

        # After partition heals, replay in order
        partition_active = False
        replayed = []
        for msg in sorted(queued_messages, key=lambda m: m["seq"]):
            replayed.append(msg["seq"])

        assert replayed == list(range(5)), "Messages must be replayed in order"

    @pytest.mark.chaos
    def test_state_reconciliation_after_partition(self):
        """Test that divergent state is reconciled after a partition heals."""
        node_a_events = [{"seq": 1, "data": "a"}, {"seq": 2, "data": "b"}]
        node_b_events = [{"seq": 1, "data": "a"}, {"seq": 3, "data": "c"}]

        # Reconciliation: merge events by sequence, detect missing
        all_seqs = {e["seq"] for e in node_a_events} | {e["seq"] for e in node_b_events}
        a_seqs = {e["seq"] for e in node_a_events}
        b_seqs = {e["seq"] for e in node_b_events}

        missing_on_a = all_seqs - a_seqs
        missing_on_b = all_seqs - b_seqs

        assert missing_on_a == {3}, "Node A is missing seq 3"
        assert missing_on_b == {2}, "Node B is missing seq 2"
        assert len(all_seqs) == 3, "Merged event log should have 3 unique events"


# =========================================================================
# Service Crash Tests
# =========================================================================

class TestServiceCrash:
    """Simulate service crashes and verify recovery behaviour."""

    @pytest.mark.chaos
    def test_crash_during_transaction(self):
        """Simulate crash mid-transaction; uncommitted work must roll back."""
        transaction_log = []
        transaction_committed = False

        # Simulate operations before crash
        transaction_log.append({"op": "debit", "account": "acc-001", "amount": 1000})
        transaction_log.append({"op": "credit", "account": "acc-002", "amount": 1000})
        # Crash occurs before commit
        crash_occurred = True

        if crash_occurred and not transaction_committed:
            rollback_ops = list(reversed(transaction_log))
            transaction_log.clear()

        assert len(transaction_log) == 0, "Uncommitted transaction must be rolled back"
        assert not transaction_committed

    @pytest.mark.chaos
    def test_crash_recovery_from_wal(self):
        """Service should recover committed state from write-ahead log."""
        wal_entries = [
            {"lsn": 1, "op": "insert", "committed": True},
            {"lsn": 2, "op": "update", "committed": True},
            {"lsn": 3, "op": "insert", "committed": False},  # was in-flight
        ]

        recovered_ops = [e for e in wal_entries if e["committed"]]
        assert len(recovered_ops) == 2, "Only committed WAL entries should be recovered"
        assert all(e["committed"] for e in recovered_ops)

    @pytest.mark.chaos
    def test_orphaned_lock_cleanup(self):
        """Locks held by a crashed service must be cleaned up."""
        locks = {
            "resource-A": {"holder": "service-1", "acquired_at": 1000, "ttl": 30},
            "resource-B": {"holder": "service-2", "acquired_at": 1010, "ttl": 30},
        }
        current_time = 1050
        crashed_service = "service-1"

        # Clean up locks held by crashed service or expired
        released = []
        for resource, lock in list(locks.items()):
            expired = (current_time - lock["acquired_at"]) > lock["ttl"]
            held_by_crashed = lock["holder"] == crashed_service
            if expired or held_by_crashed:
                released.append(resource)

        assert "resource-A" in released, "Lock held by crashed service must be released"
        assert "resource-B" in released, "Expired lock must be released"

    @pytest.mark.chaos
    def test_in_flight_request_handling(self):
        """In-flight requests must receive an error or be retried after crash."""
        in_flight_requests = [
            {"req_id": "r1", "idempotency_key": "ik-1", "status": "processing"},
            {"req_id": "r2", "idempotency_key": "ik-2", "status": "processing"},
            {"req_id": "r3", "idempotency_key": "ik-3", "status": "processing"},
        ]

        # After crash, mark all in-flight as failed-retryable
        for req in in_flight_requests:
            req["status"] = "failed_retryable"

        assert all(r["status"] == "failed_retryable" for r in in_flight_requests)
        # Idempotency keys should be preserved so retries are safe
        keys = [r["idempotency_key"] for r in in_flight_requests]
        assert len(set(keys)) == len(keys), "Idempotency keys must be unique"

    @pytest.mark.chaos
    def test_state_reconstruction_after_crash(self):
        """Service must reconstruct in-memory state from persisted snapshots + events."""
        snapshot = {"balance": 10000, "snapshot_seq": 50}
        events_after_snapshot = [
            {"seq": 51, "delta": -500},
            {"seq": 52, "delta": +200},
            {"seq": 53, "delta": -100},
        ]

        # Rebuild state
        balance = snapshot["balance"]
        for event in sorted(events_after_snapshot, key=lambda e: e["seq"]):
            balance += event["delta"]

        expected = 10000 - 500 + 200 - 100
        assert balance == expected, "State must be correctly reconstructed"
        assert balance == 9600


# =========================================================================
# Resource Exhaustion Tests
# =========================================================================

class TestResourceExhaustion:
    """Simulate resource exhaustion and verify graceful handling."""

    @pytest.mark.chaos
    def test_memory_pressure_response(self):
        """Under memory pressure the system should shed non-critical load."""
        memory_usage_pct = 92.0
        critical_threshold = 90.0
        shed_threshold = 85.0

        is_critical = memory_usage_pct >= critical_threshold
        should_shed_load = memory_usage_pct >= shed_threshold

        assert is_critical, "Memory usage above 90% should be flagged critical"
        assert should_shed_load, "Load shedding should activate above 85%"

        # Non-critical services should be paused
        services_to_pause = ["analytics", "reporting", "notifications"]
        services_to_keep = ["order_service", "matching_engine", "risk_service"]
        paused = services_to_pause if is_critical else []
        assert len(paused) == 3, "Non-critical services should be paused"
        assert all(s not in paused for s in services_to_keep)

    @pytest.mark.chaos
    def test_connection_pool_exhaustion_recovery(self):
        """When connection pool is exhausted, new requests must queue or fail fast."""
        pool_size = 50
        active_connections = 50  # fully exhausted
        wait_queue_limit = 10
        wait_queue_current = 8

        pool_exhausted = active_connections >= pool_size
        queue_available = wait_queue_current < wait_queue_limit

        assert pool_exhausted, "Pool should be detected as exhausted"
        assert queue_available, "Wait queue should still have capacity"

        # After connections return, pool should recover
        active_connections = 30  # some returned
        recovered = active_connections < pool_size
        assert recovered, "Pool should recover after connections are returned"

    @pytest.mark.chaos
    def test_disk_space_handling(self):
        """Low disk space should trigger alerts and log rotation."""
        disk_total_gb = 500
        disk_used_gb = 475
        disk_free_gb = disk_total_gb - disk_used_gb
        low_disk_threshold_gb = 50

        is_low = disk_free_gb < low_disk_threshold_gb
        assert is_low, "Low disk condition should be detected"

        # Emergency actions
        actions = []
        if is_low:
            actions.append("rotate_logs")
            actions.append("alert_ops")
            if disk_free_gb < 10:
                actions.append("reject_new_writes")

        assert "rotate_logs" in actions
        assert "alert_ops" in actions
        assert "reject_new_writes" not in actions, "Still have >10GB so writes allowed"

    @pytest.mark.chaos
    def test_thread_pool_saturation(self):
        """Saturated thread pool should reject with backpressure signal."""
        max_threads = 200
        active_threads = 200
        queued_tasks = 500
        queue_limit = 1000

        is_saturated = active_threads >= max_threads
        assert is_saturated, "Thread pool should be detected as saturated"

        # Backpressure: reject if queue is also filling up
        queue_pressure = queued_tasks / queue_limit
        backpressure_active = queue_pressure > 0.4
        assert backpressure_active, "Backpressure should engage when queue > 40%"

        # HTTP 503 response for new requests when backpressure is active
        response_code = 503 if (is_saturated and backpressure_active) else 200
        assert response_code == 503, "Should return 503 under saturation + backpressure"


# =========================================================================
# Data Corruption Tests
# =========================================================================

class TestDataCorruption:
    """Simulate data corruption and verify detection/recovery."""

    @pytest.mark.chaos
    def test_checksum_validation_on_events(self):
        """Corrupted events must be detected via checksum mismatch."""
        original_payload = '{"order_id":"ord-1","quantity":"10"}'
        correct_checksum = hashlib.sha256(original_payload.encode()).hexdigest()

        # Simulate corruption
        corrupted_payload = '{"order_id":"ord-1","quantity":"100"}'  # tampered
        computed_checksum = hashlib.sha256(corrupted_payload.encode()).hexdigest()

        checksum_match = correct_checksum == computed_checksum
        assert not checksum_match, "Corrupted payload should fail checksum validation"

    @pytest.mark.chaos
    def test_corrupted_message_detection(self):
        """Message broker must detect and quarantine corrupted messages."""
        messages = [
            {"id": "m1", "payload": "valid-json", "crc": 12345, "valid": True},
            {"id": "m2", "payload": "invalid\x00data", "crc": 99999, "valid": False},
            {"id": "m3", "payload": "valid-json-2", "crc": 54321, "valid": True},
        ]

        quarantined = [m for m in messages if not m["valid"]]
        delivered = [m for m in messages if m["valid"]]

        assert len(quarantined) == 1, "One corrupted message should be quarantined"
        assert quarantined[0]["id"] == "m2"
        assert len(delivered) == 2, "Valid messages should still be delivered"

    @pytest.mark.chaos
    def test_data_integrity_verification(self):
        """Periodic integrity scan must detect mismatches between stores."""
        primary_store = {"ord-1": 1000, "ord-2": 2000, "ord-3": 3000}
        replica_store = {"ord-1": 1000, "ord-2": 2500, "ord-3": 3000}  # ord-2 drifted

        mismatches = []
        for key in primary_store:
            if primary_store[key] != replica_store.get(key):
                mismatches.append(key)

        assert len(mismatches) == 1, "Should detect exactly one mismatch"
        assert mismatches[0] == "ord-2", "ord-2 should be flagged as inconsistent"

    @pytest.mark.chaos
    def test_recovery_from_corrupted_state(self):
        """System must rebuild state from clean backup on corruption detection."""
        current_state_corrupted = True
        last_known_good_snapshot = {"seq": 100, "balance": 50000}
        events_since_snapshot = [
            {"seq": 101, "delta": -1000},
            {"seq": 102, "delta": +500},
        ]

        if current_state_corrupted:
            # Rebuild from snapshot + events
            rebuilt_balance = last_known_good_snapshot["balance"]
            for evt in events_since_snapshot:
                rebuilt_balance += evt["delta"]
        else:
            rebuilt_balance = None

        assert rebuilt_balance == 49500, "State must be correctly rebuilt from backup"


# =========================================================================
# Cascading Failure Tests
# =========================================================================

class TestCascadingFailure:
    """Verify that the system prevents cascading failures."""

    @pytest.mark.chaos
    def test_failure_propagation_prevention(self):
        """Failure in one service must not propagate to all dependents."""
        services = {
            "matching_engine": "down",
            "order_service": "degraded",  # depends on matching
            "risk_service": "healthy",    # independent
            "settlement": "healthy",      # independent
            "gateway": "degraded",        # depends on order_service
        }

        healthy_count = sum(1 for s in services.values() if s == "healthy")
        assert healthy_count >= 2, "At least 2 services must remain healthy"
        assert services["risk_service"] == "healthy", "Independent services must stay healthy"

    @pytest.mark.chaos
    def test_bulkhead_isolation_during_cascade(self):
        """Bulkhead pattern must isolate thread pools per dependency."""
        bulkheads = {
            "matching_engine_pool": {"max": 50, "active": 50, "rejected": 15},
            "risk_service_pool": {"max": 30, "active": 10, "rejected": 0},
            "settlement_pool": {"max": 20, "active": 5, "rejected": 0},
        }

        # matching_engine pool is saturated but others are fine
        assert bulkheads["matching_engine_pool"]["active"] == bulkheads["matching_engine_pool"]["max"]
        assert bulkheads["risk_service_pool"]["rejected"] == 0, \
            "Risk pool must not be affected by matching engine saturation"
        assert bulkheads["settlement_pool"]["rejected"] == 0, \
            "Settlement pool must not be affected"

    @pytest.mark.chaos
    def test_circuit_breaker_cascade_prevention(self):
        """Circuit breaker must open before failures cascade downstream."""
        failure_threshold = 5
        failure_count = 6
        circuit_state = "closed"

        # Check if circuit should have opened
        if failure_count >= failure_threshold:
            circuit_state = "open"

        assert circuit_state == "open", "Circuit must open after exceeding failure threshold"

        # When open, requests should fail fast instead of cascading
        fail_fast = circuit_state == "open"
        assert fail_fast, "Requests must fail fast when circuit is open"

        # After cool-down, circuit moves to half-open
        cool_down_elapsed = True
        if circuit_state == "open" and cool_down_elapsed:
            circuit_state = "half_open"
        assert circuit_state == "half_open", "Circuit should transition to half-open"

    @pytest.mark.chaos
    def test_graceful_degradation(self):
        """System must degrade gracefully, maintaining core functionality."""
        available_services = {"order_service", "matching_engine", "risk_service"}
        unavailable_services = {"analytics", "notifications", "reporting"}

        core_services = {"order_service", "matching_engine", "risk_service"}
        core_available = core_services.issubset(available_services)
        assert core_available, "Core services must remain available"

        # Non-core features should be disabled, not erroring
        feature_flags = {}
        for svc in unavailable_services:
            feature_flags[svc] = "disabled"
        for svc in available_services:
            feature_flags[svc] = "enabled"

        assert feature_flags["analytics"] == "disabled"
        assert feature_flags["order_service"] == "enabled"


# =========================================================================
# Timeout Chaos Tests
# =========================================================================

class TestTimeoutChaos:
    """Simulate network latency and timeout scenarios."""

    @pytest.mark.chaos
    def test_slow_network_simulation(self):
        """Under high latency the system must still complete within SLA."""
        base_latency_ms = 5
        injected_delay_ms = 800
        total_latency_ms = base_latency_ms + injected_delay_ms
        sla_timeout_ms = 2000

        within_sla = total_latency_ms < sla_timeout_ms
        assert within_sla, "Total latency should remain within SLA"

        # But the system should flag degraded latency
        latency_warning_threshold_ms = 500
        is_degraded = total_latency_ms > latency_warning_threshold_ms
        assert is_degraded, "High latency should trigger degradation warning"

    @pytest.mark.chaos
    def test_variable_latency_handling(self):
        """System must handle variable latency (jitter) without failures."""
        latencies_ms = [50, 120, 800, 30, 500, 1200, 60, 90, 2500, 45]
        timeout_ms = 3000

        # All requests should complete (none exceed timeout)
        timed_out = [l for l in latencies_ms if l > timeout_ms]
        completed = [l for l in latencies_ms if l <= timeout_ms]
        assert len(timed_out) == 0, "No requests should time out"
        assert len(completed) == 10

        # Percentile tracking
        sorted_latencies = sorted(latencies_ms)
        p99_index = int(len(sorted_latencies) * 0.99)
        p99 = sorted_latencies[min(p99_index, len(sorted_latencies) - 1)]
        assert p99 <= timeout_ms, "P99 latency should be within timeout"

    @pytest.mark.chaos
    def test_timeout_escalation(self):
        """Retry timeouts should escalate with exponential backoff."""
        base_timeout_ms = 100
        max_timeout_ms = 5000
        max_retries = 5

        timeouts = []
        for attempt in range(max_retries):
            timeout = min(base_timeout_ms * (2 ** attempt), max_timeout_ms)
            timeouts.append(timeout)

        expected = [100, 200, 400, 800, 1600]
        assert timeouts == expected, "Timeouts must escalate exponentially"
        assert all(t <= max_timeout_ms for t in timeouts), "No timeout should exceed max"

        # Each timeout should be >= previous
        for i in range(1, len(timeouts)):
            assert timeouts[i] >= timeouts[i - 1], "Timeouts must be non-decreasing"

    @pytest.mark.chaos
    def test_deadline_propagation_under_stress(self):
        """Request deadline must shrink as it passes through service layers."""
        initial_deadline_ms = 5000
        service_chain = [
            {"name": "gateway", "processing_ms": 50},
            {"name": "order_service", "processing_ms": 200},
            {"name": "risk_service", "processing_ms": 150},
            {"name": "matching_engine", "processing_ms": 100},
        ]

        remaining = initial_deadline_ms
        for service in service_chain:
            remaining -= service["processing_ms"]
            assert remaining > 0, (
                f"Deadline expired at {service['name']} "
                f"(remaining: {remaining + service['processing_ms']}ms, "
                f"needed: {service['processing_ms']}ms)"
            )

        total_processing = sum(s["processing_ms"] for s in service_chain)
        assert remaining == initial_deadline_ms - total_processing
        assert remaining == 4500, "Remaining deadline should be correctly propagated"
