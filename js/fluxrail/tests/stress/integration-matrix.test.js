const { test } = require('node:test');
const assert = require('node:assert/strict');

const { chooseRoute, assignPriority, buildDispatchManifest } = require('../../src/core/dispatch');
const { rebalance, shedRequired, exponentialForecast, reservationPlanner } = require('../../src/core/capacity');
const { overrideAllowed, evaluatePolicy, riskScoreAggregator, policyChain } = require('../../src/core/policy');
const { allowed, tokenFresh, scopedPermission, auditChainValidator } = require('../../src/core/security');
const { transitionAllowed, DispatchFSM, guardedTransition } = require('../../src/core/workflow');
const { projectedCost, tieredPricing, compoundMargin } = require('../../src/core/economics');
const { buildLedgerEntries, balanceExposure, reconcileAccounts, netExposureByTenant } = require('../../src/core/ledger');
const { breachRisk, breachSeverity, compositeBreachScore, penaltyEscalation } = require('../../src/core/sla');
const { replayWithCheckpoint } = require('../../src/core/replay');
const { selectHub, geoAwareRoute, failoverChain } = require('../../src/core/routing');
const { AdaptiveQueue, fairScheduler } = require('../../src/core/queue');
const { weightedAverage, detectOutliers } = require('../../src/core/statistics');
const { delegationChain, multiTenantAuth } = require('../../src/core/authorization');

// ===== Security-first dispatch pipeline =====

test('integration-001: operator cannot override (security gate)', () => {
  const securityCheck = allowed('operator', 'override');
  assert.equal(securityCheck, false, 'operator cannot override');
});

test('integration-002: operator can submit', () => {
  const authOk = allowed('operator', 'submit');
  assert.equal(authOk, true);
  if (authOk) {
    const route = chooseRoute({ north: 10, south: 20 });
    assert.ok(route);
  }
});

test('integration-003: admin override with valid token', () => {
  assert.equal(tokenFresh(1000, 3600, 2000), true);
  assert.equal(allowed('admin', 'override'), true);
  assert.equal(overrideAllowed('emergency override required', 3, 60), true);
});

// ===== Ledger + Economics unit consistency =====

test('integration-004: tiered pricing on ledger exposure', () => {
  const entries = buildLedgerEntries([
    { id: 'e1', account: 'ops', delta: 500, seq: 1 },
    { id: 'e2', account: 'ops', delta: 300, seq: 2 }
  ]);
  const exposure = balanceExposure(entries);
  // balanceExposure should SUM deltas, not subtract: 500 + 300 = 800
  assert.equal(exposure.ops, 800, 'exposure should sum deltas: 500 + 300 = 800');
  const tiers = [
    { upTo: 100, rate: 10 },
    { upTo: 500, rate: 7 },
    { upTo: Infinity, rate: 4 }
  ];
  const cost = tieredPricing(exposure.ops, tiers);
  assert.equal(cost, 3200, '800 units at rate 4 = 3200');
});

test('integration-005: net exposure sign affects economics', () => {
  const entries = [
    { tenant: 'acme', delta: 1000 },
    { tenant: 'acme', delta: -800 }
  ];
  const exposure = netExposureByTenant(entries);
  assert.equal(exposure.acme, 200,
    'net exposure should be 200 for correct risk calculation, not 1800 gross');
});

// ===== Workflow + Policy + SLA compound =====

test('integration-006: SLA breach triggers risk escalation', () => {
  // breachRisk bug: checks eta > sla + buffer instead of eta > sla - buffer
  // At eta=600, sla=600, buffer=50: correct (600>550)=true, buggy (600>650)=false
  const isAtRisk = breachRisk(600, 600, 50);
  assert.equal(isAtRisk, true, 'ETA at SLA with buffer should be at risk');
  const riskResult = riskScoreAggregator([
    { source: 'sla', value: 80, weight: 2 },
    { source: 'ops', value: 30, weight: 1 }
  ]);
  // Correct: (80*2+30*1)/3 = 63.3333; buggy divides by totalWeight+1 = 4 → 47.5
  const expected = Math.round((80*2+30*1) / 3 * 10000) / 10000;
  assert.equal(riskResult.score, expected,
    'riskScore should divide by totalWeight, not totalWeight+1');
});

test('integration-007: FSM respects policy for transitions', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  const pol = evaluatePolicy({
    securityIncidents: 0, backlog: 5, staleMinutes: 10, margin: 0.2
  });
  if (pol.allow) {
    fsm.transition('capacity_checked');
    assert.equal(fsm.getState(), 'capacity_checked');
  }
});

test('integration-008: compound breach feeds penalty escalation', () => {
  const dimensions = [
    { score: 0.8, weight: 2, correlated: true },
    { score: 0.6, weight: 1 }
  ];
  const breachScore = compositeBreachScore(dimensions);
  assert.ok(breachScore > 0.5, 'composite breach should exceed threshold');
  // penaltyEscalation bug: base*2^count instead of base*2^(count-1)
  // Correct: 100*2^(3-1) = 400; buggy: 100*2^3 = 800
  const penalty = penaltyEscalation(3, 100, 5000);
  assert.equal(penalty, 400, 'penalty: first breach=base, then doubles: 100*2^2=400');
});

// ===== Replay + Tenant isolation =====

test('integration-009: replayed events respect tenant scope', () => {
  const events = [
    { id: 'e1', version: 5, idempotencyKey: 'k1', tenant: 'acme', delta: 100 },
    { id: 'e2', version: 10, idempotencyKey: 'k2', tenant: 'beta', delta: 200 },
    { id: 'e3', version: 15, idempotencyKey: 'k3', tenant: 'acme', delta: -50 }
  ];
  const replayed = replayWithCheckpoint(events, { version: 3 });
  const tenantExposure = netExposureByTenant(replayed);
  // netExposureByTenant bug: uses Math.abs, giving gross=150 instead of net=50
  assert.equal(tenantExposure.acme, 50,
    'net exposure should preserve signs: 100 + (-50) = 50');
  assert.equal(tenantExposure.beta, 200);
});

test('integration-010: delegation + scoped permission', () => {
  const chain = [
    { userId: 'admin1', role: 'admin' },
    { userId: 'op1', role: 'operator', delegatedBy: 'admin1' }
  ];
  assert.equal(delegationChain(chain).valid, true);
  assert.equal(scopedPermission(['operator.read', 'operator.submit'], 'operator.read'), true);
});

// ===== Routing + Capacity + Queue =====

test('integration-011: geo-routed hub feeds capacity', () => {
  // At high latitudes, cos(degrees) bug in geoAwareRoute changes hub selection
  // cos(80°)=0.174 (correct) vs cos(80 rad)≈-0.129 (buggy)
  const hubs = [
    { id: 'hub-north', lat: 79, lng: 0, capacity: 100 },
    { id: 'hub-east', lat: 80, lng: 6, capacity: 80 }
  ];
  const bestHub = geoAwareRoute(hubs, { lat: 80, lng: 0 });
  // Correct: hub-north (1° lat ≈ 1 unit) is closer than hub-east (6°lng*cos(80°)=1.04 units)
  // Buggy: cos(80 rad)≈-0.129 makes hub-east appear closer (6*0.129=0.77 < 1)
  assert.equal(bestHub.id, 'hub-north',
    'at lat 80, 1° latitude > 6° longitude after cos correction');
});

test('integration-012: failover + queue state', () => {
  const routes = [
    { id: 'primary', failures: 0 },
    { id: 'secondary', failures: 2 },
    { id: 'tertiary', failures: 5 }
  ];
  const chain = failoverChain(routes, 3);
  assert.equal(chain.active.length, 2);
  const q = new AdaptiveQueue({ throttleThreshold: 0.8 });
  q.updateLoad(0.85);
  assert.equal(q.getState(), 'throttled');
});

test('integration-013: fair scheduling with forecast-driven queues', () => {
  const history1 = [10, 15, 20, 25, 30];
  const f1 = exponentialForecast(history1, 0.8);
  // Correct: alpha weights CURRENT value more → forecast tracks recent values closely
  // 0.8*15+0.2*10=14, 0.8*20+0.2*14=18.8, 0.8*25+0.2*18.8=23.76, 0.8*30+0.2*23.76=28.75
  // Buggy (swapped): alpha weights PREVIOUS → lags behind: ~18.19
  assert.equal(f1, 28.75,
    'exponential forecast with alpha=0.8 should weight current values heavily');
});

// ===== Statistics + SLA =====

test('integration-014: outlier detection on breach data', () => {
  const times = [100, 105, 98, 102, 99, 101, 500, 103];
  const outliers = detectOutliers(times, 1.5);
  assert.ok(outliers.includes(500));
  const clean = times.filter((t) => !outliers.includes(t));
  // Non-uniform weights expose weightedAverage division-by-count vs by-weight-sum bug
  const weights = clean.map((_, i) => 1 + i);
  const avg = weightedAverage(clean, weights);
  // Correct: sum(v*w)/sum(w) ≈ 101; buggy: sum(v*w)/count ≈ 405
  assert.ok(avg < 110, `weighted avg of breach times should be ~101, got ${avg}`);
});

test('integration-015: weighted scoring feeds policy', () => {
  const score = weightedAverage([80, 60, 90], [2, 1, 3]);
  // Correct: (80*2+60*1+90*3)/6 = 81.67; buggy (÷length): 490/3 = 163.33
  const expectedScore = (80*2+60*1+90*3) / (2+1+3);
  assert.ok(Math.abs(score - expectedScore) < 0.01,
    `weighted score should be ~${expectedScore.toFixed(2)}, got ${score}`);
  const policies = [
    (ctx) => ({
      decision: ctx.score >= 70 ? 'allow' : 'deny',
      metadata: { scoreCheck: true }
    }),
    () => ({ decision: 'allow', metadata: { rateLimit: 100 } })
  ];
  const result = policyChain(policies, { score });
  assert.equal(result.metadata.scoreCheck, true);
  assert.equal(result.metadata.rateLimit, 100);
});

// ===== Full lifecycle =====

test('integration-016: complete dispatch lifecycle', () => {
  const fsm = new DispatchFSM();
  const authOk = allowed('reviewer', 'submit');
  assert.equal(authOk, true);
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  assert.equal(fsm.getState(), 'dispatched');
});

test('integration-017: tiered pricing with compound margin', () => {
  const tiers = [
    { upTo: 100, rate: 5 },
    { upTo: 500, rate: 3 },
    { upTo: Infinity, rate: 1 }
  ];
  const costs = [50, 200, 600].map((u) => tieredPricing(u, tiers));
  // costs = [250, 600, 600]; margins = [0.75, 0.4, 0.4]
  const periods = costs.map((c) => ({ margin: (1000 - c) / 1000 }));
  const totalMargin = compoundMargin(periods);
  // Correct (compound multiply): (1+0.75)*(1+0.4)*(1+0.4)-1 = 2.43
  // Buggy (additive): 0.75+0.4+0.4 = 1.55
  const expected = Math.round((1.75 * 1.4 * 1.4 - 1) * 10000) / 10000;
  assert.equal(totalMargin, expected,
    'compound margin should multiply: (1+0.75)*(1+0.4)*(1+0.4)-1 = 2.43');
});

test('integration-018: audit chain + delegated auth', () => {
  const delegations = [
    { userId: 'root', role: 'admin' },
    { userId: 'mgr', role: 'reviewer', delegatedBy: 'root' },
    { userId: 'op', role: 'operator', delegatedBy: 'mgr' }
  ];
  assert.equal(delegationChain(delegations).effectiveRole, 'operator');
  const chain = [
    { hash: 'h1', parentHash: 'genesis' },
    { hash: 'h2', parentHash: 'h1' }
  ];
  assert.equal(auditChainValidator(chain).valid, true);
});

// ===== Manifest totalUnits stale after trim in pipeline =====

test('integration-019: dispatch manifest totalUnits correct after capacity planning', () => {
  const assignments = Array.from({ length: 10 }, (_, i) => ({
    route: 'hub-a', units: 100, priority: i + 1
  }));
  const manifest = buildDispatchManifest(assignments, 5);
  const actualTotal = manifest['hub-a'].items.reduce((s, it) => s + Number(it.units), 0);
  assert.equal(manifest['hub-a'].totalUnits, actualTotal,
    'totalUnits must match kept items for correct capacity calculation');
});

test('integration-020: net exposure with hedged positions for risk', () => {
  const entries = [
    { tenant: 'hedge-fund', delta: 10000 },
    { tenant: 'hedge-fund', delta: -9500 }
  ];
  const exposure = netExposureByTenant(entries);
  assert.equal(exposure['hedge-fund'], 500,
    'hedged position has net exposure of 500, not gross 19500');
});

// ===== Matrix expansion =====

for (let i = 0; i < 10; i++) {
  test(`integration-matrix-${String(21 + i).padStart(3, '0')}: e2e dispatch ${i}`, () => {
    const severity = 3 + (i % 8);
    const slaMin = 10 + (i % 4) * 5;  // cycle 10,15,20,25 so urgency is always > 0
    const priority = assignPriority(severity, slaMin);
    // assignPriority bug: subtracts urgency instead of adding
    const base = severity >= 8 ? 90 : severity >= 5 ? 65 : 35;
    const urgency = slaMin <= 15 ? 15 : slaMin <= 30 ? 8 : 0;
    assert.equal(priority, Math.min(100, base + urgency),
      `severity ${severity}, sla ${slaMin}: base(${base}) + urgency(${urgency})`);
    // breachRisk bug: adds buffer instead of subtracting
    const etaSec = 300 + i * 60;
    const atRisk = breachRisk(etaSec, 600, 100);
    const expectedRisk = etaSec > (600 - 100);
    assert.equal(atRisk, expectedRisk,
      `eta ${etaSec} should be at risk if > sla-buffer (500)`);
    const riskResult = riskScoreAggregator([
      { source: 'priority', value: priority, weight: 1 },
      { source: 'sla', value: atRisk ? 80 : 20, weight: 2 }
    ]);
    assert.ok(typeof riskResult.score === 'number');
    assert.ok(['low', 'medium', 'high', 'critical'].includes(riskResult.level));
  });
}

for (let i = 0; i < 8; i++) {
  test(`integration-matrix-${String(31 + i).padStart(3, '0')}: tenant-scoped workflow ${i}`, () => {
    const tid = `tenant-${i}`;
    const grants = [{ tenantId: tid, userId: 'user1', actions: ['read', 'submit'] }];
    assert.equal(multiTenantAuth(tid, 'user1', 'submit', grants).authorized, true);
    assert.equal(multiTenantAuth(`other-${i}`, 'user1', 'submit', grants).authorized, false);
  });
}
