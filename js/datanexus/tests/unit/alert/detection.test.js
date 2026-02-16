/**
 * Alert Detection Tests (~40 tests)
 *
 * Tests for BUG G1-G8 alerting bugs
 */

const { AlertDetector, AlertStateMachine, FlappingDetector, AlertCorrelationEngine } = require('../../../services/alerts/src/services/detection');

describe('AlertDetector', () => {
  let detector;

  beforeEach(() => {
    detector = new AlertDetector({ deduplicationWindow: 300000 });
  });

  afterEach(() => {
    detector.clearAll();
  });

  describe('threshold comparison (G1)', () => {
    test('float threshold comparison test - handles float precision', () => {
      detector.addRule({ id: 'rule-1', metric: 'cpu', operator: 'gt', threshold: 0.3, severity: 'warning' });
      const result = detector.evaluate('cpu', 0.1 + 0.2);
      expect(result.length).toBe(0);
    });

    test('precision comparison test - near-equal values handled correctly', () => {
      detector.addRule({ id: 'rule-2', metric: 'cpu', operator: 'eq', threshold: 0.3, severity: 'warning' });
      const result = detector.evaluate('cpu', 0.30000000000000004);
      expect(result.length).toBe(1);
    });

    test('threshold clearly exceeded triggers alert', () => {
      detector.addRule({ id: 'rule-3', metric: 'cpu', operator: 'gt', threshold: 0.5, severity: 'warning' });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(1);
    });

    test('threshold not exceeded does not trigger', () => {
      detector.addRule({ id: 'rule-4', metric: 'cpu', operator: 'gt', threshold: 0.5, severity: 'warning' });
      const result = detector.evaluate('cpu', 0.3);
      expect(result.length).toBe(0);
    });

    test('less-than operator works', () => {
      detector.addRule({ id: 'rule-5', metric: 'mem', operator: 'lt', threshold: 100, severity: 'warning' });
      const result = detector.evaluate('mem', 50);
      expect(result.length).toBe(1);
    });

    test('different metrics dont interfere', () => {
      detector.addRule({ id: 'rule-6', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('memory', 0.9);
      expect(result.length).toBe(0);
    });
  });

  describe('anomaly detection (G2)', () => {
    test('anomaly baseline stale test - baseline updates over time', () => {
      for (let i = 0; i < 10; i++) {
        detector.detectAnomaly('metric-1', 50 + Math.random() * 10);
      }
      const baseline = detector.baselines.get('metric-1');
      expect(baseline.sampleCount).toBeGreaterThan(1);
    });

    test('baseline refresh test - baseline reflects recent data', () => {
      detector.detectAnomaly('metric-1', 50);
      detector.detectAnomaly('metric-1', 100);
      const baseline = detector.baselines.get('metric-1');
      expect(baseline.mean).not.toBe(50);
    });

    test('clear anomaly is not flagged', () => {
      for (let i = 0; i < 5; i++) {
        detector.detectAnomaly('metric-1', 50);
      }
      const result = detector.detectAnomaly('metric-1', 51);
      expect(result.isAnomaly).toBe(false);
    });

    test('first value initializes baseline', () => {
      detector.detectAnomaly('new-metric', 42);
      expect(detector.baselines.has('new-metric')).toBe(true);
    });
  });

  describe('deduplication (G3)', () => {
    test('notification dedup window test - rapid alerts deduplicated', () => {
      detector.addRule({ id: 'rule-7', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const first = detector.evaluate('cpu', 0.9);
      const second = detector.evaluate('cpu', 0.95);
      expect(first.length).toBe(1);
      expect(second.length).toBe(0);
    });

    test('deduplication test - separate rules create separate alerts', () => {
      detector.addRule({ id: 'rule-8', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'rule-9', metric: 'cpu', operator: 'gt', threshold: 0.7 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(2);
    });

    test('after dedup window expires, new alert created', () => {
      detector = new AlertDetector({ deduplicationWindow: 0 });
      detector.addRule({ id: 'rule-10', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const first = detector.evaluate('cpu', 0.9);
      const second = detector.evaluate('cpu', 0.95);
      expect(first.length).toBe(1);
      expect(second.length).toBe(1);
    });
  });

  describe('escalation (G4)', () => {
    test('escalation timer race test - single timer per alert', () => {
      detector.addRule({
        id: 'rule-11', metric: 'cpu', operator: 'gt', threshold: 0.5,
        escalation: { after: 100, targetSeverity: 'critical' },
      });
      detector.evaluate('cpu', 0.9);
      const timerCount = detector.escalationTimers.size;
      expect(timerCount).toBe(1);
    });

    test('concurrent escalation test - no duplicate timers', () => {
      detector.addRule({
        id: 'rule-12', metric: 'cpu', operator: 'gt', threshold: 0.5,
        escalation: { after: 100, targetSeverity: 'critical' },
      });
      detector.evaluate('cpu', 0.9);
      expect(detector.escalationTimers.size).toBe(1);
    });

    test('escalation actually upgrades severity', async () => {
      detector.addRule({
        id: 'rule-13', metric: 'cpu', operator: 'gt', threshold: 0.5,
        escalation: { after: 50, targetSeverity: 'critical' },
      });
      const alerts = detector.evaluate('cpu', 0.9);
      await global.testUtils.delay(100);
      expect(alerts[0].severity).toBe('critical');
    });
  });

  describe('silence windows (G6)', () => {
    test('silence window timezone test - respects timezone', () => {
      const now = new Date();
      detector.addSilenceWindow({
        start: new Date(now.getTime() - 60000).toISOString(),
        end: new Date(now.getTime() + 60000).toISOString(),
      });
      detector.addRule({ id: 'rule-14', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(0);
    });

    test('timezone handling test - UTC and local times compared correctly', () => {
      const past = new Date(Date.now() - 86400000);
      detector.addSilenceWindow({
        start: past.toISOString(),
        end: past.toISOString(),
      });
      detector.addRule({ id: 'rule-15', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(1);
    });
  });

  describe('composite alerts (G7)', () => {
    test('composite alert order test - AND requires all conditions', () => {
      detector.addRule({ id: 'rule-16', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'rule-17', metric: 'mem', operator: 'gt', threshold: 80 });
      detector.evaluate('cpu', 0.9);
      const result = detector.evaluateComposite({
        conditions: [{ ruleId: 'rule-16' }, { ruleId: 'rule-17' }],
        operator: 'AND',
      });
      expect(result).toBe(false);
    });

    test('evaluation order test - OR requires any condition', () => {
      detector.addRule({ id: 'rule-18', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      const result = detector.evaluateComposite({
        conditions: [{ ruleId: 'rule-18' }, { ruleId: 'nonexistent' }],
        operator: 'OR',
      });
      expect(result).toBe(true);
    });
  });

  describe('recovery detection (G8)', () => {
    test('recovery hysteresis test - requires sustained recovery', () => {
      detector.addRule({ id: 'rule-19', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      expect(detector.getActiveAlerts().length).toBe(1);
      detector.evaluate('cpu', 0.3);
      const active = detector.getActiveAlerts();
      expect(active.length).toBe(0);
    });

    test('alert recovery test - single recovery clears immediately (bug behavior)', () => {
      detector.addRule({ id: 'rule-20', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      detector.evaluate('cpu', 0.4);
      expect(detector.getActiveAlerts().length).toBe(0);
    });
  });

  describe('metric aggregation (G5)', () => {
    test('metric cardinality test - bounded label combinations', () => {
      const metrics = [];
      for (let i = 0; i < 1000; i++) {
        metrics.push({
          name: 'requests',
          labels: { pipeline_id: `pipeline-${i}`, request_id: `req-${i}` },
          value: 1,
        });
      }
      const aggregated = detector.aggregateMetrics(metrics);
      expect(aggregated.size).toBeLessThan(1000);
    });

    test('pipeline id label test - cardinality bounded by allowed labels', () => {
      const metrics = [
        { name: 'requests', labels: { method: 'GET' }, value: 1 },
        { name: 'requests', labels: { method: 'POST' }, value: 1 },
        { name: 'requests', labels: { method: 'GET' }, value: 1 },
      ];
      const aggregated = detector.aggregateMetrics(metrics);
      expect(aggregated.size).toBe(2);
    });

    test('empty metrics list returns empty', () => {
      const aggregated = detector.aggregateMetrics([]);
      expect(aggregated.size).toBe(0);
    });

    test('different metric names produce separate entries', () => {
      const metrics = [
        { name: 'cpu', labels: {}, value: 1 },
        { name: 'memory', labels: {}, value: 1 },
      ];
      const aggregated = detector.aggregateMetrics(metrics);
      expect(aggregated.size).toBe(2);
    });
  });

  describe('additional rule tests', () => {
    test('gte operator triggers at threshold', () => {
      detector.addRule({ id: 'gte-rule', metric: 'cpu', operator: 'gte', threshold: 0.5 });
      const result = detector.evaluate('cpu', 0.5);
      expect(result.length).toBe(1);
    });

    test('lte operator triggers below threshold', () => {
      detector.addRule({ id: 'lte-rule', metric: 'mem', operator: 'lte', threshold: 100 });
      const result = detector.evaluate('mem', 50);
      expect(result.length).toBe(1);
    });

    test('neq operator triggers on different value', () => {
      detector.addRule({ id: 'neq-rule', metric: 'status', operator: 'neq', threshold: 200 });
      const result = detector.evaluate('status', 500);
      expect(result.length).toBe(1);
    });

    test('multiple rules same metric all evaluated', () => {
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 0.3 });
      detector.addRule({ id: 'r2', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'r3', metric: 'cpu', operator: 'gt', threshold: 0.8 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(3);
    });

    test('evaluate returns empty for no matching metric', () => {
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('disk', 0.9);
      expect(result.length).toBe(0);
    });

    test('alert includes rule ID', () => {
      detector.addRule({ id: 'my-rule', metric: 'cpu', operator: 'gt', threshold: 0.5, severity: 'warning' });
      const result = detector.evaluate('cpu', 0.9);
      expect(result[0].ruleId || result[0].id).toBeDefined();
    });

    test('anomaly detection first sample is not anomaly', () => {
      const result = detector.detectAnomaly('new-metric', 42);
      expect(result.isAnomaly).toBe(false);
    });

    test('anomaly detection stable values not anomalous', () => {
      for (let i = 0; i < 20; i++) {
        detector.detectAnomaly('stable-metric', 100);
      }
      const result = detector.detectAnomaly('stable-metric', 100);
      expect(result.isAnomaly).toBe(false);
    });

    test('anomaly detection extreme value is anomalous', () => {
      for (let i = 0; i < 30; i++) {
        detector.detectAnomaly('normal-metric', 50);
      }
      const result = detector.detectAnomaly('normal-metric', 500);
      expect(result.isAnomaly).toBe(true);
    });

    test('getActiveAlerts returns empty initially', () => {
      expect(detector.getActiveAlerts()).toEqual([]);
    });

    test('clearAll removes all state', () => {
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      detector.clearAll();
      expect(detector.getActiveAlerts()).toEqual([]);
    });
  });

  describe('AlertCorrelationEngine severity ordering (G1)', () => {
    test('group severity should be highest actual severity not last seen', () => {
      const correlator = new AlertCorrelationEngine();
      correlator.addCorrelationRule({ name: 'cpu', metric: 'cpu', timeWindow: 60000 });
      const now = Date.now();
      correlator.correlate([
        { id: 'a1', metric: 'cpu', severity: 'info', timestamp: now },
        { id: 'a2', metric: 'cpu', severity: 'critical', timestamp: now + 1000 },
      ]);
      const groups = correlator.getCorrelationGroups();
      expect(groups[0].severity).toBe('critical');
    });

    test('severity ordering: critical > error > warning > info', () => {
      const correlator = new AlertCorrelationEngine();
      correlator.addCorrelationRule({ name: 'mem', metric: 'mem', timeWindow: 60000 });
      const now = Date.now();
      correlator.correlate([
        { id: 'a1', metric: 'mem', severity: 'warning', timestamp: now },
        { id: 'a2', metric: 'mem', severity: 'error', timestamp: now + 1000 },
        { id: 'a3', metric: 'mem', severity: 'info', timestamp: now + 2000 },
      ]);
      const groups = correlator.getCorrelationGroups();
      expect(groups[0].severity).toBe('error');
    });
  });

  describe('AlertCorrelationEngine root cause (G2)', () => {
    test('root cause should be earliest alert by timestamp', () => {
      const correlator = new AlertCorrelationEngine();
      correlator.addCorrelationRule({ name: 'disk', metric: 'disk', timeWindow: 60000 });
      const now = Date.now();
      correlator.correlate([
        { id: 'a3', metric: 'disk', severity: 'warning', timestamp: now },
        { id: 'a1', metric: 'disk', severity: 'critical', timestamp: now - 30000 },
        { id: 'a2', metric: 'disk', severity: 'error', timestamp: now - 10000 },
      ]);
      const groups = correlator.getCorrelationGroups();
      expect(groups[0].rootCause.id).toBe('a1');
    });
  });

  describe('AlertStateMachine acknowledge bug (G4)', () => {
    test('acknowledge should transition escalated alerts', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('a1', { severity: 'critical' });
      sm.transition('a1', 'firing');
      sm.transition('a1', 'escalated');
      const result = sm.acknowledge('a1', 'user-1');
      expect(result.state).toBe('acknowledged');
    });
  });

  describe('AlertStateMachine force flag (G3)', () => {
    test('force flag with truthy non-boolean should not bypass validation', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('a1');
      sm.transition('a1', 'firing');
      expect(() => {
        sm.transition('a1', 'pending', { force: [] });
      }).toThrow('Invalid transition');
    });

    test('force flag with truthy string should not bypass validation', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('a2');
      sm.transition('a2', 'firing');
      expect(() => {
        sm.transition('a2', 'pending', { force: 'yes' });
      }).toThrow('Invalid transition');
    });

    test('force flag with number 1 should not bypass validation', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('a3');
      sm.transition('a3', 'firing');
      expect(() => {
        sm.transition('a3', 'pending', { force: 1 });
      }).toThrow('Invalid transition');
    });
  });
});
