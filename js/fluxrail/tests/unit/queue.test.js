const test = require('node:test');
const assert = require('node:assert/strict');
const { nextPolicy, shouldThrottle, penaltyScore } = require('../../src/core/queue');

test('nextPolicy escalates when failure burst rises', () => {
  assert.deepEqual(nextPolicy(1), { maxInflight: 32, dropOldest: false });
  assert.deepEqual(nextPolicy(3), { maxInflight: 16, dropOldest: true });
  assert.deepEqual(nextPolicy(6), { maxInflight: 8, dropOldest: true });
});

test('shouldThrottle at policy limits', () => {
  const p = nextPolicy(3);
  assert.equal(shouldThrottle(10, 6, p.maxInflight), true);
  assert.equal(shouldThrottle(10, 5, p.maxInflight), false);
});

test('penaltyScore scales with retries and latency', () => {
  assert.equal(penaltyScore(1, 200), 2);
  assert.equal(penaltyScore(4, 750), 11);
});
