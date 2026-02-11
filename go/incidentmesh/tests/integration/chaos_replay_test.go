package integration

import (
	"testing"

	"incidentmesh/internal/resilience"
)

func TestChaosReplayOrderedVsShuffledConverges(t *testing.T) {
	events := []resilience.IncidentEvent{
		{Version: 1, IdempotencyKey: "k1", PriorityDelta: 5, ActiveUnitsDelta: 1},
		{Version: 2, IdempotencyKey: "k2", PriorityDelta: 3, ActiveUnitsDelta: 2},
	}
	ordered := resilience.ReplayIncidentState(0, 0, 0, events)
	shuffled := resilience.ReplayIncidentState(0, 0, 0, []resilience.IncidentEvent{events[1], events[0]})
	if ordered.Priority != shuffled.Priority {
		t.Fatalf("convergence failure")
	}
}

func TestChaosReplayRejectsStale(t *testing.T) {
	events := []resilience.IncidentEvent{{Version: 1, IdempotencyKey: "k1", PriorityDelta: 10, ActiveUnitsDelta: 1}}
	s := resilience.ReplayIncidentState(0, 0, 5, events)
	if s.Applied != 0 {
		t.Fatalf("stale events should be rejected")
	}
}

func TestReplayExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"IdempotencyCollision", func(t *testing.T) {
			events := []resilience.IncidentEvent{
				{Version: 1, IdempotencyKey: "same", PriorityDelta: 5},
				{Version: 2, IdempotencyKey: "same", PriorityDelta: 3},
			}
			s := resilience.ReplayIncidentState(0, 0, 0, events)
			if s.Applied != 1 {
				t.Fatalf("should deduplicate")
			}
		}},
		{"EmptyEvents", func(t *testing.T) {
			s := resilience.ReplayIncidentState(10, 5, 0, nil)
			if s.Priority != 10 || s.ActiveUnits != 5 {
				t.Fatalf("base should remain")
			}
		}},
		{"RetryBackoff", func(t *testing.T) {
			d := resilience.RetryWithBackoff(3, 100)
			// 3rd attempt with base 100 should have delay > 100
			if d <= 100 { t.Fatalf("expected backoff delay > 100 for attempt 3, got %d", d) }
		}},
		{"IdempCheck", func(t *testing.T) {
			seen := map[string]bool{"k1": true}
			r := resilience.IdempotencyCheck("k2", seen)
			// k2 not in seen, so should return true (new key)
			if !r { t.Fatalf("expected true for new idempotency key") }
		}},
		{"VersionCheck", func(t *testing.T) {
			r := resilience.EventVersionCheck(5, 3)
			// Event version 5 > current version 3, so should be valid
			if !r { t.Fatalf("expected true for newer event version") }
		}},
		{"SnapshotMerge", func(t *testing.T) {
			a := resilience.IncidentSnapshot{Priority: 10, Version: 5}
			b := resilience.IncidentSnapshot{Priority: 20, Version: 8}
			m := resilience.SnapshotMerge(a, b)
			// Should take higher version's state
			if m.Version != 8 { t.Fatalf("expected version 8 after merge, got %d", m.Version) }
		}},
		{"QueueDepth", func(t *testing.T) {
			d := resilience.QueueDepth(5, 10)
			
			if d != 15 { t.Fatalf("expected queue depth 15 (5+10), got %d", d) }
		}},
		{"ReplayFilter", func(t *testing.T) {
			events := []resilience.IncidentEvent{{Version: 1}, {Version: 5}, {Version: 10}}
			f := resilience.ReplayFilter(events, 5)
			// Filter events with version > 5, should get version 10 only
			if len(f) != 1 { t.Fatalf("expected 1 event after filter (version > 5), got %d", len(f)) }
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
