const test = require('node:test');
const assert = require('node:assert/strict');
const { allowed, tokenFresh, fingerprint } = require('../../src/core/security');

test('role matrix allows and denies expected actions', () => {
  assert.equal(allowed('operator', 'read'), true);
  assert.equal(allowed('operator', 'override'), false);
  assert.equal(allowed('admin', 'override'), true);
});

test('token freshness guard', () => {
  assert.equal(tokenFresh(1000, 300, 1300), true);
  assert.equal(tokenFresh(1000, 300, 1301), false);
});

test('fingerprint normalizes inputs', () => {
  assert.equal(fingerprint('Tenant-A', 'Trace-7', 'Dispatch.Accepted'), 'tenant-a:trace-7:dispatch.accepted');
});
