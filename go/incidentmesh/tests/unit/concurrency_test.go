package unit

import (
	"sync/atomic"
	"testing"

	"incidentmesh/internal/concurrency"
)

func TestConcurrencyExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"NewPool", func(t *testing.T) {
			p := concurrency.NewWorkerPool(4)
			if p == nil {
				t.Fatalf("expected non-nil")
			}
		}},
		{"NewPoolZero", func(t *testing.T) {
			p := concurrency.NewWorkerPool(0)
			// Pool with 0 workers should still be created (with default or min 1)
			if p == nil { t.Fatalf("expected non-nil pool even with 0 workers") }
		}},
		{"Submit", func(t *testing.T) {
			p := concurrency.NewWorkerPool(2)
			tasks := []func() string{func() string { return "a" }, func() string { return "b" }}
			results := p.Submit(tasks)
			if len(results) != 2 {
				t.Fatalf("expected 2")
			}
		}},
		{"FanOutSafe", func(t *testing.T) {
			r := concurrency.FanOut(1, func(i int) string { return "ok" })
			if len(r) != 1 {
				t.Fatalf("expected 1")
			}
		}},
		{"SafeCounterInc", func(t *testing.T) {
			c := &concurrency.SafeCounter{}
			c.Inc()
			_ = c.Value()
		}},
		{"SafeCounterValue", func(t *testing.T) {
			c := &concurrency.SafeCounter{}
			if c.Value() != 0 {
				t.Fatalf("expected 0")
			}
		}},
		{"PipelineSingle", func(t *testing.T) {
			upper := func(s string) string { return s + "!" }
			r := concurrency.Pipeline([]string{"a", "b"}, upper)
			if len(r) != 2 {
				t.Fatalf("expected 2")
			}
		}},
		{"PipelineEmpty", func(t *testing.T) {
			r := concurrency.Pipeline(nil)
			if len(r) != 0 {
				t.Fatalf("expected empty")
			}
		}},
		{"Throttle", func(t *testing.T) {
			fn := func(s string) string { return s + "_done" }
			r := concurrency.Throttle([]string{"a", "b", "c"}, 2, fn)
			if len(r) != 3 {
				t.Fatalf("expected 3")
			}
		}},
		{"MergeResults", func(t *testing.T) {
			ch1 := make(chan string, 1)
			ch1 <- "val1"
			r := concurrency.MergeResults(ch1)
			if len(r) != 1 {
				t.Fatalf("expected 1")
			}
		}},
		{"AtomicMax", func(t *testing.T) {
			var v int64 = 5
			concurrency.AtomicMax(&v, 10)
			if atomic.LoadInt64(&v) <= 0 {
				t.Fatalf("expected positive")
			}
		}},
		{"AtomicMaxLower", func(t *testing.T) {
			var v int64 = 10
			concurrency.AtomicMax(&v, 5)
			// When new value (5) is less than current (10), value should stay at 10
			if atomic.LoadInt64(&v) != 10 { t.Fatalf("expected 10, got %d", atomic.LoadInt64(&v)) }
		}},
		{"SubmitEmpty", func(t *testing.T) {
			p := concurrency.NewWorkerPool(1)
			r := p.Submit(nil)
			if len(r) != 0 {
				t.Fatalf("expected empty")
			}
		}},
		{"ThrottleEmpty", func(t *testing.T) {
			r := concurrency.Throttle(nil, 2, func(s string) string { return s })
			if len(r) != 0 {
				t.Fatalf("expected empty")
			}
		}},
		{"PipelineMulti", func(t *testing.T) {
			s1 := func(s string) string { return s + "1" }
			s2 := func(s string) string { return s + "2" }
			r := concurrency.Pipeline([]string{"x"}, s1, s2)
			if len(r) != 1 {
				t.Fatalf("expected 1")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
