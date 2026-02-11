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
  const units = Math.abs(exposure.ops || 0);
  const tiers = [
    { upTo: 100, rate: 10 },
    { upTo: 500, rate: 7 },
    { upTo: Infinity, rate: 4 }
  ];
  const cost = tieredPricing(units, tiers);
  assert.ok(cost > 0);
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
  const isAtRisk = breachRisk(700, 600, 50);
  const riskResult = riskScoreAggregator([
    { source: 'sla', value: isAtRisk ? 80 : 20, weight: 2 },
    { source: 'ops', value: 30, weight: 1 }
  ]);
  assert.ok(riskResult.score > 40);
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
  const breachCount = breachScore > 0.5 ? 3 : 1;
  const penalty = penaltyEscalation(breachCount, 100, 5000);
  assert.ok(penalty > 100, 'multiple breaches escalate penalty');
});

// ===== Replay + Tenant isolation =====

test('integration-009: replayed events respect tenant scope', () => {
  const events = [
    { id: 'e1', version: 5, idempotencyKey: 'k1', tenant: 'acme', delta: 100 },
    { id: 'e2', version: 10, idempotencyKey: 'k2', tenant: 'beta', delta: 200 },
    { id: 'e3', version: 15, idempotencyKey: 'k3', tenant: 'acme', delta: 50 }
  ];
  const replayed = replayWithCheckpoint(events, { version: 3 });
  const tenantExposure = netExposureByTenant(replayed);
  assert.ok(tenantExposure.acme !== undefined || tenantExposure.beta !== undefined);
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
  const hubs = [
    { id: 'hub-east', lat: 0, lng: 5, capacity: 100 },
    { id: 'hub-west', lat: 0, lng: 50, capacity: 80 }
  ];
  const bestHub = geoAwareRoute(hubs, { lat: 0, lng: 3 });
  assert.equal(bestHub.id, 'hub-east');
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
  const history2 = [5, 5, 5, 5, 5];
  const f1 = exponentialForecast(history1, 0.8);
  const f2 = exponentialForecast(history2, 0.8);
  assert.ok(f1 > f2, 'trending queue should have higher forecast');
});

// ===== Statistics + SLA =====

test('integration-014: outlier detection on breach data', () => {
  const times = [100, 105, 98, 102, 99, 101, 500, 103];
  const outliers = detectOutliers(times, 1.5);
  assert.ok(outliers.includes(500));
  const clean = times.filter((t) => !outliers.includes(t));
  const avg = weightedAverage(clean, clean.map(() => 1));
  assert.ok(avg < 110);
});

test('integration-015: weighted scoring feeds policy', () => {
  const score = weightedAverage([80, 60, 90], [2, 1, 3]);
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
  const periods = costs.map((c) => ({ margin: (1000 - c) / 1000 }));
  const totalMargin = compoundMargin(periods);
  assert.ok(totalMargin > 0);
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
    const slaMin = 10 + i * 5;
    const priority = assignPriority(severity, slaMin);
    const riskResult = riskScoreAggregator([
      { source: 'priority', value: priority, weight: 1 },
      { source: 'sla', value: breachRisk(300 + i * 60, 600, 100) ? 80 : 20, weight: 2 }
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
