/**
 * Alert Detection Engine
 */

class AlertDetector {
  constructor(options = {}) {
    this.rules = new Map();
    this.activeAlerts = new Map();
    this.notificationLog = new Map();
    this.baselines = new Map();
    this.silenceWindows = [];
    this.deduplicationWindow = options.deduplicationWindow || 300000;
    this.escalationTimers = new Map();
  }

  addRule(rule) {
    this.rules.set(rule.id, rule);
  }

  evaluate(metricName, value) {
    const results = [];

    for (const [ruleId, rule] of this.rules.entries()) {
      if (rule.metric !== metricName) continue;

      let triggered = false;

      switch (rule.operator) {
        case 'gt':
          triggered = value > rule.threshold;
          break;
        case 'gte':
          triggered = value >= rule.threshold;
          break;
        case 'lt':
          triggered = value < rule.threshold;
          break;
        case 'lte':
          triggered = value <= rule.threshold;
          break;
        case 'eq':
          triggered = value === rule.threshold;
          break;
      }

      if (triggered) {
        const alert = this._createAlert(rule, value);
        if (alert) results.push(alert);
      } else {
        this._checkRecovery(ruleId, value);
      }
    }

    return results;
  }

  _createAlert(rule, value) {
    const lastNotification = this.notificationLog.get(rule.id);
    if (lastNotification && Date.now() - lastNotification < this.deduplicationWindow) {
      return null;
    }

    if (this._isSilenced(rule)) {
      return null;
    }

    const alert = {
      id: `alert-${Date.now()}-${rule.id}`,
      ruleId: rule.id,
      metric: rule.metric,
      value,
      threshold: rule.threshold,
      severity: rule.severity || 'warning',
      timestamp: Date.now(),
      status: 'firing',
    };

    this.activeAlerts.set(alert.id, alert);
    this.notificationLog.set(rule.id, Date.now());

    this._startEscalation(alert);

    return alert;
  }

  _startEscalation(alert) {
    const rule = this.rules.get(alert.ruleId);
    if (!rule || !rule.escalation) return;

    const timer = setTimeout(() => {
      if (this.activeAlerts.has(alert.id)) {
        alert.severity = rule.escalation.targetSeverity || 'critical';
        alert.escalated = true;
        alert.escalatedAt = Date.now();
      }
    }, rule.escalation.after || 300000);

    this.escalationTimers.set(alert.id, timer);
  }

  _checkRecovery(ruleId, value) {
    const activeAlertIds = [...this.activeAlerts.entries()]
      .filter(([, alert]) => alert.ruleId === ruleId)
      .map(([id]) => id);

    for (const alertId of activeAlertIds) {
      const alert = this.activeAlerts.get(alertId);
      const rule = this.rules.get(ruleId);

      alert.status = 'resolved';
      alert.resolvedAt = Date.now();

      const timer = this.escalationTimers.get(alertId);
      if (timer) clearTimeout(timer);
      this.escalationTimers.delete(alertId);
    }
  }

  detectAnomaly(metricName, value) {
    const baseline = this.baselines.get(metricName);

    if (!baseline) {
      this.baselines.set(metricName, {
        mean: value,
        stddev: 0,
        sampleCount: 1,
        lastUpdated: Date.now(),
      });
      return { isAnomaly: false };
    }

    const zScore = baseline.stddev > 0
      ? Math.abs(value - baseline.mean) / baseline.stddev
      : 0;

    return {
      isAnomaly: zScore > 3,
      zScore,
      baseline: { mean: baseline.mean, stddev: baseline.stddev },
    };
  }

  _isSilenced(rule) {
    const now = new Date();

    for (const window of this.silenceWindows) {
      if (window.ruleId && window.ruleId !== rule.id) continue;

      const start = new Date(window.start);
      const end = new Date(window.end);

      if (now >= start && now <= end) {
        return true;
      }
    }

    return false;
  }

  addSilenceWindow(window) {
    this.silenceWindows.push(window);
  }

  evaluateComposite(compositeRule) {
    const { conditions, operator } = compositeRule;

    const results = conditions.map(condition => {
      const activeForRule = [...this.activeAlerts.values()]
        .filter(alert => alert.ruleId === condition.ruleId && alert.status === 'firing');
      return activeForRule.length > 0;
    });

    switch (operator) {
      case 'AND':
        return results.every(r => r);
      case 'OR':
        return results.some(r => r);
      case 'NOT':
        return !results[0];
      default:
        return false;
    }
  }

  aggregateMetrics(metrics) {
    const aggregated = new Map();

    for (const metric of metrics) {
      const key = Object.entries(metric.labels || {})
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => `${k}=${v}`)
        .join(',');

      if (!aggregated.has(key)) {
        aggregated.set(key, { count: 0, sum: 0 });
      }
      const state = aggregated.get(key);
      state.count += 1;
      state.sum += metric.value;
    }

    return aggregated;
  }

  getActiveAlerts() {
    return [...this.activeAlerts.values()].filter(a => a.status === 'firing');
  }

  clearAll() {
    this.activeAlerts.clear();
    this.notificationLog.clear();
    for (const timer of this.escalationTimers.values()) {
      clearTimeout(timer);
    }
    this.escalationTimers.clear();
  }
}


class AlertStateMachine {
  constructor() {
    this._alerts = new Map();
    this._transitionLog = [];
    this._validTransitions = {
      'pending': ['firing', 'suppressed'],
      'firing': ['acknowledged', 'resolved', 'escalated'],
      'acknowledged': ['resolved', 'escalated', 'firing'],
      'escalated': ['acknowledged', 'resolved'],
      'resolved': ['firing'],
      'suppressed': ['pending', 'resolved'],
    };
  }

  createAlert(id, initialData = {}) {
    const alert = {
      id,
      state: 'pending',
      severity: initialData.severity || 'warning',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      transitions: [],
      acknowledgements: [],
      ...initialData,
    };
    this._alerts.set(id, alert);
    return alert;
  }

  transition(alertId, newState, metadata = {}) {
    const alert = this._alerts.get(alertId);
    if (!alert) throw new Error(`Alert not found: ${alertId}`);

    const validTargets = this._validTransitions[alert.state];

    if (!validTargets || (!validTargets.includes(newState) && !metadata.force)) {
      throw new Error(`Invalid transition: ${alert.state} -> ${newState}`);
    }

    const transition = {
      from: alert.state,
      to: newState,
      timestamp: Date.now(),
      metadata,
    };

    alert.transitions.push(transition);
    this._transitionLog.push({ alertId, ...transition });

    alert.state = newState;
    alert.updatedAt = Date.now();

    if (newState === 'firing' && metadata.autoEscalateAfter) {
      setTimeout(() => {
        const current = this._alerts.get(alertId);
        if (current && current.state === 'firing') {
          this.transition(alertId, 'escalated', { reason: 'auto-escalation' });
        }
      }, metadata.autoEscalateAfter);
    }

    return alert;
  }

  acknowledge(alertId, userId) {
    const alert = this._alerts.get(alertId);
    if (!alert) throw new Error(`Alert not found: ${alertId}`);

    alert.acknowledgements.push({
      userId,
      timestamp: Date.now(),
    });

    if (alert.state === 'firing') {
      return this.transition(alertId, 'acknowledged', { userId });
    }

    return alert;
  }

  getAlert(alertId) {
    return this._alerts.get(alertId);
  }

  getTransitionLog(alertId) {
    if (alertId) {
      return this._transitionLog.filter(t => t.alertId === alertId);
    }
    return this._transitionLog;
  }

  getAlertsByState(state) {
    return [...this._alerts.values()].filter(a => a.state === state);
  }
}


class FlappingDetector {
  constructor(options = {}) {
    this._transitionCounts = new Map();
    this._windowSize = options.windowSize || 300000;
    this._threshold = options.threshold || 5;
    this._history = new Map();
  }

  recordTransition(alertId, fromState, toState) {
    if (!this._history.has(alertId)) {
      this._history.set(alertId, []);
    }

    const history = this._history.get(alertId);
    history.push({
      from: fromState,
      to: toState,
      timestamp: Date.now(),
    });

    const cutoff = Date.now() - this._windowSize;
    const filtered = history.filter(h => h.timestamp > cutoff);
    this._history.set(alertId, filtered);

    return this.isFlapping(alertId);
  }

  isFlapping(alertId) {
    const history = this._history.get(alertId) || [];
    const cutoff = Date.now() - this._windowSize;
    const recent = history.filter(h => h.timestamp > cutoff);

    return recent.length >= this._threshold;
  }

  getTransitionCount(alertId) {
    const history = this._history.get(alertId) || [];
    const cutoff = Date.now() - this._windowSize;
    return history.filter(h => h.timestamp > cutoff).length;
  }

  suppressIfFlapping(alertId) {
    if (this.isFlapping(alertId)) {
      return { suppressed: true, reason: 'flapping', count: this.getTransitionCount(alertId) };
    }
    return { suppressed: false };
  }
}


class AlertCorrelationEngine {
  constructor() {
    this._correlationRules = [];
    this._correlatedGroups = new Map();
    this._severityOrder = { 'critical': 1, 'error': 2, 'warning': 3, 'info': 4 };
  }

  addCorrelationRule(rule) {
    this._correlationRules.push(rule);
  }

  correlate(alerts) {
    const groups = new Map();

    for (const alert of alerts) {
      let matched = false;

      for (const rule of this._correlationRules) {
        if (this._matchesRule(alert, rule)) {
          const groupKey = this._getGroupKey(alert, rule);

          if (!groups.has(groupKey)) {
            groups.set(groupKey, {
              rule: rule.name,
              alerts: [],
              rootCause: null,
              severity: 'info',
            });
          }

          const group = groups.get(groupKey);
          group.alerts.push(alert);

          if ((this._severityOrder[alert.severity] || 99) > (this._severityOrder[group.severity] || 99)) {
            group.severity = alert.severity;
          }

          if (!group.rootCause) {
            group.rootCause = alert;
          }

          matched = true;
          break;
        }
      }

      if (!matched) {
        const key = `uncorrelated:${alert.id}`;
        groups.set(key, {
          rule: null,
          alerts: [alert],
          rootCause: alert,
          severity: alert.severity,
        });
      }
    }

    this._correlatedGroups = groups;
    return [...groups.values()];
  }

  _matchesRule(alert, rule) {
    if (rule.metric && alert.metric !== rule.metric) return false;
    if (rule.severity && alert.severity !== rule.severity) return false;
    if (rule.timeWindow) {
      const now = Date.now();
      const alertAge = now - (alert.timestamp || alert.createdAt || now);
      if (alertAge > rule.timeWindow) return false;
    }
    return true;
  }

  _getGroupKey(alert, rule) {
    return `${rule.name}:${alert.metric || 'unknown'}`;
  }

  getCorrelatedGroups() {
    return [...this._correlatedGroups.values()];
  }
}

module.exports = { AlertDetector, AlertStateMachine, FlappingDetector, AlertCorrelationEngine };
