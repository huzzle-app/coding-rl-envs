const test = require('node:test');
const assert = require('node:assert/strict');
const { selectHub, deterministicPartition, churnRate } = require('../../src/core/routing');

test('selectHub chooses least congested with lexical tie-break', () => {
  assert.equal(selectHub({ west: 0.22, alpha: 0.17, east: 0.17 }), 'alpha');
});

test('deterministicPartition is stable', () => {
  const a = deterministicPartition('tenant-a', 11);
  const b = deterministicPartition('tenant-a', 11);
  assert.equal(a, b);
});

test('churnRate captures route assignment changes', () => {
  const rate = churnRate({ j1: 'r1', j2: 'r2' }, { j1: 'r1', j2: 'r5', j3: 'r9' });
  assert.equal(rate, 2 / 3);
});
