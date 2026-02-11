const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const { REQUIRED_FIELDS, EVENT_TYPES } = require('../../shared/contracts/contracts');

const SERVICES = [
  'gateway', 'auth', 'intake', 'routing', 'capacity', 'dispatch',
  'policy', 'resilience', 'audit', 'analytics', 'notifications', 'reporting'
];

test('service descriptors expose required keys', () => {
  for (const service of SERVICES) {
    const file = path.join(__dirname, '..', '..', 'services', service, 'service.json');
    const doc = JSON.parse(fs.readFileSync(file, 'utf8'));
    assert.equal(doc.service_name, service);
    assert.equal(doc.api_version, 'v1');
  }
});

test('shared contracts include trace and dispatch event', () => {
  assert.equal(REQUIRED_FIELDS.includes('trace_id'), true);
  assert.equal(EVENT_TYPES.includes('dispatch.accepted'), true);
});
