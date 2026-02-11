const test = require('node:test');
const assert = require('node:assert/strict');
const { nextPolicy } = require('../../src/core/policy');

test('nextPolicy escalates on sustained failures', () => {
  assert.equal(nextPolicy('watch', 3), 'restricted');
});
