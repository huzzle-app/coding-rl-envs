const test = require('node:test');
const assert = require('node:assert/strict');
const { replay } = require('../../src/core/resilience');

test('replay keeps latest sequence only', () => {
  const events = replay([
    { id: 'x', sequence: 1 },
    { id: 'x', sequence: 3 },
    { id: 'y', sequence: 2 }
  ]);
  assert.deepEqual(events.map((e) => `${e.id}:${e.sequence}`), ['y:2', 'x:3']);
});
