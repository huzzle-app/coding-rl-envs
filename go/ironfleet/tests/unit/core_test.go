package unit

import (
	"ironfleet/internal/allocator"
	"ironfleet/internal/policy"
	"ironfleet/internal/queue"
	"ironfleet/internal/routing"
	"ironfleet/internal/security"
	"ironfleet/internal/statistics"
	"ironfleet/internal/workflow"
	"ironfleet/pkg/models"
	"testing"
)

func TestPlanDispatchRespectsCapacity(t *testing.T) {
	out := allocator.PlanDispatch([]allocator.Order{
		{ID: "a", Urgency: 1, ETA: "09:30"},
		{ID: "b", Urgency: 3, ETA: "10:00"},
		{ID: "c", Urgency: 3, ETA: "08:30"},
	}, 2)
	if len(out) != 2 || out[0].ID != "c" || out[1].ID != "b" {
		t.Fatalf("unexpected dispatch ordering: %+v", out)
	}
}

func TestChooseRouteIgnoresBlocked(t *testing.T) {
	r := routing.ChooseRoute([]routing.Route{{Channel: "alpha", Latency: 8}, {Channel: "beta", Latency: 2}}, map[string]bool{"beta": true})
	if r == nil || r.Channel != "alpha" {
		t.Fatalf("unexpected route: %+v", r)
	}
}

func TestNextPolicyEscalates(t *testing.T) {
	if got := policy.NextPolicy("watch", 3); got != "restricted" {
		t.Fatalf("expected restricted, got %s", got)
	}
}

func TestVerifySignatureDigest(t *testing.T) {
	sig := security.Digest("manifest:v1")
	if !security.VerifySignature("manifest:v1", sig, sig) {
		t.Fatal("expected valid signature")
	}
	if security.VerifySignature("manifest:v1", sig[:len(sig)-1], sig) {
		t.Fatal("expected invalid signature")
	}
}

func TestShouldShedHardLimit(t *testing.T) {
	if queue.ShouldShed(9, 10, false) {
		t.Fatal("should not shed")
	}
	if !queue.ShouldShed(11, 10, false) {
		t.Fatal("should shed")
	}
	if !queue.ShouldShed(8, 10, true) {
		t.Fatal("should shed under emergency")
	}
}

func TestPercentileSparse(t *testing.T) {
	if got := statistics.Percentile([]int{4, 1, 9, 7}, 50); got != 4 {
		t.Fatalf("expected 4, got %d", got)
	}
	if got := statistics.Percentile(nil, 90); got != 0 {
		t.Fatalf("expected 0, got %d", got)
	}
}

func TestTransitionAllowed(t *testing.T) {
	if !workflow.CanTransition("queued", "allocated") {
		t.Fatal("expected transition")
	}
	if workflow.CanTransition("queued", "arrived") {
		t.Fatal("unexpected transition")
	}
}

func TestDispatchOrderUrgency(t *testing.T) {
	order := models.DispatchOrder{ID: "x", Severity: 3, SLAMinutes: 30}
	if order.UrgencyScore() != 120 {
		t.Fatalf("unexpected urgency: %d", order.UrgencyScore())
	}
}
