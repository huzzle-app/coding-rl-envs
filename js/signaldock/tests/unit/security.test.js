const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { verifySignature } = require('../../src/core/security');

test('verifySignature validates digest with constant-time compare', () => {
  const payload = 'manifest:v1';
  const digest = crypto.createHash('sha256').update(payload).digest('hex');
  assert.equal(verifySignature(payload, digest, digest), true);
  assert.equal(verifySignature(payload, digest.slice(0, -1), digest), false);
});
