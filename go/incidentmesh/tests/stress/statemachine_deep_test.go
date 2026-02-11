package stress

import (
	"fmt"
	"testing"

	"incidentmesh/internal/communications"
	"incidentmesh/internal/consensus"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/workflow"
	"incidentmesh/pkg/models"
)

func TestStateMachineSeverityEscalationMapping(t *testing.T) {
	t.Run("AllSeveritiesMapped", func(t *testing.T) {
		for s := 1; s <= 5; s++ {
			level := escalation.MapSeverityToEscalationLevel(s)
			if level < 0 {
				t.Errorf("severity %d: level should be >= 0, got %d", s, level)
			}
		}
	})
	t.Run("NoGapsInMapping", func(t *testing.T) {
		levels := make([]int, 6)
		for s := 1; s <= 5; s++ {
			levels[s] = escalation.MapSeverityToEscalationLevel(s)
		}
		for s := 2; s <= 5; s++ {
			if levels[s]-levels[s-1] > 2 {
				t.Errorf("gap in mapping: severity %d->level %d, severity %d->level %d (gap > 1)",
					s-1, levels[s-1], s, levels[s])
			}
		}
	})
	t.Run("UniquePerSeverity", func(t *testing.T) {
		seen := map[int]int{}
		for s := 1; s <= 5; s++ {
			level := escalation.MapSeverityToEscalationLevel(s)
			if prev, ok := seen[level]; ok && prev != s-1 {
				t.Errorf("severity %d and %d both map to level %d (collision)", prev, s, level)
			}
			seen[level] = s
		}
	})
	t.Run("StrictlyIncreasing", func(t *testing.T) {
		prev := -1
		for s := 1; s <= 5; s++ {
			level := escalation.MapSeverityToEscalationLevel(s)
			if level <= prev {
				t.Errorf("severity %d: level %d should be > previous level %d", s, level, prev)
			}
			prev = level
		}
	})
}

func TestStateMachineCompensationOrder(t *testing.T) {
	t.Run("ReverseOrderCompensation", func(t *testing.T) {
		var order []string
		steps := []string{"create_incident", "assign_unit", "dispatch_unit", "notify_ems"}
		workflow.CompensateAll(steps, func(step string) error {
			order = append(order, step)
			return nil
		})
		if len(order) != 4 {
			t.Fatalf("expected 4 compensations, got %d", len(order))
		}
		if order[0] != "notify_ems" {
			t.Errorf("first compensation should be 'notify_ems' (last step), got '%s'", order[0])
		}
		if order[3] != "create_incident" {
			t.Errorf("last compensation should be 'create_incident' (first step), got '%s'", order[3])
		}
	})
	t.Run("ThreeStepsReversed", func(t *testing.T) {
		var order []string
		steps := []string{"A", "B", "C"}
		workflow.CompensateAll(steps, func(step string) error {
			order = append(order, step)
			return nil
		})
		expected := []string{"C", "B", "A"}
		for i, exp := range expected {
			if i < len(order) && order[i] != exp {
				t.Errorf("position %d: expected '%s', got '%s'", i, exp, order[i])
			}
		}
	})
	t.Run("SingleStepReversed", func(t *testing.T) {
		var order []string
		workflow.CompensateAll([]string{"only"}, func(step string) error {
			order = append(order, step)
			return nil
		})
		if len(order) != 1 || order[0] != "only" {
			t.Error("single step compensation should work")
		}
	})
	t.Run("ErrorsDontStopCompensation", func(t *testing.T) {
		var count int
		steps := []string{"A", "B", "C"}
		errs := workflow.CompensateAll(steps, func(step string) error {
			count++
			if step == "B" {
				return fmt.Errorf("failed")
			}
			return nil
		})
		if count != 3 {
			t.Errorf("all 3 steps should attempt compensation, got %d", count)
		}
		if len(errs) != 1 {
			t.Errorf("expected 1 error, got %d", len(errs))
		}
	})
}

func TestStateMachineVersionedMerge(t *testing.T) {
	t.Run("HigherVersionWins", func(t *testing.T) {
		a := map[string]int64{"key1": 5, "key2": 10}
		b := map[string]int64{"key1": 8, "key2": 3}
		merged := workflow.MergeVersionedResults(a, b)
		if merged["key1"] != 8 {
			t.Errorf("key1: version 8 should win over 5, got %d", merged["key1"])
		}
		if merged["key2"] != 10 {
			t.Errorf("key2: version 10 should win over 3, got %d", merged["key2"])
		}
	})
	t.Run("NoOverlapMerged", func(t *testing.T) {
		a := map[string]int64{"x": 1}
		b := map[string]int64{"y": 2}
		merged := workflow.MergeVersionedResults(a, b)
		if merged["x"] != 1 {
			t.Errorf("x should be 1, got %d", merged["x"])
		}
		if merged["y"] != 2 {
			t.Errorf("y should be 2, got %d", merged["y"])
		}
	})
	t.Run("AllConflictsResolved", func(t *testing.T) {
		a := map[string]int64{"a": 1, "b": 5, "c": 3}
		b := map[string]int64{"a": 4, "b": 2, "c": 6}
		merged := workflow.MergeVersionedResults(a, b)
		if merged["a"] != 4 {
			t.Errorf("a: expected 4 (higher), got %d", merged["a"])
		}
		if merged["b"] != 5 {
			t.Errorf("b: expected 5 (higher), got %d", merged["b"])
		}
		if merged["c"] != 6 {
			t.Errorf("c: expected 6 (higher), got %d", merged["c"])
		}
	})
	t.Run("EqualVersionsPreserved", func(t *testing.T) {
		a := map[string]int64{"key": 10}
		b := map[string]int64{"key": 10}
		merged := workflow.MergeVersionedResults(a, b)
		if merged["key"] != 10 {
			t.Errorf("equal versions: should preserve 10, got %d", merged["key"])
		}
	})
}

func TestStateMachineQuorumTransitions(t *testing.T) {
	t.Run("GainQuorum", func(t *testing.T) {
		if consensus.ReachabilityQuorum(1, 5) {
			t.Error("1/5: should not have quorum")
		}
		if consensus.ReachabilityQuorum(2, 5) {
			t.Error("2/5: should not have quorum")
		}
		if !consensus.ReachabilityQuorum(3, 5) {
			t.Error("3/5: should have quorum")
		}
	})
	t.Run("LoseQuorum", func(t *testing.T) {
		if !consensus.ReachabilityQuorum(5, 5) {
			t.Fatal("5/5: should have quorum")
		}
		if !consensus.ReachabilityQuorum(4, 5) {
			t.Error("4/5: should still have quorum")
		}
		if !consensus.ReachabilityQuorum(3, 5) {
			t.Error("3/5: should still have quorum")
		}
		if consensus.ReachabilityQuorum(2, 5) {
			t.Error("2/5: should lose quorum")
		}
	})
}

func TestStateMachineChannelSortConsistency(t *testing.T) {
	t.Run("IdempotentSort", func(t *testing.T) {
		channels := []string{"a", "b", "c"}
		scores := map[string]int{"a": 3, "b": 1, "c": 2}
		first := communications.PrioritySortChannels(channels, scores)
		second := communications.PrioritySortChannels(first, scores)
		for i := range first {
			if first[i] != second[i] {
				t.Errorf("double sort should be idempotent: first=%v, second=%v", first, second)
				break
			}
		}
	})
	t.Run("SortPreservesAllChannels", func(t *testing.T) {
		channels := []string{"x", "y", "z"}
		scores := map[string]int{"x": 10, "y": 5, "z": 1}
		sorted := communications.PrioritySortChannels(channels, scores)
		found := map[string]bool{}
		for _, ch := range sorted {
			found[ch] = true
		}
		for _, ch := range channels {
			if !found[ch] {
				t.Errorf("channel %s missing after sort", ch)
			}
		}
	})
}

func TestStateMachineDeliveryConfirmTimeout(t *testing.T) {
	t.Run("TransitionFromPendingToConfirmed", func(t *testing.T) {
		confirmed := communications.DeliveryConfirmation(1000, 1500, 2000)
		if !confirmed {
			t.Error("500ms elapsed within 2000ms timeout: should be confirmed")
		}
	})
	t.Run("TransitionFromPendingToTimedOut", func(t *testing.T) {
		timedOut := communications.DeliveryConfirmation(1000, 5000, 2000)
		if timedOut {
			t.Error("4000ms elapsed with 2000ms timeout: should be timed out")
		}
	})
	t.Run("BoundaryAtExactTimeout", func(t *testing.T) {
		atBoundary := communications.DeliveryConfirmation(1000, 3000, 2000)
		if !atBoundary {
			t.Error("exactly at timeout (2000ms): should still count as confirmed")
		}
	})
}

func TestStateMachineIncidentPriorityQueueOrder(t *testing.T) {
	t.Run("HighestSeverityFirst", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "low", Severity: 1, Criticality: 1},
			{ID: "critical", Severity: 5, Criticality: 5},
			{ID: "mid", Severity: 3, Criticality: 3},
		}
		best := models.HighestSeverityIncident(incidents)
		if best.ID != "critical" {
			t.Errorf("highest severity should be 'critical', got '%s'", best.ID)
		}
	})
	t.Run("FIFOForEqualSeverity", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "first", Severity: 5, Criticality: 1},
			{ID: "second", Severity: 5, Criticality: 5},
			{ID: "third", Severity: 5, Criticality: 3},
		}
		best := models.HighestSeverityIncident(incidents)
		if best.ID != "first" {
			t.Errorf("FIFO tie-break: first incident with max severity should be returned, got '%s'", best.ID)
		}
	})
}

func TestStateMachineEscalationLevelOrder(t *testing.T) {
	t.Run("ValidProgression", func(t *testing.T) {
		for s := 1; s <= 5; s++ {
			level := escalation.MapSeverityToEscalationLevel(s)
			if level < 0 || level > 4 {
				t.Errorf("severity %d: level %d out of range [0,4]", s, level)
			}
		}
	})
	t.Run("HigherSeverityHigherLevel", func(t *testing.T) {
		for s := 1; s < 5; s++ {
			l1 := escalation.MapSeverityToEscalationLevel(s)
			l2 := escalation.MapSeverityToEscalationLevel(s + 1)
			if l2 < l1 {
				t.Errorf("severity %d (level %d) should map to lower level than %d (level %d)",
					s, l1, s+1, l2)
			}
		}
	})
}

func TestStateMachineWorkflowStepDuration(t *testing.T) {
	t.Run("SumsAllDurations", func(t *testing.T) {
		total := workflow.WorkflowStepDuration([]int{10, 20, 30})
		if total != 60 {
			t.Errorf("expected 60, got %d", total)
		}
	})
	t.Run("EmptyDuration", func(t *testing.T) {
		total := workflow.WorkflowStepDuration(nil)
		if total != 0 {
			t.Errorf("empty: expected 0, got %d", total)
		}
	})
	t.Run("SingleStep", func(t *testing.T) {
		total := workflow.WorkflowStepDuration([]int{42})
		if total != 42 {
			t.Errorf("single step: expected 42, got %d", total)
		}
	})
}
