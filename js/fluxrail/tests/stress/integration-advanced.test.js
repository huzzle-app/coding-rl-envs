const { test } = require('node:test');
const assert = require('node:assert/strict');

const { routeScorer, batchDispatch, assignPriority, buildDispatchManifest, priorityDecay } = require('../../src/core/dispatch');
const { reservationPlanner, capacityWatermark, demandProjection, capacityFragmentation, overcommitRatio } = require('../../src/core/capacity');
const { balanceExposure, reconcileAccounts, crossAccountTransfer, runningBalance, netExposureByTenant, ledgerIntegrity } = require('../../src/core/ledger');
const { tieredPricing, compoundMargin, costAllocation, discountedCashFlow, marginRatio, revenueRecognition } = require('../../src/core/economics');
const { riskScoreAggregator, evaluatePolicy, policyChain, complianceCheck, riskMatrix } = require('../../src/core/policy');
const { slaCompliance, slaCredits, compositeBreachScore, penaltyEscalation, breachSeverity, meanTimeToRecover } = require('../../src/core/sla');
const { CircuitBreaker, degradationLevel, replayState } = require('../../src/core/resilience');
const { DispatchFSM, BatchFSM, guardedTransition, parallelGuardEval } = require('../../src/core/workflow');
const { replayWithCheckpoint, orderedReplay, replaySegment } = require('../../src/core/replay');
const { weightedAverage, percentile, standardDeviation, correlationCoefficient } = require('../../src/core/statistics');
const { delegationChain, multiTenantAuth, permissionIntersection, tokenRotation } = require('../../src/core/authorization');
const { allowed, auditChainValidator, scopedPermission, rateLimit, computeAccessLevel } = require('../../src/core/security');
const { selectHub, geoAwareRoute, failoverChain, deterministicPartition, weightedRouteSelection } = require('../../src/core/routing');
const { PriorityQueue, AdaptiveQueue, fairScheduler, weightedRoundRobin, queueHealthScore } = require('../../src/core/queue');

// ===== INTEGRATION 1: Full dispatch pipeline =====
// Route scoring → Priority assignment → Capacity reservation → FSM lifecycle → Ledger

test('integration-adv-001: end-to-end dispatch pipeline', () => {
  const routes = [
    { id: 'east', latency: 15, availableCapacity: 100, failures: 0 },
    { id: 'west', latency: 50, availableCapacity: 60, failures: 1 }
  ];
  const scored = routeScorer(routes);
  assert.equal(scored[0].id, 'east');
  const priority = assignPriority(8, 15);
  assert.ok(priority >= 90);
  const requests = [
    { id: 'r1', units: 40, priority: priority },
    { id: 'r2', units: 30, priority: 50 }
  ];
  const plan = reservationPlanner(requests, scored[0].availableCapacity);
  const totalGranted = plan.reduce((s, p) => s + p.granted, 0);
  assert.ok(totalGranted <= 100);
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  assert.equal(fsm.getState(), 'dispatched');
  const entries = plan.map((p, i) => ({ account: p.id, delta: p.granted, seq: i + 1 }));
  const exposure = balanceExposure(entries);
  for (const p of plan) {
    if (p.granted > 0) {
      assert.ok(exposure[p.id] > 0);
    }
  }
});

// ===== INTEGRATION 2: Financial pipeline =====
// Ledger → Reconciliation → Tiered Pricing → Compound Margin → DCF

test('integration-adv-002: financial pipeline end-to-end', () => {
  const entries = [
    { account: 'ops', delta: 500 },
    { account: 'ops', delta: 300 },
    { account: 'ops', delta: -100 }
  ];
  const recon = reconcileAccounts(entries);
  assert.equal(recon.ops.net, 700);
  assert.equal(recon.ops.credits, 800);
  assert.equal(recon.ops.debits, 100);
  const tiers = [
    { upTo: 200, rate: 5 },
    { upTo: 500, rate: 3 },
    { upTo: Infinity, rate: 1 }
  ];
  const cost = tieredPricing(recon.ops.net, tiers);
  const expected = 200 * 5 + 300 * 3 + 200 * 1;
  assert.equal(cost, expected);
  const revenue = 3000;
  const margin = marginRatio(revenue, cost);
  assert.ok(margin > 0);
  const periods = [{ margin: 0.1 }, { margin: margin }];
  const compounded = compoundMargin(periods);
  const expectedCompound = Math.round(((1.1) * (1 + margin) - 1) * 10000) / 10000;
  assert.equal(compounded, expectedCompound);
});

// ===== INTEGRATION 3: Security + Authorization + Workflow =====

test('integration-adv-003: auth gates workflow transitions', () => {
  const chain = [
    { userId: 'admin1', role: 'admin' },
    { userId: 'op1', role: 'operator', delegatedBy: 'admin1' }
  ];
  const delegation = delegationChain(chain);
  assert.equal(delegation.valid, true);
  assert.equal(delegation.effectiveRole, 'operator');
  const authCheck = allowed(delegation.effectiveRole, 'submit');
  assert.equal(authCheck, true, 'operator should be allowed to submit');
  if (authCheck) {
    const fsm = new DispatchFSM();
    fsm.transition('validated');
    assert.equal(fsm.getState(), 'validated');
  }
});

test('integration-adv-004: permission intersection gates operations', () => {
  const userPerms = ['dispatch.read', 'dispatch.submit', 'capacity.read'];
  const required = ['dispatch.submit', 'capacity.read'];
  const check = permissionIntersection(userPerms, required);
  assert.equal(check.granted, true);
  const denied = permissionIntersection(userPerms, ['dispatch.delete']);
  assert.equal(denied.granted, false);
  assert.deepEqual(denied.missing, ['dispatch.delete']);
});

// ===== INTEGRATION 4: SLA + Risk + Policy cascade =====

test('integration-adv-005: SLA breaches cascade to risk and policy', () => {
  const deliveries = [
    { actualTime: 400, slaTime: 300 },
    { actualTime: 200, slaTime: 300 },
    { actualTime: 500, slaTime: 300 },
    { actualTime: 250, slaTime: 300 },
    { actualTime: 600, slaTime: 300 }
  ];
  const compliance = slaCompliance(deliveries);
  assert.equal(compliance.breached, 3);
  const breachScore = compliance.breached / compliance.total;
  const risk = riskScoreAggregator([
    { source: 'sla', value: breachScore * 100, weight: 2 },
    { source: 'ops', value: 30, weight: 1 }
  ]);
  assert.ok(risk.score > 30);
  const policy = evaluatePolicy({
    securityIncidents: 0,
    backlog: compliance.breached * 5,
    staleMinutes: 10,
    margin: 0.1
  });
  assert.ok(typeof policy.allow === 'boolean');
});

// ===== INTEGRATION 5: Queue health + Circuit breaker + Capacity watermark =====

test('integration-adv-006: queue health drives circuit breaker and capacity', () => {
  const health = queueHealthScore({
    depth: 50,
    processingRate: 2,
    errorRate: 0.2,
    avgLatencyMs: 300
  });
  const degrade = degradationLevel({
    errorRate: 0.2,
    p99LatencyMs: 3000,
    cpuSaturation: 0.7
  });
  assert.equal(degrade, 'degraded');
  const effectiveCapacity = degrade === 'degraded' ? 40 : 100;
  const watermark = capacityWatermark(effectiveCapacity, 30, 80);
  assert.equal(watermark, 'warning');
});

// ===== INTEGRATION 6: Replay + Ledger + Running Balance =====

test('integration-adv-007: replay events into running balance', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1', account: 'ops', delta: 500, seq: 1 },
    { id: 'e2', version: 2, idempotencyKey: 'k2', account: 'ops', delta: -200, seq: 2 },
    { id: 'e3', version: 3, idempotencyKey: 'k3', account: 'fin', delta: 300, seq: 3 },
    { id: 'e4', version: 4, idempotencyKey: 'k4', account: 'ops', delta: 100, seq: 4 }
  ];
  const replayed = replayWithCheckpoint(events, { version: 0 });
  assert.equal(replayed.length, 4);
  const snapshots = runningBalance(replayed);
  const opsSnapshots = snapshots.filter(s => s.account === 'ops');
  const lastOps = opsSnapshots[opsSnapshots.length - 1];
  assert.equal(lastOps.balance, 400);
});

// ===== INTEGRATION 7: Multi-tenant with rate limiting =====

test('integration-adv-008: tenant-scoped auth with rate limiting', () => {
  const grants = [
    { tenantId: 'acme', userId: 'u1', actions: ['read', 'write'] },
    { tenantId: 'beta', userId: 'u1', actions: ['read'] }
  ];
  assert.equal(multiTenantAuth('acme', 'u1', 'write', grants).authorized, true);
  assert.equal(multiTenantAuth('beta', 'u1', 'write', grants).authorized, false);
  const requests = [
    { timestamp: 1000 },
    { timestamp: 2000 },
    { timestamp: 3000 }
  ];
  const limit = rateLimit(requests, 5000, 5);
  assert.equal(limit.allowed, true);
  assert.equal(limit.remaining, 2);
});

// ===== INTEGRATION 8: Geo routing + Failover + Capacity =====

test('integration-adv-009: geo routing with failover and capacity', () => {
  const hubs = [
    { id: 'hub-east', lat: 0, lng: 5, capacity: 100, failures: 0 },
    { id: 'hub-west', lat: 0, lng: 50, capacity: 80, failures: 4 }
  ];
  const bestHub = geoAwareRoute(hubs, { lat: 0, lng: 3 });
  assert.equal(bestHub.id, 'hub-east');
  const failover = failoverChain(hubs, 3);
  assert.equal(failover.active.length, 1);
  assert.equal(failover.active[0].id, 'hub-east');
});

// ===== INTEGRATION 9: Batch dispatch with priority decay =====

test('integration-adv-010: batch dispatch with decayed priorities', () => {
  const assignments = [
    { id: 'a1', units: 100, priority: priorityDecay(100, 0, 60) },
    { id: 'a2', units: 50, priority: priorityDecay(100, 60, 60) },
    { id: 'a3', units: 75, priority: priorityDecay(100, 120, 60) }
  ];
  assert.equal(assignments[0].priority, 100);
  assert.equal(assignments[1].priority, 50);
  assert.equal(assignments[2].priority, 25);
  const batches = batchDispatch(assignments, 2);
  assert.equal(batches[0].items[0].id, 'a1', 'highest priority in first batch');
});

// ===== INTEGRATION 10: Statistics + SLA =====

test('integration-adv-011: statistical analysis of SLA data', () => {
  const latencies = [100, 110, 95, 105, 98, 102, 500, 103, 97, 106];
  const avg = weightedAverage(latencies, latencies.map(() => 1));
  const stdDev = standardDeviation(latencies);
  const p95 = percentile(latencies, 0.95);
  assert.ok(avg > 90 && avg < 200, `avg ${avg} should be reasonable`);
  assert.ok(stdDev > 0);
  const breachSev = breachSeverity(p95, 300);
  assert.equal(breachSev, 'major');
});

// ===== INTEGRATION 11: Cost allocation + Revenue recognition =====

test('integration-adv-012: cost allocation meets revenue recognition', () => {
  const departments = [
    { name: 'eng', headcount: 20 },
    { name: 'sales', headcount: 10 }
  ];
  const allocated = costAllocation(departments, 9000);
  assert.equal(allocated[0].allocation, 6000);
  assert.equal(allocated[1].allocation, 3000);
  const invoices = [
    { amount: 10000, deliveredPct: 80 }
  ];
  const revenue = revenueRecognition(invoices);
  assert.equal(revenue.recognized, 8000);
  assert.equal(revenue.deferred, 2000);
  const margin = marginRatio(revenue.recognized, 9000);
  assert.equal(margin, 0, 'cost exceeds recognized revenue');
});

// ===== INTEGRATION 12: Audit chain + compliance =====

test('integration-adv-013: audit chain validates with compliance rules', () => {
  const chain = [
    { hash: 'h1', parentHash: 'genesis' },
    { hash: 'h2', parentHash: 'h1' },
    { hash: 'h3', parentHash: 'h2' }
  ];
  const auditResult = auditChainValidator(chain);
  assert.equal(auditResult.valid, true);
  const rules = [
    { name: 'chain-valid', field: 'auditValid', required: true }
  ];
  const compliance = complianceCheck({ auditValid: auditResult.valid }, rules);
  assert.equal(compliance.compliant, true);
});

// ===== INTEGRATION 13: Overcommit detection pipeline =====

test('integration-adv-014: overcommit triggers risk escalation', () => {
  const ratio = overcommitRatio(150, 100);
  assert.equal(ratio, 1.5);
  const risk = riskMatrix(4, 4);
  assert.equal(risk.level, 'high');
  const policy = evaluatePolicy({
    securityIncidents: 0,
    backlog: 20,
    staleMinutes: 30,
    margin: -0.2
  });
  assert.ok(typeof policy.score === 'number');
});

// ===== INTEGRATION 14: Demand projection + Capacity fragmentation =====

test('integration-adv-015: demand projection drives capacity decisions', () => {
  const historical = [80, 85, 90, 95, 100];
  const projected = demandProjection(historical, [1, 1, 1, 1, 2]);
  const pools = [
    { free: 30 },
    { free: 50 },
    { free: 20 }
  ];
  const frag = capacityFragmentation(pools);
  const totalFree = pools.reduce((s, p) => s + p.free, 0);
  const canMeet = totalFree >= projected;
  assert.ok(typeof canMeet === 'boolean');
  assert.ok(frag >= 0 && frag <= 1);
});

// ===== INTEGRATION 15: Full lifecycle with guards and policy =====

test('integration-adv-016: guarded lifecycle with policy evaluation', () => {
  const policy = evaluatePolicy({
    securityIncidents: 0,
    backlog: 5,
    staleMinutes: 5,
    margin: 0.3
  });
  const guards = [
    () => policy.allow,
    () => true
  ];
  const result = guardedTransition('pending', { target: 'validated' }, guards);
  assert.equal(result.transitioned, true);
  assert.equal(result.state, 'validated');
});

// ===== INTEGRATION 16: MTTR + Degradation + Queue Health =====

test('integration-adv-017: MTTR feeds operational health assessment', () => {
  const incidents = [
    { detectedAt: 0, resolvedAt: 300 },
    { detectedAt: 500, resolvedAt: 700 },
    { detectedAt: 1000 }
  ];
  const mttr = meanTimeToRecover(incidents);
  assert.ok(mttr > 0);
  const health = queueHealthScore({
    depth: mttr / 10,
    processingRate: 5,
    errorRate: 0.05,
    avgLatencyMs: mttr
  });
  assert.ok(health > 0 && health <= 100);
});

// ===== INTEGRATION 17: Weighted routing + Partition =====

test('integration-adv-018: weighted route feeds partitioning', () => {
  const routes = [
    { id: 'r1', weight: 5 },
    { id: 'r2', weight: 3 },
    { id: 'r3', weight: 2 }
  ];
  const selected = weightedRouteSelection(routes);
  assert.ok(selected);
  const partition = deterministicPartition('tenant-xyz', 10);
  assert.ok(partition >= 1 && partition <= 10);
});

// ===== INTEGRATION 18: Token rotation + Access level + Permission =====

test('integration-adv-019: token rotation validates access level', () => {
  const current = { expiresAt: 10000 };
  const tokenCheck = tokenRotation(current, [], 1000, 5000);
  assert.equal(tokenCheck.valid, true);
  const level = computeAccessLevel(['operator', 'reviewer']);
  assert.equal(level, 3);
  const perms = permissionIntersection(
    ['dispatch.read', 'dispatch.submit'],
    ['dispatch.submit']
  );
  assert.equal(perms.granted, true);
});

// ===== INTEGRATION 19: Correlation analysis for capacity planning =====

test('integration-adv-020: correlation between load and latency', () => {
  const loads = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
  const latencies = [5, 8, 12, 15, 20, 28, 35, 50, 80, 120];
  const r = correlationCoefficient(loads, latencies);
  assert.ok(r > 0.9, `load-latency correlation ${r} should be > 0.9`);
});

// ===== Matrix expansion =====

for (let i = 0; i < 15; i++) {
  test(`integration-adv-matrix-${String(21 + i).padStart(3, '0')}: full pipeline ${i}`, () => {
    const severity = 3 + (i % 8);
    const slaMin = 10 + i * 5;
    const priority = assignPriority(severity, slaMin);
    const requests = [
      { id: `r-${i}`, units: 20 + i * 5, priority }
    ];
    const plan = reservationPlanner(requests, 200);
    const granted = plan[0].granted;
    const entries = [{ account: `ops-${i}`, delta: granted, seq: 1 }];
    const exposure = balanceExposure(entries);
    assert.ok(exposure[`ops-${i}`] > 0);
    const cost = tieredPricing(granted, [
      { upTo: 50, rate: 2 },
      { upTo: Infinity, rate: 1 }
    ]);
    assert.ok(cost > 0);
  });
}

for (let i = 0; i < 10; i++) {
  test(`integration-adv-matrix-${String(36 + i).padStart(3, '0')}: security→workflow ${i}`, () => {
    const roles = ['viewer', 'operator', 'reviewer', 'admin'];
    const role = roles[i % roles.length];
    const authOk = allowed(role, 'submit');
    const level = computeAccessLevel([role]);
    assert.ok(level >= 0);
    if (authOk) {
      const fsm = new DispatchFSM();
      fsm.transition('validated');
      assert.equal(fsm.getState(), 'validated');
    }
  });
}

for (let i = 0; i < 10; i++) {
  test(`integration-adv-matrix-${String(46 + i).padStart(3, '0')}: financial chain ${i}`, () => {
    const units = 100 + i * 50;
    const tiers = [
      { upTo: 200, rate: 5 },
      { upTo: 500, rate: 3 },
      { upTo: Infinity, rate: 1 }
    ];
    const cost = tieredPricing(units, tiers);
    const revenue = cost * 1.3;
    const margin = marginRatio(revenue, cost);
    assert.ok(margin > 0);
    const periods = [{ margin }];
    const compound = compoundMargin(periods);
    assert.equal(compound, margin);
  });
}

for (let i = 0; i < 10; i++) {
  test(`integration-adv-matrix-${String(56 + i).padStart(3, '0')}: replay→balance→reconcile ${i}`, () => {
    const n = 5 + i;
    const events = Array.from({ length: n }, (_, j) => ({
      id: `e${j}`, version: j + 1, idempotencyKey: `k${j}`,
      account: 'ops', delta: 100, seq: j + 1
    }));
    const replayed = replayWithCheckpoint(events, { version: 0 });
    const snapshots = runningBalance(replayed);
    assert.equal(snapshots[snapshots.length - 1].balance, n * 100);
    const recon = reconcileAccounts(replayed);
    assert.equal(recon.ops.net, n * 100);
  });
}
