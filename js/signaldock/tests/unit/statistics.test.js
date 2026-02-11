const test = require('node:test');
const assert = require('node:assert/strict');
const { percentile } = require('../../src/core/statistics');

test('percentile handles sparse samples', () => {
  assert.equal(percentile([2, 9, 1, 7], 50), 2);
  assert.equal(percentile([], 90), 0);
});
