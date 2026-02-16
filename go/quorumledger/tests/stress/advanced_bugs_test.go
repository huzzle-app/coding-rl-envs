package stress

import (
	"math"
	"sort"
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
	"quorumledger/shared/contracts"
)

// ---------------------------------------------------------------------------
// Category 1: Latent Bugs — corrupt state silently, require specific conditions
// ---------------------------------------------------------------------------

func TestTimingSafeEqualSecurity(t *testing.T) {
	if security.TimingSafeEqual("secret-key-alpha", "secret-key-beta!") {
		t.Fatal("timing-safe comparison returned true for different strings of equal length")
	}
	if security.TimingSafeEqual("aaaaaaaaaaaaaaaa", "aaaaaaaaaaaaaaab") {
		t.Fatal("single-byte difference must be detected")
	}
	if !security.TimingSafeEqual("matching", "matching") {
		t.Fatal("identical strings must compare equal")
	}
}

func TestVoteConsistencyInterleavedNodes(t *testing.T) {
	votes := []models.QuorumVote{
		{NodeID: "node-1", Epoch: 1, Approved: true},
		{NodeID: "node-2", Epoch: 1, Approved: false},
		{NodeID: "node-1", Epoch: 2, Approved: false},
	}
	if consensus.VoteConsistency(votes) {
		t.Fatal("node-1 voted true then false across interleaved entries; should be inconsistent")
	}
}

func TestAvailabilityScoreZeroWindow(t *testing.T) {
	score := resilience.AvailabilityScore(0, 0)
	if score != 0.0 {
		t.Fatalf("availability with no measurement window must be 0.0, got %.4f", score)
	}
}

func TestMergeReplayStreamsConcurrentEvents(t *testing.T) {
	streamA := []replay.ReplayEvent{
		{ID: "evt-alpha", Sequence: 10, Payload: "a"},
		{ID: "evt-gamma", Sequence: 30, Payload: "c"},
	}
	streamB := []replay.ReplayEvent{
		{ID: "evt-beta", Sequence: 10, Payload: "b"},
		{ID: "evt-delta", Sequence: 20, Payload: "d"},
	}
	merged := replay.MergeReplayStreams(streamA, streamB)
	ids := map[string]bool{}
	for _, e := range merged {
		ids[e.ID] = true
	}
	if len(ids) < 4 {
		t.Fatalf("events with different IDs but same sequence must both be preserved; got %d unique IDs: %v", len(ids), ids)
	}
}

func TestRateLimiterExactBudgetExhaustion(t *testing.T) {
	rl := queue.NewRateLimiter(5)
	allowed := 0
	for i := 0; i < 10; i++ {
		if rl.Allow() {
			allowed++
		}
	}
	if allowed != 5 {
		t.Fatalf("rate limiter with burst 5 should allow exactly 5 requests, allowed %d", allowed)
	}
}

func TestGroupByAccountPreservesInsertionOrder(t *testing.T) {
	entries := []models.LedgerEntry{
		{Account: "acct-a", AmountCents: 100, Sequence: 1},
		{Account: "acct-a", AmountCents: 200, Sequence: 2},
		{Account: "acct-a", AmountCents: 300, Sequence: 3},
	}
	groups := ledger.GroupByAccount(entries)
	acctA := groups["acct-a"]
	if len(acctA) != 3 {
		t.Fatalf("expected 3 entries for acct-a, got %d", len(acctA))
	}
	for i, e := range acctA {
		expectedSeq := int64(i + 1)
		if e.Sequence != expectedSeq {
			t.Fatalf("entry %d: expected sequence %d, got %d — insertion order not preserved", i, expectedSeq, e.Sequence)
		}
	}
}

func TestCurrencyExposureFairTreatment(t *testing.T) {
	entries := []models.LedgerEntry{
		{AmountCents: 1000, Currency: "USD"},
		{AmountCents: 1000, Currency: "EUR"},
		{AmountCents: 1000, Currency: "GBP"},
	}
	exposure := ledger.CurrencyExposure(entries)
	if exposure["USD"] != 1000 {
		t.Fatalf("USD exposure should be 1000, got %d", exposure["USD"])
	}
	if exposure["EUR"] != 1000 {
		t.Fatalf("EUR exposure should be 1000 (same as USD), got %d", exposure["EUR"])
	}
	if exposure["GBP"] != 1000 {
		t.Fatalf("GBP exposure should be 1000 (same as USD), got %d", exposure["GBP"])
	}
}

// ---------------------------------------------------------------------------
// Category 2: Domain Logic Bugs — require understanding of financial/consensus domain
// ---------------------------------------------------------------------------

func TestByzantineToleranceMinimumCluster(t *testing.T) {
	tol3 := consensus.ByzantineTolerance(3)
	if tol3 != 0 {
		t.Fatalf("BFT with 3 nodes tolerates 0 faults (need n >= 3f+1), got %d", tol3)
	}
	tol4 := consensus.ByzantineTolerance(4)
	if tol4 != 1 {
		t.Fatalf("BFT with 4 nodes tolerates 1 fault, got %d", tol4)
	}
	tol7 := consensus.ByzantineTolerance(7)
	if tol7 != 2 {
		t.Fatalf("BFT with 7 nodes tolerates 2 faults, got %d", tol7)
	}
}

func TestConcentrationRiskHerfindahlIndex(t *testing.T) {
	exposures := map[string]int64{"A": 500, "B": 500}
	hhi := risk.ConcentrationRisk(exposures)
	expected := 0.5
	if math.Abs(hhi-expected) > 0.001 {
		t.Fatalf("equal 50/50 split HHI should be 0.50, got %.4f", hhi)
	}

	monopoly := map[string]int64{"A": 1000}
	hhi2 := risk.ConcentrationRisk(monopoly)
	if math.Abs(hhi2-1.0) > 0.001 {
		t.Fatalf("single-entity monopoly HHI should be 1.0, got %.4f", hhi2)
	}

	diversified := map[string]int64{"A": 250, "B": 250, "C": 250, "D": 250}
	hhi3 := risk.ConcentrationRisk(diversified)
	expectedDiv := 0.25
	if math.Abs(hhi3-expectedDiv) > 0.001 {
		t.Fatalf("four-way equal split HHI should be 0.25, got %.4f", hhi3)
	}
}

func TestHistogramUniformDistribution(t *testing.T) {
	values := []float64{42.0, 42.0, 42.0, 42.0, 42.0}
	hist := statistics.Histogram(values, 5)
	if len(hist) != 5 {
		t.Fatalf("expected 5 buckets, got %d", len(hist))
	}
	if hist[0] != 5 {
		t.Fatalf("all identical values should land in first bucket; got hist[0]=%d", hist[0])
	}
	for i := 1; i < len(hist); i++ {
		if hist[i] != 0 {
			t.Fatalf("bucket %d should be empty for uniform values, got %d", i, hist[i])
		}
	}
}

func TestDetectAuditGapsSmallEpochDifference(t *testing.T) {
	records := []models.AuditRecord{
		{Epoch: 1}, {Epoch: 3}, {Epoch: 6},
	}
	gaps := auditing.DetectGaps(records)
	if len(gaps) != 2 {
		t.Fatalf("expected 2 gaps (epoch 3 and 6, both have diff > 1), got %d: %v", len(gaps), gaps)
	}
}

func TestReplayWindowExclusiveLowerBound(t *testing.T) {
	events := []replay.ReplayEvent{
		{ID: "e1", Sequence: 5},
		{ID: "e2", Sequence: 10},
		{ID: "e3", Sequence: 15},
	}
	window := replay.ReplayWindow(events, 5, 15)
	if len(window) != 2 {
		t.Fatalf("window (5, 15] should exclude sequence 5 itself; expected 2 events, got %d", len(window))
	}
}

func TestSortByDriftDescending(t *testing.T) {
	entries := []models.ReconciliationEntry{
		{Account: "a", Expected: 100, Actual: 110},
		{Account: "b", Expected: 100, Actual: 200},
		{Account: "c", Expected: 100, Actual: 105},
	}
	sorted := reconciliation.SortByDrift(entries)
	if sorted[0].Account != "b" {
		t.Fatalf("highest drift (account b, drift=100) should be first; got %s with drift %d",
			sorted[0].Account, sorted[0].DriftCents())
	}
	if sorted[2].Account != "c" {
		t.Fatalf("lowest drift (account c, drift=5) should be last; got %s", sorted[2].Account)
	}
}

func TestMajorityNodesAlphabeticalOrder(t *testing.T) {
	votes := []models.QuorumVote{
		{NodeID: "charlie", Approved: true},
		{NodeID: "alpha", Approved: true},
		{NodeID: "bravo", Approved: false},
		{NodeID: "delta", Approved: true},
	}
	nodes := consensus.MajorityNodes(votes)
	if len(nodes) != 3 {
		t.Fatalf("expected 3 majority nodes, got %d", len(nodes))
	}
	if !sort.StringsAreSorted(nodes) {
		t.Fatalf("majority nodes must be alphabetically sorted, got %v", nodes)
	}
}

func TestEligibleLeadersPreservesInputOrder(t *testing.T) {
	candidates := []string{"primary", "secondary", "tertiary"}
	degraded := map[string]bool{"primary": true}
	leaders := consensus.EligibleLeaders(candidates, degraded)
	if len(leaders) != 2 {
		t.Fatalf("expected 2 leaders, got %d", len(leaders))
	}
	if leaders[0] != "secondary" || leaders[1] != "tertiary" {
		t.Fatalf("leaders should preserve input order: [secondary, tertiary], got %v", leaders)
	}
}

// ---------------------------------------------------------------------------
// Category 3: Multi-Step Bugs — fixing one reveals another
// ---------------------------------------------------------------------------

func TestMultilateralNetIncludesAllGroups(t *testing.T) {
	groups := [][]models.LedgerEntry{
		{{AmountCents: 100}},
		{{AmountCents: 200}},
		{{AmountCents: -50}},
	}
	net := settlement.MultilateralNet(groups)
	if net != 250 {
		t.Fatalf("multilateral net of [100, 200, -50] should be 250, got %d", net)
	}
}

func TestShortestPathExactDistance(t *testing.T) {
	states := workflow.SettlementStates()
	dist := workflow.ShortestPath(states, "pending", "settled")
	if dist != 3 {
		t.Fatalf("pending->settled should be distance 3 (pending, approved, processing, settled), got %d", dist)
	}
	dist0 := workflow.ShortestPath(states, "pending", "pending")
	if dist0 != 0 {
		t.Fatalf("same-state distance should be 0, got %d", dist0)
	}
}

func TestSettlementEndToEndMultiStep(t *testing.T) {
	entries := []models.LedgerEntry{
		{Account: "bank-a", AmountCents: 5000, Currency: "USD"},
		{Account: "bank-b", AmountCents: -3000, Currency: "USD"},
		{Account: "bank-c", AmountCents: -2000, Currency: "USD"},
	}
	groups := [][]models.LedgerEntry{
		{{AmountCents: 5000}},
		{{AmountCents: -3000}},
		{{AmountCents: -2000}},
	}
	multilateralTotal := settlement.MultilateralNet(groups)
	if multilateralTotal != 0 {
		t.Fatalf("balanced multilateral net should be 0, got %d", multilateralTotal)
	}

	positions := settlement.NetPositions(entries)
	if positions["bank-a"] != 5000 || positions["bank-b"] != -3000 {
		t.Fatalf("net positions incorrect: %v", positions)
	}

	fee := settlement.SettlementFee(5000, 25)
	if fee > 5000 {
		t.Fatalf("fee %d exceeds principal amount 5000", fee)
	}
}

func TestLedgerPostThenReconcile(t *testing.T) {
	initial := map[string]int64{"treasury": 10000, "client": 0}
	entries := []models.LedgerEntry{
		{Account: "treasury", AmountCents: -2500, Sequence: 1},
		{Account: "client", AmountCents: 2500, Sequence: 1},
	}
	balances := ledger.ApplyEntries(initial, entries)
	expected := []models.LedgerEntry{
		{ID: "1", Account: "treasury", AmountCents: -2500},
		{ID: "2", Account: "client", AmountCents: 2500},
	}
	actual := []models.LedgerEntry{
		{ID: "1", Account: "treasury", AmountCents: -2500},
		{ID: "2", Account: "client", AmountCents: 2500},
	}
	report := reconciliation.MatchEntries(expected, actual)
	if report.Unmatched != 0 {
		t.Fatalf("identical postings should fully reconcile; got %d unmatched", report.Unmatched)
	}
	_ = balances
}

func TestAuditChainThenGapDetection(t *testing.T) {
	r1 := auditing.CreateAuditRecord("r1", "alice", "transfer", 1, "")
	r2 := auditing.CreateAuditRecord("r2", "bob", "settlement", 3, r1.Checksum)
	r3 := auditing.CreateAuditRecord("r3", "charlie", "approval", 7, r2.Checksum)

	if !auditing.ValidateAuditChain([]models.AuditRecord{r1, r2, r3}) {
		t.Fatal("chain should be valid")
	}
	gaps := auditing.DetectGaps([]models.AuditRecord{r1, r2, r3})
	if len(gaps) < 2 {
		t.Fatalf("expected gaps at epoch 3 (diff=2) and 7 (diff=4), got %d gaps: %v", len(gaps), gaps)
	}
}

// ---------------------------------------------------------------------------
// Category 4: State Machine Bugs — workflow/transition violations
// ---------------------------------------------------------------------------

func TestSettledStateFinality(t *testing.T) {
	if workflow.CanTransition("settled", "pending") {
		t.Fatal("settled state must be final; transition to pending violates settlement finality")
	}
	if workflow.CanTransition("settled", "approved") {
		t.Fatal("settled state must be final; no transitions should be allowed from settled")
	}
	if workflow.CanTransition("settled", "processing") {
		t.Fatal("settled state must be final; cannot re-process a settled transaction")
	}
}

func TestWorkflowEngineCycleProtection(t *testing.T) {
	engine := workflow.NewWorkflowEngine([]string{"init", "processing", "done"})
	engine.Advance()
	engine.Advance()
	if !engine.IsDone() {
		t.Fatal("engine should be done after reaching final state")
	}
	advanced := engine.Advance()
	if advanced {
		t.Fatal("advancing past the final state should return false, not cycle back")
	}
	if engine.State() != "done" {
		t.Fatalf("state should remain 'done' after failed advance, got %q", engine.State())
	}
}

func TestTransitionGraphNoCycles(t *testing.T) {
	states := workflow.SettlementStates()
	for _, from := range states {
		for _, to := range states {
			if workflow.CanTransition(from, to) && workflow.CanTransition(to, from) {
				if from != to {
					t.Fatalf("bidirectional transition detected: %s <-> %s creates a cycle", from, to)
				}
			}
		}
	}
}

func TestBatchPriorityDescendingOrder(t *testing.T) {
	batches := []int{3, 1, 5, 2, 4}
	sorted := workflow.BatchPriority(batches)
	for i := 1; i < len(sorted); i++ {
		if sorted[i] > sorted[i-1] {
			t.Fatalf("batch priorities should be in descending order (highest first); got %v", sorted)
		}
	}
}

func TestWorkflowStateInvariant(t *testing.T) {
	engine := workflow.NewWorkflowEngine([]string{"pending", "approved", "processing", "settled"})
	seen := map[string]bool{}
	for engine.Advance() {
		state := engine.State()
		if seen[state] {
			t.Fatalf("workflow engine visited state %q twice — indicates illegal cycle", state)
		}
		seen[state] = true
	}
	if !engine.IsDone() {
		t.Fatal("engine should be done after exhausting all advances")
	}
}


// ---------------------------------------------------------------------------
// Category 6 & 7: Integration Bugs — cross-module cascading failures
// ---------------------------------------------------------------------------

func TestAffectedDownstreamExcludesSource(t *testing.T) {
	topology := map[string][]string{
		"gateway":   {"consensus", "intake"},
		"consensus": {"ledger"},
		"intake":    {"ledger"},
		"ledger":    {"settlement"},
	}
	downstream := resilience.AffectedDownstream("gateway", topology)
	for _, svc := range downstream {
		if svc == "gateway" {
			t.Fatal("source service 'gateway' should not appear in its own downstream list")
		}
	}
	found := map[string]bool{}
	for _, s := range downstream {
		found[s] = true
	}
	for _, expected := range []string{"consensus", "intake", "ledger", "settlement"} {
		if !found[expected] {
			t.Fatalf("missing expected downstream service: %s", expected)
		}
	}
}

func TestFailoverRouteSelectsLowestLatency(t *testing.T) {
	routes := []routing.WeightedRoute{
		{Channel: "fast", Latency: 10},
		{Channel: "medium", Latency: 50},
		{Channel: "slow", Latency: 100},
	}
	best := routing.FailoverRoute(routes, map[string]bool{})
	if best == nil {
		t.Fatal("failover should return a route when none are blocked")
	}
	if best.Channel != "fast" {
		t.Fatalf("failover should select lowest latency route 'fast', got %q", best.Channel)
	}
}

func TestFailoverRouteWithOneBlocked(t *testing.T) {
	routes := []routing.WeightedRoute{
		{Channel: "primary", Latency: 5},
		{Channel: "secondary", Latency: 15},
		{Channel: "tertiary", Latency: 30},
	}
	best := routing.FailoverRoute(routes, map[string]bool{"primary": true})
	if best == nil {
		t.Fatal("failover should return secondary when primary is blocked")
	}
	if best.Channel != "secondary" {
		t.Fatalf("expected secondary route, got %q", best.Channel)
	}
}

func TestLedgerToSettlementToReconciliation(t *testing.T) {
	initial := map[string]int64{"bank-a": 100000, "bank-b": 50000}
	entries := []models.LedgerEntry{
		{Account: "bank-a", AmountCents: -30000, Sequence: 1, Currency: "USD"},
		{Account: "bank-b", AmountCents: 30000, Sequence: 1, Currency: "USD"},
	}
	balances := ledger.ApplyEntries(initial, entries)
	if balances["bank-a"] != 70000 {
		t.Fatalf("bank-a balance should be 70000, got %d", balances["bank-a"])
	}

	balance := ledger.AccountBalance(entries, "bank-a")
	if balance != -30000 {
		t.Fatalf("bank-a entry balance should be -30000, got %d", balance)
	}

	positions := settlement.NetPositions(entries)
	if positions["bank-a"] != -30000 || positions["bank-b"] != 30000 {
		t.Fatalf("unexpected net positions: %v", positions)
	}

	recon := []models.ReconciliationEntry{
		{Account: "bank-a", Expected: 70000, Actual: 70000},
		{Account: "bank-b", Expected: 80000, Actual: 80000},
	}
	drift := reconciliation.ComputeDrift(recon)
	if drift != 0 {
		t.Fatalf("expected zero drift for balanced reconciliation, got %d", drift)
	}
}

func TestConsensusQuorumToPolicy(t *testing.T) {
	votes := []models.QuorumVote{
		{NodeID: "n1", Epoch: 1, Approved: true},
		{NodeID: "n2", Epoch: 1, Approved: true},
		{NodeID: "n3", Epoch: 1, Approved: false},
	}
	ratio := consensus.ApprovalRatio(votes)
	if ratio < 0 || ratio > 1 {
		t.Fatalf("approval ratio must be in [0,1], got %.4f", ratio)
	}

	if !consensus.HasQuorum(votes, 0.5) {
		t.Fatal("2/3 votes should form quorum at 0.5 threshold")
	}

	level := policy.EscalationLevel(0, 0)
	if level < models.PolicyNormal || level > models.PolicyHalted {
		t.Fatalf("escalation level out of valid range: %d", level)
	}
}

func TestSecurityHashChainToAudit(t *testing.T) {
	chain := security.HashChain([]string{"transfer:1000", "settlement:batch-42"})
	if len(chain) != 64 {
		t.Fatalf("hash chain should produce 64-char hex digest, got %d chars", len(chain))
	}

	r1 := auditing.CreateAuditRecord("audit-1", "system", "transfer", 1, "")
	r2 := auditing.CreateAuditRecord("audit-2", "system", "settlement", 2, r1.Checksum)
	if !auditing.ValidateAuditChain([]models.AuditRecord{r1, r2}) {
		t.Fatal("properly chained audit records should validate")
	}
}

func TestReplayRecoveryToLedger(t *testing.T) {
	budget := replay.ReplayBudget(1000, 30)
	if budget <= 0 {
		t.Fatalf("replay budget must be positive for valid inputs, got %d", budget)
	}

	events := []replay.ReplayEvent{
		{ID: "e1", Sequence: 1, Payload: "credit:1000"},
		{ID: "e2", Sequence: 2, Payload: "debit:500"},
		{ID: "e3", Sequence: 3, Payload: "credit:200"},
	}
	window := replay.ReplayWindow(events, 0, 3)
	if len(window) != 3 {
		t.Fatalf("full replay window should contain all 3 events, got %d", len(window))
	}
}

func TestEndToEndSettlementWorkflow(t *testing.T) {
	windows := []models.SettlementWindow{
		{ID: "morning", OpenMinute: 0, CloseMinute: 120, Capacity: 5},
		{ID: "afternoon", OpenMinute: 120, CloseMinute: 240, Capacity: 5},
	}
	assignments := workflow.PlanSettlement(windows, 7)
	if len(assignments) != 7 {
		t.Fatalf("expected 7 assignments across 2 windows, got %d", len(assignments))
	}

	if !workflow.CanTransition("pending", "approved") {
		t.Fatal("pending->approved should be allowed")
	}
	if !workflow.CanTransition("approved", "processing") {
		t.Fatal("approved->processing should be allowed")
	}
	if !workflow.CanTransition("processing", "settled") {
		t.Fatal("processing->settled should be allowed")
	}

	overlap := workflow.WindowOverlap(windows)
	if overlap {
		t.Fatal("non-overlapping windows should not report overlap")
	}
}

func TestServiceTopologyCompleteness(t *testing.T) {
	topology := contracts.ServiceTopology
	for svc, deps := range topology {
		for _, dep := range deps {
			if dep == svc {
				t.Fatalf("service %s has self-dependency", svc)
			}
		}
	}
	criticalServices := []string{"gateway", "consensus", "ledger", "settlement", "security"}
	for _, svc := range criticalServices {
		if _, ok := topology[svc]; !ok {
			t.Fatalf("critical service %s missing from topology", svc)
		}
	}
}

func TestMultilateralNettingWithSettlementFee(t *testing.T) {
	group1 := []models.LedgerEntry{{AmountCents: 10000}}
	group2 := []models.LedgerEntry{{AmountCents: -7000}}
	group3 := []models.LedgerEntry{{AmountCents: -3000}}

	net := settlement.MultilateralNet([][]models.LedgerEntry{group1, group2, group3})
	fee := settlement.SettlementFee(net, 25)
	if fee < 0 {
		t.Fatalf("settlement fee should never be negative, got %d", fee)
	}
	if net != 0 {
		t.Fatalf("balanced groups should net to 0, got %d", net)
	}
}

func TestCrossModuleRiskAssessment(t *testing.T) {
	score := risk.ComputeRiskScore(500000, 3, 0.8)
	tier := risk.RiskTier(score)
	limit := risk.ExposureLimit(tier)
	agg := risk.AggregateRisk([]float64{score, score * 0.5, score * 1.5})
	if agg < 0 {
		t.Fatalf("aggregate risk should not be negative, got %.4f", agg)
	}
	_ = limit
}

func TestReconciliationStatusForBalancedReport(t *testing.T) {
	report := reconciliation.ReconciliationReport{
		TotalEntries: 10,
		Matched:      10,
		Unmatched:    0,
		NetDrift:     0,
	}
	status := reconciliation.ReconciliationStatus(report)
	if status != "balanced" {
		t.Fatalf("fully matched report with zero drift should be 'balanced', got %q", status)
	}
}

// ---------------------------------------------------------------------------
// Category 8: Anti-Reward-Hacking Guards
// These tests use varied inputs to prevent hardcoded return values from passing.
// ---------------------------------------------------------------------------

func TestApprovalRatioMultipleInputs(t *testing.T) {
	all := []models.QuorumVote{{NodeID: "a", Approved: true}, {NodeID: "b", Approved: true}}
	r1 := consensus.ApprovalRatio(all)
	if math.Abs(r1-1.0) > 0.001 {
		t.Fatalf("all approved should give ratio 1.0, got %.4f", r1)
	}
	none := []models.QuorumVote{{NodeID: "a", Approved: false}, {NodeID: "b", Approved: false}}
	r2 := consensus.ApprovalRatio(none)
	if math.Abs(r2-0.0) > 0.001 {
		t.Fatalf("none approved should give ratio 0.0, got %.4f", r2)
	}
	half := []models.QuorumVote{{NodeID: "a", Approved: true}, {NodeID: "b", Approved: false}}
	r3 := consensus.ApprovalRatio(half)
	if math.Abs(r3-0.5) > 0.001 {
		t.Fatalf("half approved should give ratio 0.5, got %.4f", r3)
	}
}

func TestMergeBalancesSumsSharedKeys(t *testing.T) {
	a := map[string]int64{"shared": 100, "only-a": 50}
	b := map[string]int64{"shared": 200, "only-b": 75}
	merged := ledger.MergeBalances(a, b)
	if merged["shared"] != 300 {
		t.Fatalf("shared key should be summed: 100+200=300, got %d", merged["shared"])
	}
	if merged["only-a"] != 50 {
		t.Fatalf("only-a should be 50, got %d", merged["only-a"])
	}
	if merged["only-b"] != 75 {
		t.Fatalf("only-b should be 75, got %d", merged["only-b"])
	}
}

func TestNextEscalationSingleStep(t *testing.T) {
	next := policy.NextEscalation(models.PolicyNormal)
	if next != models.PolicyWatch {
		t.Fatalf("NextEscalation(Normal) should be Watch (1), got %d", next)
	}
	next2 := policy.NextEscalation(models.PolicyWatch)
	if next2 != models.PolicyRestricted {
		t.Fatalf("NextEscalation(Watch) should be Restricted (2), got %d", next2)
	}
}

func TestEscalationLevelComputation(t *testing.T) {
	low := policy.EscalationLevel(0, 0)
	if low != models.PolicyNormal {
		t.Fatalf("zero incidents/severity should be Normal (0), got %d", low)
	}
	high := policy.EscalationLevel(10, 10)
	if high != models.PolicyHalted {
		t.Fatalf("very high incidents/severity should be Halted (3), got %d", high)
	}
}

func TestSelectReplicaPicksLowestLoad(t *testing.T) {
	candidates := map[string]int{"heavy": 90, "light": 10, "medium": 50}
	replica, ok := routing.SelectReplica(candidates, map[string]bool{})
	if !ok || replica != "light" {
		t.Fatalf("should pick lowest load replica 'light', got %q ok=%v", replica, ok)
	}
	replica2, ok2 := routing.SelectReplica(candidates, map[string]bool{"light": true})
	if !ok2 || replica2 != "medium" {
		t.Fatalf("with 'light' blocked, should pick 'medium', got %q ok=%v", replica2, ok2)
	}
}

func TestSettlementFeeMultipleAmounts(t *testing.T) {
	fee1 := settlement.SettlementFee(100000, 25)
	if fee1 != 250 {
		t.Fatalf("25bp on 100K should be 250, got %d", fee1)
	}
	fee2 := settlement.SettlementFee(500000, 10)
	if fee2 != 500 {
		t.Fatalf("10bp on 500K should be 500, got %d", fee2)
	}
	fee3 := settlement.SettlementFee(2000000, 50)
	if fee3 != 10000 {
		t.Fatalf("50bp on 2M should be 10000, got %d", fee3)
	}
}

func TestStatisticsMeanMultipleInputs(t *testing.T) {
	m1 := statistics.Mean([]float64{100.0})
	if math.Abs(m1-100.0) > 0.001 {
		t.Fatalf("mean of [100] should be 100, got %.4f", m1)
	}
	m2 := statistics.Mean([]float64{0.0, 100.0})
	if math.Abs(m2-50.0) > 0.001 {
		t.Fatalf("mean of [0,100] should be 50, got %.4f", m2)
	}
}

func TestVarianceSampleCorrection(t *testing.T) {
	vals := []float64{2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0}
	v := statistics.Variance(vals)
	expected := 32.0 / 7.0
	if math.Abs(v-expected) > 0.1 {
		t.Fatalf("sample variance should use n-1 denominator, expected ~%.3f, got %.4f", expected, v)
	}
}

func TestAccountBalanceNoOffset(t *testing.T) {
	entries := []models.LedgerEntry{
		{Account: "test", AmountCents: 500},
		{Account: "test", AmountCents: -200},
		{Account: "other", AmountCents: 999},
	}
	bal := ledger.AccountBalance(entries, "test")
	if bal != 300 {
		t.Fatalf("balance of 500 + (-200) should be 300, got %d", bal)
	}
}

func TestReplayBudgetPositiveForValidInputs(t *testing.T) {
	b1 := replay.ReplayBudget(100, 10)
	b2 := replay.ReplayBudget(500, 5)
	if b1 <= 0 || b2 <= 0 {
		t.Fatalf("replay budgets must be positive: b1=%d, b2=%d", b1, b2)
	}
	if b1 == b2 {
		t.Fatalf("different inputs should produce different budgets: both=%d", b1)
	}
}

func TestAggregateRiskPositiveResult(t *testing.T) {
	agg1 := risk.AggregateRisk([]float64{10.0, 20.0})
	agg2 := risk.AggregateRisk([]float64{50.0, 60.0, 70.0})
	if agg1 <= 0 || agg2 <= 0 {
		t.Fatalf("aggregate risk must be positive: agg1=%.4f, agg2=%.4f", agg1, agg2)
	}
	if agg1 >= agg2 {
		t.Fatalf("higher scores should produce higher aggregate: agg1=%.4f >= agg2=%.4f", agg1, agg2)
	}
}

func TestIsBalancedWithinTolerance(t *testing.T) {
	entry := models.ReconciliationEntry{Account: "a", Expected: 100, Actual: 105}
	if !entry.IsBalanced(10) {
		t.Fatal("drift of 5 within tolerance 10 should be balanced")
	}
	if entry.IsBalanced(3) {
		t.Fatal("drift of 5 outside tolerance 3 should not be balanced")
	}
}
