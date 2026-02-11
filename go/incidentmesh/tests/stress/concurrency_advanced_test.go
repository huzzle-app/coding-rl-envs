package stress

import (
	"fmt"
	"sync"
	"testing"

	"incidentmesh/internal/concurrency"
	"incidentmesh/internal/workflow"
)

// Concurrency bugs: race conditions, ordering violations, incomplete operations.

func TestConcurrencyPhantomIncidentCreation(t *testing.T) {
	// UpdateIfHigherPriority creates entries for non-existent incidents.
	// This violates the contract: "update IF EXISTS" should not create new entries.
	// In production, phantom incidents would appear in dashboards without proper intake.

	t.Run("NonExistentReturnsFailure", func(t *testing.T) {
		m := concurrency.NewConcurrentIncidentMap()
		ok := m.UpdateIfHigherPriority("phantom-1", 100)
		if ok {
			t.Error("UpdateIfHigherPriority on non-existent key should return false")
		}
	})
	t.Run("NonExistentNotCreated", func(t *testing.T) {
		m := concurrency.NewConcurrentIncidentMap()
		m.UpdateIfHigherPriority("phantom-1", 100)
		count := m.Count()
		if count != 0 {
			t.Errorf("map should be empty after update on non-existent key, got %d entries", count)
		}
	})
	t.Run("ConcurrentPhantomCreation", func(t *testing.T) {
		m := concurrency.NewConcurrentIncidentMap()
		var wg sync.WaitGroup
		for i := 0; i < 20; i++ {
			wg.Add(1)
			go func(id string) {
				defer wg.Done()
				m.UpdateIfHigherPriority(id, 50)
			}(fmt.Sprintf("phantom-%d", i))
		}
		wg.Wait()
		if m.Count() != 0 {
			t.Errorf("20 updates to non-existent keys should leave map empty, got %d phantom entries", m.Count())
		}
	})
	t.Run("ExistingKeyUpdatesCorrectly", func(t *testing.T) {
		m := concurrency.NewConcurrentIncidentMap()
		m.Set("inc-1", 50)
		ok := m.UpdateIfHigherPriority("inc-1", 100)
		if !ok {
			t.Error("update to higher priority on existing key should succeed")
		}
		val, _ := m.Get("inc-1")
		if val != 100 {
			t.Errorf("expected updated priority 100, got %d", val)
		}
	})
}

func TestConcurrencyOrderedCollectViolation(t *testing.T) {
	// OrderedParallelCollect uses channel (unordered) instead of indexed assignment.
	// Results arrive in goroutine completion order, not input order.
	// This means incident processing order is non-deterministic.

	t.Run("InputOrderPreserved", func(t *testing.T) {
		items := []string{"charlie", "alpha", "bravo"}
		fn := func(s string) string { return "processed:" + s }
		results := concurrency.OrderedParallelCollect(items, fn)
		expected := []string{"processed:charlie", "processed:alpha", "processed:bravo"}
		if len(results) != len(expected) {
			t.Fatalf("expected %d results, got %d", len(expected), len(results))
		}
		for i, r := range results {
			if r != expected[i] {
				t.Errorf("index %d: expected %s, got %s (ordering violated)", i, expected[i], r)
			}
		}
	})
	t.Run("FiveItemsPreserveOrder", func(t *testing.T) {
		items := []string{"e", "d", "c", "b", "a"}
		fn := func(s string) string { return s + "-done" }
		results := concurrency.OrderedParallelCollect(items, fn)
		for i, item := range items {
			expected := item + "-done"
			if results[i] != expected {
				t.Errorf("index %d: expected %s, got %s", i, expected, results[i])
			}
		}
	})
	t.Run("NumericOrderPreserved", func(t *testing.T) {
		items := []string{"3", "1", "2"}
		fn := func(s string) string { return "item-" + s }
		results := concurrency.OrderedParallelCollect(items, fn)
		if results[0] != "item-3" || results[1] != "item-1" || results[2] != "item-2" {
			t.Errorf("order not preserved: got %v", results)
		}
	})
}

func TestConcurrencyMergeDispatchFacilityOverride(t *testing.T) {
	// MergeParallelDispatch has a second pass that overrides the priority-selected unit
	// with a unit from a lower-priority dispatch if its facility score is 1.5× better.
	// This violates the invariant: PRIORITY MUST ALWAYS WIN over facility convenience.

	t.Run("PriorityWinsOverFacility", func(t *testing.T) {
		results := []workflow.DispatchDecision{
			{Priority: 200, ChosenUnitID: "u-urgent", FacilityScore: 10.0},
			{Priority: 50, ChosenUnitID: "u-convenient", FacilityScore: 100.0},
		}
		best := workflow.MergeParallelDispatch(results)
		if best.ChosenUnitID != "u-urgent" {
			t.Errorf("priority 200 should always win over priority 50, but got unit %s (facility score override)",
				best.ChosenUnitID)
		}
	})
	t.Run("HighPriorityUnitNotReplaced", func(t *testing.T) {
		results := []workflow.DispatchDecision{
			{Priority: 150, ChosenUnitID: "u1", FacilityScore: 5.0},
			{Priority: 100, ChosenUnitID: "u2", FacilityScore: 50.0},
			{Priority: 80, ChosenUnitID: "u3", FacilityScore: 200.0},
		}
		best := workflow.MergeParallelDispatch(results)
		if best.Priority != 150 {
			t.Errorf("highest priority (150) should be selected, got %d", best.Priority)
		}
		if best.ChosenUnitID != "u1" {
			t.Errorf("unit from highest priority dispatch should be kept, got %s", best.ChosenUnitID)
		}
	})
	t.Run("EqualPriorityLargerIncidentWins", func(t *testing.T) {
		results := []workflow.DispatchDecision{
			{Priority: 100, RequiredUnits: 2, ChosenUnitID: "u1", FacilityScore: 10.0},
			{Priority: 100, RequiredUnits: 5, ChosenUnitID: "u2", FacilityScore: 10.0},
		}
		best := workflow.MergeParallelDispatch(results)
		if best.RequiredUnits != 5 {
			t.Errorf("equal priority: larger incident (5 units) should win, got %d units", best.RequiredUnits)
		}
	})
}

func TestConcurrencyRollbackStopsOnError(t *testing.T) {
	// RollbackSteps breaks on first error, leaving remaining steps un-rolled-back.
	// This creates a partially rolled-back state that's worse than no rollback at all.

	t.Run("AllStepsRolledBackOnSuccess", func(t *testing.T) {
		var rolledBack []string
		steps := []workflow.WorkflowStep{
			{Name: "step1"}, {Name: "step2"}, {Name: "step3"},
		}
		errs := workflow.RollbackSteps(steps, func(name string) error {
			rolledBack = append(rolledBack, name)
			return nil
		})
		if len(errs) != 0 {
			t.Fatalf("no errors expected, got %d", len(errs))
		}
		if len(rolledBack) != 3 {
			t.Fatalf("all 3 steps should be rolled back, got %d", len(rolledBack))
		}
	})
	t.Run("ContinuesRollbackAfterError", func(t *testing.T) {
		var rolledBack []string
		steps := []workflow.WorkflowStep{
			{Name: "step1"}, {Name: "step2"}, {Name: "step3"},
		}
		errs := workflow.RollbackSteps(steps, func(name string) error {
			rolledBack = append(rolledBack, name)
			if name == "step2" {
				return fmt.Errorf("rollback failed: %s", name)
			}
			return nil
		})
		// Step2 error should NOT prevent step1 from being rolled back
		if len(rolledBack) < 3 {
			t.Errorf("all 3 steps should attempt rollback even after error, got %d: %v", len(rolledBack), rolledBack)
		}
		if len(errs) != 1 {
			t.Errorf("expected 1 error (from step2), got %d", len(errs))
		}
	})
	t.Run("AllErrorsCollected", func(t *testing.T) {
		steps := []workflow.WorkflowStep{
			{Name: "s1"}, {Name: "s2"}, {Name: "s3"},
		}
		errs := workflow.RollbackSteps(steps, func(name string) error {
			return fmt.Errorf("failed: %s", name)
		})
		if len(errs) != 3 {
			t.Errorf("expected 3 errors (one per step), got %d", len(errs))
		}
	})
	t.Run("ReverseOrder", func(t *testing.T) {
		var rolledBack []string
		steps := []workflow.WorkflowStep{
			{Name: "step1"}, {Name: "step2"}, {Name: "step3"},
		}
		workflow.RollbackSteps(steps, func(name string) error {
			rolledBack = append(rolledBack, name)
			return nil
		})
		if len(rolledBack) >= 3 && rolledBack[0] != "step3" {
			t.Errorf("first rollback should be step3 (reverse order), got %s", rolledBack[0])
		}
	})
}
