const test = require('node:test');
const assert = require('node:assert/strict');
const { transitionAllowed, nextStateFor } = require('../../src/core/workflow');

test('workflow transition graph is enforced', () => {
  assert.equal(transitionAllowed('drafted', 'validated'), true);
  assert.equal(transitionAllowed('drafted', 'dispatched'), false);
  assert.equal(transitionAllowed('capacity_checked', 'dispatched'), true);
});

test('nextStateFor maps events deterministically', () => {
  assert.equal(nextStateFor('validate'), 'validated');
  assert.equal(nextStateFor('publish'), 'reported');
  assert.equal(nextStateFor('unknown'), 'drafted');
});
