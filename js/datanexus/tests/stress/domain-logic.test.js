/**
 * Domain Logic Tests
 *
 * Tests requiring deep understanding of data pipeline domain concepts:
 * stream processing semantics, exactly-once delivery, event sourcing,
 * aggregation correctness, and distributed system invariants.
 */

const { StreamAggregator, ContinuousAggregation } = require('../../services/aggregate/src/services/rollups');
const { RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { ConnectorPipeline, SchemaEvolutionManager, SourceConnector, SinkConnector, ConnectorSchemaRegistry } = require('../../services/connectors/src/services/framework');
const { AlertDetector, AlertCorrelationEngine } = require('../../services/alerts/src/services/detection');
const { ContentBasedRouter } = require('../../services/router/src/services/routing');

describe('Domain Logic Bugs', () => {
  describe('ContinuousAggregation running average', () => {
    test('running average should be weighted correctly across updates', async () => {
      const agg = new ContinuousAggregation();

      agg.defineMaterialization('metrics_avg', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'cpu' }],
      });

      // First batch: average of [10, 20, 30] = 20
      await agg.update('metrics_avg', [
        { host: 'server-1', cpu: 10 },
        { host: 'server-1', cpu: 20 },
        { host: 'server-1', cpu: 30 },
      ]);

      const state1 = agg.getState('metrics_avg');
      const server1State = state1.state['server-1'];
      expect(server1State.cpu_avg).toBeCloseTo(20, 5);

      // Second batch: average of [40, 50] = 45
      // Overall average should be (10+20+30+40+50)/5 = 30
      await agg.update('metrics_avg', [
        { host: 'server-1', cpu: 40 },
        { host: 'server-1', cpu: 50 },
      ]);

      const state2 = agg.getState('metrics_avg');
      const server1State2 = state2.state['server-1'];

      // Running average should reflect all 5 values: 30
      expect(server1State2.cpu_avg).toBeCloseTo(30, 5);
    });

    test('sum aggregation should be exact for integer values', async () => {
      const agg = new ContinuousAggregation();

      agg.defineMaterialization('byte_count', {
        groupBy: ['tenant'],
        aggregations: [{ type: 'sum', field: 'bytes' }],
      });

      const records = [];
      for (let i = 0; i < 1000; i++) {
        records.push({ tenant: 'tenant-1', bytes: 1024 });
      }

      await agg.update('byte_count', records);

      const state = agg.getState('byte_count');
      expect(state.state['tenant-1'].bytes_sum).toBe(1024000);
    });

    test('min/max should handle negative values correctly', async () => {
      const agg = new ContinuousAggregation();

      agg.defineMaterialization('temp_stats', {
        groupBy: ['sensor'],
        aggregations: [
          { type: 'min', field: 'temperature' },
          { type: 'max', field: 'temperature' },
        ],
      });

      await agg.update('temp_stats', [
        { sensor: 's1', temperature: -10 },
        { sensor: 's1', temperature: 5 },
        { sensor: 's1', temperature: -20 },
        { sensor: 's1', temperature: 15 },
      ]);

      const state = agg.getState('temp_stats');
      expect(state.state['s1'].temperature_min).toBe(-20);
      expect(state.state['s1'].temperature_max).toBe(15);
    });
  });

  describe('StreamAggregator late event handling', () => {
    test('late events within allowed lateness should update window aggregate', () => {
      const aggregator = new StreamAggregator({
        allowedLateness: 10000,
        windowDuration: 60000,
      });

      // Normal events
      aggregator.addEvent({ timestamp: 5000, value: 10 });
      aggregator.addEvent({ timestamp: 15000, value: 20 });

      // Advance watermark
      aggregator.advanceWatermark(30000);

      // Late event within allowed lateness (30000 - 10000 = 20000, event at 25000 is OK)
      const result = aggregator.addEvent({ timestamp: 25000, value: 30 });
      expect(result.status).toBe('added');

      // Window aggregate should include the late event
      const windowKey = 0; // window [0, 60000)
      const window = aggregator.getWindow(windowKey);
      expect(window.aggregate.count).toBe(3);
      expect(window.aggregate.sum).toBe(60);
    });

    test('retraction should be emitted when late event updates already-emitted window', () => {
      const aggregator = new StreamAggregator({
        allowedLateness: 120000,
        windowDuration: 60000,
        retractionsEnabled: true,
      });

      // Fill window and emit
      aggregator.addEvent({ timestamp: 10000, value: 100 });
      aggregator.addEvent({ timestamp: 20000, value: 200 });

      // Advance watermark past window end to trigger emission
      const emissions = aggregator.advanceWatermark(120000);
      expect(emissions.length).toBe(1);
      expect(emissions[0].sum).toBe(300);

      // Late event arrives within allowed lateness
      aggregator.addEvent({ timestamp: 30000, value: 50 });

      // Recompute should emit retraction + update
      const updated = aggregator.recomputeWindow(0);
      expect(updated).not.toBeNull();
      expect(updated.sum).toBe(350);
      expect(updated.retraction).toBeDefined();
      expect(updated.retraction.sum).toBe(300);
    });

    test('cleanup should not leak memory in emitted windows set', () => {
      const aggregator = new StreamAggregator({
        windowDuration: 1000,
        allowedLateness: 0,
      });

      // Create and emit many windows
      for (let i = 0; i < 100; i++) {
        aggregator.addEvent({ timestamp: i * 1000 + 500, value: i });
      }

      aggregator.advanceWatermark(200000);

      // Cleanup old windows
      aggregator.cleanup(150000);

      // Windows map should be smaller after cleanup
      const windowCount = [...aggregator._windows.keys()].length;
      expect(windowCount).toBeLessThan(100);

      // But emittedWindows set should also be cleaned up
      expect(aggregator._emittedWindows.size).toBeLessThan(100);
    });
  });

  describe('SchemaEvolutionManager multi-step migration', () => {
    test('should handle multi-step schema migrations (v1->v2->v3)', () => {
      const registry = new ConnectorSchemaRegistry();
      const evolution = new SchemaEvolutionManager(registry);

      // Register incremental migrations
      evolution.registerMigration('user-events', 1, 2, (record) => ({
        ...record,
        fullName: `${record.firstName} ${record.lastName}`,
      }));

      evolution.registerMigration('user-events', 2, 3, (record) => ({
        ...record,
        email: record.email?.toLowerCase(),
        version: 3,
      }));

      const v1Record = { firstName: 'John', lastName: 'Doe', email: 'John@Example.com' };

      // Should chain: v1 -> v2 -> v3
      const migrated = evolution.evolve('user-events', v1Record, 1, 3);

      expect(migrated.fullName).toBe('John Doe');
      expect(migrated.email).toBe('john@example.com');
      expect(migrated.version).toBe(3);
    });

    test('backward compatibility check should require defaults for new fields', () => {
      const registry = new ConnectorSchemaRegistry();
      const evolution = new SchemaEvolutionManager(registry);
      evolution.setCompatibilityMode('backward');

      const oldSchema = {
        fields: {
          id: { type: 'string', required: true },
          name: { type: 'string', required: true },
        },
      };

      const newSchemaGood = {
        fields: {
          id: { type: 'string', required: true },
          name: { type: 'string', required: true },
          email: { type: 'string', required: false, default: '' },
        },
      };

      const newSchemaBad = {
        fields: {
          id: { type: 'string', required: true },
          name: { type: 'string', required: true },
          email: { type: 'string', required: true }, // No default!
        },
      };

      expect(evolution.checkCompatibility('events', oldSchema, newSchemaGood)).toBe(true);
      expect(evolution.checkCompatibility('events', oldSchema, newSchemaBad)).toBe(false);
    });
  });

  describe('ConnectorPipeline exactly-once semantics', () => {
    test('write failure should not cause duplicate records on retry', async () => {
      let writeCallCount = 0;
      const writtenRecords = [];

      const source = new SourceConnector({ topic: 'test' });
      const records = [{ id: 1, offset: 1, partition: 0 }, { id: 2, offset: 2, partition: 0 }];
      let pollCount = 0;

      source._fetchRecords = jest.fn().mockImplementation(async () => {
        pollCount++;
        if (pollCount <= 1) return records;
        return [];
      });

      const sink = new SinkConnector({ deliveryGuarantee: 'exactly-once' });
      sink._flush = jest.fn().mockImplementation(async function() {
        writeCallCount++;
        if (writeCallCount === 1) {
          throw new Error('timeout: connection reset');
        }
        const batch = this.pendingWrites.splice(0);
        writtenRecords.push(...batch);
        return batch.length;
      });

      const pipeline = new ConnectorPipeline(source, [], sink);
      await pipeline.start();

      // First process: write fails
      await pipeline.processOnce();

      // Second process: should re-process same records, not new ones
      await pipeline.processOnce();

      // Should have written records exactly once
      expect(writtenRecords.length).toBe(2);
    });

    test('transform errors should not fall back to untransformed records', async () => {
      const source = new SourceConnector({ topic: 'test' });
      source._fetchRecords = jest.fn().mockResolvedValueOnce([
        { id: 1, value: 'raw-1', partition: 0, offset: 1 },
        { id: 2, value: 'raw-2', partition: 0, offset: 2 },
      ]).mockResolvedValue([]);

      const sink = new SinkConnector({});
      const writtenRecords = [];
      sink._flush = jest.fn().mockImplementation(async function() {
        writtenRecords.push(...this.pendingWrites.splice(0));
      });

      const badTransform = async (record) => {
        throw new Error('Transform failed');
      };

      const errorHandler = jest.fn();
      const pipeline = new ConnectorPipeline(source, [badTransform], sink);
      pipeline.setErrorHandler(errorHandler);
      await pipeline.start();

      await pipeline.processOnce();

      // On transform error, pipeline should NOT write untransformed data
      // It should either skip the batch or send to dead letter
      expect(writtenRecords.every(r => r.value !== 'raw-1')).toBe(true);
    });
  });

  describe('AlertCorrelationEngine severity ordering', () => {
    test('correlated group severity should reflect actual severity levels not alphabetical', () => {
      const correlator = new AlertCorrelationEngine();

      correlator.addCorrelationRule({
        name: 'infra-alerts',
        metric: 'cpu.usage',
        timeWindow: 300000,
      });

      const alerts = [
        { id: 'a1', metric: 'cpu.usage', severity: 'critical', timestamp: Date.now() },
        { id: 'a2', metric: 'cpu.usage', severity: 'warning', timestamp: Date.now() },
        { id: 'a3', metric: 'cpu.usage', severity: 'info', timestamp: Date.now() },
      ];

      const groups = correlator.correlate(alerts);

      // Group severity should be 'critical' (highest severity)
      // Not 'warning' (alphabetically highest)
      const infraGroup = groups.find(g => g.rule === 'infra-alerts');
      expect(infraGroup).toBeDefined();
      expect(infraGroup.severity).toBe('critical');
    });

    test('root cause should be the earliest alert, not the first in array', () => {
      const correlator = new AlertCorrelationEngine();

      correlator.addCorrelationRule({
        name: 'disk-alerts',
        metric: 'disk.usage',
        timeWindow: 600000,
      });

      const now = Date.now();
      const alerts = [
        { id: 'a3', metric: 'disk.usage', severity: 'warning', timestamp: now - 5000, createdAt: now - 5000 },
        { id: 'a1', metric: 'disk.usage', severity: 'critical', timestamp: now - 30000, createdAt: now - 30000 },
        { id: 'a2', metric: 'disk.usage', severity: 'warning', timestamp: now - 15000, createdAt: now - 15000 },
      ];

      const groups = correlator.correlate(alerts);
      const diskGroup = groups.find(g => g.rule === 'disk-alerts');

      // Root cause should be alert a1 (earliest at now - 30000)
      expect(diskGroup.rootCause.id).toBe('a1');
    });
  });

  describe('ContentBasedRouter priority ordering', () => {
    test('higher priority rules should match before lower priority ones', async () => {
      const router = new ContentBasedRouter();

      router.addRule({
        name: 'low-priority',
        condition: (msg) => msg.type === 'event',
        destination: 'low-queue',
        priority: 1,
      });

      router.addRule({
        name: 'high-priority',
        condition: (msg) => msg.type === 'event' && msg.severity === 'critical',
        destination: 'high-queue',
        priority: 10,
      });

      const message = { type: 'event', severity: 'critical' };
      const result = await router.route(message);

      // High priority rule should match first
      expect(result.destination).toBe('high-queue');
      expect(result.rule).toBe('high-priority');
    });

    test('dead letter handler should be called for unmatched messages', async () => {
      const router = new ContentBasedRouter();
      const deadLetterHandler = jest.fn();
      router.setDeadLetterHandler(deadLetterHandler);

      router.addRule({
        name: 'specific-rule',
        condition: (msg) => msg.type === 'specific',
        destination: 'specific-queue',
        priority: 1,
      });

      const message = { type: 'unknown' };
      const result = await router.route(message);

      expect(result.destination).toBe('dead-letter');
      expect(deadLetterHandler).toHaveBeenCalledWith(message);
    });
  });

  describe('RollupEngine histogram boundary precision', () => {
    test('values exactly at bucket boundary should be counted in correct bucket', () => {
      const engine = new RollupEngine();

      const values = [0, 5, 10, 15, 20, 25, 30];
      const buckets = [10, 20, 30];

      const histogram = engine.buildHistogram(values, buckets);

      // Bucket [0, 10]: should include 0, 5, 10 (3 values)
      // Bucket [10, 20]: should include 15, 20 (but 10 goes here due to <= boundary)
      // Bucket [20, 30]: should include 25, 30
      // Overflow: empty

      // Value 10 should be in the <=10 bucket
      expect(histogram[0].count).toBe(3); // 0, 5, 10
      expect(histogram[1].count).toBe(2); // 15, 20
      expect(histogram[2].count).toBe(2); // 25, 30
    });

    test('cross-stream join should handle asymmetric timestamps correctly', () => {
      const engine = new RollupEngine();

      const left = [
        { id: 'a', timestamp: 1000, leftData: 'L1' },
        { id: 'b', timestamp: 2000, leftData: 'L2' },
      ];

      const right = [
        { id: 'a', timestamp: 1500, rightData: 'R1' },
        { id: 'b', timestamp: 5000, rightData: 'R2' },
      ];

      const results = engine.crossStreamJoin(left, right, 'id', 1000);

      // id='a': |1000-1500| = 500 <= 1000, should join
      // id='b': |2000-5000| = 3000 > 1000, should NOT join
      expect(results.length).toBe(1);
      expect(results[0].id).toBe('a');
      expect(results[0].leftData).toBe('L1');
      expect(results[0].rightData).toBe('R1');
    });
  });
});
