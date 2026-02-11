const test = require('node:test');
const assert = require('node:assert/strict');
const { overrideAllowed, escalationLevel, retentionBucket, evaluatePolicy } = require('../../src/core/policy');

test('overrideAllowed requires reason approvals and ttl guard', () => {
  assert.equal(overrideAllowed('committee-approved release', 2, 90), true);
  assert.equal(overrideAllowed('short', 2, 90), false);
  assert.equal(overrideAllowed('committee-approved release', 1, 90), false);
  assert.equal(overrideAllowed('committee-approved release', 2, 121), false);
});

test('escalationLevel compounds severity impact and regulatory signal', () => {
  assert.equal(escalationLevel(2, 1, false), 1);
  assert.equal(escalationLevel(8, 12, false), 4);
  assert.equal(escalationLevel(9, 12, true), 5);
});

test('retentionBucket partitions by age', () => {
  assert.equal(retentionBucket(10), 'hot');
  assert.equal(retentionBucket(90), 'warm');
  assert.equal(retentionBucket(900), 'cold');
});

test('evaluatePolicy returns score and allow decision', () => {
  const stable = evaluatePolicy({ securityIncidents: 0, backlog: 10, staleMinutes: 1, margin: 0.2 });
  const degraded = evaluatePolicy({ securityIncidents: 3, backlog: 80, staleMinutes: 20, margin: 0.01 });
  assert.equal(stable.allow, true);
  assert.equal(degraded.allow, false);
  assert.equal(stable.score > degraded.score, true);
});
