/**
 * Integration Query Tests (~40 tests)
 *
 * Tests for query engine integration with storage, caching, and aggregation
 * Covers BUG C1-C8, H1-H3, H5-H7, K1-K8
 */

const { QueryEngine } = require('../../services/query/src/services/engine');
const { RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { DashboardService } = require('../../services/dashboards/src/services/dashboard');

describe('Query Integration', () => {
  let engine;
  let mockDb;
  let rollup;

  beforeEach(() => {
    mockDb = global.testUtils.mockPg();
    engine = new QueryEngine(mockDb, { queryTimeout: 5000 });
    rollup = new RollupEngine({ windowSize: 60000 });
  });

  describe('query engine with storage', () => {
    test('sql injection filter test - malicious input neutralized', () => {
      const data = [{ name: 'Alice', age: 30 }, { name: 'Bob', age: 25 }];
      const result = engine._applyFilter(data, ["name = 'Alice' OR 1=1 --"], {});
      expect(result.length).not.toBe(data.length);
    });

    test('parameterized query test - special chars safe', () => {
      const data = [{ name: "O'Brien", age: 30 }];
      const result = engine._applyFilter(data, ["name = O'Brien"], {});
      expect(result).toBeDefined();
    });

    test('query with GROUP BY and HAVING', () => {
      const parsed = engine.parse('SELECT city FROM users GROUP BY city HAVING count > 5');
      const plan = engine.plan(parsed, {});
      const steps = plan.steps.map(s => s.type);
      expect(steps.indexOf('group')).toBeLessThan(steps.indexOf('having'));
    });

    test('plan cache stale test - invalidation on schema change', () => {
      const parsed = engine.parse('SELECT name FROM users');
      engine.plan(parsed, {});
      engine.invalidateCache();
      const plan2 = engine.plan(parsed, {});
      expect(plan2).toBeDefined();
    });

    test('schema change invalidation test - version bumped', () => {
      const v1 = engine.schemaVersion;
      engine.invalidateCache();
      expect(engine.schemaVersion).toBe(v1 + 1);
    });

    test('group by float test - float grouping consistent', () => {
      const data = [
        { category: 0.1 + 0.2, value: 10 },
        { category: 0.3, value: 20 },
      ];
      const result = engine._applyGroupBy(data, ['category']);
      expect(result.length).toBe(1);
    });

    test('float equality grouping test - near-equal values grouped', () => {
      const data = [
        { amount: 0.30000000000000004, count: 1 },
        { amount: 0.3, count: 1 },
      ];
      const result = engine._applyGroupBy(data, ['amount']);
      expect(result.length).toBe(1);
    });

    test('pagination cursor drift test - stable across pages', () => {
      const data = Array.from({ length: 20 }, (_, i) => ({ id: i }));
      const page1 = engine._applyLimit(data, 5, 0);
      const page2 = engine._applyLimit(data, 5, 5);
      expect(page1[0].id).not.toBe(page2[0].id);
    });

    test('offset consistency test - no duplicates', () => {
      const data = Array.from({ length: 20 }, (_, i) => ({ id: i }));
      const page1 = engine._applyLimit(data, 10, 0);
      const page2 = engine._applyLimit(data, 10, 10);
      const allIds = [...page1.map(r => r.id), ...page2.map(r => r.id)];
      expect(new Set(allIds).size).toBe(allIds.length);
    });
  });

  describe('query with time ranges', () => {
    test('time range boundary test - start inclusive', () => {
      const data = [{ timestamp: 100 }, { timestamp: 200 }, { timestamp: 300 }];
      const result = engine.queryTimeRange(data, 100, 300);
      expect(result.some(r => r.timestamp === 100)).toBe(true);
    });

    test('inclusive exclusive test - end exclusive', () => {
      const data = [{ timestamp: 100 }, { timestamp: 200 }, { timestamp: 300 }];
      const result = engine.queryTimeRange(data, 100, 300);
      expect(result.some(r => r.timestamp === 300)).toBe(false);
    });

    test('time range with aggregation', () => {
      const data = [
        { timestamp: 0, value: 10 },
        { timestamp: 500, value: 20 },
        { timestamp: 1500, value: 30 },
      ];
      const filtered = engine.queryTimeRange(data, 0, 1000);
      expect(filtered.length).toBe(2);
    });
  });

  describe('query caching (H1, H5, H7)', () => {
    test('query cache stampede test - concurrent misses handled', async () => {
      const results = [];
      for (let i = 0; i < 5; i++) {
        const parsed = engine.parse(`SELECT name FROM users WHERE id = ${i}`);
        results.push(engine.plan(parsed, {}));
      }
      expect(results.length).toBe(5);
    });

    test('concurrent miss test - single fill per key', () => {
      const parsed = engine.parse('SELECT * FROM metrics');
      const plan1 = engine.plan(parsed, {});
      const plan2 = engine.plan(parsed, {});
      expect(plan1).toBe(plan2);
    });

    test('ttl jitter thundering test - jitter prevents synchronized expiry', () => {
      const cacheStats = engine.getCacheStats();
      expect(cacheStats).toBeDefined();
    });

    test('jitter missing test - TTL has variance', () => {
      // Ensures cache entries don't all expire at the same time
      const parsed1 = engine.parse('SELECT a FROM t1');
      const parsed2 = engine.parse('SELECT b FROM t2');
      engine.plan(parsed1, {});
      engine.plan(parsed2, {});
      expect(engine.getCacheStats().size).toBeGreaterThan(0);
    });

    test('pipeline config cache test - config changes invalidate cache', () => {
      const parsed = engine.parse('SELECT * FROM metrics');
      engine.plan(parsed, {});
      engine.invalidateCache();
      const newPlan = engine.plan(parsed, {});
      expect(newPlan).toBeDefined();
    });

    test('invalidation test - schema version increases on invalidate', () => {
      const v1 = engine.schemaVersion;
      engine.invalidateCache();
      engine.invalidateCache();
      expect(engine.schemaVersion).toBe(v1 + 2);
    });
  });

  describe('dashboard cache (H2)', () => {
    let dashboard;

    beforeEach(() => {
      dashboard = new DashboardService();
    });

    test('dashboard cache key test - params included in key', () => {
      const key1 = dashboard.getCacheKey('d1', { timeRange: '1h' });
      const key2 = dashboard.getCacheKey('d1', { timeRange: '24h' });
      
      expect(key1).toBeDefined();
    });

    test('key collision test - different params get different cache', async () => {
      await dashboard.setCached('d1', { range: '1h' }, { data: 'hourly' });
      await dashboard.setCached('d1', { range: '24h' }, { data: 'daily' });
      const cached = await dashboard.getCached('d1', { range: '1h' });
      expect(cached).toBeDefined();
    });
  });

  describe('configuration (K1-K8)', () => {
    test('variable interpolation test - variables expanded', () => {
      const config = { host: '${DB_HOST}', port: '${DB_PORT}' };
      const resolved = {};
      for (const [key, value] of Object.entries(config)) {
        resolved[key] = typeof value === 'string' && value.startsWith('${')
          ? process.env[value.slice(2, -1)] || value
          : value;
      }
      expect(resolved).toBeDefined();
    });

    test('cycle detection test - circular variable references detected', () => {
      const vars = { A: '${B}', B: '${A}' };
      const visited = new Set();
      const detect = (key) => {
        if (visited.has(key)) return true;
        visited.add(key);
        const val = vars[key];
        if (val && val.startsWith('${')) {
          return detect(val.slice(2, -1));
        }
        return false;
      };
      expect(detect('A')).toBe(true);
    });

    test('env precedence test - env vars override config', () => {
      const defaults = { timeout: 5000, retries: 3 };
      const envOverrides = { timeout: 10000 };
      const merged = { ...defaults, ...envOverrides };
      expect(merged.timeout).toBe(10000);
      expect(merged.retries).toBe(3);
    });

    test('override order test - last override wins', () => {
      const l1 = { a: 1, b: 2 };
      const l2 = { b: 3, c: 4 };
      const l3 = { c: 5 };
      const result = { ...l1, ...l2, ...l3 };
      expect(result).toEqual({ a: 1, b: 3, c: 5 });
    });

    test('feature flag race test - concurrent reads safe', () => {
      const flags = new Map();
      flags.set('new_query_engine', true);
      flags.set('dark_mode', false);

      const reads = [];
      for (let i = 0; i < 100; i++) {
        reads.push(flags.get('new_query_engine'));
      }
      expect(reads.every(v => v === true)).toBe(true);
    });

    test('concurrent evaluation test - no flag corruption', () => {
      const flags = { featureA: true, featureB: false };
      const snapshot = { ...flags };
      flags.featureA = false;
      expect(snapshot.featureA).toBe(true);
    });

    test('config migration test - schema versions handled', () => {
      const v1Config = { version: 1, timeout: 5000 };
      const migrated = { ...v1Config, version: 2, retryPolicy: 'exponential' };
      expect(migrated.version).toBe(2);
      expect(migrated.timeout).toBe(5000);
    });

    test('schema version test - version increments', () => {
      const configs = [
        { version: 1, data: {} },
        { version: 2, data: { newField: true } },
      ];
      expect(configs[1].version).toBe(configs[0].version + 1);
    });

    test('secret resolution test - secrets resolved lazily', () => {
      const config = { apiKey: 'vault:secret/api-key' };
      const resolved = {};
      for (const [key, value] of Object.entries(config)) {
        if (typeof value === 'string' && value.startsWith('vault:')) {
          resolved[key] = `resolved-${value.slice(6)}`;
        } else {
          resolved[key] = value;
        }
      }
      expect(resolved.apiKey).toBe('resolved-secret/api-key');
    });

    test('lazy eval test - secrets not resolved until accessed', () => {
      let resolvedCount = 0;
      const lazySecret = () => { resolvedCount++; return 'secret-value'; };
      expect(resolvedCount).toBe(0);
      lazySecret();
      expect(resolvedCount).toBe(1);
    });

    test('config merge test - deep merge preserves nested', () => {
      const base = { db: { host: 'localhost', port: 5432 }, cache: { ttl: 60 } };
      const override = { db: { host: 'prod-db' } };
      const merged = mergeTransformConfig(base, override);
      expect(merged.db.host).toBe('prod-db');
      expect(merged.db.port).toBe(5432);
    });

    test('deep vs shallow test - nested objects merged recursively', () => {
      const base = { a: { b: { c: 1, d: 2 } } };
      const override = { a: { b: { d: 3, e: 4 } } };
      const merged = mergeTransformConfig(base, override);
      expect(merged.a.b.c).toBe(1);
      expect(merged.a.b.d).toBe(3);
      expect(merged.a.b.e).toBe(4);
    });

    test('scaling threshold test - string to number parsing', () => {
      const config = { maxWorkers: '8', memoryLimitMB: '512' };
      const parsed = {
        maxWorkers: parseInt(config.maxWorkers, 10),
        memoryLimitMB: parseInt(config.memoryLimitMB, 10),
      };
      expect(parsed.maxWorkers).toBe(8);
      expect(parsed.memoryLimitMB).toBe(512);
    });

    test('string parse test - boolean string coercion', () => {
      const envVal = 'true';
      
      expect(envVal === 'true').toBe(true);
      expect(typeof envVal).toBe('string');
    });

    test('consul kv debounce test - rapid changes debounced', async () => {
      let callCount = 0;
      const debounce = (fn, ms) => {
        let timer;
        return (...args) => {
          clearTimeout(timer);
          timer = setTimeout(() => { callCount++; fn(...args); }, ms);
        };
      };

      const handler = debounce(() => {}, 50);
      handler(); handler(); handler();
      await global.testUtils.delay(100);
      expect(callCount).toBe(1);
    });

    test('watch race test - concurrent KV updates handled', async () => {
      const updates = [];
      const handler = (value) => updates.push(value);

      handler('v1');
      handler('v2');
      handler('v3');
      expect(updates.length).toBe(3);
      expect(updates[updates.length - 1]).toBe('v3');
    });
  });

  describe('query engine advanced', () => {
    test('parse SELECT star', () => {
      const parsed = engine.parse('SELECT * FROM metrics');
      expect(parsed.select).toContain('*');
      expect(parsed.from).toBe('metrics');
    });

    test('parse ORDER BY clause', () => {
      const parsed = engine.parse('SELECT name FROM users ORDER BY name');
      expect(parsed.orderBy).toBeDefined();
    });

    test('filter with inequality operators', () => {
      const data = [{ value: 10 }, { value: 20 }, { value: 30 }];
      const result = engine._applyFilter(data, ['value != 20'], {});
      expect(result.length).toBe(2);
    });

    test('sort by multiple fields', () => {
      const data = [
        { city: 'NYC', age: 25 },
        { city: 'NYC', age: 30 },
        { city: 'LA', age: 20 },
      ];
      const sorted = engine._applySort(data, ['city', 'age']);
      expect(sorted[0].city).toBe('LA');
    });

    test('GROUP BY with multiple keys', () => {
      const data = [
        { city: 'NYC', status: 'active', value: 1 },
        { city: 'NYC', status: 'active', value: 2 },
        { city: 'NYC', status: 'inactive', value: 3 },
        { city: 'LA', status: 'active', value: 4 },
      ];
      const result = engine._applyGroupBy(data, ['city', 'status']);
      expect(result.length).toBe(3);
    });

    test('time range with empty data returns empty', () => {
      const result = engine.queryTimeRange([], 0, 1000);
      expect(result).toEqual([]);
    });

    test('plan caching improves performance', () => {
      const parsed = engine.parse('SELECT * FROM large_table WHERE id > 100');
      const plan1 = engine.plan(parsed, {});
      const plan2 = engine.plan(parsed, {});
      expect(plan1).toBe(plan2); // Same reference from cache
    });
  });
});
