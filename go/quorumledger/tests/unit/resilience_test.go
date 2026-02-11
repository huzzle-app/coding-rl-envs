package unit_test

import (
	"testing"

	"quorumledger/internal/resilience"
)

func TestPickLeader(t *testing.T) {
	leader := resilience.PickLeader([]string{"node-c", "node-a", "node-b"}, map[string]bool{"node-a": true})
	if leader != "node-b" {
		t.Fatalf("unexpected leader: %s", leader)
	}
}

func TestOutageTier(t *testing.T) {
	if resilience.OutageTier(2, 1) != "minor" {
		t.Fatalf("expected minor")
	}
	if resilience.OutageTier(60, 4) != "critical" {
		t.Fatalf("expected critical")
	}
}

func TestCircuitBreakerState(t *testing.T) {
	if resilience.CircuitBreakerState(10, 10) != "open" {
		t.Fatalf("expected open at threshold")
	}
	if resilience.CircuitBreakerState(5, 10) != "half-open" {
		t.Fatalf("expected half-open at threshold/2")
	}
	if resilience.CircuitBreakerState(2, 10) != "closed" {
		t.Fatalf("expected closed below half threshold")
	}
}

func TestRetryBackoff(t *testing.T) {
	if resilience.RetryBackoff(0, 100) != 100 {
		t.Fatalf("expected base for attempt 0")
	}
	if resilience.RetryBackoff(1, 100) != 200 {
		t.Fatalf("expected 200 for attempt 1, got %d", resilience.RetryBackoff(1, 100))
	}
	if resilience.RetryBackoff(2, 100) != 400 {
		t.Fatalf("expected 400 for attempt 2")
	}
}

func TestPartitionSeverity(t *testing.T) {
	if resilience.PartitionSeverity(5, 10) != "critical" {
		t.Fatalf("expected critical for 50%% partition")
	}
	if resilience.PartitionSeverity(1, 10) != "minor" {
		t.Fatalf("expected minor for 10%% partition")
	}
}
