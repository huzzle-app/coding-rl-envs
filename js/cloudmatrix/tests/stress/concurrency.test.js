/**
 * Concurrency Bug Tests
 *
 * Tests for race conditions, non-atomic operations, and concurrent access bugs.
 */

describe('Concurrency Bug Detection', () => {
  describe('Usage Meter Race Condition', () => {
    it('concurrent increments should produce accurate total', async () => {
      const { UsageMeter } = require('../../services/billing/src/services/subscription');
      const meter = new UsageMeter();

      const promises = [];
      for (let i = 0; i < 20; i++) {
        promises.push(meter.increment('api-calls'));
      }

      await Promise.all(promises);
      expect(meter.getCount('api-calls')).toBe(20);
    });

    it('concurrent increments to different keys should not interfere', async () => {
      const { UsageMeter } = require('../../services/billing/src/services/subscription');
      const meter = new UsageMeter();

      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(meter.increment('key-a'));
        promises.push(meter.increment('key-b'));
      }

      await Promise.all(promises);
      expect(meter.getCount('key-a')).toBe(10);
      expect(meter.getCount('key-b')).toBe(10);
    });

    it('snapshot should capture consistent state', async () => {
      const { UsageMeter } = require('../../services/billing/src/services/subscription');
      const meter = new UsageMeter();

      for (let i = 0; i < 5; i++) {
        await meter.increment('requests');
      }

      const snapshot = meter.takeSnapshot();
      expect(snapshot.requests).toBe(5);

      for (let i = 0; i < 3; i++) {
        await meter.increment('requests');
      }

      expect(snapshot.requests).toBe(5);
      expect(meter.getCount('requests')).toBe(8);
    });
  });

  describe('Distributed Lock Atomicity', () => {
    it('lock release should be atomic (check-and-delete)', async () => {
      const { DistributedLock } = require('../../shared/utils');

      let storedValue = null;
      const mockRedis = {
        set: jest.fn(async (key, value, opts) => {
          if (opts && opts.NX && storedValue !== null) return null;
          storedValue = value;
          return 'OK';
        }),
        get: jest.fn(async () => storedValue),
        del: jest.fn(async () => {
          storedValue = null;
          return 1;
        }),
        pexpire: jest.fn(async () => 1),
      };

      const lock = new DistributedLock(mockRedis);
      const acquired = await lock.acquire('resource-1');

      expect(acquired).not.toBeNull();

      storedValue = 'different-owner-value';

      const released = await lock.release(acquired);

      expect(released).toBe(false);
      expect(storedValue).toBe('different-owner-value');
    });

    it('two processes should not both think they hold the lock', async () => {
      const { DistributedLock } = require('../../shared/utils');

      let store = {};
      const mockRedis = {
        set: jest.fn(async (key, value, opts) => {
          if (opts && opts.NX && store[key]) return null;
          store[key] = value;
          return 'OK';
        }),
        get: jest.fn(async (key) => store[key] || null),
        del: jest.fn(async (key) => {
          delete store[key];
          return 1;
        }),
        pexpire: jest.fn(async () => 1),
      };

      const lock1 = new DistributedLock(mockRedis, { maxRetries: 1, retryDelay: 10 });
      const lock2 = new DistributedLock(mockRedis, { maxRetries: 1, retryDelay: 10 });

      const acquired1 = await lock1.acquire('shared-resource');
      const acquired2 = await lock2.acquire('shared-resource');

      expect(acquired1).not.toBeNull();
      expect(acquired2).toBeNull();
    });
  });

  describe('Connection Pool Concurrent Acquire', () => {
    it('concurrent acquires should not exceed pool size', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(3);

      const acquired = [];
      const promises = [];

      for (let i = 0; i < 3; i++) {
        promises.push(pool.acquire().then(conn => {
          acquired.push(conn);
          return conn;
        }));
      }

      await Promise.all(promises);
      expect(acquired).toHaveLength(3);
      expect(pool.getStats().active).toBe(3);

      let waiterResolved = false;
      pool.acquire().then(() => { waiterResolved = true; });

      await new Promise(r => setTimeout(r, 20));
      expect(waiterResolved).toBe(false);

      for (const conn of acquired) {
        pool.release(conn);
      }
    });

    it('release-and-reacquire cycle should maintain pool invariants', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(2);

      for (let cycle = 0; cycle < 5; cycle++) {
        const c1 = await pool.acquire();
        const c2 = await pool.acquire();

        const waiterP = pool.acquire();
        pool.release(c1);
        const c3 = await waiterP;

        pool.release(c2);
        pool.release(c3);
      }

      const stats = pool.getStats();
      expect(stats.active).toBe(0);
      expect(stats.waiting).toBe(0);
    });
  });

  describe('Bulkhead Concurrent Execution', () => {
    it('should respect maxConcurrent limit under burst load', async () => {
      const { BulkheadIsolation } = require('../../shared/clients');
      const bulkhead = new BulkheadIsolation(3);

      let concurrent = 0;
      let peakConcurrent = 0;
      const results = [];

      const task = (id) => new Promise(resolve => {
        concurrent++;
        peakConcurrent = Math.max(peakConcurrent, concurrent);
        setTimeout(() => {
          concurrent--;
          results.push(id);
          resolve(id);
        }, 20);
      });

      const promises = Array.from({ length: 10 }, (_, i) =>
        bulkhead.execute(() => task(i))
      );

      await Promise.all(promises);

      expect(peakConcurrent).toBeLessThanOrEqual(3);
      expect(results).toHaveLength(10);
    });

    it('queued tasks should execute after running tasks complete', async () => {
      const { BulkheadIsolation } = require('../../shared/clients');
      const bulkhead = new BulkheadIsolation(1);

      const order = [];

      const task = (id, delay) => new Promise(resolve => {
        order.push(`start-${id}`);
        setTimeout(() => {
          order.push(`end-${id}`);
          resolve();
        }, delay);
      });

      await Promise.all([
        bulkhead.execute(() => task('a', 30)),
        bulkhead.execute(() => task('b', 10)),
        bulkhead.execute(() => task('c', 10)),
      ]);

      expect(order[0]).toBe('start-a');
      expect(order.indexOf('end-a')).toBeLessThan(order.indexOf('start-b'));
    });
  });

  describe('Cache Stampede Protection', () => {
    it('concurrent cache misses should only trigger one DB fetch', async () => {
      const { RequestCoalescer } = require('../../shared/clients');
      const coalescer = new RequestCoalescer();

      let fetchCount = 0;
      const fetchFromDb = async () => {
        fetchCount++;
        await new Promise(r => setTimeout(r, 50));
        return { data: 'result' };
      };

      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(coalescer.coalesce('user:123', fetchFromDb));
      }

      const results = await Promise.all(promises);

      expect(fetchCount).toBe(1);
      expect(results.every(r => r.data === 'result')).toBe(true);
    });

    it('subsequent requests after completion should trigger new fetch', async () => {
      const { RequestCoalescer } = require('../../shared/clients');
      const coalescer = new RequestCoalescer();

      let fetchCount = 0;
      const fetchFromDb = async () => {
        fetchCount++;
        return { data: `result-${fetchCount}` };
      };

      const result1 = await coalescer.coalesce('key-1', fetchFromDb);
      const result2 = await coalescer.coalesce('key-1', fetchFromDb);

      expect(fetchCount).toBe(2);
      expect(result1.data).toBe('result-1');
      expect(result2.data).toBe('result-2');
    });
  });

  describe('WebSocket Broadcast During Cleanup', () => {
    it('broadcast should handle terminated connections gracefully', () => {
      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager();

      const mockWs1 = { readyState: 1, send: jest.fn(), terminate: jest.fn() };
      const mockWs2 = { readyState: 3, send: jest.fn(() => { throw new Error('closed'); }), terminate: jest.fn() };
      const mockWs3 = { readyState: 1, send: jest.fn(), terminate: jest.fn() };

      manager.connections.set('conn-1', { ws: mockWs1, rooms: new Set(['room-1']), lastPing: Date.now() });
      manager.connections.set('conn-2', { ws: mockWs2, rooms: new Set(['room-1']), lastPing: Date.now() });
      manager.connections.set('conn-3', { ws: mockWs3, rooms: new Set(['room-1']), lastPing: Date.now() });

      manager.rooms.set('room-1', new Set(['conn-1', 'conn-2', 'conn-3']));

      expect(() => {
        manager._broadcast('room-1', { type: 'update', data: 'test' });
      }).not.toThrow();

      expect(mockWs1.send).toHaveBeenCalled();
      expect(mockWs3.send).toHaveBeenCalled();
    });
  });

  describe('Rate Limiter Under Concurrent Load', () => {
    it('rate limiter should not allow more than maxTokens through simultaneously', () => {
      const { TokenBucketRateLimiter } = require('../../shared/utils');
      const limiter = new TokenBucketRateLimiter({
        maxTokens: 10,
        refillRate: 0,
        initialTokens: 10,
      });

      let consumed = 0;
      const results = [];

      for (let i = 0; i < 15; i++) {
        const allowed = limiter.tryConsume();
        results.push(allowed);
        if (allowed) consumed++;
      }

      expect(consumed).toBe(10);
      expect(results.slice(10).every(r => r === false)).toBe(true);
    });
  });

  describe('Split Brain Detection Quorum', () => {
    it('should correctly identify majority partition', () => {
      const { SplitBrainDetector } = require('../../services/presence/src/services/presence');
      const detector = new SplitBrainDetector(['node-1', 'node-2', 'node-3', 'node-4', 'node-5']);

      const result = detector.detectSplit(['node-1', 'node-2', 'node-3']);

      expect(result.hasSplit).toBe(true);
      expect(result.hasMajority).toBe(true);
      expect(result.canOperate).toBe(true);
    });

    it('minority partition should not be allowed to operate', () => {
      const { SplitBrainDetector } = require('../../services/presence/src/services/presence');
      const detector = new SplitBrainDetector(['node-1', 'node-2', 'node-3', 'node-4', 'node-5']);

      const result = detector.detectSplit(['node-1', 'node-2']);

      expect(result.hasSplit).toBe(true);
      expect(result.canOperate).toBe(false);
    });

    it('quorum size should be majority for even node count', () => {
      const { SplitBrainDetector } = require('../../services/presence/src/services/presence');
      const detector = new SplitBrainDetector(['a', 'b', 'c', 'd']);

      expect(detector.getQuorumSize()).toBe(3);
      expect(detector.isQuorumMet(['a', 'b'])).toBe(false);
      expect(detector.isQuorumMet(['a', 'b', 'c'])).toBe(true);
    });

    it('exact half should not be considered quorum', () => {
      const { SplitBrainDetector } = require('../../services/presence/src/services/presence');
      const detector = new SplitBrainDetector(['a', 'b', 'c', 'd']);

      const result = detector.detectSplit(['a', 'b']);
      expect(result.canOperate).toBe(false);
    });
  });
});
