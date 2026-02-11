package stress

import (
	"testing"

	"incidentmesh/internal/communications"
	"incidentmesh/internal/consensus"
	"incidentmesh/internal/resilience"
	"incidentmesh/pkg/models"
)

// Integration bugs: cross-component interactions that fail in combination.

func TestIntegrationElectionTimeoutBackoff(t *testing.T) {
	// ElectionTimeoutMs uses linear backoff (base + attempt*base).
	// Correct: exponential (base * 2^attempt).
	// Linear backoff causes re-elections too frequently under sustained partitions.

	t.Run("ExponentialGrowth", func(t *testing.T) {
		base := 100
		t0 := consensus.ElectionTimeoutMs(0, base)
		t1 := consensus.ElectionTimeoutMs(1, base)
		t2 := consensus.ElectionTimeoutMs(2, base)
		t3 := consensus.ElectionTimeoutMs(3, base)
		if t0 != 100 {
			t.Errorf("attempt 0: expected 100ms, got %d", t0)
		}
		if t1 != 200 {
			t.Errorf("attempt 1: expected 200ms (100*2^1), got %d", t1)
		}
		if t2 != 400 {
			t.Errorf("attempt 2: expected 400ms (100*2^2), got %d", t2)
		}
		if t3 != 800 {
			t.Errorf("attempt 3: expected 800ms (100*2^3), got %d", t3)
		}
	})
	t.Run("BackoffRatioDoubles", func(t *testing.T) {
		base := 50
		t2 := consensus.ElectionTimeoutMs(2, base)
		t4 := consensus.ElectionTimeoutMs(4, base)
		ratio := float64(t4) / float64(t2)
		// Exponential: ratio = 2^(4-2) = 4.0. Linear: ratio = (1+4)/(1+2) = 1.67
		if ratio < 3.5 || ratio > 4.5 {
			t.Errorf("timeout(4)/timeout(2) should be ~4.0 (exponential), got %.2f (t2=%d, t4=%d)",
				ratio, t2, t4)
		}
	})
}

func TestIntegrationWeightedQuorumIgnoresWeights(t *testing.T) {
	// WeightedQuorum sums vote COUNTS instead of node WEIGHTS.
	// A single high-weight node's vote should count more than many low-weight nodes.

	t.Run("HighWeightNodeAlone", func(t *testing.T) {
		votes := map[string]int{"node-A": 1}
		weights := map[string]int{"node-A": 80, "node-B": 10, "node-C": 10}
		// Node A has weight 80/100 — its vote alone should be quorum
		if !consensus.WeightedQuorum(votes, weights, 100) {
			t.Error("node-A (weight 80/100) voting alone should be a quorum")
		}
	})
	t.Run("LowWeightNodesInsufficient", func(t *testing.T) {
		votes := map[string]int{"node-B": 1, "node-C": 1}
		weights := map[string]int{"node-A": 80, "node-B": 10, "node-C": 10}
		// B+C weight = 20/100, not a quorum
		if consensus.WeightedQuorum(votes, weights, 100) {
			t.Error("nodes B+C (weight 20/100) should NOT be a quorum")
		}
	})
	t.Run("VoteCountsVsWeights", func(t *testing.T) {
		// 3 nodes vote, each with weight 5. Total weight 100. Should NOT be quorum.
		votes := map[string]int{"n1": 1, "n2": 1, "n3": 1}
		weights := map[string]int{"n1": 5, "n2": 5, "n3": 5}
		if consensus.WeightedQuorum(votes, weights, 100) {
			t.Error("3 votes with combined weight 15/100 should NOT be quorum (weights, not vote counts)")
		}
	})
}

func TestIntegrationChannelPriorityInFailover(t *testing.T) {
	// SelectHighestPriorityChannel selects LOWEST priority (< instead of >).
	// In emergency comms failover, wrong channel selection can delay notifications.

	t.Run("HighestPrioritySelected", func(t *testing.T) {
		channels := []string{"email", "sms", "push"}
		priorities := map[string]int{"email": 2, "sms": 5, "push": 1}
		best := communications.SelectHighestPriorityChannel(channels, priorities)
		if best != "sms" {
			t.Errorf("sms (priority 5) should be selected, got %s", best)
		}
	})
	t.Run("TwoChannels", func(t *testing.T) {
		channels := []string{"radio", "satellite"}
		priorities := map[string]int{"radio": 10, "satellite": 3}
		best := communications.SelectHighestPriorityChannel(channels, priorities)
		if best != "radio" {
			t.Errorf("radio (priority 10) should be selected, got %s", best)
		}
	})
	t.Run("EqualPriorityFirstWins", func(t *testing.T) {
		channels := []string{"a", "b", "c"}
		priorities := map[string]int{"a": 5, "b": 5, "c": 5}
		best := communications.SelectHighestPriorityChannel(channels, priorities)
		if best != "a" {
			t.Errorf("equal priorities: first channel should win, got %s", best)
		}
	})
}

func TestIntegrationBatchMessageIntegrity(t *testing.T) {
	// BatchMessages uses batchSize-1, losing one message per batch.
	// In emergency notification, a lost message means someone isn't alerted.

	t.Run("NoMessageLoss", func(t *testing.T) {
		messages := []string{"m1", "m2", "m3", "m4"}
		batches := communications.BatchMessages(messages, 2)
		total := 0
		for _, b := range batches {
			total += len(b)
		}
		if total != 4 {
			t.Errorf("all 4 messages must be in batches, got %d (messages lost in batching)", total)
		}
	})
	t.Run("CorrectBatchSizes", func(t *testing.T) {
		messages := []string{"m1", "m2", "m3", "m4"}
		batches := communications.BatchMessages(messages, 2)
		if len(batches) != 2 {
			t.Fatalf("4 messages / batch 2: expected 2 batches, got %d", len(batches))
		}
		for i, b := range batches {
			if len(b) != 2 {
				t.Errorf("batch %d: expected 2 messages, got %d", i, len(b))
			}
		}
	})
	t.Run("UnevenBatchComplete", func(t *testing.T) {
		messages := []string{"a", "b", "c", "d", "e", "f", "g"}
		batches := communications.BatchMessages(messages, 3)
		seen := map[string]bool{}
		for _, batch := range batches {
			for _, m := range batch {
				seen[m] = true
			}
		}
		for _, m := range messages {
			if !seen[m] {
				t.Errorf("message %q lost in batching", m)
			}
		}
	})
}

func TestIntegrationRetryBudgetWithWindow(t *testing.T) {
	// Combined test: budget within window + window expiry.

	t.Run("BudgetDeniedWithinWindow", func(t *testing.T) {
		allowed := resilience.RetryBudgetCheck(3, 5, 1000, 1500, 2000)
		if !allowed {
			t.Error("3/5 budget used within window: should allow")
		}
		denied := resilience.RetryBudgetCheck(5, 5, 1000, 1500, 2000)
		if denied {
			t.Error("5/5 budget used within window: should deny")
		}
	})
	t.Run("ExpiredWindowResets", func(t *testing.T) {
		allowed := resilience.RetryBudgetCheck(10, 5, 1000, 5000, 2000)
		if !allowed {
			t.Error("expired window: budget should reset, allow retry")
		}
	})
}

func TestIntegrationDispatchMergeThenCoverage(t *testing.T) {
	// Multi-step: MergeDispatchPlans drops unique entries from b,
	// then DispatchCoverage counts wrong entity (units vs incidents).
	// Combined: coverage metric is wrong for two independent reasons.

	t.Run("MergePreservesAllUniquePlans", func(t *testing.T) {
		a := []models.DispatchPlan{
			{IncidentID: "inc-1", UnitIDs: []string{"u1"}},
			{IncidentID: "inc-2", UnitIDs: []string{"u2"}},
		}
		b := []models.DispatchPlan{
			{IncidentID: "inc-3", UnitIDs: []string{"u3"}},
			{IncidentID: "inc-4", UnitIDs: []string{"u4"}},
		}
		merged := models.MergeDispatchPlans(a, b)
		coverage := models.DispatchCoverage(merged, 4)
		if coverage < 0.99 {
			t.Errorf("4 unique plans covering 4 incidents: expected 1.0 coverage, got %.2f (merge dropped entries or coverage miscounted)", coverage)
		}
	})
	t.Run("OverlappingMergeStillCovers", func(t *testing.T) {
		a := []models.DispatchPlan{{IncidentID: "inc-1", UnitIDs: []string{"u1"}}}
		b := []models.DispatchPlan{
			{IncidentID: "inc-1", UnitIDs: []string{"u2"}},
			{IncidentID: "inc-2", UnitIDs: []string{"u3"}},
		}
		merged := models.MergeDispatchPlans(a, b)
		incIDs := map[string]bool{}
		for _, p := range merged {
			incIDs[p.IncidentID] = true
		}
		if !incIDs["inc-2"] {
			t.Error("inc-2 (unique to list b) should survive merge")
		}
	})
}
