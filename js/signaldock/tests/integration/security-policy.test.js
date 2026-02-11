const test = require('node:test');
const assert = require('node:assert/strict');
const { nextPolicy } = require('../../src/core/policy');
const { shouldShed } = require('../../src/core/queue');

test('policy and queue pressure align', () => {
  assert.equal(nextPolicy('normal', 2), 'watch');
  assert.equal(shouldShed(15, 10, false), true);
});
