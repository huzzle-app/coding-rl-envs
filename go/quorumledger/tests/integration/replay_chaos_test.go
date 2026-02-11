package integration_test

import (
	"testing"

	"quorumledger/internal/replay"
	"quorumledger/internal/resilience"
)

func TestReplayChaosIntegration(t *testing.T) {
	budget := replay.ReplayBudget(500, 12)
	if budget < 150 {
		t.Fatalf("replay budget unexpectedly low: %d", budget)
	}
	leader := resilience.PickLeader([]string{"n1", "n2", "n3"}, map[string]bool{"n1": true, "n2": true})
	if leader != "n3" {
		t.Fatalf("expected n3 as leader, got %s", leader)
	}
}
