const test = require('node:test');
const assert = require('node:assert/strict');
const { replayState } = require('../../src/core/resilience');

test('replay idempotency collision applies once', () => {
  const events = [
    { version: 21, idempotencyKey: 'dup', inflightDelta: 3, backlogDelta: 1 },
    { version: 22, idempotencyKey: 'dup', inflightDelta: 40, backlogDelta: 20 },
    { version: 23, idempotencyKey: 'ok', inflightDelta: -2, backlogDelta: 0 }
  ];
  const snapshot = replayState(40, 20, 20, events);
  assert.equal(snapshot.applied, 2);
});

test('replay accepts equal version event', () => {
  const snapshot = replayState(10, 5, 20, [{ version: 20, idempotencyKey: 'eq', inflightDelta: 1, backlogDelta: 1 }]);
  assert.equal(snapshot.applied, 1);
  assert.equal(snapshot.version, 20);
});
