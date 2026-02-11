package unit_test

import (
	"testing"

	"quorumledger/internal/consensus"
	"quorumledger/pkg/models"
)

func TestApprovalRatio(t *testing.T) {
	votes := []models.QuorumVote{{NodeID: "n1", Approved: true}, {NodeID: "n2", Approved: false}, {NodeID: "n3", Approved: true}}
	ratio := consensus.ApprovalRatio(votes)
	if ratio <= 0.6 || ratio >= 0.7 {
		t.Fatalf("unexpected ratio: %.4f", ratio)
	}
}

func TestHasQuorum(t *testing.T) {
	votes := []models.QuorumVote{{NodeID: "n1", Approved: true}, {NodeID: "n2", Approved: true}, {NodeID: "n3", Approved: false}}
	if !consensus.HasQuorum(votes, 0.66) {
		t.Fatalf("expected quorum")
	}
}

func TestMaxEpoch(t *testing.T) {
	votes := []models.QuorumVote{{NodeID: "n1", Epoch: 3}, {NodeID: "n2", Epoch: 9}, {NodeID: "n3", Epoch: 7}}
	if consensus.MaxEpoch(votes) != 9 {
		t.Fatalf("expected max epoch 9")
	}
}

func TestByzantineTolerance(t *testing.T) {
	if consensus.ByzantineTolerance(7) != 2 {
		t.Fatalf("expected tolerance 2 for 7 nodes")
	}
	if consensus.ByzantineTolerance(4) != 1 {
		t.Fatalf("expected tolerance 1 for 4 nodes")
	}
}

func TestIsSupermajority(t *testing.T) {
	justTwo := []models.QuorumVote{{NodeID: "a", Approved: true}, {NodeID: "b", Approved: false}, {NodeID: "c", Approved: true}}
	if !consensus.IsSupermajority(justTwo) {
		t.Fatalf("expected supermajority for 2/3")
	}
}

func TestQuorumHealth(t *testing.T) {
	half := []models.QuorumVote{{NodeID: "a", Approved: true}, {NodeID: "b", Approved: false}}
	if consensus.QuorumHealth(half, 2) != "weak" {
		t.Fatalf("expected weak for 1/2 ratio, got %s", consensus.QuorumHealth(half, 2))
	}
}

func TestSplitBrainRisk(t *testing.T) {
	partA := []models.QuorumVote{{NodeID: "a", Approved: true}, {NodeID: "b", Approved: true}}
	partB := []models.QuorumVote{{NodeID: "c", Approved: true}, {NodeID: "d", Approved: true}}
	if !consensus.SplitBrainRisk(partA, partB) {
		t.Fatalf("expected split brain risk when both partitions have quorum")
	}
	noQuorum := []models.QuorumVote{{NodeID: "x", Approved: false}, {NodeID: "y", Approved: false}}
	if consensus.SplitBrainRisk(partA, noQuorum) {
		t.Fatalf("no split brain if one partition has no quorum")
	}
}
