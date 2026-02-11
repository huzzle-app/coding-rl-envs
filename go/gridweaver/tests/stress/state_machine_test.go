package stress

import (
	"testing"

	"gridweaver/internal/consensus"
	"gridweaver/internal/events"
	"gridweaver/internal/resilience"
	"gridweaver/internal/workflow"
)

func TestStateMachineBugs(t *testing.T) {

	t.Run("CircuitBreaker_ClosedToOpen", func(t *testing.T) {
		cb := resilience.NewCircuitBreaker(3, 2, 5000)
		if cb.State != "closed" {
			t.Fatalf("initial state should be closed, got %s", cb.State)
		}
		// Record 3 failures to trip the breaker
		cb.RecordResult(false, 1000)
		cb.RecordResult(false, 2000)
		cb.RecordResult(false, 3000)
		if cb.State != "open" {
			t.Fatalf("should be open after 3 failures, got %s", cb.State)
		}
	})

	t.Run("CircuitBreaker_OpenToHalfOpen", func(t *testing.T) {
		cb := resilience.NewCircuitBreaker(2, 2, 1000)
		cb.RecordResult(false, 100)
		cb.RecordResult(false, 200)
		if cb.State != "open" {
			t.Fatalf("should be open, got %s", cb.State)
		}
		// Try recording in open state before timeout - should stay open
		cb.RecordResult(true, 500)
		if cb.State != "open" {
			t.Fatalf("should stay open before timeout, got %s", cb.State)
		}
		// After timeout, should transition to half-open
		cb.RecordResult(true, 1300)
		if cb.State != "half-open" {
			t.Fatalf("should transition to half-open after timeout, got %s", cb.State)
		}
	})

	t.Run("CircuitBreaker_HalfOpenToClosed", func(t *testing.T) {
		cb := resilience.NewCircuitBreaker(2, 2, 1000)
		// Trip the breaker
		cb.RecordResult(false, 100)
		cb.RecordResult(false, 200)
		// Wait for timeout to enter half-open
		cb.RecordResult(true, 1300)
		if cb.State != "half-open" {
			t.Fatalf("should be half-open, got %s", cb.State)
		}
		// 2 successful probes should close the breaker
		cb.RecordResult(true, 1400)
		cb.RecordResult(true, 1500)
		if cb.State != "closed" {
			t.Fatalf("should be closed after successful probes, got %s", cb.State)
		}
	})

	t.Run("CircuitBreaker_HalfOpenReopens", func(t *testing.T) {
		cb := resilience.NewCircuitBreaker(2, 3, 1000)
		// Trip the breaker
		cb.RecordResult(false, 100)
		cb.RecordResult(false, 200)
		// Enter half-open
		cb.RecordResult(true, 1300)
		if cb.State != "half-open" {
			t.Fatalf("should be half-open, got %s", cb.State)
		}
		// 2 success + 1 failure in 3 probes should re-open
		cb.RecordResult(true, 1400)
		cb.RecordResult(false, 1500)
		cb.RecordResult(true, 1600)
		if cb.State != "open" {
			t.Fatalf("should re-open after mixed probes (need all success), got %s", cb.State)
		}
	})

	t.Run("CircuitBreaker_AllowRequest", func(t *testing.T) {
		cb := resilience.NewCircuitBreaker(2, 2, 1000)
		if !cb.AllowRequest(0) {
			t.Fatalf("closed breaker should allow requests")
		}
		cb.RecordResult(false, 100)
		cb.RecordResult(false, 200)
		if cb.AllowRequest(500) {
			t.Fatalf("open breaker should not allow requests before timeout")
		}
		if !cb.AllowRequest(1300) {
			t.Fatalf("open breaker should allow requests after timeout (for probing)")
		}
	})

	t.Run("RetryStateMachine_ExhaustsAttempts", func(t *testing.T) {
		rsm := resilience.NewRetryStateMachine(3, 100)
		if !rsm.ShouldRetry() {
			t.Fatalf("should allow retry initially")
		}
		rsm.RecordAttempt(false)
		rsm.RecordAttempt(false)
		rsm.RecordAttempt(false)
		// After 3 failures with max 3 attempts, should stop retrying
		rsm.RecordAttempt(false)
		if rsm.ShouldRetry() {
			t.Fatalf("should not retry after exhausting attempts (current=%d, max=%d)",
				rsm.CurrentAttempt, rsm.MaxAttempts)
		}
	})

	t.Run("RetryStateMachine_BackoffEscalates", func(t *testing.T) {
		rsm := resilience.NewRetryStateMachine(5, 100)
		rsm.RecordAttempt(false)
		bo1 := rsm.BackoffMs
		rsm.RecordAttempt(false)
		bo2 := rsm.BackoffMs
		rsm.RecordAttempt(false)
		bo3 := rsm.BackoffMs
		if bo2 <= bo1 || bo3 <= bo2 {
			t.Fatalf("backoff should escalate: %d, %d, %d", bo1, bo2, bo3)
		}
	})

	t.Run("SagaExecutor_CompensatesOnFailure", func(t *testing.T) {
		var executionOrder []string
		var compensationOrder []string
		steps := []workflow.SagaStep{
			{
				Name:       "step1",
				Execute:    func() error { executionOrder = append(executionOrder, "exec1"); return nil },
				Compensate: func() error { compensationOrder = append(compensationOrder, "comp1"); return nil },
			},
			{
				Name:       "step2",
				Execute:    func() error { executionOrder = append(executionOrder, "exec2"); return nil },
				Compensate: func() error { compensationOrder = append(compensationOrder, "comp2"); return nil },
			},
			{
				Name: "step3",
				Execute: func() error {
					executionOrder = append(executionOrder, "exec3")
					return &testError{"step3 failed"}
				},
				Compensate: func() error { compensationOrder = append(compensationOrder, "comp3"); return nil },
			},
		}
		completed, err := workflow.SagaExecutor(steps)
		if err == nil {
			t.Fatalf("should return error from step3")
		}
		if completed != 2 {
			t.Fatalf("should have completed 2 steps before failure, got %d", completed)
		}
		// Compensations should run in reverse order: comp2, comp1 (not comp3 - it failed)
		if len(compensationOrder) != 2 {
			t.Fatalf("should compensate 2 executed steps, got %d: %v", len(compensationOrder), compensationOrder)
		}
		if compensationOrder[0] != "comp2" || compensationOrder[1] != "comp1" {
			t.Fatalf("compensations should be in reverse order [comp2,comp1], got %v", compensationOrder)
		}
	})

	t.Run("SagaExecutor_AllSucceed", func(t *testing.T) {
		count := 0
		steps := []workflow.SagaStep{
			{Name: "s1", Execute: func() error { count++; return nil }, Compensate: func() error { return nil }},
			{Name: "s2", Execute: func() error { count++; return nil }, Compensate: func() error { return nil }},
		}
		completed, err := workflow.SagaExecutor(steps)
		if err != nil {
			t.Fatalf("should not error when all succeed: %v", err)
		}
		if completed != 2 {
			t.Fatalf("should report 2 completed, got %d", completed)
		}
	})

	t.Run("ChainedWorkflow_PropagatesError", func(t *testing.T) {
		steps := []func(string) (string, error){
			func(s string) (string, error) { return s + "_step1", nil },
			func(s string) (string, error) { return "", &testError2{"failed at step2"} },
			func(s string) (string, error) { return s + "_step3", nil },
		}
		_, completed, err := workflow.ChainedWorkflow("init", steps)
		if completed != 1 {
			t.Fatalf("should complete 1 step before error, got %d", completed)
		}
		if err == nil {
			t.Fatalf("should propagate error from step2")
		}
	})

	t.Run("ChainedWorkflow_SuccessChain", func(t *testing.T) {
		steps := []func(string) (string, error){
			func(s string) (string, error) { return s + "+A", nil },
			func(s string) (string, error) { return s + "+B", nil },
		}
		result, completed, err := workflow.ChainedWorkflow("start", steps)
		if err != nil {
			t.Fatalf("should not error: %v", err)
		}
		if completed != 2 {
			t.Fatalf("should complete all 2 steps, got %d", completed)
		}
		if result != "start+A+B" {
			t.Fatalf("expected 'start+A+B', got '%s'", result)
		}
	})

	t.Run("RunMultiStage_ReportsAllCompleted", func(t *testing.T) {
		stages := []func() (string, error){
			func() (string, error) { return "out1", nil },
			func() (string, error) { return "out2", nil },
			func() (string, error) { return "out3", nil },
		}
		result := workflow.RunMultiStage(stages)
		if result.Error != nil {
			t.Fatalf("should not error: %v", result.Error)
		}
		if result.StagesCompleted != 3 {
			t.Fatalf("should report 3 stages completed, got %d", result.StagesCompleted)
		}
		if len(result.Outputs) != 3 {
			t.Fatalf("should have 3 outputs, got %d", len(result.Outputs))
		}
	})

	t.Run("EventProjection_StateAccumulation", func(t *testing.T) {
		proj := events.NewProjection()
		proj.Apply(events.Event{ID: "e1", Sequence: 1, Payload: map[string]string{}})
		proj.Apply(events.Event{ID: "e2", Sequence: 2, Payload: map[string]string{}})
		proj.Apply(events.Event{ID: "e3", Sequence: 3, Payload: map[string]string{}})
		// Replay same sequence - should be rejected
		proj.Apply(events.Event{ID: "e4", Sequence: 2, Payload: map[string]string{}})
		if proj.Applied != 3 {
			t.Fatalf("should have applied 3 events (rejected replay), got %d", proj.Applied)
		}
	})

	t.Run("CausalOrder_DetectsViolations", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Sequence: 10},
			{ID: "e2", Sequence: 5},  // should come after e1
			{ID: "e3", Sequence: 20},
		}
		deps := map[string][]string{
			"e2": {"e1"}, // e2 depends on e1, but e2.seq < e1.seq
		}
		violations := events.CausalOrder(evts, deps)
		if len(violations) == 0 {
			t.Fatalf("should detect causal ordering violation for e2")
		}
		found := false
		for _, v := range violations {
			if v == "e2" {
				found = true
			}
		}
		if !found {
			t.Fatalf("e2 should be in violations list, got %v", violations)
		}
	})

	t.Run("VoteValidator_GrantsVote", func(t *testing.T) {
		ok := consensus.VoteValidator(5, 5, "", "alice", 10, 8)
		if !ok {
			t.Fatalf("should grant vote: candidate term >= voter term, no prior vote, longer log")
		}
	})

	t.Run("VoteValidator_RejectsOldTerm", func(t *testing.T) {
		ok := consensus.VoteValidator(3, 5, "", "alice", 10, 8)
		if ok {
			t.Fatalf("should reject vote: candidate term < voter term")
		}
	})

	t.Run("VoteValidator_RejectsEqualLogLength", func(t *testing.T) {
		ok := consensus.VoteValidator(5, 5, "", "alice", 10, 10)
		if !ok {
			t.Fatalf("should grant vote when candidate log is equal length (at least as up-to-date)")
		}
	})

	t.Run("LogConsistency_DetectsDivergence", func(t *testing.T) {
		leader := []int64{1, 2, 3, 4, 5}
		follower := []int64{1, 2, 9, 4, 5}
		consistent, idx := consensus.LogConsistency(leader, follower)
		if consistent {
			t.Fatalf("should detect inconsistency at index 2")
		}
		if idx != 2 {
			t.Fatalf("divergence should be at index 2, got %d", idx)
		}
	})

	t.Run("LogConsistency_MatchingLogs", func(t *testing.T) {
		leader := []int64{1, 2, 3}
		follower := []int64{1, 2, 3}
		consistent, idx := consensus.LogConsistency(leader, follower)
		if !consistent {
			t.Fatalf("matching logs should be consistent")
		}
		if idx != 3 {
			t.Fatalf("match index should be 3, got %d", idx)
		}
	})
}

type testError struct{ msg string }
func (e *testError) Error() string { return e.msg }

type testError2 struct{ msg string }
func (e *testError2) Error() string { return e.msg }
