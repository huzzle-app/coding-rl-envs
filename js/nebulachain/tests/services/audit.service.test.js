const test = require('node:test');
const assert = require('node:assert/strict');
const audit = require('../../services/audit/service');

test('validateAuditEntry rejects null entry', () => {
  const result = audit.validateAuditEntry(null);
  assert.equal(result.valid, false);
});

test('AuditTrail tracks entries per service', () => {
  const trail = new audit.AuditTrail();
  trail.append(new audit.AuditEntry('e1', 'gateway', 'read', 1000));
  trail.append(new audit.AuditEntry('e2', 'routing', 'write', 2000));
  trail.append(new audit.AuditEntry('e3', 'gateway', 'delete', 3000));
  assert.equal(trail.entriesForService('gateway').length, 2);
});

test('summarizeTrail returns service list', () => {
  const trail = new audit.AuditTrail();
  trail.append(new audit.AuditEntry('e1', 'policy', 'eval', 500));
  const summary = audit.summarizeTrail(trail);
  assert.ok(summary.services.includes('policy'));
});

test('isCompliant checks required services present', () => {
  const trail = new audit.AuditTrail();
  trail.append(new audit.AuditEntry('e1', 'gateway', 'check', 100));
  assert.equal(audit.isCompliant(trail, ['gateway']), true);
  assert.equal(audit.isCompliant(trail, ['gateway', 'routing']), false);
});
