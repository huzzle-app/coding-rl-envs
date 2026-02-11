const test = require('node:test');
const assert = require('node:assert/strict');
const { allowed, tokenFresh, fingerprint } = require('../../src/core/security');
const { overrideAllowed } = require('../../src/core/policy');

test('admin override requires fresh token and valid reason', () => {
  assert.equal(tokenFresh(1000, 600, 1500), true);
  assert.equal(overrideAllowed('documented emergency exception', 2, 90), true);
  assert.equal(allowed('admin', 'override'), true);
  assert.equal(fingerprint('Tenant-A', 'Trace-8', 'Policy.Override'), 'tenant-a:trace-8:policy.override');
});

test('operator cannot override', () => {
  assert.equal(allowed('operator', 'override'), false);
});
