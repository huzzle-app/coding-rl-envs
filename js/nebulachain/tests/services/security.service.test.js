const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const security = require('../../services/security/service');

test('validateCommandAuth verifies HMAC signature', () => {
  const secret = 'test-secret-key-1234';
  const command = 'deploy:v2';
  const sig = crypto.createHmac('sha256', secret).update(command).digest('hex');
  const result = security.validateCommandAuth({ command, signature: sig, secret, requiredRole: 'admin', userRoles: ['admin'] });
  assert.equal(result.authorized, true);
});

test('checkPathTraversal detects dot-dot attacks', () => {
  assert.equal(security.checkPathTraversal('../../etc/passwd').safe, false);
  assert.equal(security.checkPathTraversal('/safe/path').safe, true);
});

test('rateLimitCheck enforces request limits', () => {
  const result = security.rateLimitCheck({ requestCount: 200, limit: 100, windowS: 60 });
  assert.equal(result.limited, true);
});

test('computeRiskScore factors failed attempts', () => {
  const score = security.computeRiskScore({ failedAttempts: 5, geoAnomaly: true, timeAnomaly: false });
  assert.ok(score > 50);
});
