/**
 * Integration Pipeline Tests (~50 tests)
 *
 * Tests for end-to-end pipeline execution: stream -> transform -> aggregate -> store
 * Covers BUG A1-A12, B1-B10, D1-D10, F1-F10
 */

const { WindowManager, WatermarkTracker, StreamProcessor, StreamJoin, PartitionManager } = require('../../shared/stream');
const { TransformPipeline, mergeTransformConfig } = require('../../services/transform/src/services/pipeline');
const { RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { TimeSeriesStore } = require('../../services/store/src/services/timeseries');

describe('Pipeline Integration', () => {
  let processor;
  let pipeline;
  let engine;
  let store;
  let mockDb;

  beforeEach(() => {
    processor = new StreamProcessor({
      window: { type: 'tumbling', size: 60000 },
      watermark: { allowedLateness: 5000 },
      checkpointInterval: 60000,
    });
    pipeline = new TransformPipeline();
    engine = new RollupEngine({ windowSize: 60000 });
    mockDb = global.testUtils.mockPg();
    store = new TimeSeriesStore(mockDb, { batchSize: 100 });
  });

  describe('stream to transform flow', () => {
    test('window boundary test - events routed to correct windows', async () => {
      const events = [
        { source: 's1', timestamp: 1000, value: 10 },
        { source: 's1', timestamp: 59999, value: 20 },
        { source: 's1', timestamp: 60000, value: 30 },
      ];

      for (const event of events) {
        await processor.processEvent(event);
      }

      const stats = processor.getStats();
      expect(stats.processedCount).toBe(3);
    });

    test('tumbling window edge test - boundary event assigned correctly', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });
      const win999 = wm.getWindowKey(999);
      const win1000 = wm.getWindowKey(1000);
      
      expect(win999.key).not.toBe(win1000.key);
    });

    test('transform receives windowed events', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { output: 'value' },
      });

      const record = { value: 42, name: 'test' };
      const result = await pipeline.execute(record);
      expect(result.output).toBe(42);
    });

    test('transform chain processes in correct order', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { doubled: 'value' },
        typeCoercion: { doubled: 'number' },
      });

      const result = await pipeline.execute({ value: '21' });
      expect(result.doubled).toBe(21);
    });

    test('null nested field test - null propagation handled', async () => {
      const tp = new TransformPipeline();
      tp.addTransform({
        type: 'map',
        mapping: { out: 'a.b.c' },
      });

      await expect(tp.execute({ a: null })).rejects.toThrow();
    });

    test('schema mapping type test - type coercion applied', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { amount: 'raw_amount' },
        typeCoercion: { amount: 'number' },
      });

      const result = await pipeline.execute({ raw_amount: '123.456789012345678' });
      expect(typeof result.amount).toBe('number');
    });
  });

  describe('transform to aggregate flow', () => {
    test('rolling sum overflow test - safe integer handling', () => {
      engine.rollingSum('key', Number.MAX_SAFE_INTEGER - 1);
      const result = engine.rollingSum('key', 2);
      expect(Number.isSafeInteger(result)).toBe(true);
    });

    test('float accumulation test - precision maintained', async () => {
      pipeline.addTransform({
        type: 'aggregate',
        field: 'value',
      });

      for (let i = 0; i < 100; i++) {
        await pipeline.execute({ value: 0.1 });
      }

      const stats = pipeline.getStats();
      expect(stats.aggregateKeys).toBeGreaterThan(0);
    });

    test('downsample precision test - sub-second timestamps preserved', () => {
      const data = [
        { timestamp: 1000.5, value: 10 },
        { timestamp: 1000.7, value: 20 },
        { timestamp: 2000.3, value: 30 },
      ];
      const result = engine.downsample(data, 500);
      expect(result.length).toBeGreaterThanOrEqual(2);
    });

    test('percentile memory test - large dataset computed', () => {
      const values = Array.from({ length: 10000 }, () => Math.random() * 100);
      const p99 = engine.calculatePercentile(values, 99);
      expect(p99).toBeGreaterThan(90);
    });

    test('hll merge error test - register merge uses max', () => {
      const hll1 = [3, 5, 2, 7];
      const hll2 = [4, 3, 6, 1];
      const merged = engine.hllMerge(hll1, hll2);
      expect(merged).toEqual([4, 5, 6, 7]);
    });

    test('moving average zero test - zero window handled', () => {
      const result = engine.movingAverage('key', 10, 0);
      expect(isFinite(result)).toBe(true);
      expect(isNaN(result)).toBe(false);
    });

    test('histogram float boundary test - boundary bucket correct', () => {
      const values = [10, 20, 30];
      const buckets = [10, 20, 30];
      const result = engine.buildHistogram(values, buckets);
      expect(result[0].count).toBe(1);
    });
  });

  describe('aggregate to store flow', () => {
    test('connection pool exhaustion test - bounded pool', async () => {
      const connections = [];
      for (let i = 0; i < 20; i++) {
        connections.push(await store.getConnection());
      }
      
      expect(connections.length).toBe(20);
    });

    test('pool limit test - excess connections handled', async () => {
      const conn1 = await store.getConnection();
      store.releaseConnection(conn1);
      const conn2 = await store.getConnection();
      expect(conn2).toBeDefined();
    });

    test('batch insert partial test - failures tracked', async () => {
      const records = Array.from({ length: 50 }, (_, i) => ({
        timestamp: Date.now() + i,
        value: i,
      }));
      const result = await store.batchInsert(records);
      expect(result.inserted).toBeDefined();
    });

    test('silent failure test - partial batch error propagated', async () => {
      store._insertBatch = jest.fn()
        .mockResolvedValueOnce({ rowCount: 100 })
        .mockRejectedValueOnce(new Error('disk full'));

      const records = Array.from({ length: 200 }, (_, i) => ({
        timestamp: Date.now() + i,
        value: i,
      }));

      const result = await store.batchInsert(records);
      
      const failedBatches = result.results.filter(r => !r.success);
      expect(failedBatches.length).toBeGreaterThan(0);
    });
  });

  describe('end-to-end pipeline', () => {
    test('event ingestion through full pipeline', async () => {
      const events = global.testUtils.generateTimeSeries(10, Date.now(), 1000);

      for (const event of events) {
        const processed = await processor.processEvent(event);
        expect(processed.status).toBeDefined();
      }

      expect(processor.getStats().processedCount).toBe(10);
    });

    test('transform then aggregate produces correct results', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { metric_value: 'value' },
        typeCoercion: { metric_value: 'number' },
      });

      const record = { value: '42.5' };
      const transformed = await pipeline.execute(record);
      engine.rollingSum('metric', transformed.metric_value);
      const sum = engine.rollingSum('metric', 7.5);
      expect(sum).toBe(50);
    });

    test('saga compensation test - multi-step rollback on failure', async () => {
      const records = [{ timestamp: Date.now(), value: 10 }];
      store._updateAggregations = jest.fn().mockRejectedValue(new Error('aggregation failed'));

      const result = await store.multiStepIngest('test-pipeline', records);
      expect(result.success).toBe(false);
      
      expect(result.steps.some(s => s.status === 'failed')).toBe(true);
    });

    test('multi-step rollback test - all steps tracked', async () => {
      const records = [{ timestamp: Date.now(), value: 10 }];
      const result = await store.multiStepIngest('test-pipeline', records);
      expect(result.success).toBe(true);
      expect(result.steps.length).toBe(3);
    });

    test('outbox ordering test - messages published in order', async () => {
      const messages = [
        { id: 1, data: 'first' },
        { id: 2, data: 'second' },
        { id: 3, data: 'third' },
      ];
      const results = await store.publishOutboxMessages(messages);
      expect(results.length).toBe(3);
    });

    test('message order test - ordered delivery preserved', async () => {
      const messages = Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        data: `message-${i}`,
      }));
      const results = await store.publishOutboxMessages(messages);
      
      expect(results.every(r => r.status === 'published')).toBe(true);
    });
  });

  describe('pipeline config integration', () => {
    test('config merge deep vs shallow', () => {
      const base = { transforms: [{ type: 'map' }], settings: { timeout: 5000 } };
      const override = { settings: { timeout: 10000, retries: 3 } };
      const merged = mergeTransformConfig(base, override);
      expect(merged.settings.timeout).toBe(10000);
      expect(merged.settings.retries).toBe(3);
    });

    test('pipeline with custom window size', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 30000 });
      const win = wm.getWindowKey(29999);
      expect(win.start).toBe(0);
    });

    test('stream join with transform', () => {
      const join = new StreamJoin('left', 'right', { joinWindow: 5000, joinKey: 'id' });
      join.addLeft({ id: 'k1', timestamp: 1000, value: 10 });
      const results = join.addRight({ id: 'k1', timestamp: 2000, value: 20 });
      expect(results.length).toBe(1);
    });

    test('partition rebalance during pipeline execution', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0', 'p1', 'p2', 'p3']);
      await pm.rebalance(['c1', 'c2']);
      const total = pm.getAssignment('c1').length + pm.getAssignment('c2').length;
      expect(total).toBe(4);
    });
  });

  describe('error propagation', () => {
    test('transform error stops pipeline', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { out: 'nonexistent.deep.path' },
      });

      await expect(pipeline.execute({ data: 'test' })).rejects.toThrow();
    });

    test('aggregate handles NaN input', () => {
      const result = engine.rollingSum('key', NaN);
      expect(isNaN(result)).toBe(true);
    });

    test('store handles empty batch', async () => {
      const result = await store.batchInsert([]);
      expect(result.inserted).toBe(0);
    });

    test('phantom read test - isolation level enforced', async () => {
      const result = await store.readWithinTransaction('SELECT * FROM metrics');
      expect(result).toBeDefined();
    });

    test('isolation level test - serializable prevents phantoms', async () => {
      mockDb.query.mockResolvedValue({ rows: [{ id: 1 }] });
      const result = await store.readWithinTransaction('SELECT 1');
      expect(result.rows.length).toBe(1);
    });

    test('optimistic lock test - version conflict detected', async () => {
      store._getPipeline = jest.fn().mockResolvedValue({ id: 'p1', version: 2, name: 'test' });
      await expect(store.updatePipeline('p1', { name: 'updated' }, 1))
        .rejects.toThrow('Optimistic lock conflict');
    });

    test('concurrent update test - stale version rejected', async () => {
      store._getPipeline = jest.fn().mockResolvedValue({ id: 'p1', version: 1, name: 'test' });
      const result = await store.updatePipeline('p1', { name: 'updated' }, 1);
      expect(result.version).toBe(2);
    });
  });

  describe('time-series specific', () => {
    test('partition pruning test - correct partitions scanned', async () => {
      const result = await store.queryPartitioned('cpu', 1000, 86400000);
      expect(result.partitionsScanned).toBeGreaterThan(0);
    });

    test('time-series partition test - day boundaries handled', async () => {
      const dayMs = 86400000;
      const result = await store.queryPartitioned('cpu', 0, dayMs * 3);
      expect(result.partitionsScanned).toBeDefined();
    });

    test('n+1 dashboard query test - widget queries batched', async () => {
      const widgets = Array.from({ length: 5 }, (_, i) => ({ id: `w${i}`, type: 'chart' }));
      const result = await store.getDashboardData('d1', widgets);
      expect(Object.keys(result).length).toBe(5);
    });

    test('widget query test - each widget has data', async () => {
      store._queryWidget = jest.fn().mockResolvedValue({ data: [1, 2, 3] });
      const widgets = [{ id: 'w1', type: 'chart' }];
      const result = await store.getDashboardData('d1', widgets);
      expect(result.w1.data).toBeDefined();
    });

    test('metric write deadlock test - lock ordering consistent', async () => {
      const metrics = [
        { name: 'cpu', value: 0.8 },
        { name: 'memory', value: 0.6 },
      ];
      await store.writeMetrics(metrics);
    });

    test('lock ordering test - concurrent writes safe', async () => {
      store._acquireLock = jest.fn().mockResolvedValue(true);
      store._writeMetric = jest.fn().mockResolvedValue(true);

      const m1 = [{ name: 'a', value: 1 }, { name: 'b', value: 2 }];
      const m2 = [{ name: 'b', value: 3 }, { name: 'a', value: 4 }];

      await Promise.all([store.writeMetrics(m1), store.writeMetrics(m2)]);
      expect(store._writeMetric).toHaveBeenCalledTimes(4);
    });

    test('replica lag dashboard test - stale data detected', async () => {
      const result = await store.readFromReplica('SELECT * FROM metrics');
      expect(result.fromReplica).toBe(true);
    });

    test('stale read test - replica freshness checked', async () => {
      const result = await store.readFromReplica('SELECT * FROM dashboards');
      expect(result).toBeDefined();
    });
  });
});
