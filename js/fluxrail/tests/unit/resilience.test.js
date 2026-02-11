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

test('ordered and shuffled replay converges', () => {
  const ordered = [
    { version: 11, idempotencyKey: 'k1', inflightDelta: 3, backlogDelta: 2 },
    { version: 12, idempotencyKey: 'k2', inflightDelta: -1, backlogDelta: 1 },
    { version: 13, idempotencyKey: 'k3', inflightDelta: 2, backlogDelta: -1 }
  ];
  const shuffled = [ordered[2], ordered[0], ordered[1]];
  assert.deepEqual(replayState(20, 14, 10, ordered), replayState(20, 14, 10, shuffled));
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
