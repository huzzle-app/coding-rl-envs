const { test } = require('node:test');
const assert = require('node:assert/strict');

const { fairScheduler } = require('../../src/core/queue');
const { reservationPlanner } = require('../../src/core/capacity');
const { replayWithCheckpoint } = require('../../src/core/replay');
const { multiTenantAuth } = require('../../src/core/authorization');
const { reconcileAccounts } = require('../../src/core/ledger');

// ===== fairScheduler: basic correctness =====

test('concurrency-fair-001: interleaves with quantum 1', () => {
  assert.deepEqual(
    fairScheduler([['a1', 'a2', 'a3'], ['b1', 'b2']], 1),
    ['a1', 'b1', 'a2', 'b2', 'a3']
  );
});

test('concurrency-fair-002: preserves original queues', () => {
  const q1 = ['a1', 'a2'];
  const q2 = ['b1'];
  const copy1 = [...q1];
  const copy2 = [...q2];
  fairScheduler([q1, q2], 1);
  assert.deepEqual(q1, copy1);
  assert.deepEqual(q2, copy2);
});

test('concurrency-fair-003: quantum 2 takes two per round', () => {
  assert.deepEqual(
    fairScheduler([['a1', 'a2', 'a3'], ['b1', 'b2', 'b3']], 2),
    ['a1', 'a2', 'b1', 'b2', 'a3', 'b3']
  );
});

test('concurrency-fair-004: empty queues produce empty', () => {
  assert.deepEqual(fairScheduler([[], []], 1), []);
});

test('concurrency-fair-005: three queues interleaved', () => {
  assert.deepEqual(fairScheduler([['a'], ['b'], ['c']], 1), ['a', 'b', 'c']);
});

// ===== reservationPlanner: doesn't track remaining capacity =====
// Checks each request against totalCapacity instead of decrementing
// remaining, allowing total granted to exceed capacity.

test('concurrency-reserve-006: all requests fit', () => {
  const requests = [
    { id: 'r1', units: 30, priority: 5 },
    { id: 'r2', units: 40, priority: 3 },
    { id: 'r3', units: 20, priority: 8 }
  ];
  const plan = reservationPlanner(requests, 100);
  const total = plan.reduce((s, p) => s + p.granted, 0);
  assert.equal(total, 90);
});

test('concurrency-reserve-007: high priority gets capacity first', () => {
  const requests = [
    { id: 'low', units: 80, priority: 1 },
    { id: 'high', units: 80, priority: 10 }
  ];
  const plan = reservationPlanner(requests, 100);
  const high = plan.find((p) => p.id === 'high');
  const low = plan.find((p) => p.id === 'low');
  assert.equal(high.granted, 80);
  assert.equal(low.granted, 20, 'low should get remaining 20');
});

test('concurrency-reserve-008: total never exceeds capacity', () => {
  const requests = [
    { id: 'r1', units: 50, priority: 5 },
    { id: 'r2', units: 50, priority: 5 },
    { id: 'r3', units: 50, priority: 5 }
  ];
  const plan = reservationPlanner(requests, 100);
  const total = plan.reduce((s, p) => s + p.granted, 0);
  assert.ok(total <= 100, `total ${total} exceeds capacity 100`);
});

test('concurrency-reserve-009: zero capacity means all get zero', () => {
  const plan = reservationPlanner([{ id: 'r1', units: 50, priority: 10 }], 0);
  assert.equal(plan[0].granted, 0);
});

test('concurrency-reserve-010: partial allocation for last request', () => {
  const requests = [
    { id: 'r1', units: 70, priority: 10 },
    { id: 'r2', units: 50, priority: 5 }
  ];
  const plan = reservationPlanner(requests, 100);
  const r1 = plan.find((p) => p.id === 'r1');
  const r2 = plan.find((p) => p.id === 'r2');
  assert.equal(r1.granted, 70);
  assert.equal(r2.granted, 30, 'should get remaining 30, not requested 50');
});

test('concurrency-reserve-011: single request capped at capacity', () => {
  const plan = reservationPlanner([{ id: 'r1', units: 200, priority: 1 }], 100);
  assert.equal(plan[0].granted, 100);
});

test('concurrency-reserve-012: five requests competing for limited capacity', () => {
  const requests = Array.from({ length: 5 }, (_, i) => ({
    id: `r${i}`, units: 40, priority: 5 - i
  }));
  const plan = reservationPlanner(requests, 100);
  const total = plan.reduce((s, p) => s + p.granted, 0);
  assert.equal(total, 100, 'should allocate exactly 100');
  const r0 = plan.find((p) => p.id === 'r0');
  assert.equal(r0.granted, 40, 'highest priority gets full allocation');
});

// ===== replayWithCheckpoint: >= fence includes checkpoint event =====
// Should replay events with version > checkpoint.version (exclusive).
// Bug: uses >= which re-includes the checkpoint event, causing
// double-application of the checkpoint's state change.

test('concurrency-replay-013: replays events AFTER checkpoint only', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1' },
    { id: 'e2', version: 2, idempotencyKey: 'k2' },
    { id: 'e3', version: 3, idempotencyKey: 'k3' },
    { id: 'e4', version: 4, idempotencyKey: 'k4' }
  ];
  const result = replayWithCheckpoint(events, { version: 2 });
  assert.equal(result.length, 2, 'should replay versions 3 and 4 only');
  assert.equal(result[0].version, 3);
  assert.equal(result[1].version, 4);
});

test('concurrency-replay-014: checkpoint version itself NOT replayed', () => {
  const events = [
    { id: 'e1', version: 5, idempotencyKey: 'k1' },
    { id: 'e2', version: 10, idempotencyKey: 'k2' }
  ];
  const result = replayWithCheckpoint(events, { version: 5 });
  assert.equal(result.length, 1, 'version 5 is the checkpoint, only 10 should replay');
  assert.equal(result[0].version, 10);
});

test('concurrency-replay-015: checkpoint at 0 replays all', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1' },
    { id: 'e2', version: 2, idempotencyKey: 'k2' }
  ];
  assert.equal(replayWithCheckpoint(events, { version: 0 }).length, 2);
});

test('concurrency-replay-016: checkpoint at latest replays nothing', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1' },
    { id: 'e2', version: 2, idempotencyKey: 'k2' }
  ];
  assert.equal(replayWithCheckpoint(events, { version: 2 }).length, 0);
});

test('concurrency-replay-017: deduplicates by idempotency key', () => {
  const events = [
    { id: 'e1', version: 3, idempotencyKey: 'k1' },
    { id: 'e2', version: 4, idempotencyKey: 'k1' },
    { id: 'e3', version: 5, idempotencyKey: 'k2' }
  ];
  const result = replayWithCheckpoint(events, { version: 2 });
  assert.equal(result.length, 2);
});

test('concurrency-replay-018: sorted ascending by version', () => {
  const events = [
    { id: 'e3', version: 30, idempotencyKey: 'k3' },
    { id: 'e1', version: 10, idempotencyKey: 'k1' },
    { id: 'e2', version: 20, idempotencyKey: 'k2' }
  ];
  const result = replayWithCheckpoint(events, { version: 5 });
  assert.equal(result[0].version, 10);
  assert.equal(result[2].version, 30);
});

// ===== multiTenantAuth: doesn't scope grants to tenant =====

test('concurrency-tenant-019: authorized with matching tenant', () => {
  const grants = [{ tenantId: 'acme', userId: 'u1', actions: ['read', 'write'] }];
  assert.equal(multiTenantAuth('acme', 'u1', 'read', grants).authorized, true);
});

test('concurrency-tenant-020: denied for wrong action', () => {
  const grants = [{ tenantId: 'acme', userId: 'u1', actions: ['read'] }];
  assert.equal(multiTenantAuth('acme', 'u1', 'delete', grants).authorized, false);
});

test('concurrency-tenant-021: cross-tenant grant must NOT authorize', () => {
  const grants = [
    { tenantId: 'other-corp', userId: 'u1', actions: ['read', 'write', 'delete'] }
  ];
  assert.equal(
    multiTenantAuth('acme', 'u1', 'read', grants).authorized,
    false,
    'grant for other-corp must not authorize for acme'
  );
});

test('concurrency-tenant-022: user grants in multiple tenants scoped correctly', () => {
  const grants = [
    { tenantId: 'alpha', userId: 'u1', actions: ['admin'] },
    { tenantId: 'beta', userId: 'u1', actions: ['read'] }
  ];
  assert.equal(
    multiTenantAuth('beta', 'u1', 'admin', grants).authorized,
    false,
    'admin grant is for alpha, not beta'
  );
});

test('concurrency-tenant-023: no grants means denied', () => {
  assert.equal(multiTenantAuth('acme', 'u1', 'read', []).authorized, false);
});

test('concurrency-tenant-024: different user denied', () => {
  const grants = [{ tenantId: 'acme', userId: 'u1', actions: ['read'] }];
  assert.equal(multiTenantAuth('acme', 'u2', 'read', grants).authorized, false);
});

// ===== reconcileAccounts: concurrent adjustment interactions =====

test('concurrency-reconcile-025: sequential adjustments compound', () => {
  const entries = [{ account: 'ops', delta: 1000 }];
  const adjustments = [
    { account: 'ops', factor: 1.1 },
    { account: 'ops', factor: 1.05 }
  ];
  const result = reconcileAccounts(entries, adjustments);
  const expected = Math.round(1000 * 1.1 * 1.05 * 100) / 100;
  assert.equal(result.ops.net, expected);
});

test('concurrency-reconcile-026: adjustment to missing account ignored', () => {
  const entries = [{ account: 'a', delta: 100 }];
  const adjustments = [{ account: 'missing', factor: 2 }];
  const result = reconcileAccounts(entries, adjustments);
  assert.equal(result.a.net, 100);
});

// ===== Matrix expansion =====

for (let i = 0; i < 12; i++) {
  test(`concurrency-matrix-${String(27 + i).padStart(3, '0')}: capacity tracking ${i}`, () => {
    const numReq = 3 + i;
    const requests = Array.from({ length: numReq }, (_, j) => ({
      id: `r${j}`, units: 20, priority: numReq - j
    }));
    const plan = reservationPlanner(requests, 60);
    const total = plan.reduce((s, p) => s + p.granted, 0);
    assert.ok(total <= 60, `total ${total} should not exceed 60`);
    assert.equal(total, Math.min(numReq * 20, 60));
  });
}

for (let i = 0; i < 11; i++) {
  test(`concurrency-matrix-${String(39 + i).padStart(3, '0')}: tenant isolation ${i}`, () => {
    const tA = `tenant-${i}-a`;
    const tB = `tenant-${i}-b`;
    const grants = [
      { tenantId: tA, userId: 'user1', actions: ['read', 'write'] },
      { tenantId: tB, userId: 'user1', actions: ['read'] }
    ];
    assert.equal(multiTenantAuth(tA, 'user1', 'write', grants).authorized, true);
    assert.equal(multiTenantAuth(tB, 'user1', 'write', grants).authorized, false);
  });
}
