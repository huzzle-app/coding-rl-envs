const { test } = require('node:test');
const assert = require('node:assert/strict');

const { fairScheduler, weightedRoundRobin, PriorityQueue, AdaptiveQueue } = require('../../src/core/queue');
const { reservationPlanner } = require('../../src/core/capacity');
const { replayWithCheckpoint, replaySegment, dedupeEvents } = require('../../src/core/replay');
const { replayState, bulkheadPartition, CircuitBreaker } = require('../../src/core/resilience');
const { reconcileAccounts, crossAccountTransfer, runningBalance } = require('../../src/core/ledger');
const { multiTenantAuth } = require('../../src/core/authorization');
const { rateLimit } = require('../../src/core/security');
const { BatchFSM } = require('../../src/core/workflow');

// ===== fairScheduler: preserves input queues (no mutation) =====
// The scheduler should not modify the input arrays. Using splice on copies
// is correct, but we verify the contract.

test('concurrency-adv-001: fair scheduler preserves input queues', () => {
  const q1 = ['a', 'b', 'c'];
  const q2 = ['d', 'e'];
  const original1 = [...q1];
  const original2 = [...q2];
  fairScheduler([q1, q2], 1);
  assert.deepEqual(q1, original1, 'input queue 1 must not be mutated');
  assert.deepEqual(q2, original2, 'input queue 2 must not be mutated');
});

test('concurrency-adv-002: fair scheduler total items preserved', () => {
  const queues = [['a', 'b'], ['c', 'd', 'e'], ['f']];
  const result = fairScheduler(queues, 1);
  assert.equal(result.length, 6);
});

test('concurrency-adv-003: fair scheduler quantum 3 batching', () => {
  const result = fairScheduler([['a', 'b', 'c', 'd'], ['e', 'f', 'g']], 3);
  assert.equal(result.length, 7);
  assert.deepEqual(result.slice(0, 3), ['a', 'b', 'c']);
  assert.deepEqual(result.slice(3, 6), ['e', 'f', 'g']);
  assert.equal(result[6], 'd');
});

// ===== weightedRoundRobin: weight-proportional scheduling =====

test('concurrency-adv-004: weighted round robin respects weights', () => {
  const q1 = ['a1', 'a2', 'a3', 'a4'];
  const q2 = ['b1', 'b2'];
  const result = weightedRoundRobin([q1, q2], [2, 1]);
  assert.equal(result[0], 'a1');
  assert.equal(result[1], 'a2');
  assert.equal(result[2], 'b1');
  assert.equal(result.length, 6);
});

test('concurrency-adv-005: weighted round robin equal weights acts as fair', () => {
  const result = weightedRoundRobin([['a', 'b'], ['c', 'd']], [1, 1]);
  assert.deepEqual(result, ['a', 'c', 'b', 'd']);
});

test('concurrency-adv-006: weighted round robin handles empty queues', () => {
  assert.deepEqual(weightedRoundRobin([[], []], [1, 1]), []);
});

test('concurrency-adv-007: weighted round robin uneven exhaustion', () => {
  const result = weightedRoundRobin([['a'], ['b', 'c', 'd']], [1, 2]);
  assert.equal(result.length, 4);
});

// ===== reservationPlanner: concurrent requests don't exceed capacity =====
// Bug: checks each request against totalCapacity instead of remaining

test('concurrency-adv-008: competing reservations respect capacity', () => {
  const requests = Array.from({ length: 10 }, (_, i) => ({
    id: `r${i}`, units: 20, priority: 10 - i
  }));
  const plan = reservationPlanner(requests, 100);
  const total = plan.reduce((s, p) => s + p.granted, 0);
  assert.ok(total <= 100, `total ${total} exceeds capacity 100`);
  assert.equal(total, 100, 'should use all available capacity');
});

test('concurrency-adv-009: priority ordering in reservation', () => {
  const requests = [
    { id: 'low', units: 80, priority: 1 },
    { id: 'high', units: 80, priority: 10 },
    { id: 'med', units: 80, priority: 5 }
  ];
  const plan = reservationPlanner(requests, 100);
  const high = plan.find(p => p.id === 'high');
  assert.equal(high.granted, 80, 'highest priority gets full allocation');
  const total = plan.reduce((s, p) => s + p.granted, 0);
  assert.ok(total <= 100);
});

test('concurrency-adv-010: partial allocation for last fitting request', () => {
  const requests = [
    { id: 'r1', units: 60, priority: 10 },
    { id: 'r2', units: 60, priority: 5 }
  ];
  const plan = reservationPlanner(requests, 100);
  const r2 = plan.find(p => p.id === 'r2');
  assert.equal(r2.granted, 40, 'should grant remaining 40, not 60');
});

// ===== replayWithCheckpoint: concurrent checkpoint + replay =====
// Bug: uses >= instead of > for version filter, re-including checkpoint event

test('concurrency-adv-011: checkpoint exclusivity', () => {
  const events = Array.from({ length: 20 }, (_, i) => ({
    id: `e${i}`, version: i + 1, idempotencyKey: `k${i}`
  }));
  const result = replayWithCheckpoint(events, { version: 10 });
  assert.equal(result.length, 10, 'should replay versions 11-20 only');
  assert.equal(result[0].version, 11);
});

test('concurrency-adv-012: idempotent dedup in concurrent replays', () => {
  const events = [
    { id: 'e1', version: 5, idempotencyKey: 'k1' },
    { id: 'e2', version: 6, idempotencyKey: 'k1' },
    { id: 'e3', version: 7, idempotencyKey: 'k2' }
  ];
  const result = replayWithCheckpoint(events, { version: 4 });
  const keys = result.map(e => e.idempotencyKey);
  assert.equal(new Set(keys).size, keys.length, 'no duplicate idempotency keys');
});

// ===== replayState: concurrent event ordering =====
// Bug: inflight -= delta (should be +=)

test('concurrency-adv-013: replay state applies events in order', () => {
  const events = [
    { version: 2, idempotencyKey: 'k1', inflightDelta: 5, backlogDelta: -2 },
    { version: 3, idempotencyKey: 'k2', inflightDelta: 3, backlogDelta: 1 }
  ];
  const state = replayState(10, 20, 1, events);
  assert.equal(state.inflight, 18, '10 + 5 + 3 = 18');
  assert.equal(state.backlog, 19, '20 + (-2) + 1 = 19');
  assert.equal(state.applied, 2);
});

test('concurrency-adv-014: replay state skips already-applied versions', () => {
  const events = [
    { version: 1, idempotencyKey: 'k1', inflightDelta: 100 },
    { version: 5, idempotencyKey: 'k2', inflightDelta: 10 }
  ];
  const state = replayState(0, 0, 3, events);
  assert.equal(state.applied, 1, 'only version 5 should be applied');
  assert.equal(state.inflight, 10);
});

test('concurrency-adv-015: replay state deduplicates by idempotency key', () => {
  const events = [
    { version: 2, idempotencyKey: 'k1', inflightDelta: 5 },
    { version: 3, idempotencyKey: 'k1', inflightDelta: 10 }
  ];
  const state = replayState(0, 0, 1, events);
  assert.equal(state.applied, 1, 'duplicate key should be processed once');
  assert.equal(state.inflight, 5);
});

// ===== rateLimit: sliding window correctness =====

test('concurrency-adv-016: rate limit allows within budget', () => {
  const requests = [
    { timestamp: 1000 },
    { timestamp: 2000 },
    { timestamp: 3000 }
  ];
  const result = rateLimit(requests, 5000, 5);
  assert.equal(result.allowed, true);
  assert.equal(result.remaining, 2);
});

test('concurrency-adv-017: rate limit blocks when exhausted', () => {
  const requests = Array.from({ length: 10 }, (_, i) => ({ timestamp: 1000 + i * 100 }));
  const result = rateLimit(requests, 5000, 5);
  assert.equal(result.allowed, false);
});

test('concurrency-adv-018: rate limit window expiry', () => {
  const requests = [
    { timestamp: 1000 },
    { timestamp: 2000 },
    { timestamp: 10000 }
  ];
  const result = rateLimit(requests, 5000, 3);
  assert.equal(result.allowed, true, 'old requests outside window should not count');
});

// ===== multiTenantAuth: tenant isolation under concurrent access =====
// Bug: doesn't check tenantId in grant matching

test('concurrency-adv-019: tenant isolation prevents cross-access', () => {
  const grants = [
    { tenantId: 'alpha', userId: 'u1', actions: ['read', 'write', 'admin'] },
    { tenantId: 'beta', userId: 'u1', actions: ['read'] }
  ];
  assert.equal(multiTenantAuth('beta', 'u1', 'admin', grants).authorized, false,
    'admin grant is for alpha, must not apply to beta');
  assert.equal(multiTenantAuth('alpha', 'u1', 'admin', grants).authorized, true);
});

test('concurrency-adv-020: tenant grants with same user different scopes', () => {
  const grants = [
    { tenantId: 't1', userId: 'u1', actions: ['read'] },
    { tenantId: 't2', userId: 'u1', actions: ['write'] }
  ];
  assert.equal(multiTenantAuth('t1', 'u1', 'write', grants).authorized, false);
  assert.equal(multiTenantAuth('t2', 'u1', 'read', grants).authorized, false);
});

// ===== bulkheadPartition: correct partition sizing =====

test('concurrency-adv-021: bulkhead creates correct partitions', () => {
  const tasks = ['a', 'b', 'c', 'd', 'e'];
  const partitions = bulkheadPartition(tasks, 2);
  assert.equal(partitions.length, 3);
  assert.deepEqual(partitions[0], ['a', 'b']);
  assert.deepEqual(partitions[1], ['c', 'd']);
  assert.deepEqual(partitions[2], ['e']);
});

test('concurrency-adv-022: bulkhead single partition', () => {
  const partitions = bulkheadPartition(['a', 'b'], 5);
  assert.equal(partitions.length, 1);
  assert.deepEqual(partitions[0], ['a', 'b']);
});

test('concurrency-adv-023: bulkhead empty tasks', () => {
  assert.deepEqual(bulkheadPartition([], 3), []);
});

// ===== reconcileAccounts: concurrent adjustments compound =====

test('concurrency-adv-024: sequential adjustments to same account compound', () => {
  const entries = [{ account: 'ops', delta: 1000 }];
  const adjustments = [
    { account: 'ops', factor: 1.1 },
    { account: 'ops', factor: 1.05 }
  ];
  const result = reconcileAccounts(entries, adjustments);
  const expected = 1000 * 1.1 * 1.05;
  assert.equal(result.ops.net, expected);
});

test('concurrency-adv-025: concurrent transfers maintain invariants', () => {
  let entries = [
    { id: 'e1', account: 'A', delta: 1000, seq: 1 },
    { id: 'e2', account: 'B', delta: 500, seq: 2 }
  ];
  entries = crossAccountTransfer(entries, 'A', 'B', 200);
  entries = crossAccountTransfer(entries, 'B', 'A', 100);
  const snapshots = runningBalance(entries);
  const finalA = snapshots.filter(s => s.account === 'A').pop().balance;
  const finalB = snapshots.filter(s => s.account === 'B').pop().balance;
  assert.equal(finalA, 900, 'A: 1000 - 200 + 100 = 900');
  assert.equal(finalB, 600, 'B: 500 + 200 - 100 = 600');
});

// ===== BatchFSM: concurrent transitions =====

test('concurrency-adv-026: batch transitions are atomic per machine', () => {
  const batch = new BatchFSM(5);
  batch.transitionAll('validated');
  batch.transitionAll('capacity_checked');
  const results = batch.transitionAll('dispatched');
  assert.equal(results.filter(r => r.success).length, 5);
  const dist = batch.stateDistribution();
  assert.equal(dist['dispatched'], 5);
});

test('concurrency-adv-027: batch handles mixed valid/invalid transitions', () => {
  const batch = new BatchFSM(4);
  batch.transitionAll('validated');
  batch.machines[0].transition('capacity_checked');
  batch.machines[1].transition('capacity_checked');
  const results = batch.transitionAll('dispatched');
  const successes = results.filter(r => r.success).length;
  assert.equal(successes, 2, 'only capacity_checked machines can dispatch');
});

// ===== CircuitBreaker: concurrent failure tracking =====

test('concurrency-adv-028: circuit breaker tracks failures accurately', () => {
  const cb = new CircuitBreaker({ threshold: 5, cooldownMs: 10000 });
  for (let i = 0; i < 4; i++) cb.recordFailure(i * 100);
  assert.equal(cb.getState(), 'closed');
  cb.recordFailure(400);
  assert.equal(cb.getState(), 'open');
});

test('concurrency-adv-029: success reduces failure count', () => {
  const cb = new CircuitBreaker({ threshold: 5, cooldownMs: 10000 });
  cb.recordFailure(100);
  cb.recordFailure(200);
  cb.recordSuccess();
  cb.recordSuccess();
  assert.equal(cb.getState(), 'closed');
  assert.equal(cb.failureCount, 0);
});

test('concurrency-adv-030: rapid fail-recover-fail cycle', () => {
  const cb = new CircuitBreaker({ threshold: 3, cooldownMs: 1000, halfOpenMax: 2 });
  cb.recordFailure(0);
  cb.recordFailure(100);
  cb.recordFailure(200);
  assert.equal(cb.getState(), 'open');
  cb.attemptReset(2000);
  assert.equal(cb.getState(), 'half-open');
  cb.recordSuccess();
  cb.recordSuccess();
  assert.equal(cb.getState(), 'closed');
  cb.recordFailure(3000);
  cb.recordFailure(3100);
  cb.recordFailure(3200);
  assert.equal(cb.getState(), 'open');
});

// ===== Matrix expansion =====

for (let i = 0; i < 15; i++) {
  test(`concurrency-adv-matrix-${String(31 + i).padStart(3, '0')}: reservation capacity bound ${i}`, () => {
    const n = 5 + i;
    const unitsPer = 30;
    const cap = 100;
    const requests = Array.from({ length: n }, (_, j) => ({
      id: `r${j}`, units: unitsPer, priority: n - j
    }));
    const plan = reservationPlanner(requests, cap);
    const total = plan.reduce((s, p) => s + p.granted, 0);
    assert.ok(total <= cap, `total ${total} must not exceed ${cap}`);
    assert.equal(total, Math.min(n * unitsPer, cap));
  });
}

for (let i = 0; i < 15; i++) {
  test(`concurrency-adv-matrix-${String(46 + i).padStart(3, '0')}: replay checkpoint exclusive ${i}`, () => {
    const n = 10 + i;
    const events = Array.from({ length: n }, (_, j) => ({
      id: `e${j}`, version: j + 1, idempotencyKey: `k${j}`
    }));
    const checkpoint = Math.floor(n / 2);
    const result = replayWithCheckpoint(events, { version: checkpoint });
    assert.equal(result.length, n - checkpoint,
      `with checkpoint at ${checkpoint}, should replay ${n - checkpoint} events`);
    assert.equal(result[0].version, checkpoint + 1);
  });
}

for (let i = 0; i < 10; i++) {
  test(`concurrency-adv-matrix-${String(61 + i).padStart(3, '0')}: tenant isolation ${i}`, () => {
    const tenants = Array.from({ length: 3 }, (_, t) => `tenant-${i}-${t}`);
    const grants = tenants.map(tid => ({
      tenantId: tid,
      userId: 'shared-user',
      actions: [`action-${tid}`]
    }));
    for (let t = 0; t < tenants.length; t++) {
      assert.equal(
        multiTenantAuth(tenants[t], 'shared-user', `action-${tenants[t]}`, grants).authorized,
        true
      );
      for (let o = 0; o < tenants.length; o++) {
        if (o !== t) {
          assert.equal(
            multiTenantAuth(tenants[t], 'shared-user', `action-${tenants[o]}`, grants).authorized,
            false,
            `action for ${tenants[o]} must not work in ${tenants[t]}`
          );
        }
      }
    }
  });
}
