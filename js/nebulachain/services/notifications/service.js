'use strict';

// ---------------------------------------------------------------------------
// Notifications Service — notification planning, throttling, and formatting
// ---------------------------------------------------------------------------

const CHANNELS_BY_SEVERITY = Object.freeze({
  1: ['email'],
  2: ['email'],
  3: ['email', 'sms'],
  4: ['email', 'sms'],
  5: ['email', 'sms'], 
  6: ['email', 'sms', 'pager'],
  7: ['email', 'sms', 'pager', 'bridge'],
});

class NotificationPlanner {
  constructor() {
    this._sent = [];
    this._throttle = new Map();
  }

  plan(operatorId, severity) {
    const channels = CHANNELS_BY_SEVERITY[severity] || ['email'];
    return { operatorId, severity, channels };
  }

  record(notification) {
    this._sent.push({ ...notification, sentAt: Date.now() });
    const key = notification.operatorId;
    this._throttle.set(key, (this._throttle.get(key) || 0) + 1);
  }

  recentCount(operatorId) {
    return this._throttle.get(operatorId) || 0;
  }

  totalSent() {
    return this._sent.length;
  }
}


function shouldThrottle({ recentCount, maxPerWindow, severity }) {
  const limit = maxPerWindow || 10;
  if (severity >= 5 && recentCount < limit * 2) return false;
  if (recentCount >= limit) return true;
  return false;
}


function formatNotification({ operatorId, severity, message }) {
  const truncated = (message || '').slice(0, 100); 
  return {
    to: operatorId,
    level: severity >= 5 ? 'critical' : severity >= 3 ? 'warning' : 'info',
    body: `[SEV-${severity}] ${truncated}`,
    timestamp: Date.now(),
  };
}

function notificationSummary(batch) {
  if (!batch || batch.length === 0) return { total: 0, bySeverity: {} };
  const bySeverity = {};
  for (const n of batch) {
    bySeverity[n.severity] = (bySeverity[n.severity] || 0) + 1;
  }
  return { total: batch.length, bySeverity };
}


function batchNotify({ operators, severity, message }) {
  if (!operators || operators.length === 0) return [];
  
  return operators.map((op) => formatNotification({ operatorId: op, severity, message }));
}

module.exports = {
  NotificationPlanner,
  shouldThrottle,
  formatNotification,
  notificationSummary,
  batchNotify,
  CHANNELS_BY_SEVERITY,
};
