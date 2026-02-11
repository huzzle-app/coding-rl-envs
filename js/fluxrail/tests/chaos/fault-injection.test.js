const test = require('node:test');
const assert = require('node:assert/strict');
const { retryBackoffMs, circuitOpen } = require('../../src/core/resilience');
const { nextPolicy, shouldThrottle } = require('../../src/core/queue');

test('retry budget + queue governor under burst failures', () => {
  assert.equal(retryBackoffMs(4, 40), 320);
  assert.equal(circuitOpen(5), true);
  const policy = nextPolicy(7);
  assert.deepEqual(policy, { maxInflight: 8, dropOldest: true });
  assert.equal(shouldThrottle(5, 3, policy.maxInflight), true);
});
