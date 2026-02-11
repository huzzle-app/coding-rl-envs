package unit_test

import (
	"testing"

	"quorumledger/internal/reconciliation"
	"quorumledger/pkg/models"
)

func TestComputeDrift(t *testing.T) {
	entries := []models.ReconciliationEntry{
		{Account: "a", Expected: 1000, Actual: 1100},
		{Account: "b", Expected: 500, Actual: 500},
	}
	drift := reconciliation.ComputeDrift(entries)
	if drift != 100 {
		t.Fatalf("expected drift 100, got %d", drift)
	}
}

func TestDriftExceedsThreshold(t *testing.T) {
	entries := []models.ReconciliationEntry{
		{Account: "a", Expected: 1000, Actual: 1200},
	}
	if !reconciliation.DriftExceedsThreshold(entries, 100) {
		t.Fatalf("expected drift to exceed threshold 100")
	}
	if reconciliation.DriftExceedsThreshold(entries, 200) {
		t.Fatalf("drift should not exceed threshold 200")
	}
}

func TestReconciliationStatus(t *testing.T) {
	balanced := reconciliation.ReconciliationReport{Matched: 5, Unmatched: 0, NetDrift: 0}
	if reconciliation.ReconciliationStatus(balanced) != "balanced" {
		t.Fatalf("expected balanced status")
	}
}

func TestUnmatchedEntries(t *testing.T) {
	expected := []models.LedgerEntry{{ID: "e1"}, {ID: "e2"}, {ID: "e3"}}
	actual := []models.LedgerEntry{{ID: "e1"}, {ID: "e3"}}
	unmatched := reconciliation.UnmatchedEntries(expected, actual)
	if len(unmatched) != 1 || unmatched[0] != "e2" {
		t.Fatalf("expected e2 unmatched, got %v", unmatched)
	}
}
