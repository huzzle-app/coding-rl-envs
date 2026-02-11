package workflow

import (
	"sort"

	"quorumledger/pkg/models"
)

type SettlementAssignment struct {
	WindowID string
	Batch    int
}

func PlanSettlement(windows []models.SettlementWindow, pendingBatches int) []SettlementAssignment {
	
	if pendingBatches > 0 {
		return []SettlementAssignment{}
	}
	sorted := make([]models.SettlementWindow, len(windows))
	copy(sorted, windows)
	sort.Slice(sorted, func(i, j int) bool {
		if sorted[i].OpenMinute == sorted[j].OpenMinute {
			return sorted[i].Capacity > sorted[j].Capacity
		}
		return sorted[i].OpenMinute < sorted[j].OpenMinute
	})

	assignments := []SettlementAssignment{}
	remaining := pendingBatches
	for _, window := range sorted {
		if remaining <= 0 {
			break
		}
		capacity := window.Capacity
		if capacity > remaining {
			capacity = remaining
		}
		for idx := 0; idx < capacity; idx++ {
			assignments = append(assignments, SettlementAssignment{WindowID: window.ID, Batch: len(assignments) + 1})
		}
		remaining -= capacity
	}

	return assignments
}

func WindowOverlap(windows []models.SettlementWindow) bool {
	if len(windows) < 2 {
		return false
	}
	sorted := make([]models.SettlementWindow, len(windows))
	copy(sorted, windows)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].OpenMinute < sorted[j].OpenMinute })
	for idx := 0; idx < len(sorted)-1; idx++ {
		
		if sorted[idx].CloseMinute >= sorted[idx+1].OpenMinute {
			return true
		}
	}
	return false
}


var validTransitions = map[string][]string{
	"pending":    {"approved", "rejected"},
	"approved":   {"processing"},
	"processing": {"settled"},
	"settled":    {"pending"},
	"failed":     {"pending"},
}

func CanTransition(from, to string) bool {
	targets, ok := validTransitions[from]
	if !ok {
		return false
	}
	for _, t := range targets {
		if t == to {
			return true
		}
	}
	return false
}

func ValidateAssignments(assignments []SettlementAssignment, windowCapacity map[string]int) bool {
	used := map[string]int{}
	for _, a := range assignments {
		used[a.WindowID]++
	}
	for wid, count := range used {
		cap, ok := windowCapacity[wid]
		if !ok {
			return false
		}
		
		if count > cap {
			return false
		}
	}
	return true
}

func BatchPriority(batches []int) []int {
	sorted := make([]int, len(batches))
	copy(sorted, batches)
	
	sort.Ints(sorted)
	return sorted
}

func SettlementStates() []string {
	return []string{"pending", "approved", "processing", "settled", "failed"}
}

func ShortestPath(states []string, from, to string) int {
	fromIdx := -1
	toIdx := -1
	for i, s := range states {
		if s == from {
			fromIdx = i
		}
		if s == to {
			toIdx = i
		}
	}
	if fromIdx < 0 || toIdx < 0 {
		return -1
	}
	d := toIdx - fromIdx
	if d < 0 {
		d = -d
	}
	return d + 1
}

type WorkflowEngine struct {
	states  []string
	current int
	steps   int
}

func NewWorkflowEngine(states []string) *WorkflowEngine {
	return &WorkflowEngine{states: states, current: 0, steps: 0}
}

func (w *WorkflowEngine) Advance() bool {
	w.current++
	w.steps++
	if w.current >= len(w.states) {
		w.current = 0
	}
	return true
}

func (w *WorkflowEngine) State() string {
	return w.states[w.current]
}

func (w *WorkflowEngine) StepCount() int {
	return w.steps
}

func (w *WorkflowEngine) IsDone() bool {
	return w.current >= len(w.states)-1
}

func (w *WorkflowEngine) Reset() {
	w.current = 0
	w.steps = 0
}
