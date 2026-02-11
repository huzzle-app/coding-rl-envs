const test = require('node:test');
const assert = require('node:assert/strict');
const { chooseRoute } = require('../../src/core/routing');

test('chooseRoute ignores blocked channels', () => {
  const route = chooseRoute([
    { channel: 'north', latency: 12 },
    { channel: 'delta', latency: 6 }
  ], ['delta']);
  assert.equal(route.channel, 'north');
});
