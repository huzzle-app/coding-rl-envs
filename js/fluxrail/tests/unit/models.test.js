const test = require('node:test');
const assert = require('node:assert/strict');

const { Incident } = require('../../src/models/incident');
const { DispatchPlan } = require('../../src/models/dispatch-plan');

test('Incident critical flag and audit record', () => {
  const incident = new Incident({ id: 'inc-1', severity: 9, service: 'routing', summary: 'partition', createdAt: '2026-01-01T00:00:00Z' });
  assert.equal(incident.isCritical(), true);
  assert.equal(incident.toAuditRecord().service, 'routing');
});

test('DispatchPlan metrics and validation', () => {
  const plan = new DispatchPlan({
    planId: 'dp-1',
    route: 'r-a',
    assignments: [{ units: 3, priority: 60 }, { units: 5, priority: 85 }],
    createdBy: 'ops'
  });
  assert.equal(plan.totalUnits(), 8);
  assert.equal(plan.highPriorityCount(), 1);
  assert.equal(plan.validate(), true);
});
