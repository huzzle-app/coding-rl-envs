/**
 * Aggregation Rollup Tests (~40 tests)
 *
 * Tests for BUG D1-D10 aggregation bugs
 */

const { RollupEngine, ContinuousAggregation, StreamAggregator } = require('../../../services/aggregate/src/services/rollups');

describe('RollupEngine', () => {
  let engine;

  beforeEach(() => {
    engine = new RollupEngine({ windowSize: 60000 });
  });

  describe('rolling sum (D1)', () => {
    test('integer overflow test - handles values near MAX_SAFE_INTEGER', () => {
      engine.rollingSum('key', Number.MAX_SAFE_INTEGER - 1);
      const result = engine.rollingSum('key', 2);
      expect(Number.isSafeInteger(result)).toBe(true);
    });

    test('rolling sum accumulates correctly', () => {
      engine.rollingSum('key', 10);
      engine.rollingSum('key', 20);
      const result = engine.rollingSum('key', 30);
      expect(result).toBe(60);
    });

    test('different keys have independent sums', () => {
      engine.rollingSum('a', 10);
      engine.rollingSum('b', 20);
      expect(engine.rollingSum('a', 5)).toBe(15);
      expect(engine.rollingSum('b', 5)).toBe(25);
    });
  });

  describe('downsampling (D2)', () => {
    test('downsample precision test - sub-second precision preserved', () => {
      const data = [
        { timestamp: 1000.5, value: 10 },
        { timestamp: 1000.7, value: 20 },
        { timestamp: 2000.3, value: 30 },
      ];
      const result = engine.downsample(data, 500);
      expect(result.length).toBeGreaterThanOrEqual(2);
    });

    test('alias precision test - timestamps accurate to millisecond', () => {
      const data = [
        { timestamp: 1000, value: 10 },
        { timestamp: 2000, value: 20 },
      ];
      const result = engine.downsample(data, 1000);
      expect(result[0].timestamp).toBe(1000);
    });

    test('downsample computes correct averages', () => {
      const data = [
        { timestamp: 0, value: 10 },
        { timestamp: 500, value: 20 },
      ];
      const result = engine.downsample(data, 1000);
      expect(result[0].avg).toBe(15);
    });

    test('empty data returns empty result', () => {
      const result = engine.downsample([], 1000);
      expect(result).toEqual([]);
    });
  });

  describe('percentile (D3)', () => {
    test('percentile memory test - handles large datasets', () => {
      const values = Array.from({ length: 100000 }, () => Math.random() * 100);
      const p99 = engine.calculatePercentile(values, 99);
      expect(p99).toBeGreaterThan(90);
    });

    test('memory spike test - bounded memory usage', () => {
      const values = Array.from({ length: 10000 }, (_, i) => i);
      const p50 = engine.calculatePercentile(values, 50);
      expect(p50).toBeCloseTo(5000, -2);
    });

    test('percentile of single value', () => {
      expect(engine.calculatePercentile([42], 50)).toBe(42);
    });

    test('percentile of sorted values', () => {
      const values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      expect(engine.calculatePercentile(values, 50)).toBe(5);
    });
  });

  describe('HyperLogLog (D4)', () => {
    test('hll merge error test - uses max not sum for register merge', () => {
      const hll1 = [3, 5, 2, 7];
      const hll2 = [4, 3, 6, 1];
      const merged = engine.hllMerge(hll1, hll2);
      expect(merged[0]).toBe(Math.max(3, 4));
      expect(merged[1]).toBe(Math.max(5, 3));
      expect(merged[2]).toBe(Math.max(2, 6));
      expect(merged[3]).toBe(Math.max(7, 1));
    });

    test('count distinct merge test - merged count correct', () => {
      const hll1 = [3, 5, 2, 7];
      const hll2 = [4, 3, 6, 1];
      const merged = engine.hllMerge(hll1, hll2);
      const count = engine.hllCount(merged);
      expect(count).toBeGreaterThan(0);
    });

    test('hll merge with null returns other', () => {
      const hll1 = [3, 5, 2, 7];
      expect(engine.hllMerge(hll1, null)).toBe(hll1);
      expect(engine.hllMerge(null, hll1)).toBe(hll1);
    });

    test('hll count of empty registers returns 0', () => {
      expect(engine.hllCount([])).toBe(0);
      expect(engine.hllCount(null)).toBe(0);
    });
  });

  describe('moving average (D5)', () => {
    test('moving average zero test - empty window handled gracefully', () => {
      const result = engine.movingAverage('key', 10, 0);
      expect(isFinite(result)).toBe(true);
    });

    test('denominator zero test - zero window size doesnt produce NaN', () => {
      const result = engine.movingAverage('key', 10, 0);
      expect(isNaN(result)).toBe(false);
    });

    test('moving average of single value', () => {
      const result = engine.movingAverage('key', 10, 5);
      expect(result).toBe(10);
    });

    test('moving average window slides', () => {
      engine.movingAverage('key', 10, 3);
      engine.movingAverage('key', 20, 3);
      engine.movingAverage('key', 30, 3);
      const result = engine.movingAverage('key', 40, 3);
      expect(result).toBeCloseTo(30, 0);
    });
  });

  describe('rate calculation (D6)', () => {
    test('rate clock skew test - negative time delta handled', () => {
      engine.calculateRate('key', 100, 2000);
      const result = engine.calculateRate('key', 200, 1000);
      expect(result).toBeGreaterThanOrEqual(0);
    });

    test('clock skew calculation test - correct rate with normal time', () => {
      engine.calculateRate('key', 100, 1000);
      const result = engine.calculateRate('key', 200, 2000);
      expect(result).toBe(100);
    });

    test('first rate call returns zero', () => {
      const result = engine.calculateRate('key', 100, 1000);
      expect(result).toBe(0);
    });

    test('zero time delta returns zero', () => {
      engine.calculateRate('key', 100, 1000);
      const result = engine.calculateRate('key', 200, 1000);
      expect(result).toBe(0);
    });
  });

  describe('histogram (D7)', () => {
    test('histogram float boundary test - boundary values in correct bucket', () => {
      const values = [10, 20, 30];
      const buckets = [10, 20, 30];
      const result = engine.buildHistogram(values, buckets);
      expect(result[0].count).toBe(1);
    });

    test('bucket comparison test - value equal to boundary goes to that bucket', () => {
      const values = [10.0];
      const buckets = [10.0, 20.0];
      const result = engine.buildHistogram(values, buckets);
      expect(result[0].count + result[1].count).toBe(1);
      expect(result[result.length - 1].le).toBe('+Inf');
    });

    test('values above all buckets go to overflow', () => {
      const values = [100];
      const buckets = [10, 20, 30];
      const result = engine.buildHistogram(values, buckets);
      expect(result[result.length - 1].count).toBe(1);
    });

    test('empty values produce zero counts', () => {
      const result = engine.buildHistogram([], [10, 20, 30]);
      expect(result.every(b => b.count === 0)).toBe(true);
    });
  });

  describe('top-N (D8)', () => {
    test('top-n tiebreak test - consistent ordering for equal values', () => {
      const items = [
        { id: 'a', score: 100 },
        { id: 'b', score: 100 },
        { id: 'c', score: 100 },
      ];
      const result1 = engine.topN(items, 2, x => x.score);
      const result2 = engine.topN(items, 2, x => x.score);
      expect(result1.map(r => r.id)).toEqual(result2.map(r => r.id));
    });

    test('consistent ordering test - top-N is deterministic', () => {
      const items = Array.from({ length: 10 }, (_, i) => ({ id: `item-${i}`, score: i % 3 }));
      const r1 = engine.topN(items, 5, x => x.score);
      const r2 = engine.topN(items, 5, x => x.score);
      expect(r1.map(r => r.id)).toEqual(r2.map(r => r.id));
    });
  });

  describe('running total (D9)', () => {
    test('running total reset test - resets at window boundary', () => {
      engine.runningTotal('key', 10, 0);
      engine.runningTotal('key', 20, 0);
      const afterReset = engine.runningTotal('key', 5, 60000);
      expect(afterReset).toBe(5);
    });

    test('boundary reset test - boundary event goes to new window', () => {
      engine.runningTotal('key', 10, 0);
      const atBoundary = engine.runningTotal('key', 20, 60000);
      expect(atBoundary).toBe(20);
    });

    test('accumulates within window', () => {
      engine.runningTotal('key', 10, 0);
      const total = engine.runningTotal('key', 20, 0);
      expect(total).toBe(30);
    });
  });

  describe('cross-stream join (D10)', () => {
    test('cross-stream watermark test - joins within time window', () => {
      const left = [{ id: 'k1', timestamp: 1000, value: 10 }];
      const right = [{ id: 'k1', timestamp: 2000, value: 20 }];
      const result = engine.crossStreamJoin(left, right, 'id', 5000);
      expect(result.length).toBe(1);
    });

    test('join alignment test - outside window produces no results', () => {
      const left = [{ id: 'k1', timestamp: 1000, value: 10 }];
      const right = [{ id: 'k1', timestamp: 100000, value: 20 }];
      const result = engine.crossStreamJoin(left, right, 'id', 5000);
      expect(result.length).toBe(0);
    });

    test('different keys produce no results', () => {
      const left = [{ id: 'k1', timestamp: 1000 }];
      const right = [{ id: 'k2', timestamp: 2000 }];
      const result = engine.crossStreamJoin(left, right, 'id', 5000);
      expect(result.length).toBe(0);
    });
  });

  describe('state management', () => {
    test('clearState removes all state', () => {
      engine.rollingSum('key', 10);
      engine.clearState();
      expect(engine.rollingSum('key', 5)).toBe(5);
    });

    test('clearState affects all keys', () => {
      engine.rollingSum('a', 10);
      engine.rollingSum('b', 20);
      engine.clearState();
      expect(engine.rollingSum('a', 1)).toBe(1);
      expect(engine.rollingSum('b', 2)).toBe(2);
    });
  });

  describe('additional rolling sum', () => {
    test('negative values accumulated correctly', () => {
      engine.rollingSum('key', 10);
      engine.rollingSum('key', -5);
      const result = engine.rollingSum('key', 0);
      expect(result).toBe(5);
    });

    test('zero value does not change sum', () => {
      engine.rollingSum('key', 42);
      const result = engine.rollingSum('key', 0);
      expect(result).toBe(42);
    });

    test('float values accumulated', () => {
      engine.rollingSum('key', 0.1);
      engine.rollingSum('key', 0.2);
      const result = engine.rollingSum('key', 0);
      expect(result).toBeCloseTo(0.3, 10);
    });
  });

  describe('additional rate calculation', () => {
    test('rate with equal timestamps returns zero', () => {
      engine.calculateRate('key', 100, 1000);
      const result = engine.calculateRate('key', 200, 1000);
      expect(result).toBe(0);
    });

    test('rate with decreasing value', () => {
      engine.calculateRate('key', 200, 1000);
      const result = engine.calculateRate('key', 100, 2000);
      expect(result).toBeDefined();
    });
  });

  describe('additional downsample', () => {
    test('single point downsample', () => {
      const data = [{ timestamp: 0, value: 42 }];
      const result = engine.downsample(data, 1000);
      expect(result.length).toBe(1);
    });

    test('downsample large dataset', () => {
      const data = Array.from({ length: 1000 }, (_, i) => ({
        timestamp: i * 100,
        value: Math.random() * 100,
      }));
      const result = engine.downsample(data, 10000);
      expect(result.length).toBeGreaterThan(0);
      expect(result.length).toBeLessThan(1000);
    });
  });

  describe('additional top-N', () => {
    test('top-N with N larger than items', () => {
      const items = [{ id: 'a', score: 10 }];
      const result = engine.topN(items, 5, x => x.score);
      expect(result.length).toBe(1);
    });

    test('top-N with N=0 returns empty', () => {
      const items = [{ id: 'a', score: 10 }];
      const result = engine.topN(items, 0, x => x.score);
      expect(result.length).toBe(0);
    });

    test('top-N with different scores', () => {
      const items = [
        { id: 'a', score: 30 },
        { id: 'b', score: 10 },
        { id: 'c', score: 50 },
        { id: 'd', score: 20 },
      ];
      const result = engine.topN(items, 2, x => x.score);
      expect(result[0].score).toBeGreaterThanOrEqual(result[1].score);
    });
  });

  describe('ContinuousAggregation avg formula (D9)', () => {
    test('avg of single batch should be correct', () => {
      const agg = new ContinuousAggregation();
      agg.defineMaterialization('m1', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'cpu' }],
      });
      agg.update('m1', [
        { host: 'h1', cpu: 10 },
        { host: 'h1', cpu: 20 },
        { host: 'h1', cpu: 30 },
      ]);
      const state = agg.getState('m1');
      expect(state.state['h1'].cpu_avg).toBeCloseTo(20, 5);
    });

    test('avg across two batches should use correct weighted formula', () => {
      const agg = new ContinuousAggregation();
      agg.defineMaterialization('m2', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'cpu' }],
      });
      agg.update('m2', [
        { host: 'h1', cpu: 10 },
        { host: 'h1', cpu: 20 },
      ]);
      agg.update('m2', [{ host: 'h1', cpu: 30 }]);
      const state = agg.getState('m2');
      // True avg = (10+20+30)/3 = 20, buggy = (15+30)/2 = 22.5
      expect(state.state['h1'].cpu_avg).toBeCloseTo(20, 5);
    });

    test('avg across many single-value batches should converge to true mean', () => {
      const agg = new ContinuousAggregation();
      agg.defineMaterialization('m3', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'val' }],
      });
      const values = [100, 200, 300, 400, 500];
      for (const v of values) {
        agg.update('m3', [{ host: 'h1', val: v }]);
      }
      const state = agg.getState('m3');
      expect(state.state['h1'].val_avg).toBeCloseTo(300, 5);
    });

    test('avg count should track actual number of records', () => {
      const agg = new ContinuousAggregation();
      agg.defineMaterialization('m4', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'x' }],
      });
      agg.update('m4', [{ host: 'h1', x: 1 }, { host: 'h1', x: 2 }]);
      agg.update('m4', [{ host: 'h1', x: 3 }, { host: 'h1', x: 4 }]);
      const state = agg.getState('m4');
      expect(state.state['h1'].x_count).toBe(4);
    });
  });

  describe('RollupEngine moving average boundary (D5)', () => {
    test('moving average at exact window boundary should drop oldest value', () => {
      const engine = new RollupEngine({ windowSize: 3 });
      engine.addDataPoint('metric1', 10);
      engine.addDataPoint('metric1', 20);
      engine.addDataPoint('metric1', 30);
      engine.addDataPoint('metric1', 40);
      const avg = engine.getMovingAverage('metric1');
      // Window of 3: should be avg of [20,30,40] = 30
      expect(avg).toBeCloseTo(30, 5);
    });
  });

  describe('RollupEngine HLL merge (D7)', () => {
    test('HLL merge should use max, not sum', () => {
      const engine = new RollupEngine({});
      const hll1 = [5, 3, 7, 2];
      const hll2 = [4, 8, 1, 6];
      const merged = engine.mergeHLL(hll1, hll2);
      // Element-wise max: [5,8,7,6]
      expect(merged).toEqual([5, 8, 7, 6]);
    });

    test('HLL count after merge should not over-estimate', () => {
      const engine = new RollupEngine({});
      const hll1 = [3, 3, 3, 3];
      const hll2 = [3, 3, 3, 3];
      const merged = engine.mergeHLL(hll1, hll2);
      // Max of identical arrays: still [3,3,3,3], not [6,6,6,6]
      for (let i = 0; i < merged.length; i++) {
        expect(merged[i]).toBe(Math.max(hll1[i], hll2[i]));
      }
    });
  });
});
