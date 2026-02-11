package chaos

import (
	"ironfleet/internal/resilience"
	"reflect"
	"testing"
)

func TestReplayLatestSequenceWins(t *testing.T) {
	out := resilience.Replay([]resilience.Event{{ID: "x", Sequence: 1}, {ID: "x", Sequence: 2}})
	if len(out) != 1 || out[0].Sequence != 2 {
		t.Fatalf("unexpected replay output: %+v", out)
	}
}

func TestReplayOrderedAndShuffledConverge(t *testing.T) {
	a := resilience.Replay([]resilience.Event{{ID: "k", Sequence: 1}, {ID: "k", Sequence: 2}})
	b := resilience.Replay([]resilience.Event{{ID: "k", Sequence: 2}, {ID: "k", Sequence: 1}})
	if !reflect.DeepEqual(a, b) {
		t.Fatalf("expected replay equivalence")
	}
}
