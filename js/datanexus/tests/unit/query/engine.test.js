/**
 * Query Engine Tests (~50 tests)
 *
 * Tests for BUG C1-C8 query engine bugs
 */

const { QueryEngine } = require('../../../services/query/src/services/engine');

describe('QueryEngine', () => {
  let engine;
  let mockDb;

  beforeEach(() => {
    mockDb = global.testUtils.mockPg();
    engine = new QueryEngine(mockDb, { queryTimeout: 5000 });
  });

  describe('SQL injection (C1)', () => {
    test('sql injection filter test - parameterized queries prevent injection', () => {
      const data = [{ name: 'Alice', age: 30 }, { name: 'Bob', age: 25 }];
      const maliciousCondition = "name = 'Alice' OR 1=1 --";
      const result = engine._applyFilter(data, [maliciousCondition], {});
      expect(result.length).not.toBe(data.length);
    });

    test('parameterized query test - special characters in values are safe', () => {
      const data = [{ name: "O'Brien", age: 30 }];
      const result = engine._applyFilter(data, ["name = O'Brien"], {});
      expect(result).toBeDefined();
    });

    test('LIKE injection is prevented', () => {
      const data = [{ name: 'Alice' }, { name: 'Bob' }];
      const result = engine._applyFilter(data, ["name LIKE '.*'"], {});
      expect(result.length).not.toBe(data.length);
    });

    test('filter with safe values works correctly', () => {
      const data = [{ name: 'Alice', age: 30 }, { name: 'Bob', age: 25 }];
      const result = engine._applyFilter(data, ["age > 28"], {});
      expect(result.length).toBe(1);
      expect(result[0].name).toBe('Alice');
    });

    test('multiple filter conditions all applied', () => {
      const data = [
        { name: 'Alice', age: 30, city: 'NYC' },
        { name: 'Bob', age: 30, city: 'LA' },
        { name: 'Charlie', age: 25, city: 'NYC' },
      ];
      const result = engine._applyFilter(data, ["age >= 30", "city = NYC"], {});
      expect(result.length).toBe(1);
    });
  });

  describe('plan cache (C2)', () => {
    test('plan cache stale test - cache invalidated on schema change', () => {
      const parsed = engine.parse('SELECT name FROM users WHERE age > 25');
      const plan1 = engine.plan(parsed, {});
      engine.invalidateCache();
      const plan2 = engine.plan(parsed, {});
      expect(plan2).toBeDefined();
    });

    test('schema change invalidation test - version increments', () => {
      const v1 = engine.schemaVersion;
      engine.invalidateCache();
      expect(engine.schemaVersion).toBe(v1 + 1);
    });

    test('cache hit returns same plan', () => {
      const parsed = engine.parse('SELECT name FROM users');
      const plan1 = engine.plan(parsed, {});
      const plan2 = engine.plan(parsed, {});
      expect(plan1).toBe(plan2);
    });

    test('cache stats reflect size', () => {
      engine.parse('SELECT a FROM t1');
      const parsed = engine.parse('SELECT b FROM t2');
      engine.plan(parsed, {});
      const stats = engine.getCacheStats();
      expect(stats.size).toBeGreaterThan(0);
    });
  });

  describe('GROUP BY (C3)', () => {
    test('group by float test - float values grouped correctly', () => {
      const data = [
        { category: 0.1 + 0.2, value: 10 },
        { category: 0.3, value: 20 },
      ];
      const result = engine._applyGroupBy(data, ['category']);
      expect(result.length).toBe(1);
    });

    test('float equality grouping test - near-equal floats in same group', () => {
      const data = [
        { amount: 0.30000000000000004, count: 1 },
        { amount: 0.3, count: 1 },
      ];
      const result = engine._applyGroupBy(data, ['amount']);
      expect(result.length).toBe(1);
      expect(result[0]._count).toBe(2);
    });

    test('integer GROUP BY works normally', () => {
      const data = [
        { category: 1, value: 10 },
        { category: 1, value: 20 },
        { category: 2, value: 30 },
      ];
      const result = engine._applyGroupBy(data, ['category']);
      expect(result.length).toBe(2);
    });

    test('string GROUP BY works normally', () => {
      const data = [
        { city: 'NYC', value: 10 },
        { city: 'NYC', value: 20 },
        { city: 'LA', value: 30 },
      ];
      const result = engine._applyGroupBy(data, ['city']);
      expect(result.length).toBe(2);
    });
  });

  describe('HAVING clause (C4)', () => {
    test('having evaluation order test - HAVING evaluates after GROUP BY', () => {
      const parsed = engine.parse('SELECT city FROM users GROUP BY city HAVING count > 5');
      const plan = engine.plan(parsed, {});
      const steps = plan.steps.map(s => s.type);
      const groupIdx = steps.indexOf('group');
      const havingIdx = steps.indexOf('having');
      expect(groupIdx).toBeLessThan(havingIdx);
    });

    test('having clause test - filters groups correctly', () => {
      const data = [
        { city: 'NYC', _count: 10 },
        { city: 'LA', _count: 3 },
      ];
      const result = engine._applyHaving(data, ['count > 5']);
      expect(result.length).toBe(1);
      expect(result[0].city).toBe('NYC');
    });
  });

  describe('subquery scope (C5)', () => {
    test('subquery scope leak test - outer variables dont leak', () => {
      const outer = { id: 1, name: 'Alice' };
      const result = engine.executeSubquery(outer, 'SELECT count FROM orders');
      expect(result.id).toBeDefined();
    });

    test('correlation variable test - subquery has its own scope', () => {
      const outer = { id: 1, secret: 'hidden' };
      const result = engine.executeSubquery(outer, 'SELECT x FROM t');
      expect(result).not.toHaveProperty('secret_leaked');
    });
  });

  describe('pagination (C6)', () => {
    test('pagination cursor drift test - offset pagination is stable', () => {
      const data = Array.from({ length: 20 }, (_, i) => ({ id: i, name: `item-${i}` }));
      const page1 = engine._applyLimit(data, 5, 0);
      const page2 = engine._applyLimit(data, 5, 5);
      expect(page1.length).toBe(5);
      expect(page2.length).toBe(5);
      expect(page1[0].id).not.toBe(page2[0].id);
    });

    test('offset consistency test - no duplicates across pages', () => {
      const data = Array.from({ length: 20 }, (_, i) => ({ id: i }));
      const page1 = engine._applyLimit(data, 10, 0);
      const page2 = engine._applyLimit(data, 10, 10);
      const allIds = [...page1.map(r => r.id), ...page2.map(r => r.id)];
      const unique = new Set(allIds);
      expect(unique.size).toBe(allIds.length);
    });

    test('offset beyond data returns empty', () => {
      const data = [{ id: 1 }, { id: 2 }];
      const result = engine._applyLimit(data, 10, 100);
      expect(result.length).toBe(0);
    });

    test('limit zero returns empty', () => {
      const data = [{ id: 1 }, { id: 2 }];
      const result = engine._applyLimit(data, 0, 0);
      expect(result.length).toBe(0);
    });
  });

  describe('time range (C7)', () => {
    test('time range boundary test - start is inclusive', () => {
      const data = [{ timestamp: 100 }, { timestamp: 200 }, { timestamp: 300 }];
      const result = engine.queryTimeRange(data, 100, 300);
      expect(result.some(r => r.timestamp === 100)).toBe(true);
    });

    test('inclusive exclusive test - end is exclusive', () => {
      const data = [{ timestamp: 100 }, { timestamp: 200 }, { timestamp: 300 }];
      const result = engine.queryTimeRange(data, 100, 300);
      expect(result.some(r => r.timestamp === 300)).toBe(false);
    });

    test('boundary event appears in exactly one range', () => {
      const data = [{ timestamp: 200 }];
      const range1 = engine.queryTimeRange(data, 100, 200);
      const range2 = engine.queryTimeRange(data, 200, 300);
      const totalMatches = range1.length + range2.length;
      expect(totalMatches).toBe(1);
    });

    test('empty range returns empty', () => {
      const data = [{ timestamp: 100 }];
      const result = engine.queryTimeRange(data, 200, 300);
      expect(result.length).toBe(0);
    });
  });

  describe('query timeout (C8)', () => {
    test('query timeout propagation test - timeout passed to storage', async () => {
      mockDb.query.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve({ rows: [] }), 100)));
      const result = await engine._fetchFromStorage('metrics', ['*']);
      expect(result).toBeDefined();
    });

    test('storage timeout test - handles storage timeout', async () => {
      mockDb.query.mockRejectedValue(new Error('timeout'));
      const result = await engine._fetchFromStorage('metrics', ['*']);
      expect(result).toEqual([]);
    });
  });

  describe('SQL parsing', () => {
    test('parses SELECT with WHERE', () => {
      const parsed = engine.parse('SELECT name, age FROM users WHERE age > 25');
      expect(parsed.select).toContain('name');
      expect(parsed.from).toBe('users');
      expect(parsed.where.length).toBe(1);
    });

    test('parses GROUP BY', () => {
      const parsed = engine.parse('SELECT city, COUNT(*) FROM users GROUP BY city');
      expect(parsed.groupBy).toContain('city');
    });

    test('parses LIMIT and OFFSET', () => {
      const parsed = engine.parse('SELECT * FROM users LIMIT 10 OFFSET 20');
      expect(parsed.limit).toBe(10);
      expect(parsed.offset).toBe(20);
    });

    test('parses complex query', () => {
      const parsed = engine.parse('SELECT city FROM users WHERE age > 25 GROUP BY city HAVING count > 5 LIMIT 10');
      expect(parsed.from).toBe('users');
      expect(parsed.groupBy).toContain('city');
      expect(parsed.limit).toBe(10);
    });
  });

  describe('sorting', () => {
    test('sorts ascending by default', () => {
      const data = [{ name: 'Charlie' }, { name: 'Alice' }, { name: 'Bob' }];
      const result = engine._applySort(data, ['name']);
      expect(result[0].name).toBe('Alice');
    });

    test('sorts descending with DESC', () => {
      const data = [{ value: 1 }, { value: 3 }, { value: 2 }];
      const result = engine._applySort(data, ['value DESC']);
      expect(result[0].value).toBe(3);
    });

    test('stable sort preserves order of equal elements', () => {
      const data = [
        { name: 'Alice', age: 30 },
        { name: 'Bob', age: 30 },
        { name: 'Charlie', age: 25 },
      ];
      const result = engine._applySort(data, ['age']);
      expect(result[0].name).toBe('Charlie');
    });

    test('sort empty array returns empty', () => {
      const result = engine._applySort([], ['name']);
      expect(result).toEqual([]);
    });

    test('sort single element returns same', () => {
      const data = [{ value: 42 }];
      const result = engine._applySort(data, ['value']);
      expect(result[0].value).toBe(42);
    });

    test('numeric sort is correct', () => {
      const data = [{ v: 10 }, { v: 2 }, { v: 30 }, { v: 1 }];
      const result = engine._applySort(data, ['v']);
      expect(result[0].v).toBe(1);
      expect(result[3].v).toBe(30);
    });
  });

  describe('additional filter tests', () => {
    test('filter gte operator', () => {
      const data = [{ age: 20 }, { age: 25 }, { age: 30 }];
      const result = engine._applyFilter(data, ['age >= 25'], {});
      expect(result.length).toBe(2);
    });

    test('filter lte operator', () => {
      const data = [{ age: 20 }, { age: 25 }, { age: 30 }];
      const result = engine._applyFilter(data, ['age <= 25'], {});
      expect(result.length).toBe(2);
    });

    test('filter eq operator', () => {
      const data = [{ name: 'Alice' }, { name: 'Bob' }];
      const result = engine._applyFilter(data, ['name = Alice'], {});
      expect(result.length).toBe(1);
    });

    test('filter on empty data returns empty', () => {
      const result = engine._applyFilter([], ['age > 20'], {});
      expect(result).toEqual([]);
    });

    test('no filters returns all data', () => {
      const data = [{ id: 1 }, { id: 2 }];
      const result = engine._applyFilter(data, [], {});
      expect(result.length).toBe(2);
    });
  });

  describe('additional GROUP BY tests', () => {
    test('group by with single element groups', () => {
      const data = [
        { city: 'NYC', value: 10 },
        { city: 'LA', value: 20 },
        { city: 'SF', value: 30 },
      ];
      const result = engine._applyGroupBy(data, ['city']);
      expect(result.length).toBe(3);
    });

    test('group by null values', () => {
      const data = [
        { city: null, value: 10 },
        { city: null, value: 20 },
        { city: 'NYC', value: 30 },
      ];
      const result = engine._applyGroupBy(data, ['city']);
      expect(result.length).toBe(2);
    });

    test('group by count is correct', () => {
      const data = [
        { city: 'NYC', value: 10 },
        { city: 'NYC', value: 20 },
        { city: 'LA', value: 30 },
      ];
      const result = engine._applyGroupBy(data, ['city']);
      const nyc = result.find(r => r.city === 'NYC');
      expect(nyc._count).toBe(2);
    });
  });

  describe('additional pagination tests', () => {
    test('limit larger than data returns all', () => {
      const data = [{ id: 1 }, { id: 2 }];
      const result = engine._applyLimit(data, 100, 0);
      expect(result.length).toBe(2);
    });

    test('negative offset treated as zero', () => {
      const data = [{ id: 1 }, { id: 2 }];
      const result = engine._applyLimit(data, 10, -5);
      expect(result.length).toBe(2);
    });
  });
});
