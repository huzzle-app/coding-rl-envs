package stress

import (
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"incidentmesh/internal/concurrency"
	"incidentmesh/internal/workflow"
)

func TestConcurrencyBoundedParallelLimit(t *testing.T) {
	t.Run("RespectsMaxConcurrent", func(t *testing.T) {
		var running int64
		var maxSeen int64
		var mu sync.Mutex
		tasks := make([]func() string, 20)
		for i := range tasks {
			tasks[i] = func() string {
				cur := atomic.AddInt64(&running, 1)
				mu.Lock()
				if cur > maxSeen {
					maxSeen = cur
				}
				mu.Unlock()
				time.Sleep(10 * time.Millisecond)
				atomic.AddInt64(&running, -1)
				return "done"
			}
		}
		results := concurrency.BoundedParallel(tasks, 3)
		if len(results) != 20 {
			t.Errorf("expected 20 results, got %d", len(results))
		}
		if maxSeen > 3 {
			t.Errorf("max concurrent should be <= 3, observed %d (bound ignored)", maxSeen)
		}
	})
	t.Run("AllTasksComplete", func(t *testing.T) {
		tasks := make([]func() string, 10)
		for i := range tasks {
			idx := i
			tasks[i] = func() string { return fmt.Sprintf("task-%d", idx) }
		}
		results := concurrency.BoundedParallel(tasks, 2)
		if len(results) != 10 {
			t.Errorf("expected 10 results, got %d", len(results))
		}
		for i, r := range results {
			expected := fmt.Sprintf("task-%d", i)
			if r != expected {
				t.Errorf("result[%d] = %s, expected %s", i, r, expected)
			}
		}
	})
	t.Run("BoundOfOne", func(t *testing.T) {
		var running int64
		var maxSeen int64
		tasks := make([]func() string, 5)
		for i := range tasks {
			tasks[i] = func() string {
				cur := atomic.AddInt64(&running, 1)
				if cur > atomic.LoadInt64(&maxSeen) {
					atomic.StoreInt64(&maxSeen, cur)
				}
				time.Sleep(5 * time.Millisecond)
				atomic.AddInt64(&running, -1)
				return "ok"
			}
		}
		concurrency.BoundedParallel(tasks, 1)
		if maxSeen > 1 {
			t.Errorf("bound=1: max concurrent should be 1, observed %d", maxSeen)
		}
	})
}

func TestConcurrencySafeAccumulate(t *testing.T) {
	t.Run("CorrectSum", func(t *testing.T) {
		values := []int64{10, 20, 30, 40, 50}
		total := concurrency.SafeAccumulate(values)
		if total != 150 {
			t.Errorf("sum of [10,20,30,40,50] should be 150, got %d", total)
		}
	})
	t.Run("SingleValue", func(t *testing.T) {
		total := concurrency.SafeAccumulate([]int64{42})
		if total != 42 {
			t.Errorf("single value 42: expected 42, got %d", total)
		}
	})
	t.Run("IncludesFirstElement", func(t *testing.T) {
		values := []int64{100, 1, 1, 1, 1}
		total := concurrency.SafeAccumulate(values)
		if total != 104 {
			t.Errorf("sum [100,1,1,1,1] should be 104, got %d (first element dropped?)", total)
		}
	})
	t.Run("LargeArray", func(t *testing.T) {
		values := make([]int64, 1000)
		for i := range values {
			values[i] = 1
		}
		total := concurrency.SafeAccumulate(values)
		if total != 1000 {
			t.Errorf("1000 ones should sum to 1000, got %d", total)
		}
	})
	t.Run("EmptyArray", func(t *testing.T) {
		total := concurrency.SafeAccumulate(nil)
		if total != 0 {
			t.Errorf("empty: expected 0, got %d", total)
		}
	})
}

func TestConcurrencyOrderPreservation(t *testing.T) {
	t.Run("BoundedParallelPreservesOrder", func(t *testing.T) {
		tasks := make([]func() string, 10)
		for i := range tasks {
			idx := i
			tasks[i] = func() string {
				time.Sleep(time.Duration(10-idx) * time.Millisecond)
				return fmt.Sprintf("item-%d", idx)
			}
		}
		results := concurrency.BoundedParallel(tasks, 5)
		for i, r := range results {
			expected := fmt.Sprintf("item-%d", i)
			if r != expected {
				t.Errorf("index %d: expected %s, got %s (order violated)", i, expected, r)
			}
		}
	})
}

func TestConcurrencyParallelMapReduce(t *testing.T) {
	t.Run("SumOfLengths", func(t *testing.T) {
		items := []string{"hello", "world", "foo"}
		result := concurrency.ParallelMapReduce(items,
			func(s string) int { return len(s) },
			func(a, b int) int { return a + b },
		)
		if result != 13 {
			t.Errorf("sum of lengths 5+5+3 should be 13, got %d", result)
		}
	})
	t.Run("MaxValue", func(t *testing.T) {
		items := []string{"a", "bbb", "cc"}
		result := concurrency.ParallelMapReduce(items,
			func(s string) int { return len(s) },
			func(a, b int) int {
				if a > b {
					return a
				}
				return b
			},
		)
		if result != 3 {
			t.Errorf("max of lengths [1,3,2] should be 3, got %d", result)
		}
	})
	t.Run("SingleItem", func(t *testing.T) {
		result := concurrency.ParallelMapReduce([]string{"test"},
			func(s string) int { return 42 },
			func(a, b int) int { return a + b },
		)
		if result != 42 {
			t.Errorf("single item: expected 42, got %d", result)
		}
	})
}

func TestConcurrencyBatchProcessCompleteness(t *testing.T) {
	t.Run("AllItemsProcessed", func(t *testing.T) {
		items := []string{"a", "b", "c", "d", "e"}
		results := workflow.BatchProcess(items, func(s string) string {
			return s + "-processed"
		})
		if len(results) != 5 {
			t.Errorf("5 items: expected 5 results, got %d", len(results))
		}
	})
	t.Run("SingleItem", func(t *testing.T) {
		results := workflow.BatchProcess([]string{"only"}, func(s string) string {
			return s
		})
		if len(results) != 1 {
			t.Errorf("single item: expected 1 result, got %d", len(results))
		}
	})
}

func TestConcurrencyCounterIncrement(t *testing.T) {
	t.Run("IncrementByOne", func(t *testing.T) {
		var counter int64 = 0
		result := workflow.CounterIncrement(&counter, 1)
		if result != 1 {
			t.Errorf("increment 0 by 1: expected 1, got %d", result)
		}
	})
	t.Run("IncrementByDelta", func(t *testing.T) {
		var counter int64 = 10
		result := workflow.CounterIncrement(&counter, 5)
		if result != 15 {
			t.Errorf("increment 10 by 5: expected 15, got %d", result)
		}
	})
	t.Run("ConcurrentIncrements", func(t *testing.T) {
		var counter int64 = 0
		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				workflow.CounterIncrement(&counter, 1)
			}()
		}
		wg.Wait()
		if counter != 100 {
			t.Errorf("100 increments by 1: expected 100, got %d", counter)
		}
	})
}

func TestConcurrencyAggregateCounters(t *testing.T) {
	t.Run("SimpleSum", func(t *testing.T) {
		counters := []int64{10, 20, 30}
		total := workflow.AggregateCounters(counters)
		if total != 60 {
			t.Errorf("aggregate [10,20,30]: expected 60, got %d", total)
		}
	})
	t.Run("SingleCounter", func(t *testing.T) {
		total := workflow.AggregateCounters([]int64{42})
		if total != 42 {
			t.Errorf("single counter 42: expected 42, got %d", total)
		}
	})
	t.Run("LargeList", func(t *testing.T) {
		counters := make([]int64, 100)
		for i := range counters {
			counters[i] = 1
		}
		total := workflow.AggregateCounters(counters)
		if total != 100 {
			t.Errorf("100 ones: expected 100, got %d", total)
		}
	})
}

func TestConcurrencyThrottleRespectsBound(t *testing.T) {
	t.Run("ResultsCorrect", func(t *testing.T) {
		items := []string{"a", "b", "c"}
		results := concurrency.Throttle(items, 1, func(s string) string {
			return s + "!"
		})
		if len(results) != 3 {
			t.Errorf("expected 3 results, got %d", len(results))
		}
		for i, r := range results {
			expected := items[i] + "!"
			if r != expected {
				t.Errorf("index %d: expected %s, got %s", i, expected, r)
			}
		}
	})
}

func TestConcurrencyFanOutIndexCorrectness(t *testing.T) {
	t.Run("IndicesMatchInput", func(t *testing.T) {
		results := concurrency.FanOut(5, func(i int) string {
			return fmt.Sprintf("result-%d", i)
		})
		for i, r := range results {
			expected := fmt.Sprintf("result-%d", i)
			if r != expected {
				t.Errorf("index %d: expected %s, got %s", i, expected, r)
			}
		}
	})
}

func TestConcurrencySafeMapOperations(t *testing.T) {
	t.Run("SetAndGet", func(t *testing.T) {
		var m sync.Map
		workflow.SafeMapSet(&m, "key", "value")
		val, ok := workflow.SafeMapGet(&m, "key")
		if !ok || val != "value" {
			t.Errorf("expected (value, true), got (%s, %v)", val, ok)
		}
	})
	t.Run("MissingKey", func(t *testing.T) {
		var m sync.Map
		_, ok := workflow.SafeMapGet(&m, "missing")
		if ok {
			t.Error("missing key should return false")
		}
	})
	t.Run("ConcurrentSetGet", func(t *testing.T) {
		var m sync.Map
		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				key := fmt.Sprintf("key-%d", idx)
				workflow.SafeMapSet(&m, key, fmt.Sprintf("val-%d", idx))
				val, ok := workflow.SafeMapGet(&m, key)
				if !ok || val != fmt.Sprintf("val-%d", idx) {
					t.Errorf("concurrent set/get failed for %s", key)
				}
			}(i)
		}
		wg.Wait()
	})
}
