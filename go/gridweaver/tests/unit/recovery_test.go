package unit

import (
	"testing"

	"gridweaver/internal/outage"
)

func TestOutagePriority(t *testing.T) {
	s := outage.PriorityScore(outage.OutageCase{Population: 24000, Critical: true, HoursDown: 4})
	if s < 300 {
		t.Fatalf("priority too low: %d", s)
	}
}

func TestOutageExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"RankOutages", func(t *testing.T) {
			cs := []outage.OutageCase{
				{Population: 1000, HoursDown: 1},
				{Population: 50000, Critical: true, HoursDown: 5},
				{Population: 5000, HoursDown: 3},
			}
			ranked := outage.RankOutages(cs)
			if len(ranked) != 3 {
				t.Fatalf("expected 3 ranked outages")
			}
		}},
		{"MergeOutages", func(t *testing.T) {
			a := []outage.OutageCase{{Population: 1000}}
			b := []outage.OutageCase{{Population: 2000}}
			merged := outage.MergeOutages(a, b)
			if len(merged) < 2 {
				t.Fatalf("expected at least 2 merged")
			}
		}},
		{"EstimateRestorationHours", func(t *testing.T) {
			c := outage.OutageCase{Population: 50000, Critical: true, HoursDown: 10}
			hours := outage.EstimateRestorationHours(c, 5)
			if hours < 0 {
				t.Fatalf("expected non-negative hours")
			}
		}},
		{"RecordRestoration", func(t *testing.T) {
			c := outage.OutageCase{Population: 1000, HoursDown: 10}
			c2 := outage.RecordRestoration(c, 3)
			if c2.HoursDown != 7 {
				t.Fatalf("expected 7 hours down, got %d", c2.HoursDown)
			}
		}},
		{"TotalAffected", func(t *testing.T) {
			cs := []outage.OutageCase{{Population: 1000}, {Population: 2000}}
			total := outage.TotalAffected(cs)
			if total != 3000 {
				t.Fatalf("expected 3000")
			}
		}},
		{"IsResolved", func(t *testing.T) {
			if !outage.IsResolved(outage.OutageCase{HoursDown: 0}) {
				t.Fatalf("expected resolved")
			}
			if outage.IsResolved(outage.OutageCase{HoursDown: 5}) {
				t.Fatalf("expected not resolved")
			}
		}},
		{"FilterCritical", func(t *testing.T) {
			cs := []outage.OutageCase{
				{Critical: true, Population: 1000},
				{Critical: false, Population: 2000},
			}
			crit := outage.FilterCritical(cs)
			if len(crit) != 1 {
				t.Fatalf("expected 1 critical")
			}
		}},
		{"FilterByMinPriority", func(t *testing.T) {
			cs := []outage.OutageCase{
				{Population: 100, HoursDown: 1},
				{Population: 50000, Critical: true, HoursDown: 5},
			}
			high := outage.FilterByMinPriority(cs, 100)
			if len(high) < 1 {
				t.Fatalf("expected at least 1 high-priority outage")
			}
		}},
		{"AveragePriority", func(t *testing.T) {
			cs := []outage.OutageCase{
				{Population: 10000, HoursDown: 2},
				{Population: 20000, HoursDown: 4},
			}
			avg := outage.AveragePriority(cs)
			if avg <= 0 {
				t.Fatalf("expected positive average priority")
			}
		}},
		{"EscalationLevelEmergency", func(t *testing.T) {
			if outage.EscalationLevel(10) != "emergency" {
				t.Fatalf("expected emergency")
			}
		}},
		{"EscalationLevelNormal", func(t *testing.T) {
			if outage.EscalationLevel(0) != "normal" {
				t.Fatalf("expected normal")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
