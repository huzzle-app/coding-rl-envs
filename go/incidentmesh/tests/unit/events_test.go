package unit

import (
	"testing"

	"incidentmesh/internal/events"
)

func TestEventsExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"NewEvent", func(t *testing.T) {
			e := events.NewEvent("alert", map[string]string{"key": "val"})
			if e.Type != "alert" {
				t.Fatalf("wrong type")
			}
		}},
		{"FilterByType", func(t *testing.T) {
			evs := []events.Event{{Type: "alert"}, {Type: "info"}, {Type: "alert"}}
			f := events.FilterByType(evs, "alert")
			if len(f) != 2 { t.Fatalf("expected 2 alert events, got %d", len(f)) }
		}},
		{"WindowEvents", func(t *testing.T) {
			evs := []events.Event{{Timestamp: 10}, {Timestamp: 20}, {Timestamp: 30}}
			w := events.WindowEvents(evs, 10, 25)
			if len(w) < 1 {
				t.Fatalf("expected events")
			}
		}},
		{"WindowEmpty", func(t *testing.T) {
			w := events.WindowEvents(nil, 0, 100)
			if len(w) != 0 {
				t.Fatalf("expected empty")
			}
		}},
		{"CountByType", func(t *testing.T) {
			evs := []events.Event{{Type: "a"}, {Type: "b"}, {Type: "a"}}
			c := events.CountByType(evs)
			if c["a"] != 2 { t.Fatalf("expected count['a']=2, got %d", c["a"]) }
			if c["b"] != 1 { t.Fatalf("expected count['b']=1, got %d", c["b"]) }
		}},
		{"CorrelateEvents", func(t *testing.T) {
			evs := []events.Event{
				{Data: map[string]string{"cid": "c1"}},
				{Data: map[string]string{"cid": "c2"}},
			}
			c := events.CorrelateEvents(evs, "cid")
			if len(c) < 1 {
				t.Fatalf("expected groups")
			}
		}},
		{"Deduplicate", func(t *testing.T) {
			evs := []events.Event{{ID: "e1"}, {ID: "e2"}, {ID: "e1"}}
			d := events.Deduplicate(evs)
			if len(d) != 2 { t.Fatalf("expected 2 unique events, got %d", len(d)) }
		}},
		{"DeduplicateNoDups", func(t *testing.T) {
			evs := []events.Event{{ID: "e1"}, {ID: "e2"}}
			d := events.Deduplicate(evs)
			if len(d) != 2 {
				t.Fatalf("expected 2")
			}
		}},
		{"LatestEvent", func(t *testing.T) {
			evs := []events.Event{{ID: "e1", Timestamp: 10}, {ID: "e2", Timestamp: 20}}
			latest := events.LatestEvent(evs)
			if latest == nil {
				t.Fatalf("expected non-nil")
			}
		}},
		{"LatestEmpty", func(t *testing.T) {
			if events.LatestEvent(nil) != nil {
				t.Fatalf("expected nil")
			}
		}},
		{"FilterEmpty", func(t *testing.T) {
			f := events.FilterByType(nil, "alert")
			if len(f) != 0 {
				t.Fatalf("expected empty")
			}
		}},
		{"CorrelateEmpty", func(t *testing.T) {
			c := events.CorrelateEvents(nil, "cid")
			if len(c) != 0 {
				t.Fatalf("expected empty")
			}
		}},
		{"CountEmpty", func(t *testing.T) {
			c := events.CountByType(nil)
			if len(c) != 0 {
				t.Fatalf("expected empty")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
