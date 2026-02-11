package unit

import (
	"testing"

	"gridweaver/internal/concurrency"
)

func TestConcurrencyExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"SemaphoreAcquire", func(t *testing.T) {
			result := concurrency.SemaphoreAcquire(3, 5)
			_ = result
		}},
		{"RateLimiterPermit", func(t *testing.T) {
			result := concurrency.RateLimiterPermit(5, 10)
			_ = result
		}},
		{"RateLimiterPermitZero", func(t *testing.T) {
			result := concurrency.RateLimiterPermit(0, 10)
			if result {
				t.Fatalf("expected no permit with 0 tokens")
			}
		}},
		{"NewPool", func(t *testing.T) {
			p := concurrency.NewPool(4)
			if p == nil {
				t.Fatalf("expected non-nil pool")
			}
		}},
		{"WorkItemFields", func(t *testing.T) {
			item := concurrency.WorkItem{ID: "w1", Payload: "data"}
			if item.ID != "w1" {
				t.Fatalf("expected ID w1")
			}
		}},
		{"ResultFields", func(t *testing.T) {
			r := concurrency.Result{ID: "r1", Output: "done"}
			if r.ID != "r1" || r.Output != "done" {
				t.Fatalf("unexpected result fields")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
