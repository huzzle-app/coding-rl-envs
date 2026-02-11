package chaos_test

import (
	"testing"

	"quorumledger/internal/consensus"
	"quorumledger/pkg/models"
)

func TestNetworkPartitionQuorum(t *testing.T) {
	votes := []models.QuorumVote{{NodeID: "a", Approved: true}, {NodeID: "b", Approved: false}, {NodeID: "c", Approved: true}}
	if !consensus.HasQuorum(votes, 0.66) {
		t.Fatalf("expected quorum under partial partition")
	}
}
