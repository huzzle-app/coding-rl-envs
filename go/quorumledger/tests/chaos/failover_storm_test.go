package chaos_test

import (
	"testing"

	"quorumledger/internal/resilience"
)

func TestFailoverStorm(t *testing.T) {
	leader := resilience.PickLeader([]string{"node-a", "node-b", "node-c"}, map[string]bool{"node-a": true, "node-b": true})
	if leader != "node-c" {
		t.Fatalf("unexpected leader after failover storm")
	}
	if resilience.OutageTier(25, 2) != "degraded" {
		t.Fatalf("expected degraded outage tier")
	}
}
