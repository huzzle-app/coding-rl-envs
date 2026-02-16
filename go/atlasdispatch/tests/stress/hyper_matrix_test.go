package stress

import (
	"atlasdispatch/internal/allocator"
	"atlasdispatch/internal/policy"
	"atlasdispatch/internal/queue"
	"atlasdispatch/internal/resilience"
	"atlasdispatch/internal/routing"
	"atlasdispatch/internal/security"
	"atlasdispatch/internal/statistics"
	"atlasdispatch/internal/workflow"
	"atlasdispatch/pkg/models"
	"fmt"
	"testing"
)

const totalCases = 9200

func TestHyperMatrix(t *testing.T) {
	for i := 0; i < totalCases; i++ {
		i := i
		t.Run(fmt.Sprintf("case_%05d", i), func(t *testing.T) {
			severityA := (i % 7) + 1
			severityB := ((i * 3) % 7) + 1
			slaA := 20 + (i % 90)
			slaB := 20 + ((i * 2) % 90)

			orderA := models.DispatchOrder{ID: fmt.Sprintf("a-%d", i), Severity: severityA, SLAMinutes: slaA}
			orderB := models.DispatchOrder{ID: fmt.Sprintf("b-%d", i), Severity: severityB, SLAMinutes: slaB}

			planned := allocator.PlanDispatch([]allocator.Order{
				{ID: orderA.ID, Urgency: orderA.UrgencyScore(), ETA: fmt.Sprintf("0%d:1%d", i%9, i%6)},
				{ID: orderB.ID, Urgency: orderB.UrgencyScore(), ETA: fmt.Sprintf("0%d:2%d", (i+3)%9, i%6)},
				{ID: fmt.Sprintf("c-%d", i), Urgency: (i % 50) + 2, ETA: fmt.Sprintf("1%d:0%d", i%4, i%6)},
			}, 2)
			if len(planned) == 0 || len(planned) > 2 {
				t.Fatalf("invalid planned size: %d", len(planned))
			}
			if len(planned) == 2 && planned[0].Urgency < planned[1].Urgency {
				t.Fatalf("urgency ordering violated: %+v", planned)
			}

			blocked := map[string]bool{}
			if i%5 == 0 {
				blocked["beta"] = true
			}
			route := routing.ChooseRoute([]routing.Route{
				{Channel: "alpha", Latency: 2 + (i % 9)},
				{Channel: "beta", Latency: i % 3},
				{Channel: "gamma", Latency: 4 + (i % 4)},
			}, blocked)
			if route == nil {
				t.Fatal("expected route")
			}
			if blocked["beta"] && route.Channel == "beta" {
				t.Fatal("blocked route selected")
			}

			src := "queued"
			dst := "allocated"
			if i%2 == 1 {
				src = "allocated"
				dst = "departed"
			}
			if !workflow.CanTransition(src, dst) {
				t.Fatalf("invalid transition %s -> %s", src, dst)
			}
			if workflow.CanTransition("arrived", "queued") {
				t.Fatal("unexpected arrived -> queued")
			}

			startPol := "normal"
			if i%2 != 0 {
				startPol = "watch"
			}
			burst := 2 + (i % 2) // even: 2, odd: 3
			pol := policy.NextPolicy(startPol, burst)
			// NextPolicy should respect per-level thresholds (normal=3, watch=3)
			switch {
			case startPol == "normal" && burst == 2:
				if pol != "normal" {
					t.Fatalf("NextPolicy(normal, 2): burst below threshold (3), should not escalate, got %s", pol)
				}
			case startPol == "watch" && burst == 3:
				if pol != "restricted" {
					t.Fatalf("NextPolicy(watch, 3): burst at threshold, should escalate to restricted, got %s", pol)
				}
			}

			depth := (i % 30) + 1
			if queue.ShouldShed(depth, 40, false) {
				t.Fatal("unexpected shed")
			}
			if !queue.ShouldShed(41, 40, false) {
				t.Fatal("expected shed")
			}

			replayed := resilience.Replay([]resilience.Event{
				{ID: fmt.Sprintf("k-%d", i%17), Sequence: 1},
				{ID: fmt.Sprintf("k-%d", i%17), Sequence: 2},
				{ID: fmt.Sprintf("z-%d", i%13), Sequence: 1},
			})
			if len(replayed) < 2 {
				t.Fatalf("replay too small: %+v", replayed)
			}

			p50 := statistics.Percentile([]int{i % 11, (i * 7) % 11, (i * 5) % 11, (i * 3) % 11}, 50)
			if p50 < 0 {
				t.Fatalf("invalid percentile: %d", p50)
			}

			if i%17 == 0 {
				payload := fmt.Sprintf("manifest:%d", i)
				digest := security.Digest(payload)
				if !security.VerifySignature(payload, digest, digest) {
					t.Fatal("expected valid signature")
				}
				if security.VerifySignature(payload, digest[1:], digest) {
					t.Fatal("expected invalid signature")
				}
			}
		})
	}
}
