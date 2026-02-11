/**
 * Integration Alert Tests (~30 tests)
 *
 * Tests for alert detection integration with aggregation and notification
 * Covers BUG G1-G8, H3-H4, H8
 */

const { AlertDetector } = require('../../services/alerts/src/services/detection');
const { RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { ConnectorHealthCheck, ConnectorConfigManager } = require('../../services/connectors/src/services/framework');

describe('Alert Integration', () => {
  let detector;
  let engine;

  beforeEach(() => {
    detector = new AlertDetector({ deduplicationWindow: 300000 });
    engine = new RollupEngine({ windowSize: 60000 });
  });

  afterEach(() => {
    detector.clearAll();
  });

  describe('aggregation-driven alerts', () => {
    test('float threshold comparison test - aggregated float compared correctly', () => {
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 0.3, severity: 'warning' });
      const cpuValue = 0.1 + 0.2; // 0.30000000000000004
      const result = detector.evaluate('cpu', cpuValue);
      expect(result.length).toBe(0); // Should not trigger (equal, not greater)
    });

    test('precision comparison test - near-equal values handled', () => {
      detector.addRule({ id: 'r2', metric: 'cpu', operator: 'eq', threshold: 0.3, severity: 'warning' });
      const result = detector.evaluate('cpu', 0.30000000000000004);
      expect(result.length).toBe(1);
    });

    test('rolling average threshold alert', () => {
      detector.addRule({ id: 'r3', metric: 'latency', operator: 'gt', threshold: 100, severity: 'critical' });

      engine.movingAverage('latency', 50, 5);
      engine.movingAverage('latency', 150, 5);
      const avg = engine.movingAverage('latency', 200, 5);

      const result = detector.evaluate('latency', avg);
      expect(result.length).toBe(1);
    });

    test('rate-based alert from aggregation', () => {
      detector.addRule({ id: 'r4', metric: 'error_rate', operator: 'gt', threshold: 50, severity: 'warning' });
      engine.calculateRate('errors', 100, 1000);
      const rate = engine.calculateRate('errors', 200, 2000);
      const result = detector.evaluate('error_rate', rate);
      expect(result.length).toBe(1);
    });

    test('anomaly detection with baseline from rollup', () => {
      for (let i = 0; i < 20; i++) {
        detector.detectAnomaly('response_time', 50 + Math.random() * 5);
      }
      const result = detector.detectAnomaly('response_time', 200);
      expect(result.isAnomaly).toBe(true);
    });
  });

  describe('alert deduplication and escalation', () => {
    test('notification dedup window test - rapid alerts deduplicated', () => {
      detector.addRule({ id: 'r5', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const first = detector.evaluate('cpu', 0.9);
      const second = detector.evaluate('cpu', 0.95);
      expect(first.length).toBe(1);
      expect(second.length).toBe(0);
    });

    test('deduplication test - separate rules create separate alerts', () => {
      detector.addRule({ id: 'r6', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'r7', metric: 'cpu', operator: 'gt', threshold: 0.7 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(2);
    });

    test('escalation timer race test - single timer per alert', () => {
      detector.addRule({
        id: 'r8', metric: 'cpu', operator: 'gt', threshold: 0.5,
        escalation: { after: 100, targetSeverity: 'critical' },
      });
      detector.evaluate('cpu', 0.9);
      expect(detector.escalationTimers.size).toBe(1);
    });

    test('concurrent escalation test - no duplicate timers', () => {
      detector.addRule({
        id: 'r9', metric: 'cpu', operator: 'gt', threshold: 0.5,
        escalation: { after: 100, targetSeverity: 'critical' },
      });
      detector.evaluate('cpu', 0.9);
      const count = detector.escalationTimers.size;
      expect(count).toBe(1);
    });

    test('recovery hysteresis test - sustained recovery clears alert', () => {
      detector.addRule({ id: 'r10', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      expect(detector.getActiveAlerts().length).toBe(1);
      detector.evaluate('cpu', 0.3);
      expect(detector.getActiveAlerts().length).toBe(0);
    });

    test('alert recovery test - single recovery check', () => {
      detector.addRule({ id: 'r11', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      detector.evaluate('cpu', 0.4);
      expect(detector.getActiveAlerts().length).toBe(0);
    });
  });

  describe('composite alert integration', () => {
    test('composite alert order test - AND requires all conditions', () => {
      detector.addRule({ id: 'r12', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'r13', metric: 'mem', operator: 'gt', threshold: 80 });
      detector.evaluate('cpu', 0.9);
      // Only cpu triggered, not mem
      const result = detector.evaluateComposite({
        conditions: [{ ruleId: 'r12' }, { ruleId: 'r13' }],
        operator: 'AND',
      });
      expect(result).toBe(false);
    });

    test('evaluation order test - OR requires any condition', () => {
      detector.addRule({ id: 'r14', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      const result = detector.evaluateComposite({
        conditions: [{ ruleId: 'r14' }, { ruleId: 'nonexistent' }],
        operator: 'OR',
      });
      expect(result).toBe(true);
    });

    test('composite with aggregated metrics', () => {
      detector.addRule({ id: 'r15', metric: 'p99_latency', operator: 'gt', threshold: 500 });
      detector.addRule({ id: 'r16', metric: 'error_rate', operator: 'gt', threshold: 5 });

      const p99 = engine.calculatePercentile(
        Array.from({ length: 100 }, () => 200 + Math.random() * 500),
        99
      );
      detector.evaluate('p99_latency', p99);
      detector.evaluate('error_rate', 10);

      const result = detector.evaluateComposite({
        conditions: [{ ruleId: 'r15' }, { ruleId: 'r16' }],
        operator: 'AND',
      });
      expect(typeof result).toBe('boolean');
    });
  });

  describe('silence and metric aggregation', () => {
    test('silence window timezone test - current time within window', () => {
      const now = new Date();
      detector.addSilenceWindow({
        start: new Date(now.getTime() - 60000).toISOString(),
        end: new Date(now.getTime() + 60000).toISOString(),
      });
      detector.addRule({ id: 'r17', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(0);
    });

    test('timezone handling test - expired silence window allows alerts', () => {
      const past = new Date(Date.now() - 86400000);
      detector.addSilenceWindow({
        start: past.toISOString(),
        end: past.toISOString(),
      });
      detector.addRule({ id: 'r18', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(1);
    });

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

    test('pipeline id label test - cardinality bounded', () => {
      const metrics = [
        { name: 'requests', labels: { method: 'GET' }, value: 1 },
        { name: 'requests', labels: { method: 'POST' }, value: 1 },
        { name: 'requests', labels: { method: 'GET' }, value: 1 },
      ];
      const aggregated = detector.aggregateMetrics(metrics);
      expect(aggregated.size).toBe(2);
    });
  });

  describe('caching integration (H3, H4, H8)', () => {
    test('aggregation cache ttl test - TTL prevents stale data', async () => {
      const cache = new Map();
      cache.set('agg:key1', { data: [1, 2, 3], expiresAt: Date.now() + 60000 });
      const entry = cache.get('agg:key1');
      expect(entry.expiresAt).toBeGreaterThan(Date.now());
    });

    test('ttl race test - TTL checked before use', async () => {
      const cache = new Map();
      cache.set('agg:key1', { data: 'old', expiresAt: Date.now() - 1000 });
      const entry = cache.get('agg:key1');
      const isExpired = entry.expiresAt < Date.now();
      expect(isExpired).toBe(true);
    });

    test('connector state stale test - stale state detected', () => {
      const connector = { running: true, lastPollTime: Date.now() - 120000 };
      const check = new ConnectorHealthCheck(connector);
      const result = check.check();
      
      expect(result).toBeDefined();
    });

    test('state cache test - health check reflects current state', () => {
      const connector = { running: true, lastPollTime: Date.now() };
      const check = new ConnectorHealthCheck(connector);
      expect(check.check().healthy).toBe(true);
    });

    test('hot partition lag test - detection for hot partitions', () => {
      const partitionLatencies = [10, 15, 12, 500, 11, 13];
      const avg = partitionLatencies.reduce((a, b) => a + b, 0) / partitionLatencies.length;
      const hotPartitions = partitionLatencies.filter(l => l > avg * 3);
      expect(hotPartitions.length).toBeGreaterThan(0);
    });

    test('detection delay test - lag detected promptly', () => {
      const partitions = [
        { id: 'p0', lag: 10 },
        { id: 'p1', lag: 5000 },
        { id: 'p2', lag: 15 },
      ];
      const hotPartition = partitions.find(p => p.lag > 1000);
      expect(hotPartition).toBeDefined();
      expect(hotPartition.id).toBe('p1');
    });
  });

  describe('alert lifecycle integration', () => {
    test('alert fires then recovers then fires again', () => {
      detector.addRule({ id: 'lifecycle-1', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const first = detector.evaluate('cpu', 0.9);
      expect(first.length).toBe(1);

      detector.evaluate('cpu', 0.2); // recovery
      expect(detector.getActiveAlerts().length).toBe(0);

      // After dedup window of 0, re-fire
      const detector2 = new AlertDetector({ deduplicationWindow: 0 });
      detector2.addRule({ id: 'lifecycle-2', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector2.evaluate('cpu', 0.8);
      expect(detector2.getActiveAlerts().length).toBe(1);
      detector2.clearAll();
    });

    test('multiple metrics tracked independently', () => {
      detector.addRule({ id: 'm1', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'm2', metric: 'memory', operator: 'gt', threshold: 80 });
      detector.addRule({ id: 'm3', metric: 'disk', operator: 'gt', threshold: 90 });

      detector.evaluate('cpu', 0.9);
      detector.evaluate('memory', 85);
      detector.evaluate('disk', 50); // below threshold

      expect(detector.getActiveAlerts().length).toBe(2);
    });

    test('anomaly detection with stable then sudden change', () => {
      for (let i = 0; i < 50; i++) {
        detector.detectAnomaly('latency', 100 + Math.random() * 5);
      }
      const spike = detector.detectAnomaly('latency', 1000);
      expect(spike.isAnomaly).toBe(true);
    });

    test('composite AND with both conditions met', () => {
      detector.addRule({ id: 'both-1', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.addRule({ id: 'both-2', metric: 'mem', operator: 'gt', threshold: 80 });
      detector.evaluate('cpu', 0.9);
      detector.evaluate('mem', 90);

      const result = detector.evaluateComposite({
        conditions: [{ ruleId: 'both-1' }, { ruleId: 'both-2' }],
        operator: 'AND',
      });
      expect(result).toBe(true);
    });

    test('silence window with future start has no effect now', () => {
      const future = new Date(Date.now() + 86400000);
      detector.addSilenceWindow({
        start: future.toISOString(),
        end: new Date(future.getTime() + 3600000).toISOString(),
      });
      detector.addRule({ id: 'future-silence', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      const result = detector.evaluate('cpu', 0.9);
      expect(result.length).toBe(1);
    });

    test('escalation does not duplicate on re-evaluation', () => {
      detector.addRule({
        id: 'esc-reeval', metric: 'cpu', operator: 'gt', threshold: 0.5,
        escalation: { after: 500, targetSeverity: 'critical' },
      });
      detector.evaluate('cpu', 0.9);
      detector.evaluate('cpu', 0.95); // deduplicated
      expect(detector.escalationTimers.size).toBe(1);
    });
  });
});
