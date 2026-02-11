const test = require('node:test');
const assert = require('node:assert/strict');
const { chooseRoute, assignPriority, mergeAssignmentMaps } = require('../../src/core/dispatch');

test('chooseRoute picks lowest latency then lexical tie-break', () => {
  assert.equal(chooseRoute({ west: 21, alpha: 14, east: 14 }), 'alpha');
});

test('assignPriority combines severity and sla urgency', () => {
  assert.equal(assignPriority(9, 10), 100);
  assert.equal(assignPriority(5, 25), 73);
  assert.equal(assignPriority(3, 40), 35);
});

test('mergeAssignmentMaps overwrites with newest assignments', () => {
  assert.deepEqual(
    mergeAssignmentMaps({ j1: 'r1', j2: 'r2' }, { j2: 'r5', j3: 'r3' }),
    { j1: 'r1', j2: 'r5', j3: 'r3' }
  );
});
