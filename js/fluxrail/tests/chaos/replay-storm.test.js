const test = require('node:test');
const assert = require('node:assert/strict');

const { orderedReplay, replayBudget } = require('../../src/core/replay');

test('replay storm remains bounded and deterministic', () => {
  const events = [];
  for (let idx = 100; idx >= 1; idx -= 1) {
    events.push({ version: idx, idempotencyKey: `k-${idx}` });
  }
  const ordered = orderedReplay(events);
  assert.equal(ordered[0].version, 1);
  assert.equal(replayBudget(events.length, 12) > 0, true);
});
