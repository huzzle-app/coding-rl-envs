package stress

import (
	"testing"

	"incidentmesh/internal/compliance"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/resilience"
	"incidentmesh/internal/workflow"
	"incidentmesh/pkg/models"
)

// State machine bugs: invalid transitions that violate system invariants.

func TestStateMachineIncidentLifecycle(t *testing.T) {
	// IncidentLifecycleTransition allows triaged→resolved, bypassing dispatch entirely.
	// In emergency response, resolving without dispatch means no responders were sent.

	t.Run("ValidFullPath", func(t *testing.T) {
		path := []string{"new", "triaged", "assigned", "dispatched", "en_route", "on_scene", "resolved", "closed"}
		for i := 0; i < len(path)-1; i++ {
			if !workflow.IncidentLifecycleTransition(path[i], path[i+1]) {
				t.Errorf("%s → %s should be valid", path[i], path[i+1])
			}
		}
	})
	t.Run("CannotResolveWithoutDispatch", func(t *testing.T) {
		// This is the critical domain invariant: you can't resolve without sending responders
		if workflow.IncidentLifecycleTransition("triaged", "resolved") {
			t.Error("triaged → resolved must be invalid: cannot resolve without dispatching responders")
		}
	})
	t.Run("CannotSkipDispatchPhase", func(t *testing.T) {
		if workflow.IncidentLifecycleTransition("assigned", "en_route") {
			t.Error("assigned → en_route invalid: must be dispatched first")
		}
	})
	t.Run("CannotResolveFromDispatch", func(t *testing.T) {
		if workflow.IncidentLifecycleTransition("dispatched", "resolved") {
			t.Error("dispatched → resolved invalid: responders must reach scene first")
		}
	})
	t.Run("ClosedIsTerminal", func(t *testing.T) {
		for _, target := range []string{"new", "triaged", "assigned", "dispatched"} {
			if workflow.IncidentLifecycleTransition("closed", target) {
				t.Errorf("closed → %s must be invalid: closed is terminal", target)
			}
		}
	})
}

func TestStateMachineEscalationNoSkipping(t *testing.T) {
	// ValidEscalationTransition allows skipping levels (e.g., 0→3).
	// Domain: each escalation level involves different responders/authority.
	// Skipping means some notification chain is bypassed.

	t.Run("ValidSingleStep", func(t *testing.T) {
		if !escalation.ValidEscalationTransition(0, 1) {
			t.Error("0 → 1 should be valid (single step)")
		}
	})
	t.Run("CannotSkipTwoLevels", func(t *testing.T) {
		if escalation.ValidEscalationTransition(0, 3) {
			t.Error("0 → 3 must be invalid: skips level 1 and 2 notification chains")
		}
	})
	t.Run("CannotSkipOneLevel", func(t *testing.T) {
		if escalation.ValidEscalationTransition(1, 4) {
			t.Error("1 → 4 must be invalid: skips levels 2 and 3")
		}
	})
	t.Run("CannotDeescalate", func(t *testing.T) {
		if escalation.ValidEscalationTransition(3, 1) {
			t.Error("3 → 1 must be invalid: de-escalation not allowed")
		}
	})
}

func TestStateMachineAutoResolveInversion(t *testing.T) {
	// AutoResolveEligible allows severity>3 to auto-resolve.
	// Domain: high severity (4,5) means active life threat — NEVER auto-resolve.

	t.Run("CriticalSeverityNeverAutoResolves", func(t *testing.T) {
		if escalation.AutoResolveEligible(5, 999, 0) {
			t.Error("severity 5 (active life threat) must NEVER auto-resolve")
		}
	})
	t.Run("HighSeverityNeverAutoResolves", func(t *testing.T) {
		if escalation.AutoResolveEligible(4, 999, 0) {
			t.Error("severity 4 must NEVER auto-resolve")
		}
	})
	t.Run("LowSeverityCanAutoResolve", func(t *testing.T) {
		if !escalation.AutoResolveEligible(1, 200, 0) {
			t.Error("severity 1 open 200min with 0 responders should auto-resolve")
		}
	})
	t.Run("LowSeverityWithRespondersCanNot", func(t *testing.T) {
		if escalation.AutoResolveEligible(2, 200, 3) {
			t.Error("active responders present: should not auto-resolve")
		}
	})
}

func TestStateMachineCircuitBreakerRecovery(t *testing.T) {
	// AdvancedCircuitBreaker requires threshold+1 successes (off-by-one).

	t.Run("ClosedBelowFailureThreshold", func(t *testing.T) {
		state := resilience.AdvancedCircuitBreaker(2, 0, 5, 3)
		if state != "closed" {
			t.Errorf("2 failures (threshold 5): expected closed, got %s", state)
		}
	})
	t.Run("OpensAtFailureThreshold", func(t *testing.T) {
		state := resilience.AdvancedCircuitBreaker(5, 0, 5, 3)
		if state != "open" {
			t.Errorf("5 failures (threshold 5): expected open, got %s", state)
		}
	})
	t.Run("HalfOpenDuringRecovery", func(t *testing.T) {
		state := resilience.AdvancedCircuitBreaker(10, 2, 5, 3)
		if state != "half-open" {
			t.Errorf("2/3 recovery successes: expected half-open, got %s", state)
		}
	})
	t.Run("ClosesAtRecoveryThreshold", func(t *testing.T) {
		state := resilience.AdvancedCircuitBreaker(10, 3, 5, 3)
		if state != "closed" {
			t.Errorf("3/3 recovery successes: expected closed, got %s", state)
		}
	})
}

func TestStateMachineCooldownUnitMismatch(t *testing.T) {
	// CooldownExpired compares millisecond elapsed time to seconds directly.
	// 5000ms elapsed with 5sec cooldown: 5000 > 5 = true (wrong! should be false)

	t.Run("CooldownNotExpiredWithinWindow", func(t *testing.T) {
		// 2000ms elapsed, 5-second cooldown (5000ms) — not expired
		if escalation.CooldownExpired(1000, 3000, 5) {
			t.Error("2000ms elapsed with 5-second cooldown: should NOT be expired")
		}
	})
	t.Run("CooldownBoundary", func(t *testing.T) {
		// 5000ms elapsed, 5-second cooldown (5000ms) — at boundary, not expired
		if escalation.CooldownExpired(1000, 6000, 5) {
			t.Error("5000ms elapsed with 5-second cooldown: boundary should NOT be expired")
		}
	})
	t.Run("CooldownExpiredAfterWindow", func(t *testing.T) {
		// 6000ms elapsed, 5-second cooldown (5000ms) — expired
		if !escalation.CooldownExpired(1000, 7000, 5) {
			t.Error("6000ms elapsed with 5-second cooldown: should be expired")
		}
	})
}

func TestStateMachineAuditChainTimestampOrdering(t *testing.T) {
	// ValidateAuditChain only checks ID uniqueness, ignores timestamp order.
	// An audit chain with timestamps [300, 100, 200] should be INVALID
	// because it indicates tampering or corruption.

	t.Run("OutOfOrderTimestampsInvalid", func(t *testing.T) {
		records := []models.AuditRecord{
			{ID: "a1", Action: "create", Timestamp: 300},
			{ID: "a2", Action: "update", Timestamp: 100},
			{ID: "a3", Action: "close", Timestamp: 200},
		}
		if compliance.ValidateAuditChain(records) {
			t.Error("audit chain [300, 100, 200] should be invalid (non-monotonic timestamps)")
		}
	})
	t.Run("OrderedTimestampsValid", func(t *testing.T) {
		records := []models.AuditRecord{
			{ID: "a1", Action: "create", Timestamp: 100},
			{ID: "a2", Action: "update", Timestamp: 200},
			{ID: "a3", Action: "close", Timestamp: 300},
		}
		if !compliance.ValidateAuditChain(records) {
			t.Error("ordered audit chain should be valid")
		}
	})
	t.Run("DuplicateIDsStillInvalid", func(t *testing.T) {
		records := []models.AuditRecord{
			{ID: "a1", Action: "create", Timestamp: 100},
			{ID: "a1", Action: "update", Timestamp: 200},
		}
		if compliance.ValidateAuditChain(records) {
			t.Error("duplicate IDs should be invalid")
		}
	})
}
