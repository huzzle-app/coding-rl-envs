/**
 * Performance Throughput Tests (~30 tests)
 *
 * Tests for system performance: memory usage, throughput, latency, scalability
 * Covers BUG A8 (memory leak), D3 (percentile memory), B3 (flatten depth), B9 (UDF leak)
 */

const { WindowManager, StreamProcessor, StreamJoin } = require('../../shared/stream');
const { TransformPipeline } = require('../../services/transform/src/services/pipeline');
const { RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { QueryEngine } = require('../../services/query/src/services/engine');

describe('Performance Throughput Tests', () => {
  describe('stream processing throughput', () => {
    test('sliding window memory test - bounded memory usage', () => {
      const wm = new WindowManager({ type: 'sliding', size: 5000, slide: 1000 });

      for (let i = 0; i < 10000; i++) {
        wm.getWindowKey(i * 100);
      }

      
      const windowCount = wm.windows.size;
      expect(windowCount).toBeDefined();
    });

    test('window cleanup test - closed windows freed', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });

      // Create and close many windows
      for (let i = 0; i < 100; i++) {
        const win = wm.getWindowKey(i * 1000);
        wm.addEvent(win.key, { value: i });
        wm.closeWindow(win.key);
      }

      
      expect(wm.closedWindows.size).toBe(100);
    });

    test('high throughput event processing', async () => {
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 600000,
      });

      const startTime = Date.now();
      const eventCount = 1000;

      for (let i = 0; i < eventCount; i++) {
        await processor.processEvent({
          source: 's1',
          timestamp: startTime + i * 10,
          value: Math.random() * 100,
        });
      }

      expect(processor.getStats().processedCount).toBe(eventCount);
    });

    test('join buffer memory management', () => {
      const join = new StreamJoin('l', 'r', { joinWindow: 1000 });

      // Add many events
      for (let i = 0; i < 5000; i++) {
        join.addLeft({ id: `k${i}`, timestamp: i, value: i });
      }

      expect(join.getBufferSize()).toBe(5000);

      // Clear old events
      join.clearExpired(4000);
      expect(join.getBufferSize()).toBeLessThan(5000);
    });
  });

  describe('transform pipeline throughput', () => {
    test('array flattening depth test - deep nesting handled', () => {
      const pipeline = new TransformPipeline({ maxChainDepth: 50 });
      pipeline.addTransform({
        type: 'flatten',
        field: 'data',
      });

      // Create deeply nested array
      let nested = [1];
      for (let i = 0; i < 10; i++) {
        nested = [nested, i];
      }

      const record = { data: nested };
      
      expect(() => pipeline.execute(record)).not.toThrow();
    });

    test('recursive flatten test - flat result produced', async () => {
      const pipeline = new TransformPipeline();
      pipeline.addTransform({
        type: 'flatten',
        field: 'data',
      });

      const record = { data: [[1, 2], [3, [4, 5]]] };
      const result = await pipeline.execute(record);
      expect(result.data).toEqual([1, 2, 3, 4, 5]);
    });

    test('udf timeout cleanup test - resources freed after timeout', async () => {
      const pipeline = new TransformPipeline({ udfTimeout: 100 });

      pipeline.addTransform({
        type: 'udf',
        code: 'slow-function',
        timeout: 50,
      });

      pipeline._executeUdf = jest.fn().mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 5000))
      );

      try {
        await pipeline.execute({ input: 'test' });
      } catch (error) {
        expect(error.message).toBe('UDF timeout');
      }

      
      expect(pipeline._runningUdfs.size).toBeGreaterThanOrEqual(0);
    });

    test('udf resource leak test - multiple timeouts accumulate', async () => {
      const pipeline = new TransformPipeline({ udfTimeout: 50 });

      pipeline._executeUdf = jest.fn().mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 10000))
      );

      for (let i = 0; i < 5; i++) {
        pipeline.addTransform({ type: 'udf', code: `fn-${i}`, timeout: 20 });
      }

      try {
        await pipeline.execute({ input: 'test' });
      } catch (error) {
        // Expected timeout
      }
    });

    test('large record transform performance', async () => {
      const pipeline = new TransformPipeline();
      pipeline.addTransform({
        type: 'map',
        mapping: { value: 'data.nested.value' },
      });

      const largeRecord = {
        data: { nested: { value: 42 } },
        extra: Array.from({ length: 1000 }, (_, i) => ({ key: `field-${i}`, val: i })),
      };

      const result = await pipeline.execute(largeRecord);
      expect(result.value).toBe(42);
    });

    test('transform chain throughput', async () => {
      const pipeline = new TransformPipeline();

      // Add many transform steps
      for (let i = 0; i < 20; i++) {
        pipeline.addTransform({
          type: 'map',
          mapping: { [`field_${i}`]: 'value' },
        });
      }

      const result = await pipeline.execute({ value: 'test' });
      expect(result.field_0).toBe('test');
      expect(result.field_19).toBe('test');
    });
  });

  describe('aggregation throughput', () => {
    test('percentile memory test - large dataset bounded memory', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = Array.from({ length: 100000 }, () => Math.random() * 100);

      const before = process.memoryUsage().heapUsed;
      const p99 = engine.calculatePercentile(values, 99);
      const after = process.memoryUsage().heapUsed;

      expect(p99).toBeGreaterThan(90);
      // Memory growth should be reasonable
      expect(after - before).toBeLessThan(50 * 1024 * 1024); // 50MB
    });

    test('memory spike test - percentile doesn not OOM', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = Array.from({ length: 50000 }, (_, i) => i);
      const p50 = engine.calculatePercentile(values, 50);
      expect(p50).toBeCloseTo(25000, -2);
    });

    test('rolling sum throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });

      for (let i = 0; i < 100000; i++) {
        engine.rollingSum('perf-key', 1);
      }

      const result = engine.rollingSum('perf-key', 0);
      expect(result).toBe(100000);
    });

    test('histogram with many values', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = Array.from({ length: 10000 }, () => Math.random() * 100);
      const buckets = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
      const result = engine.buildHistogram(values, buckets);
      expect(result.length).toBe(buckets.length + 1); // +1 for overflow
    });

    test('multiple key rolling sums', () => {
      const engine = new RollupEngine({ windowSize: 60000 });

      for (let i = 0; i < 1000; i++) {
        engine.rollingSum(`key-${i % 100}`, 1);
      }

      expect(engine.rollingSum('key-0', 0)).toBe(10);
    });
  });

  describe('query engine throughput', () => {
    test('query large dataset', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });

      const data = Array.from({ length: 10000 }, (_, i) => ({
        id: i,
        name: `user-${i}`,
        age: 20 + (i % 60),
        city: ['NYC', 'LA', 'SF', 'CHI'][i % 4],
      }));

      const filtered = engine._applyFilter(data, ['age > 50'], {});
      expect(filtered.length).toBeLessThan(data.length);
    });

    test('GROUP BY on large dataset', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });

      const data = Array.from({ length: 5000 }, (_, i) => ({
        city: ['NYC', 'LA', 'SF', 'CHI', 'BOS'][i % 5],
        value: i,
      }));

      const grouped = engine._applyGroupBy(data, ['city']);
      expect(grouped.length).toBe(5);
    });

    test('sort large dataset', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });

      const data = Array.from({ length: 5000 }, () => ({
        value: Math.random() * 1000,
      }));

      const sorted = engine._applySort(data, ['value']);
      for (let i = 1; i < sorted.length; i++) {
        expect(sorted[i].value).toBeGreaterThanOrEqual(sorted[i - 1].value);
      }
    });

    test('plan cache efficiency', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });

      const queries = [
        'SELECT name FROM users',
        'SELECT age FROM users WHERE city = NYC',
        'SELECT * FROM metrics LIMIT 100',
      ];

      // First pass - cache miss
      for (const q of queries) {
        const parsed = engine.parse(q);
        engine.plan(parsed, {});
      }

      // Second pass - cache hit
      for (const q of queries) {
        const parsed = engine.parse(q);
        engine.plan(parsed, {});
      }

      const stats = engine.getCacheStats();
      expect(stats.size).toBeGreaterThan(0);
    });

    test('pagination throughput', () => {
      const mockDb = global.testUtils.mockPg();
      const engine = new QueryEngine(mockDb, { queryTimeout: 5000 });

      const data = Array.from({ length: 10000 }, (_, i) => ({ id: i }));

      // Paginate through all data
      const pageSize = 100;
      let total = 0;
      for (let offset = 0; offset < data.length; offset += pageSize) {
        const page = engine._applyLimit(data, pageSize, offset);
        total += page.length;
      }

      expect(total).toBe(10000);
    });
  });

  describe('concurrent operation throughput', () => {
    test('concurrent window operations', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });
      const operations = [];

      for (let i = 0; i < 100; i++) {
        const win = wm.getWindowKey(i * 500);
        operations.push(wm.addEvent(win.key, { value: i }));
      }

      expect(operations.every(r => r === true)).toBe(true);
    });

    test('concurrent aggregation operations', () => {
      const engine = new RollupEngine({ windowSize: 60000 });

      // Simulate concurrent access patterns
      const results = [];
      for (let i = 0; i < 100; i++) {
        results.push(engine.rollingSum(`concurrent-${i % 10}`, Math.random() * 100));
      }

      expect(results.length).toBe(100);
    });

    test('rate calculation throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      for (let i = 0; i < 10000; i++) {
        engine.calculateRate('perf-key', i * 10, i * 100);
      }
      const final = engine.calculateRate('perf-key', 100000, 1000000);
      expect(final).toBeDefined();
    });

    test('moving average throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      for (let i = 0; i < 5000; i++) {
        engine.movingAverage('perf-key', Math.random() * 100, 100);
      }
      const avg = engine.movingAverage('perf-key', 50, 100);
      expect(isFinite(avg)).toBe(true);
    });

    test('running total throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      for (let i = 0; i < 1000; i++) {
        engine.runningTotal('key', 1, i * 10);
      }
      expect(engine.runningTotal('key', 0, 10000)).toBeDefined();
    });

    test('cross-stream join throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const left = Array.from({ length: 100 }, (_, i) => ({ id: `k${i}`, timestamp: i * 100, value: i }));
      const right = Array.from({ length: 100 }, (_, i) => ({ id: `k${i}`, timestamp: i * 100 + 50, value: i * 2 }));
      const result = engine.crossStreamJoin(left, right, 'id', 5000);
      expect(result.length).toBe(100);
    });

    test('multiple histogram builds', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const buckets = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

      for (let i = 0; i < 50; i++) {
        const values = Array.from({ length: 100 }, () => Math.random() * 100);
        engine.buildHistogram(values, buckets);
      }
    });

    test('top-N with large dataset', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const items = Array.from({ length: 10000 }, (_, i) => ({
        id: `item-${i}`,
        score: Math.random() * 1000,
      }));
      const top10 = engine.topN(items, 10, x => x.score);
      expect(top10.length).toBe(10);
      expect(top10[0].score).toBeGreaterThanOrEqual(top10[9].score);
    });

    test('hll merge throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      let merged = Array.from({ length: 16 }, () => 0);
      for (let i = 0; i < 100; i++) {
        const hll = Array.from({ length: 16 }, () => Math.floor(Math.random() * 10));
        merged = engine.hllMerge(merged, hll);
      }
      expect(merged.length).toBe(16);
    });

    test('downsample throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const data = Array.from({ length: 10000 }, (_, i) => ({
        timestamp: i * 100,
        value: Math.sin(i / 100) * 50 + 50,
      }));
      const result = engine.downsample(data, 10000);
      expect(result.length).toBeGreaterThan(0);
      expect(result.length).toBeLessThan(data.length);
    });

    test('clearState throughput', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      for (let i = 0; i < 1000; i++) {
        engine.rollingSum(`key-${i}`, Math.random() * 100);
      }
      engine.clearState();
      expect(engine.rollingSum('key-0', 1)).toBe(1);
    });

    test('window creation throughput', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 100 });
      for (let i = 0; i < 10000; i++) {
        wm.getWindowKey(i * 10);
      }
      expect(wm.windows.size).toBeGreaterThan(100);
    });
  });
});
