package integration

import (
	"testing"

	"gridweaver/internal/demandresponse"
	"gridweaver/internal/outage"
)

func TestReliabilityFlow(t *testing.T) {
	p := demandresponse.Program{CommittedMW: 10, MaxMW: 40}
	p = demandresponse.ApplyDispatch(p, 20)
	if p.CommittedMW != 30 {
		t.Fatalf("unexpected committed MW")
	}
	score := outage.PriorityScore(outage.OutageCase{Population: 12000, Critical: true, HoursDown: 3})
	if score < 200 {
		t.Fatalf("expected elevated outage score")
	}
}

func TestReliabilityFlowNoOvercommit(t *testing.T) {
	p := demandresponse.Program{CommittedMW: 30, MaxMW: 40}
	p2 := demandresponse.ApplyDispatch(p, 20)
	if p2.CommittedMW != 30 {
		t.Fatalf("should not overcommit")
	}
}

func TestReliabilityExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"OutageAndDR", func(t *testing.T) {
			oc := outage.OutageCase{Population: 25000, Critical: true, HoursDown: 6}
			score := outage.PriorityScore(oc)
			if score < 100 {
				t.Fatalf("expected high score for critical outage")
			}
			p := demandresponse.Program{CommittedMW: 0, MaxMW: 200}
			p = demandresponse.ApplyDispatch(p, 50)
			if p.CommittedMW != 50 {
				t.Fatalf("expected 50 committed")
			}
		}},
		{"DRFullCapacity", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 95, MaxMW: 100}
			p2 := demandresponse.ApplyDispatch(p, 5)
			if p2.CommittedMW != 100 {
				t.Fatalf("expected full commit")
			}
			if !demandresponse.IsFullyCommitted(p2) {
				t.Fatalf("expected fully committed")
			}
		}},
		{"OutageEscalation", func(t *testing.T) {
			if outage.EscalationLevel(7) != "elevated" {
				t.Fatalf("expected elevated for 7 outages")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
