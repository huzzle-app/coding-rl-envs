package unit_test

import (
	"testing"

	"quorumledger/internal/policy"
	"quorumledger/pkg/models"
)

func TestEscalationLevel(t *testing.T) {
	if policy.EscalationLevel(5, 5) != models.PolicyHalted {
		t.Fatalf("expected halted for 25 score")
	}
	if policy.EscalationLevel(1, 1) != models.PolicyNormal {
		t.Fatalf("expected normal for score 1")
	}
}

func TestNextEscalation(t *testing.T) {
	next := policy.NextEscalation(models.PolicyNormal)
	if next != models.PolicyRestricted {
		t.Fatalf("expected restricted after normal+2, got %d", next)
	}
	if policy.NextEscalation(models.PolicyHalted) != models.PolicyHalted {
		t.Fatalf("expected halted to stay halted")
	}
}

func TestShouldHoldTransaction(t *testing.T) {
	if !policy.ShouldHoldTransaction(1000000, models.PolicyHalted) {
		t.Fatalf("expected hold at halted level")
	}
	if policy.ShouldHoldTransaction(100, models.PolicyWatch) {
		t.Fatalf("unexpected hold for small amount at watch")
	}
}

func TestExposureBand(t *testing.T) {
	if policy.ExposureBand(10000000) != "critical" {
		t.Fatalf("expected critical for 10M, got %s", policy.ExposureBand(10000000))
	}
	if policy.ExposureBand(500000) != "medium" {
		t.Fatalf("expected medium for 500k")
	}
}
