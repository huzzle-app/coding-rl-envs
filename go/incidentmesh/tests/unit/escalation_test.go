package unit

import (
	"testing"
	"incidentmesh/internal/escalation"
)

func TestEscalationDecision(t *testing.T) {
	if !escalation.ShouldEscalate(120, 1, 3) { t.Fatalf("expected escalation") }
}

func TestEscalationExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"NoEscalation", func(t *testing.T) {
			if escalation.ShouldEscalate(50, 5, 3) { t.Fatalf("no escalation expected") }
		}},
		{"ResourceGap", func(t *testing.T) {
			if !escalation.ShouldEscalate(50, 1, 3) { t.Fatalf("expected escalation") }
		}},
		{"Level0", func(t *testing.T) {
			if escalation.EscalationLevel(30) != 0 { t.Fatalf("expected level 0") }
		}},
		{"Level1", func(t *testing.T) {
			lv := escalation.EscalationLevel(80)
			if lv != 1 { t.Fatalf("expected level 1") }
		}},
		{"Level2", func(t *testing.T) {
			lv := escalation.EscalationLevel(120)
			if lv != 2 { t.Fatalf("expected level 2") }
		}},
		{"Level150", func(t *testing.T) {
			lv := escalation.EscalationLevel(150)
			
			if lv != 3 { t.Fatalf("expected level 3 at priority 150, got %d", lv) }
		}},
		{"BatchEsc", func(t *testing.T) {
			r := escalation.BatchEscalation([]int{50,100,150}, 100)
			if len(r) != 3 { t.Fatalf("expected 3") }
		}},
		{"TimeBased", func(t *testing.T) {
			r := escalation.TimeBasedEscalation(120, 5)
			
			if !r { t.Fatalf("expected escalation for high severity after long time") }
		}},
		{"TimeBasedLow", func(t *testing.T) {
			if escalation.TimeBasedEscalation(30, 1) { t.Fatalf("too early to escalate") }
		}},
		{"Chain", func(t *testing.T) {
			idx := escalation.EscalationChain(75, []int{50,100,150})
			
			if idx != 1 { t.Fatalf("expected chain index 1 for priority 75, got %d", idx) }
		}},
		{"ChainEmpty", func(t *testing.T) {
			if escalation.EscalationChain(100, nil) != 0 { t.Fatalf("expected 0") }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
