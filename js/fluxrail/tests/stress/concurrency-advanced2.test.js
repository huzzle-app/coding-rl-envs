const { test } = require('node:test');
const assert = require('node:assert/strict');

const { PriorityQueue, AdaptiveQueue, weightedRoundRobin } = require('../../src/core/queue');
const { CircuitBreaker, bulkheadPartition, degradationLevel } = require('../../src/core/resilience');
const { replaySegment, eventCausality, compactEvents, orderedReplay } = require('../../src/core/replay');
const { crossAccountTransfer, runningBalance, buildLedgerEntries } = require('../../src/core/ledger');
const { exponentialMovingAverage, movingAverage } = require('../../src/core/statistics');
const { rateLimit, ipWhitelist } = require('../../src/core/security');
const { routeLatencyEstimate } = require('../../src/core/routing');
const { tokenRotation } = require('../../src/core/authorization');

// ===== PriorityQueue: concurrent enqueue/dequeue ordering =====
// Bug: sorts ascending (min-heap), should sort descending (max-heap)

test('concurrency2-adv-001: priority queue handles interleaved operations', () => {
  const pq = new PriorityQueue();
  pq.enqueue('critical', 100);
  pq.enqueue('normal', 10);
  assert.equal(pq.dequeue(), 'critical');
  pq.enqueue('urgent', 80);
  pq.enqueue('low', 5);
  assert.equal(pq.dequeue(), 'urgent');
  assert.equal(pq.dequeue(), 'normal');
  assert.equal(pq.dequeue(), 'low');
});

test('concurrency2-adv-002: priority queue maintains heap property', () => {
  const pq = new PriorityQueue();
  const values = [50, 30, 70, 10, 90, 60, 40, 80, 20, 100];
  values.forEach((v, i) => pq.enqueue(`item-${v}`, v));
  let prev = Infinity;
  while (pq.size() > 0) {
    const item = pq.dequeue();
    const p = parseInt(item.split('-')[1]);
    assert.ok(p <= prev, `dequeued ${p} should be <= previous ${prev}`);
    prev = p;
  }
});

test('concurrency2-adv-003: drain respects priority order', () => {
  const pq = new PriorityQueue();
  [1, 5, 3, 8, 2, 9, 4, 7, 6, 10].forEach((p, i) => pq.enqueue(`i${p}`, p));
  const top3 = pq.drain(3);
  assert.equal(top3[0], 'i10');
  assert.equal(top3[1], 'i9');
  assert.equal(top3[2], 'i8');
});

// ===== orderedReplay: version ordering for causal consistency =====
// Bug: sorts descending (newest first), breaking causality

test('concurrency2-adv-004: ordered replay maintains causal order', () => {
  const events = [
    { id: 'e3', version: 3, idempotencyKey: 'k3' },
    { id: 'e1', version: 1, idempotencyKey: 'k1' },
    { id: 'e2', version: 2, idempotencyKey: 'k2' }
  ];
  const result = orderedReplay(events);
  assert.equal(result[0].version, 1, 'earliest version must come first');
  assert.equal(result[1].version, 2);
  assert.equal(result[2].version, 3);
});

test('concurrency2-adv-005: ordered replay deduplicates before ordering', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1' },
    { id: 'e2', version: 2, idempotencyKey: 'k1' },
    { id: 'e3', version: 3, idempotencyKey: 'k2' }
  ];
  const result = orderedReplay(events);
  assert.equal(result.length, 2);
  assert.equal(result[0].version, 1);
  assert.equal(result[1].version, 3);
});

test('concurrency2-adv-006: ordered replay large batch preserves order', () => {
  const events = Array.from({ length: 50 }, (_, i) => ({
    id: `e${i}`, version: 50 - i, idempotencyKey: `k${i}`
  }));
  const result = orderedReplay(events);
  for (let i = 1; i < result.length; i++) {
    assert.ok(result[i].version >= result[i-1].version,
      `version ${result[i].version} should be >= ${result[i-1].version}`);
  }
});

// ===== eventCausality: detecting causal violations =====

test('concurrency2-adv-007: valid causality chain', () => {
  const events = [
    { id: 'e1', version: 1 },
    { id: 'e2', version: 2, causedBy: 1 },
    { id: 'e3', version: 3, causedBy: 2 }
  ];
  assert.equal(eventCausality(events).valid, true);
});

test('concurrency2-adv-008: invalid causality (future cause)', () => {
  const events = [
    { id: 'e1', version: 1, causedBy: 5 }
  ];
  assert.equal(eventCausality(events).valid, false);
});

test('concurrency2-adv-009: no causality links is valid', () => {
  const events = [
    { id: 'e1', version: 1 },
    { id: 'e2', version: 2 }
  ];
  assert.equal(eventCausality(events).valid, true);
});

// ===== compactEvents: last-write-wins semantics =====
// Bug: keeps first occurrence instead of last

test('concurrency2-adv-010: compact keeps latest version of duplicate key', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'order-1', timestamp: 100, status: 'pending' },
    { id: 'e2', idempotencyKey: 'order-1', timestamp: 200, status: 'processing' },
    { id: 'e3', idempotencyKey: 'order-1', timestamp: 300, status: 'completed' }
  ];
  const result = compactEvents(events, 1000);
  assert.equal(result.length, 1);
  assert.equal(result[0].status, 'completed', 'last-write-wins: should keep completed');
});

test('concurrency2-adv-011: compact with mixed keys', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'k1', timestamp: 10, v: 'old' },
    { id: 'e2', idempotencyKey: 'k2', timestamp: 20, v: 'only' },
    { id: 'e3', idempotencyKey: 'k1', timestamp: 30, v: 'new' }
  ];
  const result = compactEvents(events, 100);
  assert.equal(result.length, 2);
  const k1 = result.find(e => e.idempotencyKey === 'k1');
  assert.equal(k1.v, 'new');
});

// ===== crossAccountTransfer: concurrent transfers =====

test('concurrency2-adv-012: sequential transfers accumulate correctly', () => {
  let entries = [];
  entries = crossAccountTransfer(entries, 'A', 'B', 100);
  entries = crossAccountTransfer(entries, 'A', 'B', 50);
  entries = crossAccountTransfer(entries, 'B', 'A', 30);
  const snapshots = runningBalance(entries);
  const aEntries = snapshots.filter(s => s.account === 'A');
  const bEntries = snapshots.filter(s => s.account === 'B');
  const finalA = aEntries[aEntries.length - 1].balance;
  const finalB = bEntries[bEntries.length - 1].balance;
  assert.equal(finalA, -120, 'A: -100 - 50 + 30 = -120');
  assert.equal(finalB, 120, 'B: 100 + 50 - 30 = 120');
});

test('concurrency2-adv-013: transfer preserves total system balance', () => {
  let entries = [
    { id: 'init-a', account: 'A', delta: 1000, seq: 1 },
    { id: 'init-b', account: 'B', delta: 500, seq: 2 }
  ];
  for (let i = 0; i < 5; i++) {
    entries = crossAccountTransfer(entries, 'A', 'B', 50);
  }
  const snapshots = runningBalance(entries);
  const accounts = {};
  for (const s of snapshots) {
    accounts[s.account] = s.balance;
  }
  assert.equal(accounts.A + accounts.B, 1500, 'total must be preserved');
});

// ===== AdaptiveQueue: load oscillation stability =====

test('concurrency2-adv-014: queue doesn\'t flap on threshold boundary', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    shedThreshold: 0.95,
    recoveryThreshold: 0.6
  });
  const loads = [0.81, 0.79, 0.81, 0.79, 0.81];
  const states = loads.map(l => {
    q.updateLoad(l);
    return q.getState();
  });
  const transitions = states.filter((s, i) => i > 0 && s !== states[i-1]).length;
  assert.ok(transitions <= 1,
    `should not oscillate: ${states.join(' → ')}, transitions: ${transitions}`);
});

test('concurrency2-adv-015: queue steady state under constant load', () => {
  const q = new AdaptiveQueue({ throttleThreshold: 0.8, recoveryThreshold: 0.6 });
  q.updateLoad(0.5);
  for (let i = 0; i < 20; i++) {
    q.updateLoad(0.5);
    assert.equal(q.getState(), 'normal');
  }
});

// ===== movingAverage: window boundary correctness =====
// Bug: start = idx - w + 2 (should be idx - w + 1)

test('concurrency2-adv-016: moving average window 3', () => {
  const values = [10, 20, 30, 40, 50];
  const result = movingAverage(values, 3);
  assert.equal(result[2], 20, 'avg(10,20,30) = 20');
  assert.equal(result[3], 30, 'avg(20,30,40) = 30');
  assert.equal(result[4], 40, 'avg(30,40,50) = 40');
});

test('concurrency2-adv-017: moving average window 1 returns values', () => {
  const values = [5, 10, 15];
  const result = movingAverage(values, 1);
  assert.deepEqual(result, [5, 10, 15]);
});

test('concurrency2-adv-018: moving average window equals length', () => {
  const values = [10, 20, 30];
  const result = movingAverage(values, 3);
  assert.equal(result[2], 20, 'full window average of [10,20,30] = 20');
});

// ===== exponentialMovingAverage: correctness =====

test('concurrency2-adv-019: EMA alpha=1 tracks values exactly', () => {
  const result = exponentialMovingAverage([10, 20, 30], 1);
  assert.deepEqual(result, [10, 20, 30]);
});

test('concurrency2-adv-020: EMA alpha=0 stays at initial', () => {
  const result = exponentialMovingAverage([10, 20, 30], 0);
  assert.deepEqual(result, [10, 10, 10]);
});

test('concurrency2-adv-021: EMA alpha=0.5 smoothing', () => {
  const result = exponentialMovingAverage([100, 0, 100, 0], 0.5);
  assert.equal(result[0], 100);
  assert.equal(result[1], 50);
  assert.equal(result[2], 75);
  assert.equal(result[3], 37.5);
});

// ===== ipWhitelist: pattern matching =====

test('concurrency2-adv-022: exact IP match', () => {
  assert.equal(ipWhitelist('192.168.1.1', ['192.168.1.1']), true);
});

test('concurrency2-adv-023: wildcard range match', () => {
  assert.equal(ipWhitelist('10.0.1.5', ['10.0.*']), true);
});

test('concurrency2-adv-024: no match returns false', () => {
  assert.equal(ipWhitelist('172.16.0.1', ['10.0.*', '192.168.*']), false);
});

test('concurrency2-adv-025: empty ranges returns false', () => {
  assert.equal(ipWhitelist('10.0.0.1', []), false);
});

// ===== degradationLevel: metric thresholds =====

test('concurrency2-adv-026: healthy system', () => {
  assert.equal(degradationLevel({ errorRate: 0, p99LatencyMs: 100, cpuSaturation: 0.3 }), 'healthy');
});

test('concurrency2-adv-027: warning on moderate latency', () => {
  assert.equal(degradationLevel({ errorRate: 0, p99LatencyMs: 3000, cpuSaturation: 0.3 }), 'warning');
});

test('concurrency2-adv-028: degraded on high errors', () => {
  assert.equal(degradationLevel({ errorRate: 0.15, p99LatencyMs: 100, cpuSaturation: 0.3 }), 'degraded');
});

test('concurrency2-adv-029: critical on saturation', () => {
  assert.equal(degradationLevel({ errorRate: 0, p99LatencyMs: 100, cpuSaturation: 0.96 }), 'critical');
});

test('concurrency2-adv-030: critical on extreme latency', () => {
  assert.equal(degradationLevel({ errorRate: 0, p99LatencyMs: 15000, cpuSaturation: 0 }), 'critical');
});

// ===== routeLatencyEstimate =====

test('concurrency2-adv-031: single hop latency', () => {
  assert.equal(routeLatencyEstimate([{ latencyMs: 50, processingMs: 10 }]), 60);
});

test('concurrency2-adv-032: multi-hop latency sums', () => {
  const hops = [
    { latencyMs: 20, processingMs: 5 },
    { latencyMs: 30, processingMs: 10 },
    { latencyMs: 15, processingMs: 5 }
  ];
  assert.equal(routeLatencyEstimate(hops), 85);
});

test('concurrency2-adv-033: empty hops returns 0', () => {
  assert.equal(routeLatencyEstimate([]), 0);
});

// ===== tokenRotation: concurrent token validity =====

test('concurrency2-adv-034: valid token returns immediately', () => {
  const result = tokenRotation({ expiresAt: 10000 }, [], 1000, 5000);
  assert.equal(result.valid, true);
  assert.equal(result.rotated, undefined);
});

test('concurrency2-adv-035: expired token with grace period fallback', () => {
  const current = { expiresAt: 1000 };
  const prev = [{ expiresAt: 2000 }];
  const result = tokenRotation(current, prev, 500, 2300);
  assert.equal(result.valid, true);
  assert.equal(result.rotated, true);
});

test('concurrency2-adv-036: all tokens fully expired', () => {
  const result = tokenRotation({ expiresAt: 100 }, [{ expiresAt: 200 }], 100, 5000);
  assert.equal(result.valid, false);
});

test('concurrency2-adv-037: no token at all', () => {
  assert.equal(tokenRotation(null, [], 0, 1000).valid, false);
});

// ===== replaySegment: boundary and ordering =====

test('concurrency2-adv-038: replay segment sorted ascending', () => {
  const events = [
    { id: 'e3', version: 30, idempotencyKey: 'k3' },
    { id: 'e1', version: 10, idempotencyKey: 'k1' },
    { id: 'e2', version: 20, idempotencyKey: 'k2' }
  ];
  const result = replaySegment(events, 5, 25);
  assert.ok(result.length >= 1);
  for (let i = 1; i < result.length; i++) {
    assert.ok(result[i].version >= result[i-1].version);
  }
});

test('concurrency2-adv-039: replay segment deduplicates', () => {
  const events = [
    { id: 'e1', version: 10, idempotencyKey: 'k1' },
    { id: 'e2', version: 11, idempotencyKey: 'k1' },
    { id: 'e3', version: 12, idempotencyKey: 'k2' }
  ];
  const result = replaySegment(events, 5, 15);
  const keys = result.map(e => e.idempotencyKey);
  assert.equal(new Set(keys).size, keys.length);
});

test('concurrency2-adv-040: replay segment empty range', () => {
  const events = [{ id: 'e1', version: 50, idempotencyKey: 'k1' }];
  assert.equal(replaySegment(events, 1, 10).length, 0);
});

// ===== Matrix expansion =====

for (let i = 0; i < 15; i++) {
  test(`concurrency2-adv-matrix-${String(41 + i).padStart(3, '0')}: priority queue stress ${i}`, () => {
    const pq = new PriorityQueue();
    const n = 10 + i * 5;
    for (let j = 0; j < n; j++) {
      pq.enqueue(`item-${j}`, Math.floor(Math.random() * 1000) + j);
    }
    let prev = Infinity;
    let count = 0;
    while (pq.size() > 0) {
      const item = pq.dequeue();
      count++;
    }
    assert.equal(count, n);
  });
}

for (let i = 0; i < 15; i++) {
  test(`concurrency2-adv-matrix-${String(56 + i).padStart(3, '0')}: causal replay ordering ${i}`, () => {
    const n = 10 + i * 3;
    const events = Array.from({ length: n }, (_, j) => ({
      id: `e${j}`,
      version: n - j,
      idempotencyKey: `k${j}`
    }));
    const result = orderedReplay(events);
    for (let j = 1; j < result.length; j++) {
      assert.ok(result[j].version >= result[j-1].version,
        `version ${result[j].version} should be >= ${result[j-1].version}`);
    }
  });
}

for (let i = 0; i < 10; i++) {
  test(`concurrency2-adv-matrix-${String(71 + i).padStart(3, '0')}: compact last-write-wins ${i}`, () => {
    const numVersions = 3 + i;
    const events = Array.from({ length: numVersions }, (_, j) => ({
      id: `e${j}`,
      idempotencyKey: 'same-key',
      timestamp: j * 100,
      iteration: j
    }));
    const result = compactEvents(events, numVersions * 1000);
    assert.equal(result.length, 1);
    assert.equal(result[0].iteration, numVersions - 1,
      'should keep the last version');
  });
}

for (let i = 0; i < 10; i++) {
  test(`concurrency2-adv-matrix-${String(81 + i).padStart(3, '0')}: transfer chain ${i}`, () => {
    let entries = [
      { id: 'init', account: 'A', delta: 10000, seq: 1 }
    ];
    for (let j = 0; j < i + 1; j++) {
      entries = crossAccountTransfer(entries, 'A', 'B', 100);
    }
    const snapshots = runningBalance(entries);
    const aSnapshots = snapshots.filter(s => s.account === 'A');
    const bSnapshots = snapshots.filter(s => s.account === 'B');
    const finalA = aSnapshots[aSnapshots.length - 1].balance;
    const finalB = bSnapshots[bSnapshots.length - 1].balance;
    assert.equal(finalA + finalB, 10000, 'system balance must be preserved');
    assert.equal(finalA, 10000 - (i + 1) * 100);
  });
}
