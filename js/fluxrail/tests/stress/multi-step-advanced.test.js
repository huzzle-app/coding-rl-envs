const { test } = require('node:test');
const assert = require('node:assert/strict');

const { batchDispatch, routeScorer, assignPriority, buildDispatchManifest } = require('../../src/core/dispatch');
const { reservationPlanner, capacityWatermark, demandProjection } = require('../../src/core/capacity');
const { balanceExposure, reconcileAccounts, crossAccountTransfer, runningBalance } = require('../../src/core/ledger');
const { tieredPricing, costAllocation, discountedCashFlow, compoundMargin } = require('../../src/core/economics');
const { riskScoreAggregator, evaluatePolicy, complianceCheck } = require('../../src/core/policy');
const { slaCompliance, slaCredits, compositeBreachScore, penaltyEscalation } = require('../../src/core/sla');
const { CircuitBreaker, degradationLevel } = require('../../src/core/resilience');
const { DispatchFSM, BatchFSM, guardedTransition } = require('../../src/core/workflow');
const { replayWithCheckpoint } = require('../../src/core/replay');
const { weightedAverage, percentile } = require('../../src/core/statistics');

// ===== CHAIN 1: routeScorer → reservationPlanner → balanceExposure =====
// Bug A: routeScorer sorts ascending (worst first)
// Bug B: reservationPlanner doesn't track remaining capacity
// Bug C: balanceExposure subtracts instead of adds
// Fixing A gives correct route ranking for capacity planning.
// Fixing B reveals that exposure calculation is inverted (C).
// Fixing C reveals the correct financial state.

test('multistep-adv-001: route scoring feeds capacity planning', () => {
  const routes = [
    { id: 'hub-a', latency: 10, availableCapacity: 80, failures: 0 },
    { id: 'hub-b', latency: 50, availableCapacity: 40, failures: 2 }
  ];
  const scored = routeScorer(routes);
  assert.equal(scored[0].id, 'hub-a', 'best route should be first');
  const bestHub = scored[0];
  const requests = [
    { id: 'r1', units: 30, priority: 8 },
    { id: 'r2', units: 30, priority: 5 },
    { id: 'r3', units: 30, priority: 3 }
  ];
  const plan = reservationPlanner(requests, bestHub.availableCapacity);
  const totalGranted = plan.reduce((s, p) => s + p.granted, 0);
  assert.ok(totalGranted <= bestHub.availableCapacity,
    `granted ${totalGranted} must not exceed capacity ${bestHub.availableCapacity}`);
});

test('multistep-adv-002: capacity grants feed ledger entries', () => {
  const requests = [
    { id: 'r1', units: 50, priority: 10 },
    { id: 'r2', units: 50, priority: 5 }
  ];
  const plan = reservationPlanner(requests, 80);
  const entries = plan.map((p, i) => ({
    account: p.id,
    delta: p.granted,
    seq: i + 1
  }));
  const exposure = balanceExposure(entries);
  for (const p of plan) {
    if (p.granted > 0) {
      assert.ok(exposure[p.id] > 0,
        `account ${p.id} exposure should be positive, got ${exposure[p.id]}`);
    }
  }
});

test('multistep-adv-003: cross-account transfer preserves total exposure', () => {
  const entries = [
    { id: 'e1', account: 'ops', delta: 1000, seq: 1 },
    { id: 'e2', account: 'fin', delta: 500, seq: 2 }
  ];
  const beforeExposure = balanceExposure(entries);
  const totalBefore = Object.values(beforeExposure).reduce((s, v) => s + v, 0);
  const afterTransfer = crossAccountTransfer(entries, 'ops', 'fin', 200);
  const afterExposure = balanceExposure(afterTransfer);
  const totalAfter = Object.values(afterExposure).reduce((s, v) => s + v, 0);
  assert.equal(totalAfter, totalBefore,
    'transfer must preserve total exposure');
});

// ===== CHAIN 2: assignPriority → tieredPricing → compoundMargin → discountedCashFlow =====
// Bug A: assignPriority subtracts urgency
// Bug B: tieredPricing applies flat rate instead of marginal
// Bug C: compoundMargin adds instead of multiplies
// Bug D: discountedCashFlow discounts year 0

test('multistep-adv-004: priority determines pricing tier', () => {
  const priority = assignPriority(9, 10);
  assert.ok(priority >= 90, 'critical+urgent should have priority >= 90');
  const units = priority;
  const tiers = [
    { upTo: 50, rate: 1 },
    { upTo: 100, rate: 2 },
    { upTo: Infinity, rate: 3 }
  ];
  const cost = tieredPricing(units, tiers);
  const expected = 50 * 1 + (units - 50) * 2;
  assert.equal(cost, expected, 'marginal pricing across tiers');
});

test('multistep-adv-005: pricing feeds into margin calculation', () => {
  const tiers = [
    { upTo: 100, rate: 5 },
    { upTo: Infinity, rate: 3 }
  ];
  const cost = tieredPricing(150, tiers);
  const revenue = 1000;
  const margin = (revenue - cost) / revenue;
  const periods = [{ margin }, { margin: 0.05 }];
  const compounded = compoundMargin(periods);
  const expected = Math.round(((1 + margin) * 1.05 - 1) * 10000) / 10000;
  assert.equal(compounded, expected);
});

test('multistep-adv-006: compounded margin feeds DCF', () => {
  const periods = [{ margin: 0.1 }, { margin: 0.15 }];
  const compound = compoundMargin(periods);
  const baseCF = 10000;
  const cfs = [baseCF, baseCF * (1 + compound), baseCF * (1 + compound) * (1 + compound)];
  const npv = discountedCashFlow(cfs, 0.1);
  assert.ok(npv > baseCF * 2, `NPV ${npv} should be substantial`);
  const expected = Math.round((cfs[0] + cfs[1]/1.1 + cfs[2]/1.21) * 100) / 100;
  assert.equal(npv, expected);
});

// ===== CHAIN 3: evaluatePolicy → riskScoreAggregator → complianceCheck =====
// Bug A: evaluatePolicy subtracts margin bonus (should add)
// Bug B: riskScoreAggregator divides by totalWeight+1
// Fixing A reveals that risk thresholds are slightly off due to B.

test('multistep-adv-007: policy score feeds risk aggregation', () => {
  const policy = evaluatePolicy({
    securityIncidents: 0,
    backlog: 10,
    staleMinutes: 5,
    margin: 0.5
  });
  const riskInput = [
    { source: 'policy', value: policy.score, weight: 2 },
    { source: 'external', value: 30, weight: 1 }
  ];
  const risk = riskScoreAggregator(riskInput);
  assert.equal(risk.score, (policy.score * 2 + 30) / 3,
    'risk should be weighted average with correct denominator');
});

test('multistep-adv-008: risk level feeds compliance check', () => {
  const risk = riskScoreAggregator([{ source: 'audit', value: 80, weight: 1 }]);
  assert.equal(risk.score, 80);
  assert.equal(risk.level, 'critical');
  const rules = [
    { name: 'risk-threshold', field: 'riskScore', max: 70, required: true }
  ];
  const entity = { riskScore: risk.score };
  const compliance = complianceCheck(entity, rules);
  assert.equal(compliance.compliant, false, 'score 80 exceeds max 70');
  assert.equal(compliance.violations[0].type, 'above_max');
});

// ===== CHAIN 4: CircuitBreaker → degradationLevel → capacityWatermark =====
// Bug: CircuitBreaker.attemptReset compares elapsed < cooldown (inverted)
// Should transition to half-open when elapsed >= cooldown, not < cooldown.
// This means the breaker opens prematurely and the system misreads its health.

test('multistep-adv-009: circuit breaker state drives degradation assessment', () => {
  const cb = new CircuitBreaker({ threshold: 3, cooldownMs: 5000 });
  cb.recordFailure(1000);
  cb.recordFailure(2000);
  cb.recordFailure(3000);
  assert.equal(cb.getState(), 'open');
  cb.attemptReset(10000);
  assert.equal(cb.getState(), 'half-open',
    'after cooldown (10000 - 3000 = 7000 > 5000), should be half-open');
});

test('multistep-adv-010: degradation drives capacity planning', () => {
  const level = degradationLevel({ errorRate: 0.15, p99LatencyMs: 3000, cpuSaturation: 0.5 });
  assert.equal(level, 'degraded');
  const effectiveCapacity = level === 'degraded' ? 50 : 100;
  const watermark = capacityWatermark(effectiveCapacity, 30, 80);
  assert.equal(watermark, 'nominal');
});

test('multistep-adv-011: circuit breaker cooldown timing', () => {
  const cb = new CircuitBreaker({ threshold: 2, cooldownMs: 10000 });
  cb.recordFailure(0);
  cb.recordFailure(100);
  assert.equal(cb.getState(), 'open');
  cb.attemptReset(5000);
  assert.equal(cb.getState(), 'open',
    'only 5000ms elapsed (< 10000 cooldown), should stay open');
});

// ===== CHAIN 5: SLA breach → penalty → credits → financial impact =====
// Bug A: penaltyEscalation off-by-one (2^count instead of 2^(count-1))
// Bug B: slaCredits correct but penalty feeds into it
// When penalty is wrong, credit calculation is also wrong downstream.

test('multistep-adv-012: SLA pipeline from breach to financial impact', () => {
  const deliveries = [
    { actualTime: 500, slaTime: 300 },
    { actualTime: 200, slaTime: 300 },
    { actualTime: 600, slaTime: 300 },
    { actualTime: 100, slaTime: 300 }
  ];
  const compliance = slaCompliance(deliveries);
  assert.equal(compliance.breached, 2);
  assert.equal(compliance.rate, 0.5);
  const penalty = penaltyEscalation(compliance.breached, 100, 10000);
  assert.equal(penalty, 200, 'breach 2: base*2^(2-1) = 200');
  const credits = slaCredits(compliance.breached, penalty, 5000);
  assert.ok(credits > 0);
});

test('multistep-adv-013: composite breach feeds escalation chain', () => {
  const dimensions = [
    { score: 0.9, weight: 2 },
    { score: 0.3, weight: 1 }
  ];
  const breachScore = compositeBreachScore(dimensions);
  const breachCount = breachScore > 0.7 ? 4 : breachScore > 0.5 ? 2 : 1;
  const penalty = penaltyEscalation(breachCount, 50, 10000);
  const expectedPenalty = 50 * Math.pow(2, breachCount - 1);
  assert.equal(penalty, expectedPenalty);
});

// ===== CHAIN 6: BatchFSM → batchDispatch → manifest =====
// Bug in BatchFSM: completedCount only checks 'delivered' and 'archived',
// but archived isn't reachable in the current FSM (delivered is terminal).
// This means completion rate is correct for delivered but the check is misleading.

test('multistep-adv-014: batch FSM tracks completion across machines', () => {
  const batch = new BatchFSM(3);
  batch.transitionAll('validated');
  batch.transitionAll('capacity_checked');
  batch.transitionAll('dispatched');
  batch.transitionAll('in_transit');
  batch.transitionAll('delivered');
  assert.equal(batch.completionRate(), 1, 'all machines should be complete');
});

test('multistep-adv-015: partial batch completion', () => {
  const batch = new BatchFSM(4);
  batch.transitionAll('validated');
  batch.transitionAll('capacity_checked');
  const dist = batch.stateDistribution();
  assert.equal(dist['capacity_checked'], 4);
  assert.equal(batch.completionRate(), 0);
});

test('multistep-adv-016: batch dispatch creates correct weight batches', () => {
  const assignments = [
    { id: 'a1', units: 100, priority: 10 },
    { id: 'a2', units: 50, priority: 5 },
    { id: 'a3', units: 75, priority: 8 },
    { id: 'a4', units: 25, priority: 3 },
    { id: 'a5', units: 60, priority: 7 }
  ];
  const batches = batchDispatch(assignments, 2);
  assert.equal(batches.length, 3);
  assert.equal(batches[0].items[0].priority, 10, 'first batch starts with highest priority');
});

// ===== CHAIN 7: guardedTransition with policy → risk → compliance cascade =====

test('multistep-adv-017: policy-based guard blocks on risk', () => {
  const guards = [
    (current, event) => {
      const risk = riskScoreAggregator([
        { source: 'ops', value: event.riskScore || 0, weight: 1 }
      ]);
      return risk.level !== 'critical';
    },
    () => true
  ];
  const result = guardedTransition('pending', { target: 'validated', riskScore: 80 }, guards);
  assert.equal(result.transitioned, false,
    'critical risk should block transition when all guards required');
});

test('multistep-adv-018: compliance guard in transition chain', () => {
  const rules = [
    { name: 'min-units', field: 'units', min: 10, required: true }
  ];
  const guards = [
    (current, event) => {
      const check = complianceCheck(event, rules);
      return check.compliant;
    }
  ];
  const passing = guardedTransition('pending', { target: 'validated', units: 20 }, guards);
  assert.equal(passing.transitioned, true);
  const failing = guardedTransition('pending', { target: 'validated', units: 5 }, guards);
  assert.equal(failing.transitioned, false);
  assert.equal(failing.state, 'pending', 'failed guard returns current state');
});

// ===== CHAIN 8: replay → running balance → reconciliation → cost =====

test('multistep-adv-019: replayed events build running balance', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1', account: 'ops', delta: 500, seq: 1 },
    { id: 'e2', version: 2, idempotencyKey: 'k2', account: 'ops', delta: -200, seq: 2 },
    { id: 'e3', version: 3, idempotencyKey: 'k3', account: 'ops', delta: 100, seq: 3 }
  ];
  const replayed = replayWithCheckpoint(events, { version: 0 });
  const snapshots = runningBalance(replayed);
  assert.equal(snapshots[snapshots.length - 1].balance, 400);
});

test('multistep-adv-020: reconciled balance feeds cost calculation', () => {
  const entries = [
    { account: 'compute', delta: 500 },
    { account: 'compute', delta: 300 },
    { account: 'compute', delta: -100 }
  ];
  const recon = reconcileAccounts(entries);
  const tiers = [
    { upTo: 200, rate: 5 },
    { upTo: 500, rate: 3 },
    { upTo: Infinity, rate: 1 }
  ];
  const cost = tieredPricing(recon.compute.net, tiers);
  const expected = 200 * 5 + 300 * 3 + 200 * 1;
  assert.equal(cost, expected, `cost for 700 units across tiers should be ${expected}`);
});

// ===== CHAIN 9: routeScorer weight correctness → capacity planning =====
// After fixing the sort direction, the weight coefficients must also be correct.
// Latency should be weighted 0.4, capacity 0.35. When they're swapped, routes
// with high capacity but poor latency are incorrectly preferred, leading to
// bad capacity planning decisions downstream.

test('multistep-adv-020a: weight-aware route selection feeds capacity', () => {
  const routes = [
    { id: 'fast', latency: 5, availableCapacity: 40, failures: 0 },
    { id: 'large', latency: 60, availableCapacity: 95, failures: 0 }
  ];
  const scored = routeScorer(routes);
  // Correct weights: fast=38+14+25=77 > large=16+33.25+25=74.25
  assert.equal(scored[0].id, 'fast',
    'fast route should rank first with correct latency weight (0.4 > 0.35)');
  const plan = reservationPlanner(
    [{ id: 'r1', units: 35, priority: 10 }],
    scored[0].availableCapacity
  );
  assert.equal(plan[0].granted, 35, 'request fits in fast route capacity of 40');
});

// ===== CHAIN 10: PriorityQueue drain → batch processing order =====
// After fixing the sort direction, drain() must return items in the same order
// as sequential dequeue(). If drain reverses the result, batch operations
// process items in wrong priority order even though individual dequeue works.

test('multistep-adv-020b: priority queue drain feeds batch dispatch', () => {
  const { PriorityQueue } = require('../../src/core/queue');
  const pq = new PriorityQueue();
  const items = [
    { id: 'a1', units: 100, priority: 10 },
    { id: 'a2', units: 50, priority: 5 },
    { id: 'a3', units: 75, priority: 8 }
  ];
  items.forEach(item => pq.enqueue(item, item.priority));
  const drained = pq.drain(3);
  // Should be highest priority first
  assert.equal(drained[0].priority, 10, 'first drained should be priority 10');
  assert.equal(drained[drained.length - 1].priority, 5, 'last should be lowest priority');
});

// ===== CHAIN 11: demandProjection consistency → watermark accuracy =====
// After fixing the denominator, sparse weights must still default consistently.
// If defaults differ between numerator and denominator, projection is skewed,
// leading to wrong capacity watermark classification.

test('multistep-adv-020c: projection with sparse weights feeds watermark', () => {
  const historical = [80, 60, 90, 70];
  const weights = [2, undefined, 3, 1];
  const projected = demandProjection(historical, weights);
  // Correct: (80*2+60*1+90*3+70*1) / (2+1+3+1) = 500/7 ≈ 71.43
  const expected = Math.round((500 / 7) * 100) / 100;
  assert.equal(projected, expected, 'sparse weights must default consistently');
  const watermark = capacityWatermark(projected, 30, 80);
  assert.equal(watermark, 'nominal', 'projected ~71 in [50,80] range');
});

// ===== CHAIN 12: discountedCashFlow → break-even analysis =====
// DCF year 0 must NOT be discounted. If it is, NPV is understated,
// making break-even analysis overly pessimistic.

test('multistep-adv-020d: DCF feeds break-even assessment', () => {
  const { breakEvenUnits } = require('../../src/core/economics');
  const cashFlows = [5000, 3000, 3000];
  const npv = discountedCashFlow(cashFlows, 0.1);
  // Correct: 5000 + 3000/1.1 + 3000/1.21 = 5000 + 2727.27 + 2479.34 = 10206.61
  assert.ok(npv > 10000, `NPV ${npv} should exceed 10000 with year 0 undiscounted`);
  const yearlyProfit = (npv - 5000) / 2;
  assert.ok(yearlyProfit > 2500, 'yearly profit should be substantial');
});

// ===== Matrix expansion =====

for (let i = 0; i < 20; i++) {
  test(`multistep-adv-matrix-${String(21 + i).padStart(3, '0')}: route→capacity→exposure chain ${i}`, () => {
    const capacity = 50 + i * 10;
    const numRequests = 3 + (i % 5);
    const requests = Array.from({ length: numRequests }, (_, j) => ({
      id: `r${j}`,
      units: 20 + j * 5,
      priority: 10 - j
    }));
    const plan = reservationPlanner(requests, capacity);
    const total = plan.reduce((s, p) => s + p.granted, 0);
    assert.ok(total <= capacity, `total ${total} must not exceed ${capacity}`);
    const entries = plan.map((p, j) => ({ account: p.id, delta: p.granted, seq: j + 1 }));
    const exposure = balanceExposure(entries);
    const expTotal = Object.values(exposure).reduce((s, v) => s + v, 0);
    assert.equal(expTotal, total, 'total exposure should equal total granted');
  });
}

for (let i = 0; i < 15; i++) {
  test(`multistep-adv-matrix-${String(41 + i).padStart(3, '0')}: SLA→penalty→credits chain ${i}`, () => {
    const breachCount = i + 1;
    const basePenalty = 50;
    const penalty = penaltyEscalation(breachCount, basePenalty, 100000);
    const expectedPenalty = Math.min(basePenalty * Math.pow(2, breachCount - 1), 100000);
    assert.equal(penalty, expectedPenalty);
  });
}

for (let i = 0; i < 15; i++) {
  test(`multistep-adv-matrix-${String(56 + i).padStart(3, '0')}: policy→risk→compliance chain ${i}`, () => {
    const value = 15 + i * 5;
    const risk = riskScoreAggregator([{ source: 'test', value, weight: 1 }]);
    assert.equal(risk.score, value);
    const rules = [{ name: 'risk', field: 'score', max: 60 }];
    const compliance = complianceCheck({ score: risk.score }, rules);
    if (value > 60) {
      assert.equal(compliance.compliant, false);
    } else {
      assert.equal(compliance.compliant, true);
    }
  });
}
