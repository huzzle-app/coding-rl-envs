package unit_test

import (
	"reflect"
	"testing"

	"quorumledger/internal/replay"
)

func TestReplayBudget(t *testing.T) {
	if replay.ReplayBudget(0, 3) != 0 {
		t.Fatalf("expected zero budget")
	}
	if replay.ReplayBudget(100, 4) != 52 {
		t.Fatalf("unexpected replay budget")
	}
}

func TestDeduplicateIDs(t *testing.T) {
	out := replay.DeduplicateIDs([]string{"a", "b", "a", "c", "b"})
	if !reflect.DeepEqual(out, []string{"a", "b", "c"}) {
		t.Fatalf("unexpected dedupe output: %#v", out)
	}
}

func TestReplayWindow(t *testing.T) {
	events := []replay.ReplayEvent{
		{ID: "e1", Sequence: 1},
		{ID: "e2", Sequence: 5},
		{ID: "e3", Sequence: 10},
		{ID: "e4", Sequence: 15},
	}
	window := replay.ReplayWindow(events, 5, 15)
	if len(window) != 2 {
		t.Fatalf("expected 2 events in window [5,15), got %d", len(window))
	}
}

func TestEventOrdering(t *testing.T) {
	ordered := []replay.ReplayEvent{{ID: "a", Sequence: 1}, {ID: "b", Sequence: 1}, {ID: "c", Sequence: 2}}
	if !replay.EventOrdering(ordered) {
		t.Fatalf("expected events with equal sequences to be considered ordered")
	}
}

func TestCompactLog(t *testing.T) {
	events := []replay.ReplayEvent{
		{ID: "a", Sequence: 1},
		{ID: "a", Sequence: 5},
		{ID: "b", Sequence: 3},
	}
	compacted := replay.CompactLog(events)
	if len(compacted) != 2 {
		t.Fatalf("expected 2 compacted events, got %d", len(compacted))
	}
}

func TestCheckpointInterval(t *testing.T) {
	if replay.CheckpointInterval(100, 10) != 10 {
		t.Fatalf("expected interval 10 for 100/10")
	}
	if replay.CheckpointInterval(100, 0) != 100 {
		t.Fatalf("expected full count for 0 checkpoints")
	}
}
