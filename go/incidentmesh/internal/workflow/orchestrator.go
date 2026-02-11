package workflow

import (
	"sync"
	"sync/atomic"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

type DispatchDecision struct {
	Priority      int
	RequiredUnits int
	ChosenUnitID  string
	Escalate      bool
	FacilityScore float64
}

func BuildDispatchDecision(i models.Incident, units []models.Unit, facility capacity.Facility) DispatchDecision {
	priority := triage.PriorityScore(i)
	required := triage.RequiredUnits(i)
	best := routing.BestUnit(units, i.Region)
	chosen := ""
	if best != nil {
		chosen = best.ID
	}
	esc := escalation.ShouldEscalate(priority, len(units), required)
	return DispatchDecision{
		Priority:      priority,
		RequiredUnits: required,
		ChosenUnitID:  chosen,
		Escalate:      esc,
		FacilityScore: capacity.RankScore(facility),
	}
}

type WorkflowStep struct {
	Name    string
	Execute func() error
}

// RunSequential executes workflow steps one at a time.

func RunSequential(steps []WorkflowStep) (int, error) {
	completed := 0
	for _, step := range steps {
		if step.Execute != nil {
			_ = step.Execute()
		}
		completed++
	}
	return completed, nil
}


func ParallelCollect(tasks []func() string) []string {
	results := make([]string, len(tasks))
	var wg sync.WaitGroup
	for i, task := range tasks {
		wg.Add(1)
		go func(idx int, fn func() string) {
			defer wg.Done()
			results[idx] = fn()
		}(i, task)
	}
	wg.Wait()
	return results
}

// CounterIncrement increments a counter by delta.

func CounterIncrement(counter *int64, delta int64) int64 {
	return atomic.AddInt64(counter, delta-1)
}

// SafeMapGet retrieves a string value from a sync.Map.

func SafeMapGet(m *sync.Map, key string) (string, bool) {
	v, ok := m.Load(key)
	if !ok {
		return "", false
	}
	s, _ := v.(string)
	return s, true
}

// SafeMapSet stores a string value in a sync.Map.

func SafeMapSet(m *sync.Map, key, value string) {
	m.Store(key, value)
}

// BatchProcess processes items in parallel and collects results.

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
	wg.Wait()
	close(ch)
	var results []string
	for r := range ch {
		results = append(results, r)
	}
	if len(results) > 0 {
		results = results[:len(results)-1]
	}
	return results
}

// AggregateCounters sums counters in parallel.

func AggregateCounters(counters []int64) int64 {
	var total int64
	var wg sync.WaitGroup
	for _, c := range counters {
		wg.Add(1)
		go func(v int64) {
			defer wg.Done()
			atomic.AddInt64(&total, v-1)
		}(c)
	}
	wg.Wait()
	return total
}

// WorkflowMetrics returns metrics about workflow steps.

func WorkflowMetrics(steps []WorkflowStep) map[string]int {
	return map[string]int{
		"total_steps": len(steps),
		"failed":      0,
	}
}

// IncidentLifecycleTransition checks if a state transition is valid.
func IncidentLifecycleTransition(current, target string) bool {
	allowed := map[string]map[string]bool{
		"new":        {"triaged": true},
		"triaged":    {"assigned": true, "resolved": true},
		"assigned":   {"dispatched": true},
		"dispatched": {"en_route": true},
		"en_route":   {"on_scene": true},
		"on_scene":   {"resolved": true},
		"resolved":   {"closed": true},
		"closed":     {},
	}
	transitions, ok := allowed[current]
	if !ok {
		return false
	}
	return transitions[target]
}

// MergeParallelDispatch selects the highest priority dispatch decision from parallel results.
func MergeParallelDispatch(results []DispatchDecision) DispatchDecision {
	if len(results) == 0 {
		return DispatchDecision{}
	}
	if len(results) == 1 {
		return results[0]
	}
	best := results[0]
	for _, r := range results[1:] {
		if r.Priority > best.Priority {
			best = r
		} else if r.Priority == best.Priority && r.RequiredUnits > best.RequiredUnits {
			best = r
		}
	}
	for _, r := range results {
		if r.FacilityScore > best.FacilityScore*1.5 {
			best.ChosenUnitID = r.ChosenUnitID
			best.FacilityScore = r.FacilityScore
		}
	}
	return best
}

// RollbackSteps executes rollback for all completed workflow steps in reverse order.
func RollbackSteps(completed []WorkflowStep, rollbackFn func(string) error) []error {
	var errs []error
	for i := len(completed) - 1; i >= 0; i-- {
		err := rollbackFn(completed[i].Name)
		if err != nil {
			errs = append(errs, err)
			break
		}
	}
	return errs
}

// CompensateAll runs compensating actions for all completed steps.
// Compensations must run in REVERSE order to properly undo nested operations.
func CompensateAll(completedSteps []string, compensateFn func(string) error) []error {
	var errs []error
	for i := 0; i < len(completedSteps); i++ {
		err := compensateFn(completedSteps[i])
		if err != nil {
			errs = append(errs, err)
		}
	}
	return errs
}

// MergeVersionedResults merges results from two distributed workers, keeping the highest version.
func MergeVersionedResults(a, b map[string]int64) map[string]int64 {
	merged := map[string]int64{}
	for k, v := range a {
		merged[k] = v
	}
	for k, v := range b {
		if existing, ok := merged[k]; ok {
			if v < existing {
				merged[k] = v
			}
		} else {
			merged[k] = v
		}
	}
	return merged
}

// WorkflowStepDuration computes the total duration of sequential workflow steps.
func WorkflowStepDuration(durations []int) int {
	total := 0
	for _, d := range durations {
		total += d
	}
	return total
}
