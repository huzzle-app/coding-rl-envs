const test = require('node:test');
const assert = require('node:assert/strict');
const notifications = require('../../services/notifications/service');

test('NotificationPlanner plans channels by severity', () => {
  const planner = new notifications.NotificationPlanner();
  const plan = planner.plan('op1', 5);
  assert.ok(plan.channels.includes('pager'));
});

test('shouldThrottle enforces window limit', () => {
  assert.equal(notifications.shouldThrottle({ recentCount: 11, maxPerWindow: 10, severity: 3 }), true);
  assert.equal(notifications.shouldThrottle({ recentCount: 5, maxPerWindow: 10, severity: 3 }), false);
});

test('formatNotification includes severity tag', () => {
  const n = notifications.formatNotification({ operatorId: 'op1', severity: 6, message: 'alert' });
  assert.ok(n.body.includes('[SEV-6]'));
});

test('batchNotify sends to all operators', () => {
  const result = notifications.batchNotify({ operators: ['a', 'b', 'c'], severity: 4, message: 'test' });
  assert.equal(result.length, 3);
});
