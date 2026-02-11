const test = require('node:test');
const assert = require('node:assert/strict');
const { canTransition } = require('../../src/core/workflow');

test('workflow transitions remain valid', () => {
  assert.equal(canTransition('queued', 'allocated'), true);
  assert.equal(canTransition('queued', 'arrived'), false);
});
