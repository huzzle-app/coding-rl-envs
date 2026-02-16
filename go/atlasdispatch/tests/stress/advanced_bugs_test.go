package stress

import (
	"atlasdispatch/internal/allocator"
	"atlasdispatch/internal/policy"
	"atlasdispatch/internal/queue"
	"atlasdispatch/internal/resilience"
	"atlasdispatch/internal/routing"
	"atlasdispatch/internal/security"
	"atlasdispatch/internal/statistics"
	"atlasdispatch/internal/workflow"
	"atlasdispatch/pkg/models"
	"fmt"
	"math"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// Latent Bug: ScheduleWithDeadlines excludes orders at exact deadline
// Latent Bug: AllocateCostsEvenly loses remainder from truncation
// ---------------------------------------------------------------------------

func TestAllocatorDeadlineMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("deadline_%05d", i), func(t *testing.T) {
			currentHour := 10 + (i % 14)
			orders := []allocator.Order{
				{ID: fmt.Sprintf("d1-%d", i), Urgency: 5 + (i % 3), ETA: "08:00"},
				{ID: fmt.Sprintf("d2-%d", i), Urgency: 3, ETA: "09:00"},
				{ID: fmt.Sprintf("d3-%d", i), Urgency: 7, ETA: "10:00"},
			}
			deadlines := map[string]int{
				fmt.Sprintf("d1-%d", i): currentHour,
				fmt.Sprintf("d2-%d", i): currentHour + 2,
				fmt.Sprintf("d3-%d", i): currentHour - 1,
			}
			result := allocator.ScheduleWithDeadlines(orders, deadlines, currentHour)
			if len(result) != 2 {
				t.Fatalf("case %d: expected 2 eligible orders (at + after deadline), got %d", i, len(result))
			}

			total := 100.0 + float64(i%7)*10.0 + 0.01*float64(i%100)
			count := 3 + (i % 5)
			allocated := allocator.AllocateCostsEvenly(total, count)
			if len(allocated) != count {
				t.Fatalf("case %d: expected %d allocations, got %d", i, count, len(allocated))
			}
			sum := 0.0
			for _, a := range allocated {
				sum += a
			}
			if math.Abs(sum-total) > 0.001 {
				t.Fatalf("case %d: cost drift: total=%.4f sum=%.4f diff=%.4f", i, total, sum, sum-total)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// State Machine Bug: CascadeEscalate overshoots by one level
// Domain Bug: EvaluateComplianceWindow includes extra element
// ---------------------------------------------------------------------------

func TestPolicyEscalationMatrix(t *testing.T) {
	policies := []string{"normal", "watch", "restricted", "halted"}
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("escalation_%05d", i), func(t *testing.T) {
			startIdx := i % 3
			current := policies[startIdx]
			levels := 1 + (i % 2)

			result := policy.CascadeEscalate(current, levels)
			expectedIdx := startIdx + levels
			if expectedIdx >= len(policies) {
				expectedIdx = len(policies) - 1
			}
			expected := policies[expectedIdx]
			if result != expected {
				t.Fatalf("case %d: CascadeEscalate(%s, %d) = %s, want %s", i, current, levels, result, expected)
			}

			responses := make([]int, 10+(i%20))
			for j := range responses {
				responses[j] = (j*7 + i) % 100
			}
			target := 50
			windowSize := 5
			compliance := policy.EvaluateComplianceWindow(responses, target, windowSize)
			windowStart := len(responses) - windowSize
			if windowStart < 0 {
				windowStart = 0
			}
			actualWindow := responses[windowStart:]
			met := 0
			for _, r := range actualWindow {
				if r <= target {
					met++
				}
			}
			expectedCompliance := float64(met) / float64(len(actualWindow)) * 100.0
			if math.Abs(compliance-expectedCompliance) > 0.01 {
				t.Fatalf("case %d: compliance=%.2f, expected=%.2f (window len: got %d, want %d)",
					i, compliance, expectedCompliance, len(responses)-windowStart, windowSize)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// State Machine Bug: ValidateTransitionPath skips intermediate transitions
// Latent Bug: TransitionBatch doesn't write to global audit log
// ---------------------------------------------------------------------------

func TestWorkflowPathMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("path_%05d", i), func(t *testing.T) {
			validPaths := [][]string{
				{"queued", "allocated", "departed", "arrived"},
				{"queued", "allocated", "departed"},
				{"queued", "allocated", "cancelled"},
				{"queued", "cancelled"},
			}
			invalidPaths := [][]string{
				{"queued", "cancelled", "departed", "arrived"},
				{"queued", "departed", "arrived"},
				{"allocated", "queued", "allocated"},
				{"arrived", "departed", "allocated"},
			}

			pathIdx := i % len(validPaths)
			if !workflow.ValidateTransitionPath(validPaths[pathIdx]) {
				t.Fatalf("case %d: valid path %v rejected", i, validPaths[pathIdx])
			}

			invIdx := i % len(invalidPaths)
			if workflow.ValidateTransitionPath(invalidPaths[invIdx]) {
				t.Fatalf("case %d: invalid path %v accepted", i, invalidPaths[invIdx])
			}

			we := workflow.NewWorkflowEngine()
			entityID := fmt.Sprintf("entity-%d", i)
			we.Register(entityID, "queued")
			transitions := map[string]string{entityID: "allocated"}
			results := we.TransitionBatch(transitions)
			if !results[entityID].Success {
				t.Fatalf("case %d: batch transition failed: %s", i, results[entityID].Reason)
			}

			auditLog := we.AuditLog()
			found := false
			for _, record := range auditLog {
				if record.EntityID == entityID && record.From == "queued" && record.To == "allocated" {
					found = true
					break
				}
			}
			if !found {
				t.Fatalf("case %d: batch transition not recorded in audit log (log len: %d)", i, len(auditLog))
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Multi-step Bug: MergeEventStreams only deduplicates within each stream
// Multi-step Bug: ReplayFromCheckpoint skips event at checkpoint sequence
// ---------------------------------------------------------------------------

func TestResilienceStreamMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("stream_%05d", i), func(t *testing.T) {
			sharedID := fmt.Sprintf("shared-%d", i%20)
			streamA := []resilience.Event{
				{ID: sharedID, Sequence: 1},
				{ID: fmt.Sprintf("a-only-%d", i), Sequence: 2},
			}
			streamB := []resilience.Event{
				{ID: sharedID, Sequence: 3},
				{ID: fmt.Sprintf("b-only-%d", i), Sequence: 4},
			}
			merged := resilience.MergeEventStreams([][]resilience.Event{streamA, streamB})

			idCount := make(map[string]int)
			for _, e := range merged {
				idCount[e.ID]++
			}
			if idCount[sharedID] > 1 {
				t.Fatalf("case %d: cross-stream duplicate not removed: %s appears %d times",
					i, sharedID, idCount[sharedID])
			}

			checkpointSeq := 5
			events := []resilience.Event{
				{ID: fmt.Sprintf("e1-%d", i), Sequence: 4},
				{ID: fmt.Sprintf("e2-%d", i), Sequence: 5},
				{ID: fmt.Sprintf("e3-%d", i), Sequence: 6},
				{ID: fmt.Sprintf("e4-%d", i), Sequence: 7},
			}
			replayed := resilience.ReplayFromCheckpoint(events, checkpointSeq)

			hasCheckpointEvent := false
			for _, e := range replayed {
				if e.Sequence == checkpointSeq {
					hasCheckpointEvent = true
					break
				}
			}
			if !hasCheckpointEvent {
				t.Fatalf("case %d: event at checkpoint sequence %d missing from replay (got %d events)",
					i, checkpointSeq, len(replayed))
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Domain Bug: MergePriorityQueues keeps lower priority for duplicate items
// Domain Bug: EstimateWaitTimeBatch uses cumulative depth
// ---------------------------------------------------------------------------

func TestQueueMergeMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("qmerge_%05d", i), func(t *testing.T) {
			a := queue.NewPriorityQueue()
			b := queue.NewPriorityQueue()
			sharedID := fmt.Sprintf("shared-%d", i)
			hiPri := 10 + (i % 20)
			loPri := 1 + (i % 5)

			a.Enqueue(queue.Item{ID: sharedID, Priority: hiPri})
			a.Enqueue(queue.Item{ID: fmt.Sprintf("a-%d", i), Priority: 8})
			b.Enqueue(queue.Item{ID: sharedID, Priority: loPri})
			b.Enqueue(queue.Item{ID: fmt.Sprintf("b-%d", i), Priority: 12})

			merged := queue.MergePriorityQueues(a, b)
			found := false
			items := merged.Drain(merged.Size())
			for _, item := range items {
				if item.ID == sharedID {
					found = true
					if item.Priority != hiPri {
						t.Fatalf("case %d: merged duplicate %s has priority %d, want %d (highest)",
							i, sharedID, item.Priority, hiPri)
					}
				}
			}
			if !found {
				t.Fatalf("case %d: shared item %s missing from merged queue", i, sharedID)
			}

			depths := []int{10, 20, 30}
			rate := 10.0
			waits := queue.EstimateWaitTimeBatch(depths, rate)
			for j, d := range depths {
				expected := float64(d) / rate
				if math.Abs(waits[j]-expected) > 0.001 {
					t.Fatalf("case %d: wait[%d] = %.2f, want %.2f (depth=%d, rate=%.1f)",
						i, j, waits[j], expected, d, rate)
				}
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Integration Bug: ValidateTokenSequence rejects equal-expiry tokens
// ---------------------------------------------------------------------------

func TestSecurityTokenMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("token_%05d", i), func(t *testing.T) {
			expiry := time.Now().Add(time.Duration(60+i%60) * time.Minute)

			sameExpiryTokens := []security.Token{
				{Value: fmt.Sprintf("tok1-%d", i), Subject: "user-a", ExpiresAt: expiry},
				{Value: fmt.Sprintf("tok2-%d", i), Subject: "user-a", ExpiresAt: expiry},
			}
			valid, failIdx := security.ValidateTokenSequence(sameExpiryTokens)
			if !valid {
				t.Fatalf("case %d: tokens with same expiry rejected at index %d", i, failIdx)
			}

			increasingTokens := []security.Token{
				{Value: fmt.Sprintf("inc1-%d", i), Subject: "user-b", ExpiresAt: expiry},
				{Value: fmt.Sprintf("inc2-%d", i), Subject: "user-b", ExpiresAt: expiry.Add(time.Minute)},
				{Value: fmt.Sprintf("inc3-%d", i), Subject: "user-b", ExpiresAt: expiry.Add(2 * time.Minute)},
			}
			valid2, failIdx2 := security.ValidateTokenSequence(increasingTokens)
			if !valid2 {
				t.Fatalf("case %d: strictly increasing tokens rejected at index %d", i, failIdx2)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Domain Bug: PlanMultiLegOptimized returns maxLegs+1 legs
// Integration Bug: ChooseRouteWithFallback ignores blocked for secondaries
// ---------------------------------------------------------------------------

func TestRoutingFallbackMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("routing_%05d", i), func(t *testing.T) {
			routes := []routing.Route{
				{Channel: "ch-a", Latency: 2 + (i % 5)},
				{Channel: "ch-b", Latency: 4 + (i % 3)},
				{Channel: "ch-c", Latency: 1 + (i % 6)},
				{Channel: "ch-d", Latency: 3 + (i % 4)},
				{Channel: "ch-e", Latency: 5 + (i % 2)},
			}
			maxLegs := 3
			plan := routing.PlanMultiLegOptimized(routes, nil, maxLegs)
			if len(plan.Legs) > maxLegs {
				t.Fatalf("case %d: PlanMultiLegOptimized returned %d legs, max is %d",
					i, len(plan.Legs), maxLegs)
			}

			primaries := []routing.Route{
				{Channel: "primary-a", Latency: 5},
			}
			secondaries := []routing.Route{
				{Channel: "sec-ok", Latency: 3},
				{Channel: "sec-blocked", Latency: 1},
			}
			blocked := map[string]bool{
				"primary-a":   true,
				"sec-blocked": true,
			}
			chosen := routing.ChooseRouteWithFallback(primaries, secondaries, blocked)
			if chosen != nil && chosen.Channel == "sec-blocked" {
				t.Fatalf("case %d: fallback selected blocked secondary route %s", i, chosen.Channel)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Domain Bug: WeightedMean returns sum instead of normalized mean
// Domain Bug: CorrelationCoeff uses dx*dx instead of dx*dy
// ---------------------------------------------------------------------------

func TestStatisticsWeightedMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("stats_%05d", i), func(t *testing.T) {
			values := []float64{float64(2 + i%10), float64(4 + i%8), float64(6 + i%6)}
			weights := []float64{1.0, 2.0, 1.0}
			got := statistics.WeightedMean(values, weights)
			totalWeight := 0.0
			weightedSum := 0.0
			for j := range values {
				weightedSum += values[j] * weights[j]
				totalWeight += weights[j]
			}
			expected := weightedSum / totalWeight
			if math.Abs(got-expected) > 0.001 {
				t.Fatalf("case %d: WeightedMean = %.4f, want %.4f", i, got, expected)
			}

			x := []float64{1.0, 2.0, 3.0, 4.0, 5.0}
			scale := 2.0 + float64(i%5)
			y := make([]float64, len(x))
			for j := range x {
				y[j] = x[j] * scale
			}
			corr := statistics.CorrelationCoeff(x, y)
			if math.Abs(corr-1.0) > 0.001 {
				t.Fatalf("case %d: CorrelationCoeff of perfectly correlated data = %.4f, want 1.0", i, corr)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Domain Bug: PrioritizeOrders uses inverted SLA tiebreaker
// ---------------------------------------------------------------------------

func TestModelPriorityMatrix(t *testing.T) {
	for i := 0; i < 250; i++ {
		i := i
		t.Run(fmt.Sprintf("priority_%05d", i), func(t *testing.T) {
			baseSev := 2 + (i % 3)
			baseSLA := 20 + (i % 50)
			orderA := models.DispatchOrder{
				ID:         fmt.Sprintf("tight-%d", i),
				Severity:   baseSev,
				SLAMinutes: baseSLA,
			}
			orderB := models.DispatchOrder{
				ID:         fmt.Sprintf("loose-%d", i),
				Severity:   baseSev + 1,
				SLAMinutes: baseSLA + 10,
			}

			if orderA.UrgencyScore() != orderB.UrgencyScore() {
				t.Skipf("case %d: scores differ, skipping tiebreaker test", i)
			}

			prioritized := models.PrioritizeOrders([]models.DispatchOrder{orderB, orderA})

			if len(prioritized) != 2 {
				t.Fatalf("case %d: expected 2 orders, got %d", i, len(prioritized))
			}
			if prioritized[0].SLAMinutes > prioritized[1].SLAMinutes {
				t.Fatalf("case %d: shorter SLA should rank first when urgency tied (score=%d), got SLA %d before %d",
					i, prioritized[0].UrgencyScore(), prioritized[0].SLAMinutes, prioritized[1].SLAMinutes)
			}
		})
	}
}

// Concurrency tests are in tests/concurrency/ to isolate race detector impact

// ---------------------------------------------------------------------------
// Multi-step Integration: dispatch + routing + workflow combined flows
// ---------------------------------------------------------------------------

func TestMultiStepIntegrationMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("integration_%05d", i), func(t *testing.T) {
			severity := 3 + (i % 3)
			sla := 30 + (i % 60)
			order := models.DispatchOrder{ID: fmt.Sprintf("int-%d", i), Severity: severity, SLAMinutes: sla}

			planned := allocator.PlanDispatch([]allocator.Order{
				{ID: order.ID, Urgency: order.UrgencyScore(), ETA: fmt.Sprintf("%02d:00", 8+i%12)},
			}, 1)
			if len(planned) != 1 {
				t.Fatalf("case %d: expected 1 planned order", i)
			}

			routes := []routing.Route{
				{Channel: "fast", Latency: 2},
				{Channel: "slow", Latency: 10},
				{Channel: "blocked-ch", Latency: 1},
			}
			blocked := map[string]bool{"blocked-ch": true}
			plan := routing.PlanMultiLegOptimized(routes, blocked, 2)
			if len(plan.Legs) > 2 {
				t.Fatalf("case %d: multi-leg exceeded max legs: %d", i, len(plan.Legs))
			}

			we := workflow.NewWorkflowEngine()
			we.Register(order.ID, "queued")

			transitions := map[string]string{order.ID: "allocated"}
			batchResults := we.TransitionBatch(transitions)
			if !batchResults[order.ID].Success {
				t.Fatalf("case %d: batch transition to allocated failed", i)
			}

			auditLog := we.AuditLog()
			if len(auditLog) == 0 {
				t.Fatalf("case %d: audit log empty after batch transition", i)
			}

			result := we.Transition(order.ID, "departed")
			if !result.Success {
				t.Fatalf("case %d: transition to departed failed after batch allocated", i)
			}

			pol := policy.CascadeEscalate("normal", 1)
			if pol != "watch" {
				t.Fatalf("case %d: CascadeEscalate(normal, 1) = %s, want watch", i, pol)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// State Machine Depth: complex workflow paths and policy state transitions
// ---------------------------------------------------------------------------

func TestStateMachineDepthMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("statemachine_%05d", i), func(t *testing.T) {
			we := workflow.NewWorkflowEngine()
			id := fmt.Sprintf("sm-%d", i)
			we.Register(id, "queued")

			fullPath := []string{"queued", "allocated", "departed", "arrived"}
			if !workflow.ValidateTransitionPath(fullPath) {
				t.Fatalf("case %d: full valid path rejected", i)
			}

			cancelPath := []string{"queued", "cancelled", "allocated"}
			if workflow.ValidateTransitionPath(cancelPath) {
				t.Fatalf("case %d: invalid path through cancelled accepted", i)
			}

			r1 := we.Transition(id, "allocated")
			if !r1.Success {
				t.Fatalf("case %d: queued->allocated failed", i)
			}
			r2 := we.Transition(id, "departed")
			if !r2.Success {
				t.Fatalf("case %d: allocated->departed failed", i)
			}
			r3 := we.Transition(id, "arrived")
			if !r3.Success {
				t.Fatalf("case %d: departed->arrived failed", i)
			}

			if !we.IsTerminal(id) {
				t.Fatalf("case %d: arrived should be terminal", i)
			}

			pe := policy.NewPolicyEngine("normal")
			pe.Escalate(3, "test-burst")
			if pe.Current() != "watch" {
				t.Fatalf("case %d: expected watch after escalation, got %s", i, pe.Current())
			}
			pe.Escalate(3, "continued-burst")
			if pe.Current() != "restricted" {
				t.Fatalf("case %d: expected restricted after second escalation, got %s", i, pe.Current())
			}

			cascaded := policy.CascadeEscalate("normal", 2)
			if cascaded != "restricted" {
				t.Fatalf("case %d: CascadeEscalate(normal, 2) = %s, want restricted", i, cascaded)
			}
		})
	}
}

// ===========================================================================
// COMPLEX BUG TESTS — require domain understanding, not just operator swaps
// ===========================================================================

// ---------------------------------------------------------------------------
// Complex: TransitionChain should be atomic — if any step fails, all
// previous transitions must be rolled back. The entity should remain
// in its original state, not in a partially-transitioned state.
// ---------------------------------------------------------------------------

func TestWorkflowChainAtomicity(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("chain_atomic_%05d", i), func(t *testing.T) {
			we := workflow.NewWorkflowEngine()
			id := fmt.Sprintf("chain-%d", i)
			we.Register(id, "queued")

			results := we.TransitionChain(id, []string{"allocated", "INVALID_STATE", "departed"})

			hasFailure := false
			for _, r := range results {
				if !r.Success {
					hasFailure = true
					break
				}
			}
			if !hasFailure {
				t.Fatalf("case %d: chain should have at least one failure", i)
			}

			finalState := we.GetState(id)
			if finalState != "queued" {
				t.Fatalf("case %d: after failed chain, entity should be rolled back to 'queued', got '%s'", i, finalState)
			}

			history := we.History(id)
			if len(history) > 0 {
				t.Fatalf("case %d: after rollback, history should be empty, got %d records", i, len(history))
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: DetectGaps should find missing sequences but must NOT advance
// the checkpoint past gaps. The checkpoint should only advance to the
// highest contiguous sequence, not to expectedMax. Advancing past gaps
// makes them invisible to future detection calls.
// ---------------------------------------------------------------------------

func TestCheckpointGapDetection(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("gap_detect_%05d", i), func(t *testing.T) {
			cm := resilience.NewCheckpointManager()
			streamID := fmt.Sprintf("stream-%d", i)

			events := []resilience.Event{
				{ID: "e1", Sequence: 1},
				{ID: "e2", Sequence: 2},
				{ID: "e4", Sequence: 4},
				{ID: "e5", Sequence: 5},
			}

			gaps := cm.DetectGaps(streamID, events, 5)
			if len(gaps) != 1 || gaps[0] != 3 {
				t.Fatalf("case %d: first call expected gaps=[3], got %v", i, gaps)
			}

			gaps2 := cm.DetectGaps(streamID, events, 5)
			if len(gaps2) != 1 || gaps2[0] != 3 {
				t.Fatalf("case %d: second call should still detect gap at 3 (checkpoint should not advance past gap), got gaps=%v", i, gaps2)
			}

			currentCheckpoint := cm.GetCheckpoint(streamID)
			if currentCheckpoint > 2 {
				t.Fatalf("case %d: checkpoint should be at highest contiguous sequence (2), got %d", i, currentCheckpoint)
			}
		})
	}
}

// CircuitBreakerPool race tests are in tests/concurrency/ package

// ---------------------------------------------------------------------------
// Complex: ScoreAndRankRoutes uses min-max normalization. When all routes
// have identical latency, maxLat == minLat, so normLat = 0, giving all
// routes the maximum latency score (1.0). This makes reliability the
// ONLY differentiator, which is wrong — when latencies are equal, routes
// should receive a neutral latency score (0.5), not the best score.
// The result: a route with low reliability but "best" latency (tied)
// ranks too high relative to a route with high reliability.
// ---------------------------------------------------------------------------

func TestRoutingScoreNormalization(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("score_norm_%05d", i), func(t *testing.T) {
			baseLat := 2 + (i % 8)
			spread := 10 + (i % 20)
			fastRel := 0.20 + float64(i%10)*0.02
			slowRel := 0.90 + float64(i%10)*0.01

			routes := []routing.Route{
				{Channel: "fast-low-rel", Latency: baseLat},
				{Channel: "slow-high-rel", Latency: baseLat + spread},
			}
			reliabilities := map[string]float64{
				"fast-low-rel":  fastRel,
				"slow-high-rel": slowRel,
			}

			ranked := routing.ScoreAndRankRoutes(routes, reliabilities)
			if len(ranked) != 2 {
				t.Fatalf("case %d: expected 2 ranked routes, got %d", i, len(ranked))
			}

			if ranked[0].Channel != "fast-low-rel" {
				t.Fatalf("case %d: with correct normalization the worst-latency route (normLat=1) "+
					"should get score=rel*(1-1)=0 and rank last, but '%s' ranked first "+
					"(fast rel=%.2f, slow rel=%.2f, spread=%d)",
					i, ranked[0].Channel, fastRel, slowRel, spread)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: EvaluateAndAdjust checks both escalation and de-escalation in
// the same call. After escalation changes `result` from "normal" to "watch",
// the de-escalation check uses the NEW value ("watch") and finds that
// successStreak >= deescalationStreaks["watch"]=5. If true, it de-escalates
// back to "normal", completely cancelling the escalation.
// This is a logic error: escalation and de-escalation should be mutually
// exclusive. If we escalated, we should NOT also check for de-escalation
// in the same evaluation cycle.
// ---------------------------------------------------------------------------

func TestPolicyEvaluationHysteresis(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("hysteresis_%05d", i), func(t *testing.T) {
			pe := policy.NewPolicyEngine("normal")

			pe.EvaluateAndAdjust(0.5, 10)

			current := pe.Current()
			if current != "watch" {
				t.Fatalf("case %d: failureRate=0.5 with 'normal' threshold=0.3 should escalate to 'watch', got '%s'"+
					" (escalation may have been cancelled by de-escalation in same call)", i, current)
			}

			pe2 := policy.NewPolicyEngine("watch")
			pe2.EvaluateAndAdjust(0.25, 15)
			current2 := pe2.Current()
			if current2 != "restricted" {
				t.Fatalf("case %d: failureRate=0.25 with 'watch' threshold=0.2 should escalate to 'restricted', got '%s'", i, current2)
			}

			pe3 := policy.NewPolicyEngine("watch")
			pe3.EvaluateAndAdjust(0.1, 5)
			current3 := pe3.Current()
			if current3 != "normal" {
				t.Fatalf("case %d: failureRate=0.1 (below watch threshold 0.2) with successStreak=5 should de-escalate to 'normal', got '%s'", i, current3)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: EstimateDispatchCost charges the full fixed cost (base fee +
// latency surcharge) to EACH order individually. When N orders share the
// same route, the correct cost is:
//   per_order = (fixedCost / N) + variableCost
// But the function charges:
//   per_order = fixedCost + variableCost
// This overestimates total dispatch cost by fixedCost * (N-1).
// Simple 1-order tests pass because fixedCost/1 == fixedCost.
// ---------------------------------------------------------------------------

func TestDispatchCostAmortization(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("cost_amort_%05d", i), func(t *testing.T) {
			numOrders := 3 + (i % 8)
			orders := make([]allocator.Order, numOrders)
			for j := 0; j < numOrders; j++ {
				orders[j] = allocator.Order{
					ID:      fmt.Sprintf("order-%d-%d", i, j),
					Urgency: 5,
					ETA:     "10:00",
				}
			}

			baseFee := 100.0
			latency := 10
			perKm := 2.0
			distance := 50.0

			costs := allocator.EstimateDispatchCost(orders, latency, baseFee, perKm, distance)

			fixedCost := baseFee + float64(latency)*0.5
			variableCost := perKm * distance
			expectedPerOrder := fixedCost/float64(numOrders) + variableCost

			totalCost := 0.0
			for _, c := range costs {
				totalCost += c
			}
			expectedTotal := fixedCost + variableCost*float64(numOrders)

			if math.Abs(totalCost-expectedTotal) > 0.01 {
				t.Fatalf("case %d: total cost=%.2f, expected=%.2f (fixed=%.2f should be shared across %d orders)",
					i, totalCost, expectedTotal, fixedCost, numOrders)
			}

			for id, cost := range costs {
				if math.Abs(cost-expectedPerOrder) > 0.01 {
					t.Fatalf("case %d: order %s cost=%.2f, expected=%.2f (fixed %.2f / %d + variable %.2f)",
						i, id, cost, expectedPerOrder, fixedCost, numOrders, variableCost)
				}
			}
		})
	}
}

// ===========================================================================
// COMPLEX BUG TESTS II — domain-specific, algorithmic, and integration bugs
// ===========================================================================

// ---------------------------------------------------------------------------
// Complex: BatchScheduleWithPreemption overwrites the preempted order in the
// planned slice without first saving it to the rejected list. The preempted
// order simply vanishes — len(planned)+len(rejected) < len(orders).
// ---------------------------------------------------------------------------

func TestPreemptionScheduleMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("preempt_%05d", i), func(t *testing.T) {
			capacity := 2
			orders := []allocator.Order{
				{ID: fmt.Sprintf("low-%d", i), Urgency: 1 + (i % 3), ETA: "08:00"},
				{ID: fmt.Sprintf("med-%d", i), Urgency: 5 + (i % 2), ETA: "09:00"},
				{ID: fmt.Sprintf("high-%d", i), Urgency: 10 + (i % 5), ETA: "10:00"},
			}
			result := allocator.BatchScheduleWithPreemption(orders, capacity)

			totalAccounted := len(result.Planned) + len(result.Rejected)
			if totalAccounted != len(orders) {
				t.Fatalf("case %d: %d orders in, %d planned + %d rejected = %d accounted (lost %d orders — "+
					"preempted order was overwritten without being added to rejected)",
					i, len(orders), len(result.Planned), len(result.Rejected),
					totalAccounted, len(orders)-totalAccounted)
			}

			if len(result.Planned) > capacity {
				t.Fatalf("case %d: planned %d exceeds capacity %d", i, len(result.Planned), capacity)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: ExponentialBackoff applies jitter AFTER capping at maxDelayMs.
// This means the final delay can exceed maxDelayMs by up to
// maxDelayMs * jitterFraction. The correct implementation should cap
// the result AFTER adding jitter: min(delay + jitter, maxDelayMs).
// ---------------------------------------------------------------------------

func TestExponentialBackoffMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("backoff_%05d", i), func(t *testing.T) {
			base := int64(100 + (i % 100))
			maxDelay := int64(5000 + (i % 5000))
			jitter := 0.1 + float64(i%20)*0.05

			for attempt := 0; attempt < 20; attempt++ {
				delay := resilience.ExponentialBackoff(attempt, base, maxDelay, jitter)
				if delay > maxDelay {
					t.Fatalf("case %d, attempt %d: delay %d exceeds maxDelay %d "+
						"(jitter applied after cap — should be capped after jitter)",
						i, attempt, delay, maxDelay)
				}
				if delay < 0 {
					t.Fatalf("case %d, attempt %d: delay %d is negative", i, attempt, delay)
				}
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: ReconcileCheckpoints skips streams with checkpoint=0, treating
// them as "uninitialized" instead of "start from beginning". When a new
// stream is registered at checkpoint 0, its events should prevent GC of
// events that it hasn't yet processed. The global minimum should be 0,
// not the minimum of only non-zero streams.
// ---------------------------------------------------------------------------

func TestReconcileCheckpointsMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("reconcile_%05d", i), func(t *testing.T) {
			cm := resilience.NewCheckpointManager()
			numAdvanced := 2 + (i % 3)
			for s := 0; s < numAdvanced; s++ {
				cm.Record(fmt.Sprintf("advanced-%d-%d", i, s), 10+s*5+(i%20))
			}
			cm.Record(fmt.Sprintf("new-%d", i), 0)

			globalMin := cm.ReconcileCheckpoints()
			if globalMin != 0 {
				t.Fatalf("case %d: with a zero-checkpoint stream, global min should be 0, got %d "+
					"(zero-checkpoint streams represent 'start from beginning' and must not be skipped)",
					i, globalMin)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: RateLimitBatch deducts tokens from the bucket before checking if
// the request can be approved. When a request is rejected, its tokens are
// still consumed, starving subsequent requests that should have succeeded.
// The correct implementation only deducts tokens for approved requests.
// ---------------------------------------------------------------------------

func TestRateLimitBatchMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("ratelimit_%05d", i), func(t *testing.T) {
			maxTokens := 10 + (i % 20)
			rl := queue.NewRateLimiter(maxTokens, 0)

			smallCost := 2 + (i % 3)
			numSmall := (maxTokens - 2) / smallCost
			if numSmall < 1 {
				numSmall = 1
			}

			costs := make([]int, 0)
			for j := 0; j < numSmall; j++ {
				costs = append(costs, smallCost)
			}
			costs = append(costs, maxTokens+1)
			costs = append(costs, 1)

			results := rl.RateLimitBatch(costs)
			lastIdx := len(results) - 1
			rejectIdx := lastIdx - 1

			if results[rejectIdx] {
				t.Skipf("case %d: large request was unexpectedly approved", i)
			}

			consumed := 0
			for j := 0; j < rejectIdx; j++ {
				if results[j] {
					consumed += costs[j]
				}
			}
			remaining := maxTokens - consumed

			if remaining >= 1 && !results[lastIdx] {
				t.Fatalf("case %d: trailing request (cost=1) rejected despite %d tokens remaining "+
					"— rejected request at index %d consumed %d tokens it shouldn't have",
					i, remaining, rejectIdx, costs[rejectIdx])
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: CheckPathPermission uses first-match semantics instead of
// longest-prefix-match. When a broad deny rule ("/api") is listed before
// a specific allow rule ("/api/public"), requests to "/api/public/..."
// are incorrectly denied. Real permission systems (nginx, IAM) use
// longest prefix match so specific rules override general ones.
// ---------------------------------------------------------------------------

func TestPathPermissionMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("pathperm_%05d", i), func(t *testing.T) {
			bases := []string{"/api", "/admin", "/data", "/service"}
			subs := []string{"/public", "/health", "/status", "/open"}

			basePath := bases[i%len(bases)]
			subPath := subs[i%len(subs)]
			specificPath := basePath + subPath
			requestPath := specificPath + fmt.Sprintf("/resource-%d", i)

			rules := []security.PathRule{
				{PathPrefix: basePath, Allow: false},
				{PathPrefix: specificPath, Allow: true},
			}

			result := security.CheckPathPermission(requestPath, rules)
			if !result {
				t.Fatalf("case %d: path '%s' should be allowed by specific rule '%s' "+
					"(longest prefix match should win over broad deny '%s')",
					i, requestPath, specificPath, basePath)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: ComputeFleetUtilization includes cancelled vessels in the
// denominator. Cancelled vessels are no longer part of the active fleet —
// they should be excluded from both numerator AND denominator. Including
// them artificially deflates utilization. With 5 active, 3 cancelled,
// 2 arrived: correct = 5/7 ≈ 71%, buggy = 5/10 = 50%.
// ---------------------------------------------------------------------------

func TestFleetUtilizationMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("utilization_%05d", i), func(t *testing.T) {
			numOrders := 10 + (i % 10)
			numCancelled := 2 + (i % 4)
			numArrived := 1 + (i % 3)
			if numCancelled+numArrived >= numOrders {
				numCancelled = 2
				numArrived = 1
			}

			orders := make([]models.DispatchOrder, numOrders)
			states := make(map[string]string)

			for j := 0; j < numOrders; j++ {
				id := fmt.Sprintf("vessel-%d-%d", i, j)
				orders[j] = models.DispatchOrder{ID: id, Severity: 3, SLAMinutes: 60}
				if j < numCancelled {
					states[id] = "cancelled"
				} else if j < numCancelled+numArrived {
					states[id] = "arrived"
				} else {
					states[id] = "departed"
				}
			}

			utilization := models.ComputeFleetUtilization(orders, states)

			activeCount := numOrders - numCancelled - numArrived
			inServiceCount := numOrders - numCancelled
			expectedUtilization := float64(activeCount) / float64(inServiceCount)

			if math.Abs(utilization-expectedUtilization) > 0.001 {
				t.Fatalf("case %d: utilization=%.4f, expected=%.4f (active=%d, in-service=%d, "+
					"cancelled=%d should be excluded from denominator)",
					i, utilization, expectedUtilization, activeCount, inServiceCount, numCancelled)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: ExponentialMovingAverage initializes EMA to 0.0 instead of the
// first sample value. For a constant series [100, 100, 100] with alpha=0.5:
//   Correct: EMA = [100, 100, 100]
//   Buggy:   EMA = [50, 75, 87.5]   (biased toward zero)
// The downward bias decays exponentially but never fully vanishes for short
// series. Tests with many samples may miss this if they only check the tail.
// ---------------------------------------------------------------------------

func TestExponentialMovingAverageMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("ema_%05d", i), func(t *testing.T) {
			baseVal := 50.0 + float64(i%100)
			alpha := 0.1 + float64(i%9)*0.1

			values := make([]float64, 5)
			for j := range values {
				values[j] = baseVal
			}

			ema := statistics.ExponentialMovingAverage(values, alpha)
			if ema == nil {
				t.Fatalf("case %d: EMA returned nil for valid input", i)
			}

			if math.Abs(ema[0]-baseVal) > 0.001 {
				t.Fatalf("case %d: EMA[0]=%.4f, expected %.4f (first value should equal first input "+
					"when properly initialized, not biased toward 0)", i, ema[0], baseVal)
			}

			for j, v := range ema {
				if math.Abs(v-baseVal) > 0.001 {
					t.Fatalf("case %d: EMA[%d]=%.4f, expected %.4f for constant series "+
						"(init bias propagating from EMA_0=0 instead of EMA_0=first_value)",
						i, j, v, baseVal)
				}
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Complex: PlanDispatchWithConstraints doesn't check Earliest <= currentHour.
// A high-urgency order whose time window hasn't opened yet (Earliest in the
// future) gets scheduled over a lower-urgency order that IS available now.
// The scheduler should only consider orders whose window is currently open:
// Earliest <= currentHour <= Latest.
// ---------------------------------------------------------------------------

func TestConstrainedDispatchMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("constrained_%05d", i), func(t *testing.T) {
			currentHour := 10 + (i % 8)

			futureOrder := allocator.TimeConstrainedOrder{
				ID:       fmt.Sprintf("future-%d", i),
				Urgency:  10 + (i % 5),
				Earliest: currentHour + 5,
				Latest:   currentHour + 10,
			}

			readyOrder := allocator.TimeConstrainedOrder{
				ID:       fmt.Sprintf("ready-%d", i),
				Urgency:  2 + (i % 3),
				Earliest: currentHour - 2,
				Latest:   currentHour + 10,
			}

			result := allocator.PlanDispatchWithConstraints(
				[]allocator.TimeConstrainedOrder{futureOrder, readyOrder},
				currentHour, 1,
			)

			if len(result) != 1 {
				t.Fatalf("case %d: expected 1 scheduled order, got %d", i, len(result))
			}

			if result[0].ID != readyOrder.ID {
				t.Fatalf("case %d: order '%s' scheduled but not available until hour %d "+
					"(current=%d). Available order '%s' should be preferred — "+
					"Earliest constraint not enforced",
					i, result[0].ID, futureOrder.Earliest, currentHour, readyOrder.ID)
			}
		})
	}
}

// ===========================================================================
// UNTESTED BUG COVERAGE — bugs with zero prior test signal
// ===========================================================================

// ---------------------------------------------------------------------------
// Routing Bug: ChooseRoute selects highest-latency route instead of lowest.
// The sort comparator uses > (descending) instead of < (ascending), causing
// the worst available route to be selected every time.
// ---------------------------------------------------------------------------

func TestChooseRouteOrderingMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("route_order_%05d", i), func(t *testing.T) {
			lowLat := 1 + (i % 4)
			highLat := lowLat + 5 + (i % 10)
			routes := []routing.Route{
				{Channel: fmt.Sprintf("fast-%d", i), Latency: lowLat},
				{Channel: fmt.Sprintf("slow-%d", i), Latency: highLat},
			}
			best := routing.ChooseRoute(routes, nil)
			if best == nil {
				t.Fatalf("case %d: ChooseRoute returned nil for non-empty unblocked routes", i)
			}
			if best.Latency != lowLat {
				t.Fatalf("case %d: ChooseRoute should select lowest latency (%d), got %s with latency %d "+
					"(sort comparator may be inverted)", i, lowLat, best.Channel, best.Latency)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Routing Bug: CompareRoutes returns inverted values — returns +1 when a
// has lower latency (should be -1 to sort first) and -1 when a has higher
// latency (should be +1 to sort last).
// ---------------------------------------------------------------------------

func TestCompareRoutesMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("cmp_routes_%05d", i), func(t *testing.T) {
			latA := 2 + (i % 5)
			latB := latA + 3 + (i % 7)
			cmp := routing.CompareRoutes(
				routing.Route{Channel: "a", Latency: latA},
				routing.Route{Channel: "b", Latency: latB},
			)
			if cmp >= 0 {
				t.Fatalf("case %d: CompareRoutes(latency=%d, latency=%d) = %d, want negative "+
					"(lower latency should sort first)", i, latA, latB, cmp)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Allocator Bug: HasConflict uses >= for end boundary instead of >.
// Adjacent time slots (one ends at hour X, next starts at hour X) should
// NOT conflict, but the >= operator treats them as overlapping.
// ---------------------------------------------------------------------------

func TestHasConflictBoundaryMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("conflict_%05d", i), func(t *testing.T) {
			slotStart := 10 + (i % 8)
			slotEnd := slotStart + 4

			slots := []allocator.BerthSlot{
				{BerthID: fmt.Sprintf("b-%d", i), StartHour: slotStart, EndHour: slotEnd, Occupied: true},
			}

			// Adjacent: new slot ends exactly where existing starts — should NOT conflict
			if allocator.HasConflict(slots, slotStart-3, slotStart) {
				t.Fatalf("case %d: adjacent slot [%d,%d) next to [%d,%d) should NOT conflict "+
					"(newEnd == slot.StartHour is not overlap)",
					i, slotStart-3, slotStart, slotStart, slotEnd)
			}

			// Overlapping: should conflict
			if !allocator.HasConflict(slots, slotStart+1, slotEnd+2) {
				t.Fatalf("case %d: overlapping slot should conflict", i)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Allocator Bug: CheckCapacity uses <= instead of <. When currentLoad
// equals maxCapacity, the berth/vessel is full and should reject new cargo.
// The <= operator incorrectly allows loading at max capacity.
// ---------------------------------------------------------------------------

func TestCheckCapacityBoundaryMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("capacity_%05d", i), func(t *testing.T) {
			maxCap := 10 + (i % 20)

			// At capacity: should reject (return false)
			if allocator.CheckCapacity(maxCap, maxCap) {
				t.Fatalf("case %d: CheckCapacity(%d, %d) should return false when at max capacity",
					i, maxCap, maxCap)
			}

			// Below capacity: should accept
			if !allocator.CheckCapacity(maxCap-1, maxCap) {
				t.Fatalf("case %d: CheckCapacity(%d, %d) should return true when below capacity",
					i, maxCap-1, maxCap)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Allocator Bug: CompareByUrgencyThenETA returns inverted urgency comparison.
// Higher urgency should sort first (return negative), but the function
// returns +1 for higher-urgency 'a', causing it to sort last.
// ---------------------------------------------------------------------------

func TestCompareByUrgencyMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("cmp_urgency_%05d", i), func(t *testing.T) {
			urgA := 10 + (i % 10)
			urgB := urgA - 5 - (i % 3)
			if urgB < 1 {
				urgB = 1
			}

			cmp := allocator.CompareByUrgencyThenETA(
				allocator.Order{ID: "a", Urgency: urgA, ETA: "10:00"},
				allocator.Order{ID: "b", Urgency: urgB, ETA: "10:00"},
			)
			if cmp >= 0 {
				t.Fatalf("case %d: CompareByUrgencyThenETA(urgency=%d, urgency=%d) = %d, "+
					"want negative (higher urgency should sort first)", i, urgA, urgB, cmp)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Queue Bug: PriorityQueue.Enqueue sorts ascending instead of descending.
// Dequeue should return the highest-priority item, but ascending sort
// puts the lowest-priority item at index 0.
// ---------------------------------------------------------------------------

func TestPriorityQueueOrderMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("pq_order_%05d", i), func(t *testing.T) {
			pq := queue.NewPriorityQueue()
			lowPri := 1 + (i % 5)
			highPri := lowPri + 10 + (i % 10)

			pq.Enqueue(queue.Item{ID: fmt.Sprintf("low-%d", i), Priority: lowPri})
			pq.Enqueue(queue.Item{ID: fmt.Sprintf("high-%d", i), Priority: highPri})

			top := pq.Dequeue()
			if top == nil {
				t.Fatalf("case %d: Dequeue returned nil from non-empty queue", i)
			}
			if top.Priority != highPri {
				t.Fatalf("case %d: PriorityQueue should dequeue highest priority first (%d), got %d "+
					"(Enqueue sort may be inverted)", i, highPri, top.Priority)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Routing Bug: EstimateRouteCost uses 0.3 delay surcharge coefficient
// instead of the correct 0.5. This underestimates the cost impact of
// high-latency routes by 40%.
// ---------------------------------------------------------------------------

func TestEstimateRouteCostMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("route_cost_%05d", i), func(t *testing.T) {
			latency := 5 + (i % 20)
			fuelRate := 1.5 + float64(i%10)*0.2
			distance := 50.0 + float64(i%100)

			cost := routing.EstimateRouteCost(latency, fuelRate, distance)
			baseCost := fuelRate * distance
			delaySurcharge := float64(latency) * 0.5
			expected := baseCost + delaySurcharge

			if math.Abs(cost-expected) > 0.001 {
				t.Fatalf("case %d: EstimateRouteCost(lat=%d, fuel=%.2f, dist=%.1f) = %.4f, "+
					"want %.4f (delay surcharge coefficient should be 0.5, not 0.3)",
					i, latency, fuelRate, distance, cost, expected)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Security Bug: IsAllowedOrigin uses case-sensitive comparison. Domain
// names are case-insensitive per RFC 4343, so "Example.COM" should match
// "example.com" in the allowlist.
// ---------------------------------------------------------------------------

func TestIsAllowedOriginCaseMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("origin_%05d", i), func(t *testing.T) {
			domains := []string{"example.com", "api.dispatch.io", "internal.fleet.net", "port-auth.gov"}
			domain := domains[i%len(domains)]

			variants := []string{
				fmt.Sprintf("%s", domain),
				fmt.Sprintf("%s", capitalize(domain)),
				fmt.Sprintf("%s", allCaps(domain)),
			}

			for _, variant := range variants {
				if !security.IsAllowedOrigin(variant, []string{domain}) {
					t.Fatalf("case %d: IsAllowedOrigin(%q, [%q]) should be true "+
						"(domain comparison should be case-insensitive per RFC 4343)",
						i, variant, domain)
				}
			}
		})
	}
}

func capitalize(s string) string {
	if len(s) == 0 {
		return s
	}
	b := []byte(s)
	if b[0] >= 'a' && b[0] <= 'z' {
		b[0] -= 32
	}
	return string(b)
}

func allCaps(s string) string {
	b := []byte(s)
	for i := range b {
		if b[i] >= 'a' && b[i] <= 'z' {
			b[i] -= 32
		}
	}
	return string(b)
}

// ---------------------------------------------------------------------------
// Security Bug: SanitisePath doesn't decode URL-encoded sequences before
// checking for path traversal. An attacker can use %2e%2e (URL-encoded "..")
// to bypass the containment check.
// ---------------------------------------------------------------------------

func TestSanitisePathTraversalMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("sanitise_%05d", i), func(t *testing.T) {
			traversalPayloads := []string{
				"foo/%2e%2e/etc/passwd",
				"uploads/..%2f..%2fetc/shadow",
				"%2e%2e/%2e%2e/root",
				"data/%2e%2e%2f%2e%2e%2fsecrets",
			}
			payload := traversalPayloads[i%len(traversalPayloads)]
			result := security.SanitisePath(payload)
			if result != "" {
				t.Fatalf("case %d: SanitisePath(%q) = %q, want empty string "+
					"(URL-encoded path traversal should be detected and rejected)",
					i, payload, result)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Policy Bug: ShouldDeescalate multiplies threshold by 3, requiring 3x the
// success streak to de-escalate. With threshold=3 for "watch", the function
// requires 9 consecutive successes instead of the configured 3.
// ---------------------------------------------------------------------------

func TestShouldDeescalateMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("deesc_%05d", i), func(t *testing.T) {
			levels := []struct {
				policy    string
				threshold int
			}{
				{"normal", 3},
				{"watch", 3},
				{"restricted", 1},
			}
			level := levels[i%len(levels)]

			if !policy.ShouldDeescalate(level.policy, level.threshold) {
				t.Fatalf("case %d: ShouldDeescalate(%s, %d) should be true "+
					"(streak equals threshold), got false — threshold may be incorrectly multiplied",
					i, level.policy, level.threshold)
			}

			if policy.ShouldDeescalate(level.policy, level.threshold-1) {
				t.Fatalf("case %d: ShouldDeescalate(%s, %d) should be false "+
					"(streak below threshold)",
					i, level.policy, level.threshold-1)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Resilience Bug: ShouldCheckpoint uses threshold > 1000 instead of >= 100.
// This means checkpointing only triggers after 1001 events since last
// checkpoint, instead of the intended 100.
// ---------------------------------------------------------------------------

func TestShouldCheckpointMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("checkpoint_%05d", i), func(t *testing.T) {
			cm := resilience.NewCheckpointManager()

			if !cm.ShouldCheckpoint(100) {
				t.Fatalf("case %d: ShouldCheckpoint(100) should be true when lastSequence=0 "+
					"(100 events since checkpoint exceeds threshold of 100)", i)
			}

			cm.Record("s", 50)
			if !cm.ShouldCheckpoint(150) {
				t.Fatalf("case %d: ShouldCheckpoint(150) should be true when lastSequence=50 "+
					"(100 events since checkpoint)", i)
			}
		})
	}
}

// ===========================================================================
// REMAINING UNTESTED BUG COVERAGE — closing all zero-signal gaps
// ===========================================================================

// ---------------------------------------------------------------------------
// Resilience Bug: RecordSuccess uses > 3 instead of >= 3. In half_open state,
// the circuit breaker requires 4 consecutive successes to close instead of 3.
// The threshold for closing should be 3 successes.
// ---------------------------------------------------------------------------

func TestCircuitBreakerCloseMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("cb_close_%05d", i), func(t *testing.T) {
			cb := resilience.NewCircuitBreaker(2, 1)

			cb.RecordFailure()
			cb.RecordFailure()
			if cb.State() != "open" {
				t.Fatalf("case %d: expected open after 2 failures (threshold=2), got %s", i, cb.State())
			}

			time.Sleep(2 * time.Millisecond)
			state := cb.State()
			if state != "half_open" {
				t.Fatalf("case %d: expected half_open after recovery time, got %s", i, state)
			}

			cb.RecordSuccess()
			cb.RecordSuccess()
			cb.RecordSuccess()

			finalState := cb.State()
			if finalState != "closed" {
				t.Fatalf("case %d: after 3 successes in half_open, circuit should close, got '%s' "+
					"(RecordSuccess may require > 3 instead of >= 3)", i, finalState)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Statistics Bug: Variance uses N (population) instead of N-1 (sample).
// For sample variance (Bessel's correction), the denominator should be
// len(values)-1 to produce an unbiased estimate. With [2, 4, 6]:
//   mean = 4, sumSq = 8
//   Correct (sample):     8 / 2 = 4.0
//   Buggy (population):   8 / 3 ≈ 2.667
// ---------------------------------------------------------------------------

func TestVarianceSampleMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("variance_%05d", i), func(t *testing.T) {
			base := float64(10 + i%50)
			spread := float64(2 + i%10)
			values := []float64{base - spread, base, base + spread}

			got := statistics.Variance(values)

			avg := (values[0] + values[1] + values[2]) / 3.0
			sumSq := 0.0
			for _, v := range values {
				d := v - avg
				sumSq += d * d
			}
			expected := sumSq / float64(len(values)-1)

			if math.Abs(got-expected) > 0.001 {
				t.Fatalf("case %d: Variance(%v) = %.4f, want %.4f "+
					"(should use N-1 denominator for sample variance, not N)",
					i, values, got, expected)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Statistics Bug: percentileFloat adds +50 to the rank calculation, same
// as the Percentile bug. For a 4-element array at p50:
//   Correct: rank = (50 * 4) / 100 = 2 → index 1 (2nd element)
//   Buggy:   rank = ((50 * 4) + 50) / 100 = 2.5 → 3 → index 2 (3rd element)
// This shifts all percentile results upward.
// ---------------------------------------------------------------------------

func TestPercentileFloatBiasMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("pctf_bias_%05d", i), func(t *testing.T) {
			rt := statistics.NewResponseTimeTracker(1000)
			values := []float64{10.0, 20.0, 30.0, 40.0}
			for _, v := range values {
				rt.Record(v)
			}

			p50 := rt.P50()
			if p50 != 20.0 {
				t.Fatalf("case %d: P50 of [10,20,30,40] should be 20.0 (2nd element), got %.1f "+
					"(percentileFloat may add +50 bias to rank calculation)", i, p50)
			}

			rt2 := statistics.NewResponseTimeTracker(1000)
			for j := 1; j <= 10; j++ {
				rt2.Record(float64(j * 10))
			}
			p95 := rt2.P95()
			if math.Abs(p95-100.0) < 0.001 {
				t.Fatalf("case %d: P95 of [10..100] should not equal max (100.0) — "+
					"bias in rank formula pushing index too high", i)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Resilience Bug: Deduplicate uses string(rune(e.Sequence)) for the
// deduplication key. For sequences > 127, different sequences can map to
// the same rune representation, causing false deduplication. For example,
// sequences 97 and 97 are the same, but sequences 128 and 192 could
// collide depending on UTF-8 encoding. More critically, sequences 0-127
// map to ASCII, causing collisions like seq=65 ('A') for ID "x" colliding
// with seq=65 for ID "x" (correct) but not detecting seq=195+128 combos.
// The correct approach is to use strconv.Itoa(e.Sequence).
// ---------------------------------------------------------------------------

func TestDeduplicateHighSequenceMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("dedup_%05d", i), func(t *testing.T) {
			// Sequences in the surrogate pair range (0xD800-0xDFFF) all map to
			// the Unicode replacement character when converted via string(rune(seq)).
			// This means different sequences produce the same deduplication key,
			// causing legitimate unique events to be falsely "deduplicated".
			baseSeq := 0xD800 + (i % 100) // surrogate range: 55296-55395
			otherSeq := 0xD800 + 100 + (i % 100) // different surrogate: 55396-55495
			events := []resilience.Event{
				{ID: fmt.Sprintf("stream-%d", i), Sequence: baseSeq},
				{ID: fmt.Sprintf("stream-%d", i), Sequence: otherSeq},
			}
			result := resilience.Deduplicate(events)
			if len(result) != 2 {
				t.Fatalf("case %d: Deduplicate should keep 2 unique events "+
					"(same ID, sequences %d and %d), got %d "+
					"(string(rune(seq)) maps surrogates to same replacement char)",
					i, baseSeq, otherSeq, len(result))
			}

			// Also test with sequences > 0x10FFFF (beyond valid Unicode range)
			// All map to replacement character, causing collisions
			hugeSeqA := 0x110000 + i
			hugeSeqB := 0x110000 + i + 1000
			events2 := []resilience.Event{
				{ID: fmt.Sprintf("big-%d", i), Sequence: hugeSeqA},
				{ID: fmt.Sprintf("big-%d", i), Sequence: hugeSeqB},
			}
			result2 := resilience.Deduplicate(events2)
			if len(result2) != 2 {
				t.Fatalf("case %d: Deduplicate should keep 2 unique events "+
					"(same ID, sequences %d and %d), got %d "+
					"(rune key collides for values beyond Unicode range)",
					i, hugeSeqA, hugeSeqB, len(result2))
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Security Bug: TokenStore.Validate uses time.Now().Before(tok.ExpiresAt)
// which returns true when the token is still valid (not expired). But the
// function returns nil (invalid) in this case. The logic is inverted:
// it rejects valid tokens and accepts expired tokens.
// ---------------------------------------------------------------------------

func TestTokenValidationMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("tokval_%05d", i), func(t *testing.T) {
			ts := security.NewTokenStore()

			validToken := security.Token{
				Value:     fmt.Sprintf("valid-%d", i),
				Subject:   fmt.Sprintf("user-%d", i),
				ExpiresAt: time.Now().Add(time.Duration(60+i%60) * time.Minute),
			}
			ts.Store(validToken)

			result := ts.Validate(validToken.Value)
			if result == nil {
				t.Fatalf("case %d: Validate(%q) returned nil for valid token (expires in %d min) "+
					"— Before/After check may be inverted",
					i, validToken.Value, 60+i%60)
			}
			if result.Subject != validToken.Subject {
				t.Fatalf("case %d: validated token has wrong subject: got %q, want %q",
					i, result.Subject, validToken.Subject)
			}

			expiredToken := security.Token{
				Value:     fmt.Sprintf("expired-%d", i),
				Subject:   fmt.Sprintf("user-%d", i),
				ExpiresAt: time.Now().Add(-time.Duration(10+i%60) * time.Minute),
			}
			ts.Store(expiredToken)

			result2 := ts.Validate(expiredToken.Value)
			if result2 != nil {
				t.Fatalf("case %d: Validate(%q) returned non-nil for expired token "+
					"— Before/After check may be inverted", i, expiredToken.Value)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Policy Bug: CheckSLACompliance uses strict < instead of <=. When response
// time exactly equals the target, the SLA should be considered met. A
// response in exactly 30 minutes when the target is 30 minutes is compliant.
// ---------------------------------------------------------------------------

func TestSLAComplianceBoundaryMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("sla_bound_%05d", i), func(t *testing.T) {
			target := 30 + (i % 60)

			if !policy.CheckSLACompliance(target, target) {
				t.Fatalf("case %d: CheckSLACompliance(%d, %d) should be true "+
					"(response at exactly the target is compliant, uses < instead of <=)",
					i, target, target)
			}

			if !policy.CheckSLACompliance(target-1, target) {
				t.Fatalf("case %d: CheckSLACompliance(%d, %d) should be true "+
					"(response before target)", i, target-1, target)
			}

			if policy.CheckSLACompliance(target+1, target) {
				t.Fatalf("case %d: CheckSLACompliance(%d, %d) should be false "+
					"(response after target)", i, target+1, target)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Policy Bug: SLAPercentage guards with total < 0 instead of total <= 0.
// When total=0, it should return 0.0 (avoid division by zero), but the
// current guard allows total=0 through, causing a NaN or Inf result.
// ---------------------------------------------------------------------------

func TestSLAPercentageZeroDivMatrix(t *testing.T) {
	for i := 0; i < 200; i++ {
		i := i
		t.Run(fmt.Sprintf("sla_zero_%05d", i), func(t *testing.T) {
			result := policy.SLAPercentage(0, 0)
			if math.IsNaN(result) || math.IsInf(result, 0) {
				t.Fatalf("case %d: SLAPercentage(0, 0) should return 0.0, got %v "+
					"(guard uses < 0 instead of <= 0, allowing division by zero)", i, result)
			}
			if result != 0.0 {
				t.Fatalf("case %d: SLAPercentage(0, 0) should return 0.0, got %.4f", i, result)
			}

			met := 5 + (i % 10)
			total := 10 + (i % 20)
			expected := float64(met) / float64(total) * 100.0
			got := policy.SLAPercentage(met, total)
			if math.Abs(got-expected) > 0.01 {
				t.Fatalf("case %d: SLAPercentage(%d, %d) = %.2f, want %.2f",
					i, met, total, got, expected)
			}
		})
	}
}
