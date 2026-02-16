package stress

import (
	"fmt"
	"testing"

	"quorumledger/internal/auditing"
	"quorumledger/internal/consensus"
	"quorumledger/internal/ledger"
	"quorumledger/internal/policy"
	"quorumledger/internal/queue"
	"quorumledger/internal/reconciliation"
	"quorumledger/internal/replay"
	"quorumledger/internal/resilience"
	"quorumledger/internal/risk"
	"quorumledger/internal/routing"
	"quorumledger/internal/security"
	"quorumledger/internal/settlement"
	"quorumledger/internal/statistics"
	"quorumledger/internal/workflow"
	"quorumledger/pkg/models"
)

const totalCases = 7500

func TestHyperMatrix(t *testing.T) {
	for i := 0; i < totalCases; i++ {
		i := i
		t.Run(fmt.Sprintf("case_%05d", i), func(t *testing.T) {
			bucket := i % 14
			switch bucket {
			case 0:
				votes := []models.QuorumVote{
					{NodeID: fmt.Sprintf("n%d", i%5), Epoch: int64(i % 100), Approved: i%3 != 0},
					{NodeID: fmt.Sprintf("n%d", (i+1)%5), Epoch: int64(i%100 + 1), Approved: i%4 != 0},
					{NodeID: fmt.Sprintf("n%d", (i+2)%5), Epoch: int64(i%100 + 2), Approved: true},
				}
				ratio := consensus.ApprovalRatio(votes)
				if ratio < 0 || ratio > 1 {
					t.Fatalf("invalid ratio: %.4f", ratio)
				}
				tol := consensus.ByzantineTolerance(3 + i%7)
				if tol < 0 {
					t.Fatalf("negative tolerance: %d", tol)
				}
				health := consensus.QuorumHealth(votes, 3)
				if health != "strong" && health != "adequate" && health != "weak" && health != "failed" {
					t.Fatalf("invalid health: %s", health)
				}

			case 1:
				entries := []models.LedgerEntry{
					{Account: "a", AmountCents: int64(i%500 - 250), Sequence: 1, Currency: "USD"},
					{Account: "b", AmountCents: int64(250 - i%500), Sequence: 1, Currency: "USD"},
				}
				exp := ledger.NetExposure(entries)
				if exp < 0 {
					t.Fatalf("negative exposure: %d", exp)
				}
				bal := ledger.AccountBalance(entries, "a")
				if bal != int64(i%500-250) {
					t.Fatalf("wrong balance: %d", bal)
				}
				overdrawn := ledger.DetectOverdraft(map[string]int64{"a": 100}, entries)
				_ = overdrawn
				merged := ledger.MergeBalances(map[string]int64{"x": 100}, map[string]int64{"x": int64(i%50 + 1), "y": 200})
				if merged["y"] != 200 {
					t.Fatalf("merge y failed")
				}
				if merged["x"] != 100+int64(i%50+1) {
					t.Fatalf("merge x should sum: expected %d, got %d", 100+int64(i%50+1), merged["x"])
				}

			case 2:
				budget := replay.ReplayBudget(100+i%200, 5+i%10)
				if budget < 0 {
					t.Fatalf("negative budget: %d", budget)
				}
				events := []replay.ReplayEvent{
					{ID: fmt.Sprintf("e-%d", i%17), Sequence: int64(i % 100)},
					{ID: fmt.Sprintf("e-%d", i%17), Sequence: int64(i%100 + 5)},
					{ID: fmt.Sprintf("f-%d", i%13), Sequence: int64(i%100 + 1)},
				}
				compacted := replay.CompactLog(events)
				if len(compacted) < 1 {
					t.Fatalf("compact too small")
				}
				window := replay.ReplayWindow(events, int64(i%50), int64(i%50+50))
				_ = window
				interval := replay.CheckpointInterval(100+i%50, 5+i%5)
				if interval < 1 {
					t.Fatalf("invalid interval: %d", interval)
				}

			case 3:
				candidates := []string{"alpha", "beta", "gamma", "delta"}
				degraded := map[string]bool{}
				if i%3 == 0 {
					degraded["alpha"] = true
				}
				if i%5 == 0 {
					degraded["beta"] = true
				}
				leader := resilience.PickLeader(candidates, degraded)
				if leader == "" {
					t.Fatalf("no leader selected")
				}
				if degraded[leader] && !allDegraded(candidates, degraded) {
					t.Fatalf("degraded leader selected: %s", leader)
				}
				state := resilience.CircuitBreakerState(i%15, 10)
				if state != "open" && state != "half-open" && state != "closed" {
					t.Fatalf("invalid state: %s", state)
				}
				backoff := resilience.RetryBackoff(i%5, 100)
				if backoff < 100 {
					t.Fatalf("backoff below base: %d", backoff)
				}

			case 4:
				score := risk.ComputeRiskScore(int64(i*1000), i%5, float64(i%100)/100.0)
				tier := risk.RiskTier(score)
				if tier != "low" && tier != "moderate" && tier != "high" && tier != "critical" {
					t.Fatalf("invalid tier: %s", tier)
				}
				limit := risk.ExposureLimit(tier)
				if tier == "critical" && limit != 0 {
					t.Fatalf("expected 0 limit for critical")
				}
				agg := risk.AggregateRisk([]float64{score, score * 0.5})
				if agg < 0 {
					t.Fatalf("negative aggregate: %.4f", agg)
				}

			case 5:
				candidates := map[string]int{"r1": 10 + i%20, "r2": 5 + i%15, "r3": 20 + i%30}
				blocked := map[string]bool{}
				if i%4 == 0 {
					blocked["r2"] = true
				}
				replica, ok := routing.SelectReplica(candidates, blocked)
				if !ok {
					t.Fatalf("no replica")
				}
				if blocked[replica] {
					t.Fatalf("blocked replica selected")
				}
				routes := []routing.WeightedRoute{
					{Channel: "a", Latency: 10 + i%20},
					{Channel: "b", Latency: 5 + i%10},
					{Channel: "c", Latency: 30 + i%10},
				}
				fast, _ := routing.PartitionRoutes(routes, 20)
				_ = fast
				health := routing.RouteHealth(routes, blocked)
				if health != "healthy" && health != "degraded" && health != "critical" && health != "down" {
					t.Fatalf("invalid health: %s", health)
				}

			case 6:
				payload := fmt.Sprintf("tx:%d", i)
				chain := security.HashChain([]string{payload, "salt"})
				if len(chain) != 64 {
					t.Fatalf("invalid hash length: %d", len(chain))
				}
				level := security.PermissionLevel("operator")
				if level <= 0 {
					t.Fatalf("invalid permission level: %d", level)
				}
				token := fmt.Sprintf("tok_%016d", i)
				valid := security.ValidateToken(token, 16)
				if !valid {
					t.Fatalf("expected valid token")
				}
				req := security.AuditRequired("escalation")
				if !req {
					t.Fatalf("expected escalation to require audit")
				}

			case 7:
				values := []int{i%100 + 1, (i*3)%100 + 1, (i*7)%100 + 1, (i*11)%100 + 1}
				p50 := statistics.Percentile(values, 50)
				if p50 < 0 {
					t.Fatalf("negative percentile: %d", p50)
				}
				sla := statistics.RollingSLA(values, 50)
				if sla < 0 || sla > 1 {
					t.Fatalf("invalid SLA: %.4f", sla)
				}
				fvals := []float64{float64(values[0]), float64(values[1]), float64(values[2]), float64(values[3])}
				m := statistics.Mean(fvals)
				if m <= 0 {
					t.Fatalf("invalid mean: %.4f", m)
				}
				med := statistics.Median(fvals)
				if med <= 0 {
					t.Fatalf("invalid median: %.4f", med)
				}

			case 8:
				windows := []models.SettlementWindow{
					{ID: "w1", OpenMinute: 10, CloseMinute: 20, Capacity: 2},
					{ID: "w2", OpenMinute: 20, CloseMinute: 30, Capacity: 3},
				}
				assignments := workflow.PlanSettlement(windows, 1+i%4)
				if len(assignments) == 0 {
					t.Fatalf("no assignments")
				}
				allowed := workflow.CanTransition("pending", "approved")
				if !allowed {
					t.Fatalf("expected pending->approved")
				}
				disallowed := workflow.CanTransition("processing", "failed")
				if !disallowed {
					t.Fatalf("expected processing->failed allowed")
				}
				e := workflow.NewWorkflowEngine([]string{"a", "b", "c"})
				e.Advance()
				if e.StepCount() != 1 {
					t.Fatalf("expected 1 step")
				}

			case 9:
				r1 := auditing.CreateAuditRecord(fmt.Sprintf("r%d", i), "alice", "transfer", int64(i), "")
				if r1.Checksum == "" {
					t.Fatalf("empty checksum")
				}
				r2 := auditing.CreateAuditRecord(fmt.Sprintf("r%d-2", i), "bob", "settlement", int64(i+1), r1.Checksum)
				chain := []models.AuditRecord{r1, r2}
				if !auditing.ValidateAuditChain(chain) {
					t.Fatalf("chain validation failed")
				}
				complete := auditing.AuditTrailComplete(chain, []string{"transfer", "settlement"})
				if !complete {
					t.Fatalf("expected complete trail")
				}
				filtered := auditing.FilterByEpochRange(chain, int64(i), int64(i+2))
				if len(filtered) != 2 {
					t.Fatalf("expected 2 filtered records, got %d", len(filtered))
				}

			case 10:
				level := policy.EscalationLevel(i%6, (i%4)+1)
				if level < models.PolicyNormal || level > models.PolicyHalted {
					t.Fatalf("invalid level: %d", level)
				}
				next := policy.NextEscalation(models.PolicyNormal)
				if next != models.PolicyWatch {
					t.Fatalf("NextEscalation(Normal) should be Watch (1), got %d", next)
				}
				hold := policy.ShouldHoldTransaction(int64(i*1000), models.PolicyHalted)
				if !hold {
					t.Fatalf("expected hold at halted")
				}
				band := policy.ExposureBand(int64(i * 1000))
				if band != "low" && band != "medium" && band != "high" && band != "critical" {
					t.Fatalf("invalid band: %s", band)
				}

			case 11:
				depth := (i % 30) + 1
				if queue.ShouldShed(depth, 40, false) && depth < 40 {
					t.Fatalf("unexpected shed at depth %d", depth)
				}
				if !queue.ShouldShed(40, 40, false) {
					t.Fatalf("expected shed at max depth")
				}
				q := queue.NewPriorityQueue(5)
				q.Enqueue(models.QueueItem{ID: fmt.Sprintf("q%d", i), Priority: i % 10})
				q.Enqueue(models.QueueItem{ID: fmt.Sprintf("q%d-b", i), Priority: (i + 5) % 10})
				if q.Size() != 2 {
					t.Fatalf("expected size 2")
				}
				wait := queue.EstimateWaitTime(i%10, 100)
				if wait != (i%10)*100 {
					t.Fatalf("unexpected wait: %d", wait)
				}

			case 12:
				entries := []models.ReconciliationEntry{
					{Account: "a", Expected: int64(1000 + i%500), Actual: int64(1000 + i%500 + i%100)},
				}
				drift := reconciliation.ComputeDrift(entries)
				_ = drift
				exceeds := reconciliation.DriftExceedsThreshold(entries, int64(i%100+1))
				_ = exceeds
				report := reconciliation.ReconciliationReport{Matched: 5, Unmatched: 0, NetDrift: 0}
				status := reconciliation.ReconciliationStatus(report)
				if status != "balanced" {
					t.Fatalf("expected balanced, got %s", status)
				}

			case 13:
				entries := []models.LedgerEntry{
					{Account: "x", AmountCents: int64(i%1000 + 100)},
					{Account: "y", AmountCents: int64(-(i%500 + 50))},
				}
				positions := settlement.NetPositions(entries)
				if len(positions) != 2 {
					t.Fatalf("expected 2 positions")
				}
				fee := settlement.SettlementFee(int64(i*100+1000), 25)
				if fee < 0 {
					t.Fatalf("negative fee: %d", fee)
				}
				batches := settlement.OptimalBatching(entries, 1)
				if len(batches) != 2 {
					t.Fatalf("expected 2 batches for 2 entries with size 1")
				}
			}
		})
	}
}

func allDegraded(candidates []string, degraded map[string]bool) bool {
	for _, c := range candidates {
		if !degraded[c] {
			return false
		}
	}
	return true
}
