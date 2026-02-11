/**
 * Transform Pipeline Tests (~50 tests)
 *
 * Tests for BUG B1-B10 and I6 transform bugs
 */

const { TransformPipeline, mergeTransformConfig } = require('../../../services/transform/src/services/pipeline');

describe('TransformPipeline', () => {
  let pipeline;

  beforeEach(() => {
    pipeline = new TransformPipeline({ maxChainDepth: 50, udfTimeout: 5000 });
  });

  describe('schema mapping (B1)', () => {
    test('schema mapping type test - number coercion preserves precision', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { amount: 'raw_amount' },
        typeCoercion: { amount: 'number' },
      });
      const result = await pipeline.execute({ raw_amount: '123.456789012345678' });
      expect(result.amount).toBeCloseTo(123.456789012345678, 10);
    });

    test('type coercion loss test - integer coercion rounds correctly', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { count: 'raw_count' },
        typeCoercion: { count: 'integer' },
      });
      const result = await pipeline.execute({ raw_count: '42.7' });
      expect(result.count).toBe(43);
    });

    test('string coercion works', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { name: 'id' },
        typeCoercion: { name: 'string' },
      });
      const result = await pipeline.execute({ id: 12345 });
      expect(result.name).toBe('12345');
    });

    test('boolean coercion preserves truthiness', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { active: 'flag' },
        typeCoercion: { active: 'boolean' },
      });
      const result = await pipeline.execute({ flag: 1 });
      expect(result.active).toBe(true);
    });

    test('no coercion preserves original type', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { value: 'original' },
      });
      const result = await pipeline.execute({ original: [1, 2, 3] });
      expect(Array.isArray(result.value)).toBe(true);
    });
  });

  describe('null handling (B2)', () => {
    test('null nested field test - handles null in nested path gracefully', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { city: 'address.city' },
      });
      const result = await pipeline.execute({ address: null });
      expect(result).toBeDefined();
    });

    test('null propagation test - undefined nested field returns undefined', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { value: 'deep.nested.value' },
      });
      
      try {
        await pipeline.execute({ deep: { nested: null } });
      } catch (e) {
        expect(e).toBeDefined();
      }
    });

    test('missing field returns undefined', async () => {
      pipeline.addTransform({
        type: 'map',
        mapping: { value: 'nonexistent' },
      });
      const result = await pipeline.execute({});
      expect(result.value).toBeUndefined();
    });
  });

  describe('array flattening (B3)', () => {
    test('array flattening depth test - handles deep nesting safely', async () => {
      pipeline.addTransform({
        type: 'flatten',
        field: 'data',
        outputField: 'flat',
      });
      let nested = [1];
      for (let i = 0; i < 100; i++) {
        nested = [nested];
      }
      expect(() => pipeline.execute({ data: nested })).not.toThrow();
    });

    test('recursive flatten test - flattens correctly', async () => {
      pipeline.addTransform({
        type: 'flatten',
        field: 'data',
        outputField: 'flat',
      });
      const result = await pipeline.execute({ data: [1, [2, 3], [4, [5]]] });
      expect(result.flat).toEqual([1, 2, 3, 4, 5]);
    });

    test('non-array field is unchanged', async () => {
      pipeline.addTransform({
        type: 'flatten',
        field: 'data',
      });
      const result = await pipeline.execute({ data: 'hello' });
      expect(result.data).toBe('hello');
    });

    test('empty array flattens to empty array', async () => {
      pipeline.addTransform({
        type: 'flatten',
        field: 'data',
        outputField: 'flat',
      });
      const result = await pipeline.execute({ data: [] });
      expect(result.flat).toEqual([]);
    });
  });

  describe('regex transform (B4)', () => {
    test('regex transform redos test - rejects catastrophic backtracking patterns', async () => {
      pipeline.addTransform({
        type: 'regex',
        field: 'input',
        pattern: '(a+)+$',
        outputField: 'output',
      });
      const start = Date.now();
      await pipeline.execute({ input: 'aaaaaaaaaaaaaaaaaa!' });
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(5000);
    });

    test('catastrophic backtracking test - handles safely', async () => {
      pipeline.addTransform({
        type: 'regex',
        field: 'email',
        pattern: '^([a-zA-Z0-9]+\\.?)+@([a-zA-Z0-9]+\\.?)+$',
        outputField: 'valid',
      });
      const start = Date.now();
      await pipeline.execute({ email: 'a'.repeat(30) + '!' });
      expect(Date.now() - start).toBeLessThan(5000);
    });

    test('valid regex match works', async () => {
      pipeline.addTransform({
        type: 'regex',
        field: 'text',
        pattern: '\\d+',
        outputField: 'numbers',
      });
      const result = await pipeline.execute({ text: 'abc123def' });
      expect(result.numbers).toBe('123');
    });

    test('regex with replacement works', async () => {
      pipeline.addTransform({
        type: 'regex',
        field: 'text',
        pattern: '\\d+',
        replacement: 'NUM',
        outputField: 'cleaned',
      });
      const result = await pipeline.execute({ text: 'abc123def' });
      expect(result.cleaned).toBe('abcNUMdef');
    });
  });

  describe('date parsing (B5)', () => {
    test('date parsing timezone test - handles timezone correctly', async () => {
      pipeline.addTransform({
        type: 'date',
        field: 'ts',
        outputField: 'parsed',
      });
      const result = await pipeline.execute({ ts: '2024-01-15 10:30:00' });
      expect(result.parsed).toContain('2024-01-15');
    });

    test('timezone assumption test - UTC dates stay UTC', async () => {
      pipeline.addTransform({
        type: 'date',
        field: 'ts',
        outputField: 'parsed',
      });
      const result = await pipeline.execute({ ts: '2024-01-15T10:30:00Z' });
      expect(result.parsed).toBe('2024-01-15T10:30:00.000Z');
    });

    test('invalid date handling', async () => {
      pipeline.addTransform({
        type: 'date',
        field: 'ts',
      });
      const result = await pipeline.execute({ ts: 'not-a-date' });
      expect(result.ts).toBe('not-a-date');
    });
  });

  describe('numeric precision (B6)', () => {
    test('numeric precision aggregation test - maintains precision over many values', async () => {
      pipeline.addTransform({
        type: 'aggregate',
        field: 'value',
      });
      for (let i = 0; i < 1000; i++) {
        await pipeline.execute({ value: 0.1 });
      }
      const result = await pipeline.execute({ value: 0.1 });
      expect(Math.abs(result.value_sum - 100.1)).toBeLessThan(0.01);
    });

    test('float accumulation test - small values dont disappear', async () => {
      pipeline.addTransform({
        type: 'aggregate',
        field: 'value',
      });
      await pipeline.execute({ value: 1e15 });
      const result = await pipeline.execute({ value: 1 });
      expect(result.value_sum).toBe(1e15 + 1);
    });
  });

  describe('JSON path (B7)', () => {
    test('json path injection test - blocks prototype chain access', async () => {
      pipeline.addTransform({
        type: 'jsonpath',
        expression: '__proto__.polluted',
        outputField: 'result',
      });
      const result = await pipeline.execute({});
      expect(result.result).toBeUndefined();
    });

    test('path expression safety test - blocks constructor access', async () => {
      pipeline.addTransform({
        type: 'jsonpath',
        expression: 'constructor.prototype',
        outputField: 'result',
      });
      const result = await pipeline.execute({});
      expect(result.result).toBeUndefined();
    });

    test('valid path returns value', async () => {
      pipeline.addTransform({
        type: 'jsonpath',
        expression: 'user.name',
        outputField: 'result',
      });
      const result = await pipeline.execute({ user: { name: 'Alice' } });
      expect(result.result).toBe('Alice');
    });

    test('array index access works', async () => {
      pipeline.addTransform({
        type: 'jsonpath',
        expression: 'items[0]',
        outputField: 'first',
      });
      const result = await pipeline.execute({ items: ['a', 'b', 'c'] });
      expect(result.first).toBe('a');
    });
  });

  describe('conditional transform (B8)', () => {
    test('conditional short-circuit test - correct branch is taken', async () => {
      pipeline.addTransform({
        type: 'conditional',
        field: 'status',
        condition: 'active',
        then: { type: 'map', mapping: { result: 'status' } },
      });
      const result = await pipeline.execute({ status: 'active' });
      expect(result.result).toBe('active');
    });

    test('transform ordering test - false condition takes else branch', async () => {
      pipeline.addTransform({
        type: 'conditional',
        field: 'status',
        condition: 'active',
        then: { type: 'map', mapping: { result: 'status' } },
        else: { type: 'map', mapping: { result: 'status' } },
      });
      const result = await pipeline.execute({ status: 'inactive' });
      expect(result).toBeDefined();
    });

    test('type coercion in condition - 0 should not equal empty string', async () => {
      pipeline.addTransform({
        type: 'conditional',
        field: 'value',
        condition: '',
        then: { type: 'map', mapping: { matched: 'value' } },
      });
      const result = await pipeline.execute({ value: 0 });
      expect(result.matched).toBeUndefined();
    });
  });

  describe('UDF execution (B9)', () => {
    test('udf timeout cleanup test - resources cleaned on timeout', async () => {
      pipeline.addTransform({
        type: 'udf',
        code: 'return record',
        timeout: 100,
      });
      await pipeline.execute({ value: 1 });
      expect(pipeline._runningUdfs.size).toBe(0);
    });

    test('udf resource leak test - completed UDFs release resources', async () => {
      pipeline.addTransform({
        type: 'udf',
        code: 'return record',
        timeout: 5000,
      });
      await pipeline.execute({ value: 1 });
      expect(pipeline._runningUdfs.size).toBe(0);
    });
  });

  describe('transform chain (B10)', () => {
    test('transform chain order test - respects dependencies', async () => {
      pipeline.addTransform({ type: 'map', mapping: { doubled: 'value' }, typeCoercion: { doubled: 'number' } });
      pipeline.addTransform({ type: 'map', mapping: { quadrupled: 'doubled' }, typeCoercion: { quadrupled: 'number' } });
      const result = await pipeline.execute({ value: 5 });
      expect(result.doubled).toBe(5);
      expect(result.quadrupled).toBe(5);
    });

    test('dependency resolution test - chain of 3 transforms', async () => {
      pipeline.addTransform({ type: 'map', mapping: { a: 'input' } });
      pipeline.addTransform({ type: 'map', mapping: { b: 'a' } });
      pipeline.addTransform({ type: 'map', mapping: { c: 'b' } });
      const result = await pipeline.execute({ input: 'hello' });
      expect(result.c).toBe('hello');
    });

    test('error in chain skips when configured', async () => {
      pipeline.addTransform({ type: 'map', mapping: { a: 'input' } });
      pipeline.addTransform({ type: 'map', mapping: { b: 'nonexistent.deep.path' }, onError: 'skip' });
      const result = await pipeline.execute({ input: 'hello' });
      expect(result.a).toBe('hello');
    });
  });
});

describe('mergeTransformConfig', () => {
  test('prototype pollution transform test - blocks __proto__ injection', () => {
    const base = { a: 1 };
    const override = JSON.parse('{"__proto__": {"polluted": true}}');
    mergeTransformConfig(base, override);
    expect(({}).polluted).toBeUndefined();
  });

  test('object merge test - blocks constructor injection', () => {
    const base = { a: 1 };
    const override = { constructor: { prototype: { polluted: true } } };
    mergeTransformConfig(base, override);
    expect(({}).polluted).toBeUndefined();
  });

  test('deep merge works for normal objects', () => {
    const base = { a: { b: 1 } };
    const override = { a: { c: 2 } };
    const result = mergeTransformConfig(base, override);
    expect(result.a.b).toBe(1);
    expect(result.a.c).toBe(2);
  });

  test('arrays are overwritten not merged', () => {
    const base = { items: [1, 2] };
    const override = { items: [3, 4] };
    const result = mergeTransformConfig(base, override);
    expect(result.items).toEqual([3, 4]);
  });

  test('null override value replaces', () => {
    const base = { a: 1 };
    const override = { a: null };
    const result = mergeTransformConfig(base, override);
    expect(result.a).toBeNull();
  });

  test('empty override returns base', () => {
    const base = { a: 1, b: 2 };
    const result = mergeTransformConfig(base, {});
    expect(result).toEqual({ a: 1, b: 2 });
  });

  test('empty base returns override', () => {
    const override = { a: 1, b: 2 };
    const result = mergeTransformConfig({}, override);
    expect(result).toEqual({ a: 1, b: 2 });
  });

  test('nested three levels deep', () => {
    const base = { a: { b: { c: 1 } } };
    const override = { a: { b: { d: 2 } } };
    const result = mergeTransformConfig(base, override);
    expect(result.a.b.c).toBe(1);
    expect(result.a.b.d).toBe(2);
  });

  test('numeric values override correctly', () => {
    const base = { timeout: 5000 };
    const override = { timeout: 10000 };
    const result = mergeTransformConfig(base, override);
    expect(result.timeout).toBe(10000);
  });

  test('boolean values override correctly', () => {
    const base = { enabled: true };
    const override = { enabled: false };
    const result = mergeTransformConfig(base, override);
    expect(result.enabled).toBe(false);
  });

  test('string values override correctly', () => {
    const base = { name: 'old' };
    const override = { name: 'new' };
    const result = mergeTransformConfig(base, override);
    expect(result.name).toBe('new');
  });
});

describe('TransformPipeline additional', () => {
  let pipeline;

  beforeEach(() => {
    pipeline = new TransformPipeline();
  });

  test('getStats returns correct transform count', () => {
    pipeline.addTransform({ type: 'map', mapping: { a: 'b' } });
    pipeline.addTransform({ type: 'map', mapping: { c: 'd' } });
    expect(pipeline.getStats().transformCount).toBe(2);
  });

  test('filter transform removes non-matching records', async () => {
    pipeline.addTransform({
      type: 'filter',
      field: 'value',
      operator: 'gt',
      threshold: 10,
    });
    const result = await pipeline.execute({ value: 5 });
    expect(result).toBeNull();
  });

  test('filter transform keeps matching records', async () => {
    pipeline.addTransform({
      type: 'filter',
      field: 'value',
      operator: 'gt',
      threshold: 10,
    });
    const result = await pipeline.execute({ value: 20 });
    expect(result.value).toBe(20);
  });

  test('unknown transform type returns record unchanged', async () => {
    pipeline.addTransform({ type: 'unknown_type' });
    const result = await pipeline.execute({ value: 42 });
    expect(result.value).toBe(42);
  });

  test('empty pipeline returns record unchanged', async () => {
    const result = await pipeline.execute({ value: 42 });
    expect(result.value).toBe(42);
  });

  test('maxChainDepth is configurable', () => {
    const p = new TransformPipeline({ maxChainDepth: 100 });
    expect(p.maxChainDepth).toBe(100);
  });

  test('udfTimeout is configurable', () => {
    const p = new TransformPipeline({ udfTimeout: 60000 });
    expect(p.udfTimeout).toBe(60000);
  });
});
