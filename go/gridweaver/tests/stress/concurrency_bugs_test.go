package stress

import (
	"fmt"
	"sync"
	"testing"

	"gridweaver/internal/concurrency"
	"gridweaver/internal/workflow"
)

func TestConcurrencyBugs(t *testing.T) {

	t.Run("ParallelReduce_Sum", func(t *testing.T) {
		items := []int{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
		result := concurrency.ParallelReduce(items,
			func(v int) int { return v * 2 },
			func(a, b int) int { return a + b },
			0,
		)
		// Expected: sum of 2+4+6+8+10+12+14+16+18+20 = 110
		if result != 110 {
			t.Fatalf("expected 110, got %d", result)
		}
	})

	t.Run("ParallelReduce_EmptyInput", func(t *testing.T) {
		result := concurrency.ParallelReduce(nil,
			func(v int) int { return v },
			func(a, b int) int { return a + b },
			42,
		)
		if result != 42 {
			t.Fatalf("empty input should return initial value 42, got %d", result)
		}
	})

	t.Run("ParallelMap_CorrectResults", func(t *testing.T) {
		items := []string{"hello", "world", "foo"}
		results := concurrency.ParallelMap(items, func(s string) string {
			return s + "!"
		})
		expected := []string{"hello!", "world!", "foo!"}
		for i, r := range results {
			if r != expected[i] {
				t.Fatalf("index %d: expected %s, got %s", i, expected[i], r)
			}
		}
	})

	t.Run("ParallelMap_PreservesOrder", func(t *testing.T) {
		items := make([]string, 100)
		for i := range items {
			items[i] = fmt.Sprintf("item_%d", i)
		}
		results := concurrency.ParallelMap(items, func(s string) string { return s })
		for i, r := range results {
			if r != items[i] {
				t.Fatalf("order not preserved at index %d: expected %s, got %s", i, items[i], r)
			}
		}
	})

	t.Run("BoundedBuffer_FIFO", func(t *testing.T) {
		buf := concurrency.NewBoundedBuffer(3)
		buf.Put("a")
		buf.Put("b")
		buf.Put("c")
		v, ok := buf.Get()
		if !ok || v != "a" {
			t.Fatalf("expected 'a', got '%s'", v)
		}
		v, _ = buf.Get()
		if v != "b" {
			t.Fatalf("expected 'b', got '%s'", v)
		}
	})

	t.Run("BoundedBuffer_RejectsFull", func(t *testing.T) {
		buf := concurrency.NewBoundedBuffer(2)
		buf.Put("a")
		buf.Put("b")
		ok := buf.Put("c")
		if ok {
			t.Fatalf("should reject when buffer is full")
		}
		if buf.Size() != 2 {
			t.Fatalf("size should be 2, got %d", buf.Size())
		}
	})

	t.Run("BoundedBuffer_EmptyGet", func(t *testing.T) {
		buf := concurrency.NewBoundedBuffer(5)
		_, ok := buf.Get()
		if ok {
			t.Fatalf("should return false on empty buffer")
		}
	})

	t.Run("BoundedBuffer_ConcurrentAccess", func(t *testing.T) {
		buf := concurrency.NewBoundedBuffer(100)
		var wg sync.WaitGroup
		// 10 producers, each puts 10 items
		for i := 0; i < 10; i++ {
			wg.Add(1)
			go func(id int) {
				defer wg.Done()
				for j := 0; j < 10; j++ {
					buf.Put(fmt.Sprintf("%d_%d", id, j))
				}
			}(i)
		}
		wg.Wait()
		if buf.Size() != 100 {
			t.Fatalf("expected 100 items, got %d", buf.Size())
		}
	})

	t.Run("ConcurrentSet_ThreadSafe", func(t *testing.T) {
		set := concurrency.NewConcurrentSet()
		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func(id int) {
				defer wg.Done()
				key := fmt.Sprintf("item_%d", id)
				set.Add(key)
			}(i)
		}
		wg.Wait()
		if set.Size() != 50 {
			t.Fatalf("expected 50 items, got %d", set.Size())
		}
	})

	t.Run("ConcurrentSet_ContainsAndRemove", func(t *testing.T) {
		set := concurrency.NewConcurrentSet()
		set.Add("alpha")
		set.Add("beta")
		if !set.Contains("alpha") {
			t.Fatalf("should contain alpha")
		}
		set.Remove("alpha")
		if set.Contains("alpha") {
			t.Fatalf("should not contain alpha after removal")
		}
		if set.Size() != 1 {
			t.Fatalf("expected size 1, got %d", set.Size())
		}
	})

	t.Run("BarrierSync_AllGoroutinesPass", func(t *testing.T) {
		n := 5
		barrier := concurrency.NewBarrier(n)
		var results []int
		var mu sync.Mutex
		var wg sync.WaitGroup
		for i := 0; i < n; i++ {
			wg.Add(1)
			go func(id int) {
				defer wg.Done()
				barrier.Wait()
				mu.Lock()
				results = append(results, id)
				mu.Unlock()
			}(i)
		}
		wg.Wait()
		if len(results) != n {
			t.Fatalf("all %d goroutines should pass barrier, got %d", n, len(results))
		}
	})

	t.Run("TransactionalBatch_RollsBackOnError", func(t *testing.T) {
		var processed []string
		var rolledBack []string
		items := []string{"a", "b", "c", "d"}
		count, err := workflow.TransactionalBatch(
			items,
			func(s string) error {
				if s == "c" {
					return fmt.Errorf("failed on %s", s)
				}
				processed = append(processed, s)
				return nil
			},
			func(s string) error {
				rolledBack = append(rolledBack, s)
				return nil
			},
		)
		if err == nil {
			t.Fatalf("should return error")
		}
		if count != 2 {
			t.Fatalf("should have processed 2 items before failure, got %d", count)
		}
		// Should roll back a, b in reverse order
		if len(rolledBack) != 2 {
			t.Fatalf("should roll back 2 items, got %d", len(rolledBack))
		}
		if rolledBack[0] != "b" || rolledBack[1] != "a" {
			t.Fatalf("rollback should be in reverse order [b,a], got %v", rolledBack)
		}
	})

	t.Run("TransactionalBatch_AllSucceed", func(t *testing.T) {
		count, err := workflow.TransactionalBatch(
			[]string{"x", "y", "z"},
			func(s string) error { return nil },
			func(s string) error { return nil },
		)
		if err != nil {
			t.Fatalf("should not error: %v", err)
		}
		if count != 3 {
			t.Fatalf("should process all 3, got %d", count)
		}
	})

	t.Run("EventualConsistencyCheck_ConvergesEventually", func(t *testing.T) {
		callCount := 0
		readFn := func() string {
			callCount++
			if callCount >= 3 {
				return "expected"
			}
			return "stale"
		}
		found, attempts := workflow.EventualConsistencyCheck(readFn, "expected", 10)
		if !found {
			t.Fatalf("should find expected value within retries")
		}
		if attempts != 3 {
			t.Fatalf("should converge on attempt 3, got %d", attempts)
		}
	})

	t.Run("EventualConsistencyCheck_NeverConverges", func(t *testing.T) {
		found, attempts := workflow.EventualConsistencyCheck(
			func() string { return "wrong" },
			"expected",
			5,
		)
		if found {
			t.Fatalf("should not find match")
		}
		if attempts != 5 {
			t.Fatalf("should exhaust all 5 retries, got %d", attempts)
		}
	})

	t.Run("SafeCounter_ConcurrentIncrements", func(t *testing.T) {
		c := &workflow.SafeCounter{}
		var wg sync.WaitGroup
		for i := 0; i < 1000; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				c.Inc()
			}()
		}
		wg.Wait()
		if c.Value() != 1000 {
			t.Fatalf("expected 1000, got %d", c.Value())
		}
	})
}
