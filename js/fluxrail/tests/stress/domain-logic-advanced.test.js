const { test } = require('node:test');
const assert = require('node:assert/strict');

const { breakEvenUnits, revenueRecognition, costAllocation, discountedCashFlow } = require('../../src/core/economics');
const { capacityWatermark, overcommitRatio } = require('../../src/core/capacity');
const { complianceCheck, riskMatrix, policyPrecedence } = require('../../src/core/policy');
const { slaCredits, slaCompliance } = require('../../src/core/sla');
const { routeLatencyEstimate, partitionRebalance } = require('../../src/core/routing');
const { priorityDecay, batchDispatch } = require('../../src/core/dispatch');
const { correlationCoefficient, histogram } = require('../../src/core/statistics');
const { tokenRotation, permissionIntersection } = require('../../src/core/authorization');
const { computeAccessLevel } = require('../../src/core/security');

// ===== costAllocation: divides by department count instead of headcount weight =====
// Cost should be proportional to headcount, not evenly distributed.

test('domain-adv-001: cost allocation proportional to headcount', () => {
  const departments = [
    { name: 'eng', headcount: 30 },
    { name: 'sales', headcount: 10 }
  ];
  const result = costAllocation(departments, 1000);
  assert.equal(result[0].allocation, 750, 'eng: 30/40 * 1000 = 750');
  assert.equal(result[1].allocation, 250, 'sales: 10/40 * 1000 = 250');
});

test('domain-adv-002: cost allocation single department gets all', () => {
  const result = costAllocation([{ name: 'ops', headcount: 5 }], 500);
  assert.equal(result[0].allocation, 500);
});

test('domain-adv-003: cost allocation three departments', () => {
  const departments = [
    { name: 'a', headcount: 10 },
    { name: 'b', headcount: 20 },
    { name: 'c', headcount: 10 }
  ];
  const result = costAllocation(departments, 4000);
  assert.equal(result[0].allocation, 1000);
  assert.equal(result[1].allocation, 2000);
  assert.equal(result[2].allocation, 1000);
});

test('domain-adv-004: cost allocation total equals input', () => {
  const departments = [
    { name: 'x', headcount: 3 },
    { name: 'y', headcount: 7 }
  ];
  const result = costAllocation(departments, 10000);
  const total = result.reduce((s, d) => s + d.allocation, 0);
  assert.equal(total, 10000, 'allocations must sum to total cost');
});

test('domain-adv-005: cost allocation empty returns empty', () => {
  assert.deepEqual(costAllocation([], 1000), []);
});

// ===== discountedCashFlow: discounts year 0 (should not discount present value) =====
// DCF formula: NPV = CF0 + CF1/(1+r) + CF2/(1+r)^2 + ...
// Year 0 cash flow is NOT discounted. Bug applies discount to year 0 too.

test('domain-adv-006: DCF year 0 not discounted', () => {
  const result = discountedCashFlow([1000], 0.1);
  assert.equal(result, 1000, 'year 0 cash flow should not be discounted');
});

test('domain-adv-007: DCF two years', () => {
  const result = discountedCashFlow([1000, 1100], 0.1);
  assert.equal(result, 2000, '1000 + 1100/1.1 = 2000');
});

test('domain-adv-008: DCF three years', () => {
  const cfs = [100, 110, 121];
  const result = discountedCashFlow(cfs, 0.1);
  const expected = Math.round((100 + 110/1.1 + 121/1.21) * 100) / 100;
  assert.equal(result, expected);
});

test('domain-adv-009: DCF zero rate returns sum', () => {
  assert.equal(discountedCashFlow([100, 200, 300], 0), 600);
});

test('domain-adv-010: DCF empty returns 0', () => {
  assert.equal(discountedCashFlow([], 0.1), 0);
});

// ===== revenueRecognition: recognizes based on delivery percentage =====

test('domain-adv-011: fully delivered invoice recognized', () => {
  const result = revenueRecognition([{ amount: 1000, deliveredPct: 100 }]);
  assert.equal(result.recognized, 1000);
  assert.equal(result.deferred, 0);
});

test('domain-adv-012: partially delivered splits correctly', () => {
  const result = revenueRecognition([{ amount: 1000, deliveredPct: 60 }]);
  assert.equal(result.recognized, 600);
  assert.equal(result.deferred, 400);
});

test('domain-adv-013: multiple invoices aggregated', () => {
  const invoices = [
    { amount: 500, deliveredPct: 100 },
    { amount: 500, deliveredPct: 50 }
  ];
  const result = revenueRecognition(invoices);
  assert.equal(result.recognized, 750);
  assert.equal(result.deferred, 250);
});

test('domain-adv-014: zero delivery means all deferred', () => {
  const result = revenueRecognition([{ amount: 1000, deliveredPct: 0 }]);
  assert.equal(result.recognized, 0);
  assert.equal(result.deferred, 1000);
});

// ===== breakEvenUnits: correct calculation =====

test('domain-adv-015: basic break-even', () => {
  assert.equal(breakEvenUnits(1000, 20, 10), 100, '1000 / (20-10) = 100');
});

test('domain-adv-016: zero contribution margin returns Infinity', () => {
  assert.equal(breakEvenUnits(1000, 10, 10), Infinity);
});

test('domain-adv-017: negative contribution margin returns Infinity', () => {
  assert.equal(breakEvenUnits(1000, 5, 10), Infinity);
});

test('domain-adv-018: break-even rounds up', () => {
  assert.equal(breakEvenUnits(100, 15, 10), 20, 'ceil(100/5) = 20');
});

// ===== capacityWatermark: threshold boundaries =====

test('domain-adv-019: critical below low threshold', () => {
  assert.equal(capacityWatermark(10, 20, 80), 'critical');
});

test('domain-adv-020: warning between low and midpoint', () => {
  assert.equal(capacityWatermark(30, 20, 80), 'warning');
});

test('domain-adv-021: nominal between midpoint and high', () => {
  assert.equal(capacityWatermark(60, 20, 80), 'nominal');
});

test('domain-adv-022: surplus above high', () => {
  assert.equal(capacityWatermark(90, 20, 80), 'surplus');
});

test('domain-adv-023: at low boundary is critical', () => {
  assert.equal(capacityWatermark(20, 20, 80), 'critical');
});

// ===== PriorityQueue: must dequeue highest first AND drain in same order =====
// A max-priority queue must: (1) sort descending so dequeue() returns highest,
// AND (2) drain(n) must return items in the same priority order as sequential
// dequeue() calls. Both the sort direction and drain ordering must be correct.

const { PriorityQueue, queueHealthScore, weightedRoundRobin } = require('../../src/core/queue');

test('domain-adv-024: priority queue dequeues highest first', () => {
  const pq = new PriorityQueue();
  pq.enqueue('low', 1);
  pq.enqueue('high', 10);
  pq.enqueue('med', 5);
  assert.equal(pq.dequeue(), 'high', 'highest priority (10) should come first');
});

test('domain-adv-025: priority queue peek returns highest', () => {
  const pq = new PriorityQueue();
  pq.enqueue('a', 3);
  pq.enqueue('b', 7);
  assert.equal(pq.peek(), 'b');
});

test('domain-adv-026: priority queue drain takes highest N', () => {
  const pq = new PriorityQueue();
  [1, 5, 3, 8, 2].forEach((p, i) => pq.enqueue(`item-${i}`, p));
  const drained = pq.drain(2);
  assert.equal(drained[0], 'item-3', 'first drained should be priority 8');
  assert.equal(drained[1], 'item-1', 'second drained should be priority 5');
});

test('domain-adv-027: priority queue size tracks correctly', () => {
  const pq = new PriorityQueue();
  pq.enqueue('a', 1);
  pq.enqueue('b', 2);
  assert.equal(pq.size(), 2);
  pq.dequeue();
  assert.equal(pq.size(), 1);
});

test('domain-adv-028: empty priority queue returns null', () => {
  const pq = new PriorityQueue();
  assert.equal(pq.dequeue(), null);
  assert.equal(pq.peek(), null);
});

test('domain-adv-028a: drain order matches sequential dequeue order', () => {
  const pq1 = new PriorityQueue();
  const pq2 = new PriorityQueue();
  [3, 7, 1, 9, 5].forEach((p, i) => {
    pq1.enqueue(`item-${i}`, p);
    pq2.enqueue(`item-${i}`, p);
  });
  // Sequential dequeue
  const sequential = [];
  for (let i = 0; i < 3; i++) sequential.push(pq1.dequeue());
  // Batch drain
  const batched = pq2.drain(3);
  assert.deepEqual(batched, sequential,
    'drain(n) must return items in same order as n sequential dequeue() calls');
});

test('domain-adv-028b: drain preserves descending priority order', () => {
  const pq = new PriorityQueue();
  [10, 20, 30, 40, 50].forEach((p, i) => pq.enqueue(`item-${i}`, p));
  const drained = pq.drain(3);
  assert.equal(drained[0], 'item-4', 'first should be priority 50');
  assert.equal(drained[1], 'item-3', 'second should be priority 40');
  assert.equal(drained[2], 'item-2', 'third should be priority 30');
});

// ===== queueHealthScore: throughput bonus SUBTRACTED instead of ADDED =====
// Higher processing rate should improve (increase) health score, not decrease it.

test('domain-adv-029: high throughput improves health', () => {
  const healthy = queueHealthScore({ depth: 40, processingRate: 10, errorRate: 0.1, avgLatencyMs: 500 });
  const slow = queueHealthScore({ depth: 40, processingRate: 1, errorRate: 0.1, avgLatencyMs: 500 });
  assert.ok(healthy > slow, `high throughput ${healthy} should score better than low ${slow}`);
});

test('domain-adv-030: zero errors and low depth gives high score', () => {
  const score = queueHealthScore({ depth: 5, processingRate: 10, errorRate: 0, avgLatencyMs: 50 });
  assert.ok(score >= 80, `healthy queue should score >= 80, got ${score}`);
});

test('domain-adv-031: high error rate drops score', () => {
  const highErr = queueHealthScore({ depth: 10, processingRate: 5, errorRate: 0.5, avgLatencyMs: 200 });
  const lowErr = queueHealthScore({ depth: 10, processingRate: 5, errorRate: 0, avgLatencyMs: 200 });
  assert.ok(highErr < lowErr, `high error rate ${highErr} should score worse than low error rate ${lowErr}`);
  assert.ok(highErr <= 60, `50% error rate should give score <= 60, got ${highErr}`);
});

// ===== riskMatrix: correct risk level boundaries =====

test('domain-adv-032: critical risk at 5x5', () => {
  const result = riskMatrix(5, 5);
  assert.equal(result.level, 'critical');
  assert.equal(result.score, 25);
});

test('domain-adv-033: low risk at 1x1', () => {
  const result = riskMatrix(1, 1);
  assert.equal(result.level, 'low');
});

test('domain-adv-034: medium risk at 3x3', () => {
  const result = riskMatrix(3, 3);
  assert.equal(result.level, 'medium');
});

test('domain-adv-035: high risk at 4x4', () => {
  const result = riskMatrix(4, 4);
  assert.equal(result.level, 'high');
});

// ===== policyPrecedence: sorts by priority ascending (lower number = higher precedence) =====

test('domain-adv-036: policies sorted by priority', () => {
  const policies = [
    { name: 'rate-limit', priority: 2 },
    { name: 'auth', priority: 1 },
    { name: 'audit', priority: 3 }
  ];
  const sorted = policyPrecedence(policies);
  assert.equal(sorted[0].name, 'auth');
  assert.equal(sorted[2].name, 'audit');
});

test('domain-adv-037: tie-breaking by name', () => {
  const policies = [
    { name: 'beta', priority: 1 },
    { name: 'alpha', priority: 1 }
  ];
  const sorted = policyPrecedence(policies);
  assert.equal(sorted[0].name, 'alpha');
});

// ===== slaCredits: correct credit calculation =====

test('domain-adv-038: SLA credits proportional to breaches', () => {
  assert.equal(slaCredits(3, 100, 10000), 300);
});

test('domain-adv-039: SLA credits capped at max', () => {
  assert.equal(slaCredits(10, 100, 500), 500);
});

test('domain-adv-040: zero breaches zero credits', () => {
  assert.equal(slaCredits(0, 100, 1000), 0);
});

// ===== correlationCoefficient =====

test('domain-adv-041: perfect positive correlation', () => {
  assert.equal(correlationCoefficient([1, 2, 3], [1, 2, 3]), 1);
});

test('domain-adv-042: perfect negative correlation', () => {
  assert.equal(correlationCoefficient([1, 2, 3], [3, 2, 1]), -1);
});

test('domain-adv-043: no correlation', () => {
  const r = correlationCoefficient([1, 2, 3, 4], [1, -1, 1, -1]);
  assert.ok(Math.abs(r) < 0.5);
});

test('domain-adv-043a: correlation coefficient bounded in [-1, 1]', () => {
  const r = correlationCoefficient([1, 3, 5, 2, 4], [2, 4, 6, 1, 3]);
  assert.ok(r >= -1 && r <= 1,
    `Pearson r must be in [-1, 1], got ${r}`);
  assert.ok(r > 0.7, 'should show strong positive correlation');
});

test('domain-adv-043b: correlation with unequal variance magnitudes', () => {
  const xs = [10, 20, 30, 40, 50];
  const ys = [1, 2, 3, 4, 5];
  const r = correlationCoefficient(xs, ys);
  assert.equal(r, 1, 'perfectly linearly related data should give r=1 regardless of scale');
});

test('domain-adv-043c: correlation with mixed positive and negative deviations', () => {
  const r = correlationCoefficient([1, 5, 3, 7, 2], [3, 8, 4, 9, 1]);
  assert.ok(r >= -1 && r <= 1, `r=${r} must be bounded`);
});

// ===== routeLatencyEstimate: must include full processing time =====
// The total latency of a route is the sum of all hop latencies AND processing
// times. Both are in milliseconds. Mixing units or scaling either component
// produces incorrect route latency estimates.

test('domain-adv-043d: route latency includes full processing time', () => {
  const hops = [
    { latencyMs: 10, processingMs: 50 },
    { latencyMs: 20, processingMs: 30 }
  ];
  const total = routeLatencyEstimate(hops);
  assert.equal(total, 110, '10+50+20+30 = 110ms total');
});

test('domain-adv-043e: route latency with dominant processing', () => {
  const hops = [
    { latencyMs: 5, processingMs: 200 },
    { latencyMs: 5, processingMs: 300 }
  ];
  const total = routeLatencyEstimate(hops);
  assert.equal(total, 510, 'processing dominates: 5+200+5+300=510');
});

test('domain-adv-043f: single hop latency', () => {
  assert.equal(routeLatencyEstimate([{ latencyMs: 100, processingMs: 50 }]), 150);
});

// ===== histogram: bucket distribution =====

test('domain-adv-044: evenly distributed values', () => {
  const values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const result = histogram(values, 2);
  assert.equal(result.length, 2);
  assert.equal(result[0].count + result[1].count, 10);
});

test('domain-adv-045: single value one bucket', () => {
  const result = histogram([5, 5, 5], 3);
  assert.equal(result.length, 1);
  assert.equal(result[0].count, 3);
});

// ===== computeAccessLevel: returns max role level =====

test('domain-adv-046: admin gets level 4', () => {
  assert.equal(computeAccessLevel(['admin']), 4);
});

test('domain-adv-047: multiple roles returns max', () => {
  assert.equal(computeAccessLevel(['viewer', 'admin', 'operator']), 4);
});

test('domain-adv-048: empty roles returns 0', () => {
  assert.equal(computeAccessLevel([]), 0);
});

test('domain-adv-049: unknown role returns 0', () => {
  assert.equal(computeAccessLevel(['unknown']), 0);
});

// ===== tokenRotation: grace period for rotated tokens =====

test('domain-adv-050: valid current token accepted', () => {
  const current = { expiresAt: 5000 };
  assert.equal(tokenRotation(current, [], 1000, 3000).valid, true);
});

test('domain-adv-051: expired current falls back to previous in grace', () => {
  const current = { expiresAt: 1000 };
  const previous = [{ expiresAt: 2000 }];
  const result = tokenRotation(current, previous, 1000, 2500);
  assert.equal(result.valid, true);
  assert.equal(result.rotated, true);
});

test('domain-adv-052: all tokens expired beyond grace', () => {
  const current = { expiresAt: 1000 };
  const previous = [{ expiresAt: 500 }];
  assert.equal(tokenRotation(current, previous, 100, 5000).valid, false);
});

// ===== permissionIntersection =====

test('domain-adv-053: all required permissions present', () => {
  const result = permissionIntersection(['read', 'write', 'delete'], ['read', 'write']);
  assert.equal(result.granted, true);
  assert.deepEqual(result.missing, []);
});

test('domain-adv-054: missing permissions reported', () => {
  const result = permissionIntersection(['read'], ['read', 'write']);
  assert.equal(result.granted, false);
  assert.deepEqual(result.missing, ['write']);
});

test('domain-adv-055: empty required always granted', () => {
  assert.equal(permissionIntersection(['read'], []).granted, true);
});

// ===== priorityDecay: exponential decay over time =====

test('domain-adv-056: no decay at age 0', () => {
  assert.equal(priorityDecay(100, 0, 60), 100);
});

test('domain-adv-057: half decay at half-life', () => {
  assert.equal(priorityDecay(100, 60, 60), 50);
});

test('domain-adv-058: two half-lives gives quarter', () => {
  assert.equal(priorityDecay(100, 120, 60), 25);
});

// ===== partitionRebalance: produces 0-indexed partitions =====

test('domain-adv-059: rebalance assigns new partitions', () => {
  const mapping = { 'tenant-a': { data: 'x' }, 'tenant-b': { data: 'y' } };
  const result = partitionRebalance(mapping, 4);
  assert.ok(result['tenant-a'].partition >= 0);
  assert.ok(result['tenant-a'].partition < 4);
});

test('domain-adv-060: empty mapping returns empty', () => {
  assert.deepEqual(partitionRebalance({}, 4), {});
});

// ===== Matrix expansion =====

for (let i = 0; i < 20; i++) {
  test(`domain-adv-matrix-${String(61 + i).padStart(3, '0')}: cost allocation ${i} depts`, () => {
    const n = 2 + (i % 5);
    const departments = Array.from({ length: n }, (_, j) => ({
      name: `dept-${j}`,
      headcount: 10 + j * 5
    }));
    const totalCost = 10000;
    const result = costAllocation(departments, totalCost);
    const totalAlloc = result.reduce((s, d) => s + d.allocation, 0);
    const totalHead = departments.reduce((s, d) => s + d.headcount, 0);
    assert.ok(Math.abs(totalAlloc - totalCost) < 1,
      `allocations ${totalAlloc} should sum to ${totalCost}`);
    for (const dept of result) {
      const expected = Math.round((dept.headcount / totalHead) * totalCost * 100) / 100;
      assert.equal(dept.allocation, expected,
        `${dept.name} allocation should be ${expected}, got ${dept.allocation}`);
    }
  });
}

for (let i = 0; i < 20; i++) {
  test(`domain-adv-matrix-${String(81 + i).padStart(3, '0')}: DCF scenarios ${i}`, () => {
    const rate = 0.05 + i * 0.01;
    const cfs = [1000, 500, 500];
    const result = discountedCashFlow(cfs, rate);
    const expected = Math.round((1000 + 500/(1 + rate) + 500/Math.pow(1 + rate, 2)) * 100) / 100;
    assert.equal(result, expected);
  });
}

for (let i = 0; i < 15; i++) {
  test(`domain-adv-matrix-${String(101 + i).padStart(3, '0')}: priority queue ordering ${i}`, () => {
    const pq = new PriorityQueue();
    const n = 5 + i;
    const priorities = Array.from({ length: n }, (_, j) => j * 3 + 1);
    priorities.forEach((p, idx) => pq.enqueue(`item-${idx}`, p));
    const first = pq.dequeue();
    assert.equal(first, `item-${n - 1}`, 'should dequeue highest priority first');
  });
}

for (let i = 0; i < 15; i++) {
  test(`domain-adv-matrix-${String(116 + i).padStart(3, '0')}: SLA compliance ${i}`, () => {
    const total = 10 + i * 5;
    const breached = Math.min(i, total);
    const deliveries = Array.from({ length: total }, (_, j) => ({
      actualTime: j < breached ? 200 : 50,
      slaTime: 100
    }));
    const result = slaCompliance(deliveries);
    assert.equal(result.breached, breached);
    assert.equal(result.total, total);
    const expectedRate = Math.round(((total - breached) / total) * 10000) / 10000;
    assert.equal(result.rate, expectedRate);
  });
}

for (let i = 0; i < 10; i++) {
  test(`domain-adv-matrix-${String(131 + i).padStart(3, '0')}: route latency ${i} hops`, () => {
    const numHops = 2 + i;
    const hops = Array.from({ length: numHops }, (_, j) => ({
      latencyMs: 10 + j * 5,
      processingMs: 20 + j * 10
    }));
    const total = routeLatencyEstimate(hops);
    const expected = hops.reduce((s, h) => s + h.latencyMs + h.processingMs, 0);
    assert.equal(total, expected,
      `total latency for ${numHops} hops should be ${expected}, got ${total}`);
  });
}

for (let i = 0; i < 10; i++) {
  test(`domain-adv-matrix-${String(141 + i).padStart(3, '0')}: correlation bounded ${i}`, () => {
    const n = 4 + i;
    const xs = Array.from({ length: n }, (_, j) => Math.pow(j, 1.5) + i);
    const ys = Array.from({ length: n }, (_, j) => j * 3 - Math.pow(j, 0.5) * i);
    const r = correlationCoefficient(xs, ys);
    assert.ok(r >= -1 && r <= 1,
      `r=${r} must be in [-1, 1] (n=${n})`);
  });
}
