package integration

import (
	"math"
	"testing"

	"gridweaver/internal/resilience"
)

func TestChaosReplayOrderedVsShuffledConverges(t *testing.T) {
	ordered := []resilience.DispatchEvent{
		{Version: 11, IdempotencyKey: "k1", GenerationDelta: 30, ReserveDelta: 4},
		{Version: 12, IdempotencyKey: "k2", GenerationDelta: -10, ReserveDelta: 1},
		{Version: 13, IdempotencyKey: "k3", GenerationDelta: 8, ReserveDelta: -2},
	}
	shuffled := []resilience.DispatchEvent{ordered[2], ordered[0], ordered[1]}
	a := resilience.ReplayDispatch(500, 70, 10, ordered)
	b := resilience.ReplayDispatch(500, 70, 10, shuffled)
	if math.Abs(a.GenerationMW-b.GenerationMW) > 1e-9 || math.Abs(a.ReserveMW-b.ReserveMW) > 1e-9 || a.Version != b.Version {
		t.Fatalf("ordered and shuffled replay should converge")
	}
}

func TestChaosReplayRejectsStale(t *testing.T) {
	events := []resilience.DispatchEvent{
		{Version: 9, IdempotencyKey: "old", GenerationDelta: 100, ReserveDelta: 100},
		{Version: 10, IdempotencyKey: "eq", GenerationDelta: 5, ReserveDelta: 2},
	}
	s := resilience.ReplayDispatch(400, 50, 10, events)
	if s.Applied != 1 || s.GenerationMW != 405 || s.ReserveMW != 52 {
		t.Fatalf("stale event should be ignored")
	}
}

func TestChaosReplayIdempotencyCollision(t *testing.T) {
	events := []resilience.DispatchEvent{
		{Version: 11, IdempotencyKey: "dup", GenerationDelta: 5, ReserveDelta: 1},
		{Version: 12, IdempotencyKey: "dup", GenerationDelta: 100, ReserveDelta: 100},
		{Version: 13, IdempotencyKey: "ok", GenerationDelta: -2, ReserveDelta: 0},
	}
	s := resilience.ReplayDispatch(300, 40, 10, events)
	if s.Applied != 2 {
		t.Fatalf("expected deduped apply count 2")
	}
}

func TestChaosReplayStaleDuplicateDoesNotShadowFreshEvent(t *testing.T) {
	events := []resilience.DispatchEvent{
		{Version: 9, IdempotencyKey: "dup", GenerationDelta: 100, ReserveDelta: 100},
		{Version: 11, IdempotencyKey: "dup", GenerationDelta: 7, ReserveDelta: 3},
	}
	s := resilience.ReplayDispatch(300, 40, 10, events)
	if s.Applied != 1 || s.GenerationMW != 307 || s.ReserveMW != 43 {
		t.Fatalf("fresh event should not be shadowed by stale duplicate")
	}
}
