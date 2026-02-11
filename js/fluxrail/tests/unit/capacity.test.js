const test = require('node:test');
const assert = require('node:assert/strict');
const { rebalance, shedRequired, dynamicBuffer } = require('../../src/core/capacity');

test('rebalance honors reserve floor', () => {
  assert.equal(rebalance(10, 8, 4), 6);
  assert.equal(rebalance(2, 8, 4), 0);
});

test('shedRequired triggers at hard limit', () => {
  assert.equal(shedRequired(7, 8), false);
  assert.equal(shedRequired(8, 8), true);
});

test('dynamicBuffer is clamped', () => {
  assert.equal(dynamicBuffer(2, 0.06, 0.2), 0.09);
  assert.equal(dynamicBuffer(-5, 0.06, 0.2), 0.06);
  assert.equal(dynamicBuffer(30, 0.06, 0.2), 0.2);
});
