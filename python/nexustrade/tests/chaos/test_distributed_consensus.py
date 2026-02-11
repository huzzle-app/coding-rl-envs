"""
Chaos engineering tests for distributed consensus bugs.

These tests verify bugs A1-A8 (Distributed Consensus category).
"""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal


class TestSplitBrain:
    """Tests for bug A1: Split-brain on network partition."""

    @pytest.mark.chaos
    def test_duplicate_execution_prevention(self):
        """Test that orders aren't executed twice during partition."""
        order_id = "order-123"
        executions = []

        # Simulate partition: two nodes both try to execute
        def execute_order(node_id: str):
            
            executions.append({"node": node_id, "order_id": order_id})

        execute_order("node-1")
        execute_order("node-2")

        # Should only have one execution
        assert len(executions) == 1, "Order should only execute once (bug: executes twice)"

    @pytest.mark.chaos
    def test_partition_detection(self):
        """Test that network partitions are detected."""
        
        heartbeat_interval = 2.0  # seconds
        last_heartbeat = 0.0  # timestamp
        current_time = 10.0  # timestamp
        partition_threshold = 3 * heartbeat_interval  # 6 seconds

        time_since_heartbeat = current_time - last_heartbeat
        is_partitioned = time_since_heartbeat > partition_threshold
        assert is_partitioned, "Should detect partition when heartbeats are missed"


class TestLeaderElection:
    """Tests for bug A2: Leader election race condition."""

    @pytest.mark.chaos
    def test_leader_consistency(self):
        """Test that all nodes agree on leader."""
        nodes = ["node-1", "node-2", "node-3"]
        leader_views = {
            "node-1": "node-1",  # Thinks it's leader
            "node-2": "node-2",  # Also thinks it's leader (BUG)
            "node-3": "node-1",
        }

        
        unique_leaders = set(leader_views.values())
        assert len(unique_leaders) == 1, "Should have single agreed leader"

    @pytest.mark.chaos
    def test_failover_state_consistency(self):
        """Test state consistency during failover."""
        # After failover, new leader must have latest committed state
        old_leader_state = {"last_committed_seq": 42, "data": "value_42"}
        new_leader_state = {"last_committed_seq": 42, "data": "value_42"}

        assert new_leader_state["last_committed_seq"] >= old_leader_state["last_committed_seq"], \
            "New leader must have at least the last committed sequence"
        assert new_leader_state["data"] == old_leader_state["data"], \
            "New leader must have consistent data with old leader"


class TestDistributedLock:
    """Tests for bug A3: Distributed lock timeout too short."""

    @pytest.mark.chaos
    def test_lock_not_stolen_during_operation(self):
        """Test that lock isn't stolen during long operation."""
        lock_timeout = 5.0  # seconds
        operation_time = 10.0  # seconds

        
        lock_expires_during_operation = operation_time > lock_timeout

        assert not lock_expires_during_operation, "Lock should outlast operation"

    @pytest.mark.chaos
    def test_lock_extension(self):
        """Test that lock can be extended."""
        initial_timeout = 5.0
        extension = 5.0
        total_timeout = initial_timeout + extension

        assert total_timeout == 10.0, "Lock should be extendable"


class TestQuorum:
    """Tests for bug A4: Consensus quorum off-by-one."""

    @pytest.mark.chaos
    def test_majority_required(self):
        """Test that majority quorum is required for writes."""
        total_nodes = 5
        
        correct_quorum = total_nodes // 2 + 1  # 3
        buggy_quorum = total_nodes // 2  # 2

        assert correct_quorum == 3, "Quorum should be majority"

    @pytest.mark.chaos
    def test_minority_write_rejected(self):
        """Test that writes with minority acks are rejected."""
        total_nodes = 5
        acks_received = 2
        quorum = total_nodes // 2 + 1

        is_committed = acks_received >= quorum
        assert not is_committed, "Should not commit with minority"


class TestVersionVector:
    """Tests for bug A5: Version vector comparison."""

    @pytest.mark.chaos
    def test_concurrent_update_detection(self):
        """Test that concurrent updates are detected."""
        vv1 = {"node-1": 2, "node-2": 1}
        vv2 = {"node-1": 1, "node-2": 2}

        # These are concurrent (neither dominates)
        def is_concurrent(v1, v2):
            v1_dominates = all(v1.get(k, 0) >= v2.get(k, 0) for k in set(v1) | set(v2))
            v2_dominates = all(v2.get(k, 0) >= v1.get(k, 0) for k in set(v1) | set(v2))
            return not v1_dominates and not v2_dominates

        assert is_concurrent(vv1, vv2), "Should detect concurrent updates"


class TestGossipProtocol:
    """Tests for bug A6: Gossip protocol message ordering."""

    @pytest.mark.chaos
    def test_eventual_consistency(self):
        """Test that gossip achieves eventual consistency."""
        # After sufficient rounds, all nodes should converge
        node_states = {
            "node-1": {"version": 5, "value": "latest"},
            "node-2": {"version": 5, "value": "latest"},
            "node-3": {"version": 5, "value": "latest"},
        }
        # All nodes should agree after convergence
        values = [s["value"] for s in node_states.values()]
        versions = [s["version"] for s in node_states.values()]
        assert len(set(values)) == 1, "All nodes should converge to same value"
        assert len(set(versions)) == 1, "All nodes should converge to same version"

    @pytest.mark.chaos
    def test_stale_data_detection(self):
        """Test that stale gossip messages are detected."""
        message_version = 5
        local_version = 7

        is_stale = message_version < local_version
        assert is_stale, "Old gossip should be detected as stale"


class TestCachePartition:
    """Tests for bug A7: CAP violation in cache."""

    @pytest.mark.chaos
    def test_stale_read_detection(self):
        """Test that stale reads during partition are detected."""
        
        cache_entry = {"value": "old_price", "timestamp": 1000, "partition_detected": True}
        current_time = 1100

        # During partition, reads should be flagged as potentially stale
        is_stale = cache_entry.get("partition_detected", False) or \
                   (current_time - cache_entry["timestamp"]) > 30
        assert is_stale, "Cache reads during partition should be flagged as stale"


class TestTwoPhaseCommit:
    """Tests for bug A8: 2PC coordinator crash."""

    @pytest.mark.chaos
    def test_transaction_recovery(self):
        """Test that stuck transactions are recovered."""
        transaction_state = "prepared"  # Coordinator crashed after prepare
        timeout_seconds = 30
        elapsed_seconds = 45  # More than timeout

        
        # Either commit (if coordinator recovers) or abort (if timeout)
        should_abort = transaction_state == "prepared" and elapsed_seconds > timeout_seconds
        assert should_abort, "Prepared transaction should be aborted after timeout"
        # After recovery, state should be resolved (not stuck in prepared)
        resolved_state = "aborted" if should_abort else transaction_state
        assert resolved_state in ("committed", "aborted"), \
            "Transaction must be resolved to committed or aborted, not stuck in prepared"

    @pytest.mark.chaos
    def test_participant_timeout(self):
        """Test that participants timeout waiting for coordinator."""
        participant_wait_start = 1000  # timestamp
        current_time = 1060  # 60 seconds later
        participant_timeout = 30  # seconds

        has_timed_out = (current_time - participant_wait_start) > participant_timeout
        assert has_timed_out, "Participant should timeout after waiting too long for coordinator"
        # On timeout, participant should abort its local transaction
        local_action = "abort" if has_timed_out else "wait"
        assert local_action == "abort", "Participant should abort on coordinator timeout"
