const test = require('node:test');
const assert = require('node:assert/strict');
const { shouldShed } = require('../../src/core/queue');

test('shouldShed uses hard-limit semantics', () => {
  assert.equal(shouldShed(9, 10, false), false);
  assert.equal(shouldShed(11, 10, false), true);
  assert.equal(shouldShed(8, 10, true), true);
});
