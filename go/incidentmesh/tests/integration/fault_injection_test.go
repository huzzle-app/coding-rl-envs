package integration

import (
	"testing"

	"incidentmesh/internal/resilience"
)

func TestQueueShedAtHardLimit(t *testing.T) {
	if !resilience.ShouldShedLoad(100, 100) {
		t.Fatalf("should shed at limit")
	}
}

func TestReplayWindowRejectsOldEvent(t *testing.T) {
	if resilience.ReplayWindowAccept(50, 200, 10) {
		t.Fatalf("should reject old event")
	}
}

func TestIdempotencyCollisionMerge(t *testing.T) {
	if resilience.MergeIdempotency([]string{"a", "b", "a", "c"}) != 3 {
		t.Fatalf("expected 3 unique")
	}
}

func TestFailureBurstPolicyTightening(t *testing.T) {
	p := resilience.NextQueuePolicy(7)
	if p.MaxInFlight != 8 {
		t.Fatalf("expected tight policy")
	}
}

func TestFaultExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"NoShed", func(t *testing.T) {
			if resilience.ShouldShedLoad(50, 100) {
				t.Fatalf("no shed expected")
			}
		}},
		{"WindowAccept", func(t *testing.T) {
			if !resilience.ReplayWindowAccept(190, 200, 15) {
				t.Fatalf("should accept")
			}
		}},
		{"MediumBurst", func(t *testing.T) {
			p := resilience.NextQueuePolicy(4)
			if p.MaxInFlight != 16 {
				t.Fatalf("expected medium policy")
			}
		}},
		{"LowBurst", func(t *testing.T) {
			p := resilience.NextQueuePolicy(1)
			if p.MaxInFlight != 32 {
				t.Fatalf("expected relaxed policy")
			}
		}},
		{"BatchDedup", func(t *testing.T) {
			d := resilience.BatchDedup([]string{"a", "b", "a", "c"})
			// Should deduplicate to 3 unique strings
			if len(d) != 3 { t.Fatalf("expected 3 unique items, got %d", len(d)) }
		}},
		{"EventChecksum", func(t *testing.T) {
			e := resilience.IncidentEvent{Version: 1, IdempotencyKey: "k1", PriorityDelta: 5}
			cs := resilience.EventChecksum(e)
			if cs == "" {
				t.Fatalf("expected non-empty")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
