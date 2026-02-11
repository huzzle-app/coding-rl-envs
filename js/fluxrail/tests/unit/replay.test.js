const test = require('node:test');
const assert = require('node:assert/strict');

const { replayBudget, dedupeEvents, orderedReplay } = require('../../src/core/replay');

test('replayBudget is bounded and non-zero', () => {
  assert.equal(replayBudget(0, 10), 0);
  assert.equal(replayBudget(100, 5), 63);
});

test('dedupeEvents and orderedReplay', () => {
  const events = [
    { version: 2, idempotencyKey: 'b' },
    { version: 1, idempotencyKey: 'a' },
    { version: 1, idempotencyKey: 'a' }
  ];
  assert.equal(dedupeEvents(events).length, 2);
  const ordered = orderedReplay(events);
  assert.deepEqual(ordered.map((event) => event.idempotencyKey), ['a', 'b']);
});
