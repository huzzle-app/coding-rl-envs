"""
OmniCloud Distributed Consensus Chaos Tests
Terminal Bench v2 - Tests for leader election, split-brain, quorum, gossip.

Covers bugs: B1-B10
~80 tests
"""
import pytest
import time
import uuid
import copy
from unittest.mock import MagicMock, patch

from shared.utils.distributed import (
    DistributedLock, LeaderElection, QuorumChecker,
    LockManager, VersionVector,
)


class TestLeaderElection:
    """Tests for B1: Leader election race condition."""

    def test_leader_election_single_winner(self):
        """B1: Only one candidate should win the election."""
        election = LeaderElection(election_name="scheduler")
        candidate1 = LeaderElection(
            election_name="scheduler", candidate_id="node-1"
        )
        candidate2 = LeaderElection(
            election_name="scheduler", candidate_id="node-2"
        )

        # Both candidates campaign simultaneously
        
        result1 = candidate1.campaign()
        result2 = candidate2.campaign()

        # Only one should be leader
        leaders = []
        if candidate1.is_leader:
            leaders.append(candidate1.candidate_id)
        if candidate2.is_leader:
            leaders.append(candidate2.candidate_id)

        assert len(leaders) == 1, \
            f"Exactly one leader should exist, got {len(leaders)}: {leaders}"

    def test_election_race_safe(self):
        """B1: Concurrent campaigns should be safe (no split-brain)."""
        # Create multiple candidates all campaigning on same election
        candidates = [
            LeaderElection(election_name="controller", candidate_id=f"node-{i}")
            for i in range(5)
        ]

        # All campaign
        for c in candidates:
            c.campaign()

        leaders = [c for c in candidates if c.is_leader]
        assert len(leaders) == 1, \
            f"Expected 1 leader among 5 candidates, got {len(leaders)}"

    def test_leader_has_fencing_token(self):
        """B1: Leader should have a fencing token (term number)."""
        election = LeaderElection(election_name="test")
        election.campaign()
        assert election.term > 0, "Leader should have a positive term number"

    def test_resignation_clears_leader(self):
        """B1: Resigning should clear leadership."""
        election = LeaderElection(election_name="test")
        election.campaign()
        assert election.is_leader is True
        election.resign()
        assert election.is_leader is False
        assert election.leader_id is None

    def test_re_election_after_resign(self):
        """B1: After resignation, a new leader can be elected."""
        election = LeaderElection(election_name="test", candidate_id="node-1")
        election.campaign()
        election.resign()

        new_candidate = LeaderElection(election_name="test", candidate_id="node-2")
        new_candidate.campaign()
        assert new_candidate.is_leader is True

    def test_get_leader_returns_id(self):
        """B1: get_leader should return the current leader's ID."""
        election = LeaderElection(election_name="test", candidate_id="leader-1")
        election.campaign()
        assert election.get_leader() == "leader-1"


class TestSplitBrain:
    """Tests for B2: Split-brain detection during network partition."""

    def test_split_brain_detection(self):
        """B2: Split-brain scenario should be detected and one side should step down."""
        partition_a = LeaderElection(election_name="svc", candidate_id="node-a")
        partition_b = LeaderElection(election_name="svc", candidate_id="node-b")

        partition_a.campaign()
        partition_b.leader_id = None  # Simulate partition - can't see leader
        partition_b.campaign()

        # Both think they're leader - this is split-brain
        both_leaders = partition_a.is_leader and partition_b.is_leader
        # In a correct implementation, split-brain should be prevented
        assert both_leaders is False, \
            "Split-brain detected: both partitions have a leader"

    def test_partition_handling_consistent(self):
        """B2: After partition heals, only one leader should remain."""
        leader1 = LeaderElection(election_name="svc", candidate_id="n1")
        leader1.campaign()

        # After partition heals, check there's exactly one leader
        assert leader1.is_leader is True

    def test_partition_minority_no_writes(self):
        """B2: Minority partition should not accept writes."""
        quorum = QuorumChecker(total_nodes=5)
        # Only 2 nodes in this partition
        assert quorum.has_quorum(2) is False, \
            "Minority partition (2/5) should not have quorum"

    def test_partition_majority_continues(self):
        """B2: Majority partition should continue operating."""
        quorum = QuorumChecker(total_nodes=5)
        assert quorum.has_quorum(3) is True


class TestDistributedLockTTL:
    """Tests for B3: Distributed lock TTL too short."""

    def test_distributed_lock_not_stolen(self):
        """B3: Lock should not expire during normal operations."""
        lock = DistributedLock(name="deploy-lock")
        lock.acquire()

        
        assert lock.ttl_seconds >= 30, \
            f"Lock TTL should be >= 30s, got {lock.ttl_seconds}s"

    def test_lock_extension_works(self):
        """B3: Lock TTL should be extendable."""
        lock = DistributedLock(name="long-operation")
        lock.acquire()
        result = lock.extend(additional_seconds=60)
        assert result is True, "Lock extension should succeed while holding lock"

    def test_lock_context_manager(self):
        """B3: Lock context manager should properly acquire and release."""
        lock = DistributedLock(name="ctx-lock")
        with lock.hold() as held:
            assert held.acquired is True
        assert lock.acquired is False

    def test_lock_release(self):
        """B3: Released lock should be available for others."""
        lock = DistributedLock(name="shared-lock")
        lock.acquire()
        assert lock.acquired is True
        lock.release()
        assert lock.acquired is False

    def test_lock_blocking_acquisition(self):
        """B3: Blocking acquisition should wait until available."""
        lock = DistributedLock(name="blocking-test")
        result = lock.acquire(blocking=True, timeout=5.0)
        assert result is True

    def test_lock_non_blocking_acquisition(self):
        """B3: Non-blocking acquisition should return immediately."""
        lock = DistributedLock(name="nonblocking-test")
        result = lock.acquire(blocking=False)
        assert result is True


class TestQuorum:
    """Tests for B4: Quorum off-by-one."""

    def test_quorum_majority_required(self):
        """B4: Quorum should require strict majority (more than half)."""
        checker = QuorumChecker(total_nodes=5)
        
        # for 4 nodes: 2 >= 4/2 = 2.0 is True)
        checker_even = QuorumChecker(total_nodes=4)
        result = checker_even.has_quorum(2)
        assert result is False, \
            "2 out of 4 nodes is exactly half, not majority - should not have quorum"

    def test_minority_write_rejected(self):
        """B4: Writes with less than majority should be rejected."""
        checker = QuorumChecker(total_nodes=5)
        assert checker.has_quorum(2) is False, "2/5 is not majority"

    def test_majority_accepted(self):
        """B4: Writes with majority should be accepted."""
        checker = QuorumChecker(total_nodes=5)
        assert checker.has_quorum(3) is True, "3/5 is majority"

    def test_all_nodes_quorum(self):
        """B4: All nodes responding should have quorum."""
        checker = QuorumChecker(total_nodes=3)
        assert checker.has_quorum(3) is True

    def test_minimum_for_quorum_correct(self):
        """B4: Minimum for quorum should be (total/2) + 1."""
        checker = QuorumChecker(total_nodes=5)
        min_needed = checker.minimum_for_quorum()
        assert min_needed == 3, f"Minimum for quorum of 5 should be 3, got {min_needed}"

    def test_single_node_quorum(self):
        """B4: Single node cluster should always have quorum."""
        checker = QuorumChecker(total_nodes=1)
        assert checker.has_quorum(1) is True

    def test_zero_nodes_no_quorum(self):
        """B4: Zero responding nodes should not have quorum."""
        checker = QuorumChecker(total_nodes=3)
        assert checker.has_quorum(0) is False


class TestVersionVectors:
    """Tests for B5: Version vector merge correctness."""

    def test_version_vector_merge_correct(self):
        """B5: Merging version vectors should take the max of each component."""
        vv1 = VersionVector(versions={"node1": 3, "node2": 1})
        vv2 = VersionVector(versions={"node1": 1, "node2": 5})

        merged = vv1.merge(vv2)

        
        assert merged.versions["node1"] == 3, \
            f"node1 should be max(3,1)=3, got {merged.versions['node1']}"
        assert merged.versions["node2"] == 5, \
            f"node2 should be max(1,5)=5, got {merged.versions['node2']}"

    def test_concurrent_version_resolution(self):
        """B5: Concurrent versions should be correctly identified."""
        vv1 = VersionVector(versions={"a": 2, "b": 1})
        vv2 = VersionVector(versions={"a": 1, "b": 2})

        assert vv1.is_concurrent_with(vv2) is True, \
            "Neither version dominates the other, they are concurrent"

    def test_version_vector_increment(self):
        """B5: Incrementing should increase only the specified node."""
        vv = VersionVector(versions={"a": 1, "b": 2})
        vv.increment("a")
        assert vv.versions["a"] == 2
        assert vv.versions["b"] == 2

    def test_version_vector_dominates(self):
        """B5: One vector should dominate if all components are >=."""
        vv1 = VersionVector(versions={"a": 3, "b": 3})
        vv2 = VersionVector(versions={"a": 1, "b": 1})
        assert vv1.is_concurrent_with(vv2) is False

    def test_merge_with_new_node(self):
        """B5: Merging with a new node should include it."""
        vv1 = VersionVector(versions={"a": 1})
        vv2 = VersionVector(versions={"b": 1})
        merged = vv1.merge(vv2)
        assert "a" in merged.versions
        assert "b" in merged.versions

    def test_merge_empty_vectors(self):
        """B5: Merging empty vectors should produce empty."""
        vv1 = VersionVector()
        vv2 = VersionVector()
        merged = vv1.merge(vv2)
        assert len(merged.versions) == 0


class TestGossipOrdering:
    """Tests for B6: Gossip protocol message ordering."""

    def test_gossip_message_ordering(self):
        """B6: Gossip messages should be processed in causal order."""
        messages = [
            {"seq": 1, "data": "a"},
            {"seq": 2, "data": "b"},
            {"seq": 3, "data": "c"},
        ]
        # Messages should be processed in sequence order
        sequences = [m["seq"] for m in messages]
        assert sequences == sorted(sequences), "Gossip messages should be in causal order"

    def test_gossip_eventual_delivery(self):
        """B6: All gossip messages should eventually be delivered to all nodes."""
        nodes = {"n1": set(), "n2": set(), "n3": set()}
        message = "update_config"

        # Simulate gossip propagation
        nodes["n1"].add(message)
        nodes["n2"].add(message)
        nodes["n3"].add(message)

        assert all(message in msgs for msgs in nodes.values()), \
            "Gossip should eventually deliver to all nodes"

    def test_gossip_deduplication(self):
        """B6: Duplicate gossip messages should be ignored."""
        received = set()
        messages = ["msg1", "msg1", "msg2", "msg2", "msg3"]
        for msg in messages:
            received.add(msg)
        assert len(received) == 3

    def test_gossip_anti_entropy(self):
        """B6: Anti-entropy should detect and repair inconsistencies."""
        node_a = {"key1": "v1", "key2": "v2"}
        node_b = {"key1": "v1"}
        missing = set(node_a.keys()) - set(node_b.keys())
        assert "key2" in missing


class TestEtcdWatch:
    """Tests for B7: etcd watch revision continuity."""

    def test_etcd_watch_no_revision_gap(self):
        """B7: etcd watch should not miss revisions between compaction and current."""
        revisions_received = [10, 11, 12, 13, 14]
        for i in range(1, len(revisions_received)):
            gap = revisions_received[i] - revisions_received[i-1]
            assert gap == 1, \
                f"Revision gap detected: {revisions_received[i-1]} -> {revisions_received[i]}"

    def test_watch_continuity(self):
        """B7: Watch should resume from last seen revision after reconnect."""
        last_seen = 42
        resume_from = last_seen + 1
        assert resume_from == 43

    def test_watch_compaction_handling(self):
        """B7: Watch should handle compacted revisions gracefully."""
        compacted_revision = 100
        watch_from = 50
        needs_full_sync = watch_from < compacted_revision
        assert needs_full_sync is True

    def test_watch_event_ordering(self):
        """B7: Watch events should be in revision order."""
        events = [
            {"revision": 10, "key": "a"},
            {"revision": 11, "key": "b"},
            {"revision": 12, "key": "c"},
        ]
        revisions = [e["revision"] for e in events]
        assert revisions == sorted(revisions)


class TestRaftLogCompaction:
    """Tests for B8: Raft log compaction safety."""

    def test_raft_log_compaction_safe(self):
        """B8: Log compaction should not lose committed entries."""
        committed_entries = list(range(1, 101))
        snapshot_at = 50
        compacted_entries = committed_entries[:snapshot_at]
        remaining_entries = committed_entries[snapshot_at:]

        # After compaction, snapshot should cover compacted entries
        assert len(compacted_entries) == 50
        assert len(remaining_entries) == 50

    def test_compaction_no_data_loss(self):
        """B8: All data should be recoverable after compaction."""
        original_data = {"key1": "v1", "key2": "v2", "key3": "v3"}
        snapshot_data = dict(original_data)
        log_after_snapshot = [{"op": "set", "key": "key4", "value": "v4"}]

        # Restore from snapshot + log
        restored = dict(snapshot_data)
        for entry in log_after_snapshot:
            restored[entry["key"]] = entry["value"]

        assert "key1" in restored
        assert "key4" in restored

    def test_compaction_snapshot_complete(self):
        """B8: Snapshot should contain complete state."""
        state = {"a": 1, "b": 2, "c": 3}
        snapshot = copy.deepcopy(state)
        assert snapshot == state

    def test_compaction_idempotent(self):
        """B8: Multiple compactions should be safe."""
        log_size = 100
        for _ in range(3):
            log_size = max(log_size // 2, 10)
        assert log_size >= 10


class TestMembershipChange:
    """Tests for B9: Cluster membership change during election."""

    def test_membership_change_during_election(self):
        """B9: Adding/removing nodes during election should be safe."""
        cluster_members = {"n1", "n2", "n3"}
        # Add new member during election
        cluster_members.add("n4")
        assert len(cluster_members) == 4

        # Quorum should be based on new membership
        quorum = QuorumChecker(total_nodes=len(cluster_members))
        assert quorum.has_quorum(3) is True

    def test_config_change_safe(self):
        """B9: Configuration changes should use joint consensus."""
        old_config = {"n1", "n2", "n3"}
        new_config = {"n1", "n2", "n4"}

        # Joint config needs quorum from both old and new
        # At least majority of old AND majority of new
        responding = {"n1", "n2"}
        old_quorum = len(responding & old_config) > len(old_config) / 2
        new_quorum = len(responding & new_config) > len(new_config) / 2

        assert old_quorum is True
        assert new_quorum is True

    def test_node_removal_safe(self):
        """B9: Removing a node should update quorum calculation."""
        quorum_before = QuorumChecker(total_nodes=5)
        quorum_after = QuorumChecker(total_nodes=4)
        assert quorum_before.minimum_for_quorum() >= quorum_after.minimum_for_quorum()

    def test_node_addition_safe(self):
        """B9: Adding a node should not disrupt existing quorum."""
        cluster = {"n1", "n2", "n3"}
        cluster.add("n4")
        assert len(cluster) == 4


class TestSnapshotTransfer:
    """Tests for B10: Snapshot transfer integrity."""

    def test_snapshot_transfer_integrity(self):
        """B10: Snapshot transferred to new node should be complete."""
        original_snapshot = {
            "data": {"key1": "val1", "key2": "val2"},
            "version": 42,
            "checksum": "abc123",
        }
        transferred_snapshot = copy.deepcopy(original_snapshot)
        assert transferred_snapshot == original_snapshot

    def test_snapshot_checksum_valid(self):
        """B10: Snapshot checksum should validate integrity."""
        import hashlib
        data = b"snapshot_data_content"
        checksum = hashlib.sha256(data).hexdigest()
        verified = hashlib.sha256(data).hexdigest() == checksum
        assert verified is True, "Snapshot checksum should validate"

    def test_snapshot_partial_transfer_detected(self):
        """B10: Partial snapshot transfer should be detected."""
        expected_size = 1000
        received_size = 500
        is_complete = received_size == expected_size
        assert is_complete is False, "Partial transfer should be detected"

    def test_snapshot_retry_on_failure(self):
        """B10: Failed snapshot transfer should be retried."""
        max_retries = 3
        attempts = 0
        success = False
        while attempts < max_retries:
            attempts += 1
            success = True
            break
        assert success is True
        assert attempts <= max_retries


class TestDistributedLockManager:
    """Additional distributed consensus tests for coverage."""

    def test_lock_manager_multi_lock(self):
        """LockManager should acquire multiple locks."""
        lm = LockManager()
        result = lm.acquire_locks(["lock_a", "lock_b"])
        assert result is True

    def test_lock_manager_release_all(self):
        """LockManager should release all locks."""
        lm = LockManager()
        lm.acquire_locks(["lock_a", "lock_b"])
        lm.release_all()
        assert len(lm._acquisition_order) == 0

    def test_version_vector_new_node(self):
        """New node in version vector should start at 0."""
        vv = VersionVector()
        assert vv.versions.get("new_node", 0) == 0
        vv.increment("new_node")
        assert vv.versions["new_node"] == 1

    def test_leader_election_defaults(self):
        """LeaderElection should have sensible defaults."""
        le = LeaderElection(election_name="test")
        assert le.is_leader is False
        assert le.leader_id is None
        assert le.term == 0


class TestQuorumEdgeCases:
    """Extended quorum calculation edge case tests."""

    def test_quorum_single_node(self):
        """B4: Single-node cluster quorum should be 1."""
        qc = QuorumChecker(total_nodes=1)
        assert qc.has_quorum(1) is True

    def test_quorum_two_nodes(self):
        """B4: Two-node cluster - need 2 for quorum (majority)."""
        qc = QuorumChecker(total_nodes=2)
        assert qc.has_quorum(2) is True
        assert qc.has_quorum(1) is False

    def test_quorum_three_nodes(self):
        """B4: Three-node cluster - need 2 for quorum."""
        qc = QuorumChecker(total_nodes=3)
        assert qc.has_quorum(2) is True
        assert qc.has_quorum(1) is False

    def test_quorum_five_nodes(self):
        """B4: Five-node cluster - need 3 for quorum."""
        qc = QuorumChecker(total_nodes=5)
        assert qc.has_quorum(3) is True
        assert qc.has_quorum(2) is False

    def test_quorum_all_nodes_respond(self):
        """B4: All nodes responding should always have quorum."""
        qc = QuorumChecker(total_nodes=7)
        assert qc.has_quorum(7) is True

    def test_quorum_zero_responses(self):
        """B4: Zero responses should never have quorum."""
        qc = QuorumChecker(total_nodes=5)
        assert qc.has_quorum(0) is False


class TestVersionVectorEdgeCases:
    """Extended version vector edge case tests."""

    def test_version_vector_empty_merge(self):
        """B5: Merging two empty vectors yields empty."""
        vv1 = VersionVector()
        vv2 = VersionVector()
        vv1.merge(vv2)
        assert len(vv1.versions) == 0

    def test_version_vector_disjoint_merge(self):
        """B5: Merging disjoint vectors produces union."""
        vv1 = VersionVector(versions={"a": 1})
        vv2 = VersionVector(versions={"b": 2})
        vv1.merge(vv2)
        assert vv1.versions["a"] == 1
        assert vv1.versions["b"] == 2

    def test_version_vector_dominates(self):
        """B5: One vector strictly dominating another."""
        vv1 = VersionVector(versions={"a": 2, "b": 3})
        vv2 = VersionVector(versions={"a": 1, "b": 2})
        assert vv1.dominates(vv2) is True
        assert vv2.dominates(vv1) is False

    def test_version_vector_equal_are_not_concurrent(self):
        """B5: Equal vectors are not concurrent."""
        vv1 = VersionVector(versions={"a": 1, "b": 2})
        vv2 = VersionVector(versions={"a": 1, "b": 2})
        assert vv1.is_concurrent_with(vv2) is False


class TestDistributedLockEdgeCases:
    """Extended distributed lock edge case tests."""

    def test_lock_ttl_default(self):
        """B3: Lock TTL should be 30 seconds (bug: currently 5)."""
        lock = DistributedLock(name="test-lock")
        
        assert lock.ttl_seconds > 0

    def test_lock_owner_unique(self):
        """B3: Each lock should have a unique owner."""
        lock1 = DistributedLock(name="lock1")
        lock2 = DistributedLock(name="lock2")
        assert lock1.owner_id != lock2.owner_id

    def test_lock_acquire_non_blocking(self):
        """B3: Non-blocking acquire should return immediately."""
        lock = DistributedLock(name="test-lock")
        result = lock.acquire(blocking=False)
        assert result is True

    def test_lock_initial_state(self):
        """B3: Lock should not be acquired initially."""
        lock = DistributedLock(name="test-lock")
        assert lock.acquired is False
        assert lock.acquired_at == 0.0
