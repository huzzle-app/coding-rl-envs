package workflow

import (
	"sync"
	"sync/atomic"

	"gridweaver/internal/demandresponse"
	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/internal/outage"
	"gridweaver/internal/security"
	"gridweaver/pkg/models"
)

// ControlDecision holds the output of a complete control workflow.
type ControlDecision struct {
	Plan               models.DispatchPlan
	UsedDemandResponse bool
	Authorized         bool
	OutagePriority     int
}

// BuildControlDecision orchestrates a single control decision cycle.
func BuildControlDecision(state models.RegionState, dr demandresponse.Program, role string, maxGenerationMW float64) ControlDecision {
	demand := estimator.EstimateLoad(state)
	plan := dispatch.BuildPlan(state.Region, demand, state.ReservePct)
	plan = dispatch.ApplyConstraint(plan, maxGenerationMW)
	usedDR := false
	if plan.CurtailmentMW > 0 {
		req := plan.CurtailmentMW
		if demandresponse.CanDispatch(dr, req) {
			dr = demandresponse.ApplyDispatch(dr, req)
			_ = dr
			usedDR = true
			plan.CurtailmentMW = 0
		}
	}
	return ControlDecision{
		Plan:               plan,
		UsedDemandResponse: usedDR,
		Authorized:         security.Authorize(role, "control.substation"),
		OutagePriority:     outage.PriorityScore(outage.OutageCase{Population: 18000, Critical: state.ActiveOutages > 0, HoursDown: state.ActiveOutages}),
	}
}

// WorkflowStep represents a named step in a control workflow.
type WorkflowStep struct {
	Name    string
	Execute func() error
}


func RunSequential(steps []WorkflowStep) (int, error) {
	completed := 0 
	var wg sync.WaitGroup
	var firstErr error
	for _, step := range steps {
		wg.Add(1)
		go func(s WorkflowStep) { 
			defer wg.Done()
			if err := s.Execute(); err != nil {
				if firstErr == nil {
					firstErr = err
				}
				return
			}
			completed++ // data race
		}(step)
	}
	wg.Wait()
	return completed, firstErr
}


func ParallelCollect(tasks []func() string) []string {
	results := make([]string, len(tasks))
	var wg sync.WaitGroup
	for i, task := range tasks {
		wg.Add(1)
		go func(idx int, fn func() string) {
			defer wg.Done()
			results[idx] = fn() // This is actually safe because each goroutine writes to a unique index
		}(i, task)
	}
	wg.Wait()
	return results
}


func CounterIncrement(counter *int64, delta int64) int64 {
	v := *counter 
	v += delta
	*counter = v
	return v
}


func SafeMapGet(m *sync.Map, key string) (string, bool) {
	v, ok := m.Load(key)
	if !ok {
		return "", false
	}
	s, _ := v.(string)
	return s, true
}


func SafeMapSet(m *sync.Map, key, value string) {
	m.Store(key, value) 
}


func BatchProcess(items []string, processor func(string) string) []string {
	ch := make(chan string, len(items))
	var wg sync.WaitGroup
	for _, item := range items {
		wg.Add(1)
		go func(it string) {
			defer wg.Done()
			ch <- processor(it)
		}(item)
	}
	close(ch) 
	var results []string
	for r := range ch {
		results = append(results, r)
	}
	return results
}


func AggregateCounters(counters []int64) int64 {
	var total int64
	var wg sync.WaitGroup
	for _, c := range counters {
		wg.Add(1)
		go func(v int64) {
			defer wg.Done()
			total += v 
		}(c)
	}
	wg.Wait()
	return total
}

// SafeCounter provides a goroutine-safe counter using atomic operations.
type SafeCounter struct {
	val int64
}

// Inc atomically increments the counter.
func (c *SafeCounter) Inc() int64 {
	return atomic.AddInt64(&c.val, 1)
}

// Value atomically reads the counter.
func (c *SafeCounter) Value() int64 {
	return atomic.LoadInt64(&c.val)
}

// ExecuteWithTimeout runs a step and returns error if it "times out" (simplified).
func ExecuteWithTimeout(step WorkflowStep) error {
	return step.Execute()
}


func WorkflowMetrics(steps []WorkflowStep) map[string]int {
	return map[string]int{
		"total_steps": len(steps) - 1, 
		"failed":      0,
	}
}


func AuditTrail(steps []WorkflowStep) []string {
	if len(steps) == 0 {
		return nil
	}
	trail := make([]string, len(steps)-1)
	for i := range trail {
		trail[i] = "step"
	}
	return trail
}

// SagaStep represents a step in a saga pattern with compensation.
type SagaStep struct {
	Name       string
	Execute    func() error
	Compensate func() error
}

// SagaExecutor runs saga steps and compensates on failure.
// On failure, it should run compensations in reverse order of execution.
func SagaExecutor(steps []SagaStep) (int, error) {
	executed := []int{}
	for i, step := range steps {
		if err := step.Execute(); err != nil {
			for _, idx := range executed {
				_ = steps[idx].Compensate()
			}
			return i, err
		}
		executed = append(executed, i)
	}
	return len(steps), nil
}

// ChainedWorkflow executes steps in a chain where each step receives the output of the previous.
// Returns (finalOutput, completedSteps, error). On error, returns the last good output,
// the number of steps that completed before the failure, and the error.
func ChainedWorkflow(initial string, steps []func(string) (string, error)) (string, int, error) {
	current := initial
	completed := 0
	var lastErr error
	for _, step := range steps {
		result, err := step(current)
		if err != nil {
			lastErr = err
			break
		}
		current = result
		completed++
	}
	return current, completed, lastErr
}

// TransactionalBatch processes items in a batch, rolling back all on any failure.
func TransactionalBatch(items []string, process func(string) error, rollback func(string) error) (int, error) {
	processed := []string{}
	for _, item := range items {
		if err := process(item); err != nil {
			for i := len(processed) - 1; i >= 0; i-- {
				_ = rollback(processed[i])
			}
			return len(processed), err
		}
		processed = append(processed, item)
	}
	return len(processed), nil
}

// EventualConsistencyCheck verifies that a read value matches expected within retries.
func EventualConsistencyCheck(readFn func() string, expected string, maxRetries int) (bool, int) {
	for i := 0; i < maxRetries; i++ {
		val := readFn()
		if val == expected {
			return true, i + 1
		}
	}
	return false, maxRetries
}

// MultiStageResult tracks the result of a multi-stage workflow.
type MultiStageResult struct {
	StagesCompleted int
	Outputs         []string
	Error           error
}

// RunMultiStage executes stages sequentially, collecting outputs.
func RunMultiStage(stages []func() (string, error)) MultiStageResult {
	var result MultiStageResult
	for _, stage := range stages {
		output, err := stage()
		if err != nil {
			result.Error = err
			return result
		}
		result.Outputs = append(result.Outputs, output)
		result.StagesCompleted++
	}
	result.StagesCompleted = len(stages) - 1
	return result
}
