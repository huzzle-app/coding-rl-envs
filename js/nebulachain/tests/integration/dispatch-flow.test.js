const test = require('node:test');
const assert = require('node:assert/strict');
const { planWindow } = require('../../src/core/scheduling');
const { chooseRoute } = require('../../src/core/routing');
const { canTransition } = require('../../src/core/workflow');

test('dispatch + routing + workflow flow', () => {
  const selected = planWindow([{ id: 'A', urgency: 7, eta: '10:00' }], 1);
  const route = chooseRoute([{ channel: 'north', latency: 3 }], []);
  assert.equal(selected.length, 1);
  assert.equal(route.channel, 'north');
  assert.equal(canTransition('queued', 'allocated'), true);
});
