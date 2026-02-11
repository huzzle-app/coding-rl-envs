package concurrency_test

import (
	"fmt"
	"sync"
	"testing"

	"quorumledger/internal/policy"
	"quorumledger/internal/queue"
	"quorumledger/internal/risk"
	"quorumledger/internal/statistics"
	"quorumledger/internal/workflow"
	"quorumledger/pkg/models"
)

func TestResponseTimeTrackerConcurrentAccess(t *testing.T) {
	tracker := statistics.NewResponseTimeTracker(100)
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				tracker.Record(id*100 + j)
				tracker.P50()
				tracker.P99()
			}
		}(i)
	}
	wg.Wait()
	if tracker.Count() == 0 {
		t.Fatal("expected non-zero sample count after concurrent recording")
	}
}

func TestPriorityQueueConcurrentAccess(t *testing.T) {
	q := queue.NewPriorityQueue(10000)
	for i := 0; i < 200; i++ {
		q.Enqueue(models.QueueItem{ID: fmt.Sprintf("init-%d", i), Priority: i})
	}
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for j := 0; j < 200; j++ {
			q.Enqueue(models.QueueItem{ID: fmt.Sprintf("w-%d", j), Priority: j})
		}
	}()
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 200; j++ {
				q.Size()
			}
		}()
	}
	wg.Wait()
}

func TestRiskScoresConcurrentAccess(t *testing.T) {
	scores := make([]float64, 100)
	for i := range scores {
		scores[i] = float64(i)
	}
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				scores[id*10] = float64(j)
				risk.AggregateRisk(scores)
			}
		}(i)
	}
	wg.Wait()
}

func TestPolicyEngineConcurrentAccess(t *testing.T) {
	engine := policy.NewPolicyEngine(1000000)
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				engine.Escalate()
				engine.CurrentLevel()
				engine.ShouldHold(500000)
				engine.Deescalate()
			}
		}()
	}
	wg.Wait()
}

func TestWorkflowEngineConcurrentAccess(t *testing.T) {
	e := workflow.NewWorkflowEngine([]string{"pending", "processing", "settled", "done"})
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for j := 0; j < 200; j++ {
			e.Advance()
		}
	}()
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 200; j++ {
				e.StepCount()
				e.IsDone()
			}
		}()
	}
	wg.Wait()
}

func TestRateLimiterConcurrentAccess(t *testing.T) {
	rl := queue.NewRateLimiter(100)
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				rl.Allow()
				rl.Remaining()
			}
		}()
	}
	wg.Wait()
}
