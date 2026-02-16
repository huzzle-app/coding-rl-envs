const test = require('node:test');
const assert = require('node:assert/strict');
const { retryBackoffMs, circuitOpen, replayState } = require('../../src/core/resilience');

test('retryBackoffMs grows exponentially', () => {
  assert.equal(retryBackoffMs(1, 50), 50);
  assert.equal(retryBackoffMs(3, 50), 200);
});

test('circuitOpen gates after burst threshold', () => {
  assert.equal(circuitOpen(4), false);
  assert.equal(circuitOpen(5), true);
});

test('ordered and shuffled replay converges to correct values', () => {
  const ordered = [
    { version: 11, idempotencyKey: 'k1', inflightDelta: 3, backlogDelta: 2 },
    { version: 12, idempotencyKey: 'k2', inflightDelta: -1, backlogDelta: 1 },
    { version: 13, idempotencyKey: 'k3', inflightDelta: 2, backlogDelta: -1 }
  ];
  const shuffled = [ordered[2], ordered[0], ordered[1]];
  const result = replayState(20, 14, 10, ordered);
  assert.deepEqual(result, replayState(20, 14, 10, shuffled));
  // Verify actual values: inflight should ADD deltas (3 + -1 + 2 = 4), so 20 + 4 = 24
  assert.equal(result.inflight, 24, 'inflight should accumulate deltas: 20 + 3 + (-1) + 2 = 24');
  assert.equal(result.backlog, 16, 'backlog: 14 + 2 + 1 + (-1) = 16');
  assert.equal(result.applied, 3);
});

test('stale duplicate does not shadow fresh event', () => {
  const events = [
    { version: 9, idempotencyKey: 'dup', inflightDelta: 99, backlogDelta: 99 },
    { version: 11, idempotencyKey: 'dup', inflightDelta: 4, backlogDelta: 3 }
  ];
  const snapshot = replayState(15, 7, 10, events);
  assert.equal(snapshot.applied, 1);
  assert.equal(snapshot.inflight, 19);
  assert.equal(snapshot.backlog, 10);
});
