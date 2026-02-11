const test = require('node:test');
const assert = require('node:assert/strict');
const { DispatchTicket } = require('../../src/models/dispatch-ticket');

test('dispatch model computes weighted urgency', () => {
  const t = new DispatchTicket('D-1', 3, 30);
  assert.equal(t.urgencyScore(), 120);
});
