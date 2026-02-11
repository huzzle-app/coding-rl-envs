const test = require('node:test');
const assert = require('node:assert/strict');

const { topoSort } = require('../../src/core/dependency');

test('topoSort orders dependencies', () => {
  const order = topoSort(['a', 'b', 'c'], [['a', 'b'], ['b', 'c']]);
  assert.deepEqual(order, ['a', 'b', 'c']);
});

test('topoSort detects cycle', () => {
  assert.throws(() => topoSort(['a', 'b'], [['a', 'b'], ['b', 'a']]));
});
