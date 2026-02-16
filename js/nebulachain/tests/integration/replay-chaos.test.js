const test = require('node:test');
const assert = require('node:assert/strict');
const { replay } = require('../../src/core/resilience');

test('ordered and shuffled replay converge', () => {
  const a = replay([{ id: 'k', sequence: 1 }, { id: 'k', sequence: 2 }]);
  const b = replay([{ id: 'k', sequence: 2 }, { id: 'k', sequence: 1 }]);
  assert.deepEqual(a, b);
  // Convergence must be to the latest state (highest sequence) for disaster recovery
  assert.equal(a[0].sequence, 2, 'replay must converge to latest sequence for disaster recovery');
});
