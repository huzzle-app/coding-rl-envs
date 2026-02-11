const test = require('node:test');
const assert = require('node:assert/strict');
const { planWindow } = require('../../src/core/scheduling');

test('planWindow enforces berth capacity', () => {
  const result = planWindow([
    { id: 'a', urgency: 1, eta: '09:00' },
    { id: 'b', urgency: 4, eta: '10:00' },
    { id: 'c', urgency: 4, eta: '08:30' }
  ], 2);
  assert.deepEqual(result.map((v) => v.id), ['c', 'b']);
});
