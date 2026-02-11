package unit

import (
	"testing"

	"gridweaver/internal/events"
)

func TestEventsExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"SortBySequence", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e3", Sequence: 30},
				{ID: "e1", Sequence: 10},
				{ID: "e2", Sequence: 20},
			}
			sorted := events.SortBySequence(evts)
			if len(sorted) != 3 {
				t.Fatalf("expected 3 events")
			}
		}},
		{"DeduplicateEvents", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Sequence: 10},
				{ID: "e2", Sequence: 20},
				{ID: "e1", Sequence: 30},
			}
			deduped := events.DeduplicateEvents(evts)
			if len(deduped) != 2 {
				t.Fatalf("expected 2 deduped events, got %d", len(deduped))
			}
		}},
		{"FilterByType", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Type: "dispatch"},
				{ID: "e2", Type: "outage"},
				{ID: "e3", Type: "dispatch"},
			}
			filtered := events.FilterByType(evts, "dispatch")
			_ = filtered 
		}},
		{"FilterByRegion", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Region: "west"},
				{ID: "e2", Region: "east"},
				{ID: "e3", Region: "west"},
			}
			filtered := events.FilterByRegion(evts, "west")
			if len(filtered) < 1 {
				t.Fatalf("expected at least 1 west event")
			}
		}},
		{"WindowEvents", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Sequence: 5},
				{ID: "e2", Sequence: 10},
				{ID: "e3", Sequence: 15},
				{ID: "e4", Sequence: 20},
			}
			window := events.WindowEvents(evts, 10, 20)
			if len(window) < 1 {
				t.Fatalf("expected events in window")
			}
		}},
		{"LastEventPerRegion", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Sequence: 10, Region: "west"},
				{ID: "e2", Sequence: 20, Region: "west"},
				{ID: "e3", Sequence: 15, Region: "east"},
			}
			last := events.LastEventPerRegion(evts)
			if len(last) != 2 {
				t.Fatalf("expected 2 regions")
			}
		}},
		{"CountByType", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Type: "dispatch"},
				{ID: "e2", Type: "outage"},
			}
			counts := events.CountByType(evts)
			_ = counts 
		}},
		{"SequenceGaps", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Sequence: 10},
				{ID: "e2", Sequence: 15},
				{ID: "e3", Sequence: 20},
			}
			gaps := events.SequenceGaps(evts)
			_ = gaps 
		}},
		{"MaxSequence", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Sequence: 10},
				{ID: "e2", Sequence: 30},
				{ID: "e3", Sequence: 20},
			}
			max := events.MaxSequence(evts)
			if max != 30 {
				t.Fatalf("expected max sequence 30, got %d", max)
			}
		}},
		{"MaxSequenceEmpty", func(t *testing.T) {
			max := events.MaxSequence(nil)
			if max != 0 {
				t.Fatalf("expected 0 for nil events")
			}
		}},
		{"GroupByRegion", func(t *testing.T) {
			evts := []events.Event{
				{ID: "e1", Region: "west"},
				{ID: "e2", Region: "east"},
				{ID: "e3", Region: "west"},
			}
			groups := events.GroupByRegion(evts)
			if len(groups) != 2 {
				t.Fatalf("expected 2 groups")
			}
			if len(groups["west"]) != 2 {
				t.Fatalf("expected 2 west events")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
