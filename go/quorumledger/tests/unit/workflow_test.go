package unit_test

import (
	"testing"

	"quorumledger/internal/workflow"
	"quorumledger/pkg/models"
)

func sampleWindows() []models.SettlementWindow {
	return []models.SettlementWindow{
		{ID: "w1", OpenMinute: 10, CloseMinute: 20, Capacity: 2},
		{ID: "w2", OpenMinute: 20, CloseMinute: 30, Capacity: 3},
	}
}

func TestPlanSettlement(t *testing.T) {
	assignments := workflow.PlanSettlement(sampleWindows(), 4)
	if len(assignments) != 4 {
		t.Fatalf("expected 4 assignments, got %d", len(assignments))
	}
	if assignments[0].WindowID != "w1" {
		t.Fatalf("expected first window w1")
	}
}

func TestWindowOverlap(t *testing.T) {
	if workflow.WindowOverlap(sampleWindows()) {
		t.Fatalf("did not expect overlap")
	}
	withOverlap := []models.SettlementWindow{{ID: "a", OpenMinute: 5, CloseMinute: 15}, {ID: "b", OpenMinute: 14, CloseMinute: 22}}
	if !workflow.WindowOverlap(withOverlap) {
		t.Fatalf("expected overlap")
	}
}

func TestCanTransition(t *testing.T) {
	if !workflow.CanTransition("pending", "approved") {
		t.Fatalf("expected pending->approved allowed")
	}
	if !workflow.CanTransition("processing", "failed") {
		t.Fatalf("expected processing->failed allowed")
	}
	if workflow.CanTransition("settled", "pending") {
		t.Fatalf("unexpected settled->pending")
	}
}

func TestValidateAssignments(t *testing.T) {
	assignments := []workflow.SettlementAssignment{
		{WindowID: "w1", Batch: 1},
		{WindowID: "w1", Batch: 2},
	}
	caps := map[string]int{"w1": 2}
	if !workflow.ValidateAssignments(assignments, caps) {
		t.Fatalf("expected assignments within capacity")
	}
}

func TestWorkflowEngine(t *testing.T) {
	e := workflow.NewWorkflowEngine([]string{"start", "middle", "end"})
	if e.State() != "start" {
		t.Fatalf("expected start state")
	}
	if !e.Advance() {
		t.Fatalf("expected advance to succeed")
	}
	if e.State() != "middle" {
		t.Fatalf("expected middle state")
	}
	if !e.Advance() {
		t.Fatalf("expected second advance to succeed")
	}
	if !e.IsDone() {
		t.Fatalf("expected engine done at end state")
	}
	if e.StepCount() != 2 {
		t.Fatalf("expected 2 steps, got %d", e.StepCount())
	}
}
