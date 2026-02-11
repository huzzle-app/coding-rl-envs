const test = require('node:test');
const assert = require('node:assert/strict');
const { percentile, boundedRatio, movingAverage } = require('../../src/core/statistics');

test('percentile returns expected rank sample', () => {
  assert.equal(percentile([1, 3, 5, 7, 9], 0.5), 5);
  assert.equal(percentile([1, 3, 5, 7, 9], 1), 9);
});

test('boundedRatio clamps into [0, 1]', () => {
  assert.equal(boundedRatio(3, 0), 0);
  assert.equal(boundedRatio(2, 5), 0.4);
  assert.equal(boundedRatio(8, 5), 1);
});

test('movingAverage computes rolling windows', () => {
  assert.deepEqual(movingAverage([2, 4, 6, 8], 2), [2, 3, 5, 7]);
});
