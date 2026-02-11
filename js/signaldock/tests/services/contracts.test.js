const test = require('node:test');
const assert = require('node:assert/strict');
const contracts = require('../../shared/contracts/contracts');

test('service contracts expose required descriptors', () => {
  assert.equal(contracts.gateway.id, 'gateway');
  assert.equal(typeof contracts.routing.port, 'number');
});
