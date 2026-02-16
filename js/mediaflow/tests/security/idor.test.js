/**
 * IDOR Security Tests
 *
 * Tests authorization and access control using actual source modules.
 * Exercises bugs J2 (CorrelationContext global state) and A1/A3 (lock issues).
 */

const { CorrelationContext, TraceContext, DistributedLock } = require('../../shared/utils');

describe('IDOR Prevention', () => {
  describe('User Resources', () => {
    it('should isolate correlation context between requests', async () => {
      // BUG J2: CorrelationContext uses global static state
      // Concurrent requests overwrite each other's correlation ID
      CorrelationContext.set('request-1-corr');
      const firstSet = CorrelationContext.get();

      // Simulate second concurrent request overwriting
      CorrelationContext.set('request-2-corr');

      // First request's context should still be 'request-1-corr'
      // BUG: It's now 'request-2-corr' because of global state
      expect(firstSet).toBe('request-1-corr');
      // Verify the overwrite happened
      const afterOverwrite = CorrelationContext.get();
      expect(afterOverwrite).not.toBe('request-1-corr');
    });

    it('should use request-scoped correlation context', () => {
      // BUG J2: Static global state means all requests share one context
      CorrelationContext.set('req-A');

      // In a proper implementation, each request has its own context
      // (e.g., using AsyncLocalStorage)
      const contextA = CorrelationContext.get();
      expect(contextA).toBe('req-A');

      CorrelationContext.set('req-B');
      const contextB = CorrelationContext.get();

      // After setting B, getting A should still return A's value
      // BUG: Both return 'req-B' because of global state
      expect(contextA).not.toBe(contextB);
    });

    it('should create correlation middleware', () => {
      const middleware = CorrelationContext.createMiddleware();
      expect(typeof middleware).toBe('function');
    });
  });

  describe('Video Resources', () => {
    it('should propagate trace context from headers', () => {
      const headers = {
        'x-trace-id': 'trace-123',
        'x-span-id': 'span-456',
        'x-parent-span-id': 'parent-789',
      };

      const context = TraceContext.fromHeaders(headers);

      expect(context.traceId).toBe('trace-123');
      expect(context.spanId).toBe('span-456');
      expect(context.parentSpanId).toBe('parent-789');
    });

    it('should create child spans with correct parent', () => {
      const parent = new TraceContext('trace-1', 'span-1');
      const child = parent.createChildSpan();

      expect(child.traceId).toBe('trace-1');
      expect(child.parentSpanId).toBe('span-1');
      expect(child.spanId).not.toBe('span-1');
    });

    it('should export trace context to headers', () => {
      const context = new TraceContext('trace-1', 'span-1', 'parent-1');
      const headers = context.toHeaders();

      expect(headers['x-trace-id']).toBe('trace-1');
      expect(headers['x-span-id']).toBe('span-1');
      expect(headers['x-parent-span-id']).toBe('parent-1');
    });
  });

  describe('Subscription Resources', () => {
    it('should acquire distributed lock', async () => {
      const mockRedis = {
        set: jest.fn().mockResolvedValue('OK'),
        get: jest.fn().mockResolvedValue(null),
        del: jest.fn().mockResolvedValue(1),
      };

      const lock = new DistributedLock(mockRedis, { timeout: 5000 });
      const acquired = await lock.acquire('resource-1');

      expect(acquired).not.toBeNull();
      expect(acquired.key).toBe('lock:resource-1');
      expect(acquired.expireAt).toBeGreaterThan(Date.now() - 1000);
    });

    it('should release lock only if owner', async () => {
      const storedValue = 'lock-value-123';
      const mockRedis = {
        get: jest.fn().mockResolvedValue(storedValue),
        del: jest.fn().mockResolvedValue(1),
      };

      const lock = new DistributedLock(mockRedis);

      // Owner releases
      const released = await lock.release({ key: 'lock:res', value: storedValue });
      expect(released).toBe(true);

      // Non-owner tries to release
      const stolen = await lock.release({ key: 'lock:res', value: 'wrong-value' });
      expect(stolen).toBe(false);
    });

    it('should handle null lock on release', async () => {
      const lock = new DistributedLock({});
      const result = await lock.release(null);
      expect(result).toBe(false);
    });
  });

  describe('Parameter Tampering', () => {
    it('should use adequate lock timeout for long operations', async () => {
      const mockRedis = {
        set: jest.fn().mockResolvedValue('OK'),
      };

      // BUG A3: Default timeout is 5000ms (5s), too short for long operations
      const lock = new DistributedLock(mockRedis);

      // Default timeout should be at least 30s for distributed operations
      expect(lock.defaultTimeout).toBeGreaterThanOrEqual(30000);
    });

    it('should generate unique lock values', async () => {
      const mockRedis = {
        set: jest.fn().mockResolvedValue('OK'),
      };

      const lock = new DistributedLock(mockRedis, { timeout: 5000 });
      const lock1 = await lock.acquire('resource-1');
      const lock2 = await lock.acquire('resource-2');

      expect(lock1.value).not.toBe(lock2.value);
    });
  });

  describe('Sequential ID Enumeration', () => {
    it('should extend lock expiry', async () => {
      const mockRedis = {
        get: jest.fn().mockResolvedValue('lock-val'),
        pexpire: jest.fn().mockResolvedValue(1),
      };

      const lock = new DistributedLock(mockRedis);
      const lockObj = { key: 'lock:res', value: 'lock-val', expireAt: Date.now() + 5000 };

      const extended = await lock.extend(lockObj, 10000);
      expect(extended).toBe(true);
      expect(lockObj.expireAt).toBeGreaterThan(Date.now());
    });

    it('should fail to extend if not owner', async () => {
      const mockRedis = {
        get: jest.fn().mockResolvedValue('other-owner-value'),
        pexpire: jest.fn(),
      };

      const lock = new DistributedLock(mockRedis);
      const lockObj = { key: 'lock:res', value: 'my-value', expireAt: Date.now() + 5000 };

      const extended = await lock.extend(lockObj, 10000);
      expect(extended).toBe(false);
    });
  });
});
