/**
 * Collaborative Locking Tests
 *
 * Tests DistributedLock, ConnectionPool, DocumentLifecycle from actual source code.
 * Exercises bugs: non-atomic lock release, connection pool active count drift, lifecycle states.
 */

const { DistributedLock } = require('../../../shared/utils');
const { ConnectionPool, DocumentLifecycle } = require('../../../shared/realtime');

describe('DistributedLock', () => {
  let lock;
  let mockRedis;

  beforeEach(() => {
    mockRedis = {
      set: jest.fn().mockResolvedValue('OK'),
      get: jest.fn().mockResolvedValue(null),
      del: jest.fn().mockResolvedValue(1),
      pexpire: jest.fn().mockResolvedValue(1),
    };
    lock = new DistributedLock(mockRedis, { timeout: 5000, retryDelay: 10, maxRetries: 3 });
  });

  describe('acquire', () => {
    it('should acquire lock successfully', async () => {
      const result = await lock.acquire('resource-1');
      expect(result).not.toBeNull();
      expect(result.key).toContain('resource-1');
      expect(result.value).toBeDefined();
    });

    it('should return null when lock already held', async () => {
      mockRedis.set.mockResolvedValue(null); // NX fails
      const result = await lock.acquire('resource-1', 100);
      expect(result).toBeNull();
    });
  });

  describe('release', () => {
    it('should release owned lock', async () => {
      const acquired = await lock.acquire('resource-1');
      mockRedis.get.mockResolvedValue(acquired.value);
      const released = await lock.release(acquired);
      expect(released).toBe(true);
      expect(mockRedis.del).toHaveBeenCalled();
    });

    it('should not release lock owned by another', async () => {
      const acquired = await lock.acquire('resource-1');
      mockRedis.get.mockResolvedValue('different-value');
      const released = await lock.release(acquired);
      expect(released).toBe(false);
    });

    // BUG: Release is non-atomic (check-then-delete).
    // Between the GET and DEL, another client could acquire the lock,
    // and we'd delete their lock instead of ours.
    it('should release atomically to prevent race conditions', async () => {
      const acquired = await lock.acquire('resource-1');
      mockRedis.get.mockResolvedValue(acquired.value);

      await lock.release(acquired);

      // A correct implementation should use a single atomic operation
      // (e.g., Redis Lua script via eval/evalsha) for compare-and-delete.
      // BUG: uses separate GET then DEL (2 calls) instead of 1 atomic eval.
      // If the lock value changes between GET and DEL, we'd delete
      // another client's lock.
      const usedEval = mockRedis.eval !== undefined &&
        typeof mockRedis.eval === 'function' &&
        mockRedis.eval.mock.calls.length > 0;
      expect(usedEval).toBe(true);
    });

    it('should return false for null lock', async () => {
      const released = await lock.release(null);
      expect(released).toBe(false);
    });
  });

  describe('extend', () => {
    it('should extend lock TTL', async () => {
      const acquired = await lock.acquire('resource-1');
      mockRedis.get.mockResolvedValue(acquired.value);
      const extended = await lock.extend(acquired, 5000);
      expect(extended).toBe(true);
      expect(mockRedis.pexpire).toHaveBeenCalled();
    });
  });
});

describe('ConnectionPool', () => {
  describe('basic operations', () => {
    it('should acquire connections up to maxSize', async () => {
      const pool = new ConnectionPool(3);
      const conn1 = await pool.acquire();
      const conn2 = await pool.acquire();
      const conn3 = await pool.acquire();

      expect(conn1).toBeDefined();
      expect(conn2).toBeDefined();
      expect(conn3).toBeDefined();

      const stats = pool.getStats();
      expect(stats.active).toBe(3);
    });

    it('should queue when pool exhausted', async () => {
      const pool = new ConnectionPool(1);
      const conn1 = await pool.acquire();

      let acquired = false;
      const pendingAcquire = pool.acquire().then(c => { acquired = true; return c; });

      expect(pool.getStats().waiting).toBe(1);

      // Release should give connection to waiter
      pool.release(conn1);
      await pendingAcquire;
      expect(acquired).toBe(true);
    });

    it('should return released connections to available pool', async () => {
      const pool = new ConnectionPool(2);
      const conn = await pool.acquire();
      pool.release(conn);

      const stats = pool.getStats();
      expect(stats.available).toBe(1);
      expect(stats.active).toBe(0);
    });
  });

  // BUG: When a connection is released and given directly to a waiter,
  // activeCount is not decremented (the waiter path doesn't decrement).
  // This causes activeCount to drift higher than actual active connections.
  describe('active count consistency', () => {
    it('should maintain correct active count through acquire-release cycles', async () => {
      const pool = new ConnectionPool(2);

      // Acquire 2 connections
      const conn1 = await pool.acquire();
      const conn2 = await pool.acquire();
      expect(pool.getStats().active).toBe(2);

      // Release both
      pool.release(conn1);
      pool.release(conn2);
      expect(pool.getStats().active).toBe(0);
    });

    it('should maintain correct active count when releasing to waiter', async () => {
      const pool = new ConnectionPool(1);
      const conn1 = await pool.acquire();

      // Create a waiter
      const waiterPromise = pool.acquire();

      // Release conn1 - should go directly to waiter
      pool.release(conn1);
      const conn2 = await waiterPromise;

      // activeCount should be exactly 1 (the waiter now has it)
      // BUG: activeCount may be 2 because release-to-waiter doesn't decrement
      expect(pool.getStats().active).toBe(1);
    });
  });

  describe('drain', () => {
    it('should clear available connections on drain', () => {
      const pool = new ConnectionPool(5);

      pool.drain();

      const stats = pool.getStats();
      expect(stats.available).toBe(0);
      expect(stats.waiting).toBe(0);
    });

    it('should resolve waiters with null on drain', async () => {
      const pool = new ConnectionPool(1);
      await pool.acquire();

      const waiter = pool.acquire();
      pool.drain();

      const conn = await waiter;
      expect(conn).toBeNull();
    });
  });
});

describe('DocumentLifecycle', () => {
  describe('valid transitions', () => {
    it('should start in draft state', () => {
      const lc = new DocumentLifecycle('doc-1');
      expect(lc.getState()).toBe('draft');
    });

    it('should allow draft -> review', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'user-1');
      expect(lc.getState()).toBe('review');
    });

    it('should allow full happy path lifecycle', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'user-1');
      lc.transition('approved', 'user-2');
      lc.transition('published', 'user-1');
      expect(lc.getState()).toBe('published');
    });

    it('should allow archiving from published', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'u1');
      lc.transition('approved', 'u2');
      lc.transition('published', 'u1');
      lc.transition('archived', 'u1');
      expect(lc.getState()).toBe('archived');
    });

    it('should allow reactivation from archived to draft', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('archived', 'u1');
      lc.transition('draft', 'u1');
      expect(lc.getState()).toBe('draft');
    });
  });

  describe('invalid transitions', () => {
    it('should reject draft -> published (skip review)', () => {
      const lc = new DocumentLifecycle('doc-1');
      expect(() => lc.transition('published', 'u1')).toThrow();
    });

    it('should reject published -> approved (backwards)', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'u1');
      lc.transition('approved', 'u2');
      lc.transition('published', 'u1');
      expect(() => lc.transition('approved', 'u1')).toThrow();
    });
  });

  describe('history tracking', () => {
    it('should record transition history', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'user-a');
      lc.transition('approved', 'user-b');

      const history = lc.getHistory();
      expect(history).toHaveLength(2);
      expect(history[0].from).toBe('draft');
      expect(history[0].to).toBe('review');
      expect(history[0].actor).toBe('user-a');
    });
  });

  describe('reviewers', () => {
    it('should allow adding reviewers in review state', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'u1');
      lc.addReviewer('reviewer-1');
      lc.addReviewer('reviewer-2');
      expect(lc.reviewers).toHaveLength(2);
    });

    it('should reject adding reviewers outside review state', () => {
      const lc = new DocumentLifecycle('doc-1');
      expect(() => lc.addReviewer('reviewer-1')).toThrow();
    });

    it('should clear reviewers when re-entering review', () => {
      const lc = new DocumentLifecycle('doc-1');
      lc.transition('review', 'u1');
      lc.addReviewer('r1');
      lc.transition('approved', 'u2');
      lc.transition('review', 'u2');
      expect(lc.reviewers).toHaveLength(0);
    });
  });

  describe('canTransition', () => {
    it('should report possible transitions', () => {
      const lc = new DocumentLifecycle('doc-1');
      expect(lc.canTransition('review')).toBe(true);
      expect(lc.canTransition('published')).toBe(false);
    });
  });
});
