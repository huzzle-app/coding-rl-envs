const test = require('node:test');
const assert = require('node:assert/strict');

const { signPayload, verifyPayload, requiresStepUp } = require('../../src/core/authorization');

test('payload signing verification', () => {
  const signature = signPayload('deploy', 'secret');
  assert.equal(verifyPayload('deploy', signature, 'secret'), true);
  assert.equal(verifyPayload('deploy', signature, 'wrong'), false);
  assert.equal(verifyPayload('deploy', 'short', 'secret'), false);
});

test('step-up policy', () => {
  assert.equal(requiresStepUp('operator', 2, 1000), false);
  assert.equal(requiresStepUp('operator', 9, 1000), true);
  assert.equal(requiresStepUp('operator', 3, 3_000_000), true);
});
