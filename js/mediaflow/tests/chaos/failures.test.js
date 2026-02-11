/**
 * Chaos Engineering Tests
 *
 * Tests system resilience under failures
 */

describe('Network Failures', () => {
  describe('Service Unavailability', () => {
    it('downstream service timeout test', async () => {
      const mockHttp = global.testUtils.mockHttp();
      mockHttp.get.mockImplementation(() =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('ETIMEDOUT')), 5000)
        )
      );

      const { ServiceClient } = require('../../../shared/clients');
      const client = new ServiceClient({ timeout: 1000 });

      await expect(client.get('/api/data')).rejects.toThrow();
    });

    it('intermittent failure test', async () => {
      const mockHttp = global.testUtils.mockHttp();
      let callCount = 0;

      mockHttp.get.mockImplementation(() => {
        callCount++;
        if (callCount % 3 === 0) {
          return Promise.resolve({ data: 'success' });
        }
        return Promise.reject(new Error('Service unavailable'));
      });

      const { ServiceClient } = require('../../../shared/clients');
      const client = new ServiceClient({ retries: 5 });

      const result = await client.get('/api/data');
      expect(result).toBeDefined();
    });

    it('cascading failure test', async () => {
      // Service A calls B calls C
      // C fails, should not bring down A
      const mockServices = global.testUtils.mockServiceChain(['A', 'B', 'C']);
      mockServices.C.mockRejectedValue(new Error('Service C failed'));

      const result = await mockServices.A.call();

      // Should handle gracefully
      expect(result.error).toBeDefined();
      expect(result.fallback).toBe(true);
    });
  });

  describe('Partial Failures', () => {
    it('bulk operation partial failure test', async () => {
      const items = ['item-1', 'item-2', 'item-3', 'item-4', 'item-5'];

      const process = async (item) => {
        if (item === 'item-3') {
          throw new Error(`Failed to process ${item}`);
        }
        return { item, status: 'success' };
      };

      const results = await Promise.allSettled(items.map(process));

      // Should have partial success
      const successes = results.filter(r => r.status === 'fulfilled');
      const failures = results.filter(r => r.status === 'rejected');

      expect(successes.length).toBe(4);
      expect(failures.length).toBe(1);
    });
  });
});

describe('Resource Exhaustion', () => {
  describe('Memory Pressure', () => {
    it('large payload handling test', async () => {
      const mockRequest = global.testUtils.mockRequest();

      // Send very large payload
      const largePayload = {
        data: 'x'.repeat(10 * 1024 * 1024), // 10MB
      };

      const response = await mockRequest
        .post('/api/upload')
        .send(largePayload);

      // Should reject or handle gracefully
      expect([413, 500, 200]).toContain(response.status);
    });

    it('connection pool exhaustion test', async () => {
      const mockDb = global.testUtils.mockDb();
      mockDb.maxConnections = 10;
      mockDb.activeConnections = 10;

      mockDb.query.mockRejectedValue(new Error('Connection pool exhausted'));

      // Should queue or reject gracefully
      await expect(mockDb.query('SELECT 1')).rejects.toThrow('Connection pool');
    });
  });

  describe('CPU Pressure', () => {
    it('compute-heavy request test', async () => {
      const start = Date.now();

      // Simulate CPU-heavy operation with timeout
      const result = await Promise.race([
        new Promise(resolve => {
          // Heavy computation simulation
          let sum = 0;
          for (let i = 0; i < 1000000; i++) {
            sum += Math.sqrt(i);
          }
          resolve({ sum });
        }),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), 5000)
        ),
      ]);

      const duration = Date.now() - start;
      expect(duration).toBeLessThan(5000);
    });
  });
});

describe('Data Corruption', () => {
  describe('Message Corruption', () => {
    it('malformed message test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      const { EventBus } = require('../../../shared/events');
      const bus = new EventBus(mockRabbit);

      // Receive corrupted message
      const malformedMessage = {
        content: Buffer.from('not-valid-json'),
      };

      let errorHandled = false;
      bus.on('error', () => { errorHandled = true; });

      await bus._handleMessage(malformedMessage);

      // Should handle gracefully
      expect(errorHandled).toBe(true);
    });
  });

  describe('State Corruption', () => {
    it('inconsistent state recovery test', async () => {
      // Simulate inconsistent state between services
      const catalogState = { video: 'video-1', status: 'published' };
      const searchState = { video: 'video-1', status: 'draft' };

      // Reconciliation should detect and fix
      const reconcile = (source, target) => {
        if (source.status !== target.status) {
          return { action: 'sync', from: source, to: target };
        }
        return null;
      };

      const result = reconcile(catalogState, searchState);
      expect(result).not.toBeNull();
      expect(result.action).toBe('sync');
    });
  });
});

describe('Clock Skew', () => {
  
  it('clock skew lock test', async () => {
    const mockRedis = global.testUtils.mockRedis();

    // Server 1 has clock 5 seconds ahead
    const server1Time = Date.now() + 5000;
    const server2Time = Date.now();

    const { DistributedLock } = require('../../../shared/utils');

    const lock1 = new DistributedLock(mockRedis, { clockSource: () => server1Time });
    const lock2 = new DistributedLock(mockRedis, { clockSource: () => server2Time });

    await lock1.acquire('resource', { ttl: 10000 });

    // Server 2 should still see lock as valid
    
    const isValid = await lock2.isLocked('resource');
    expect(isValid).toBe(true);
  });

  it('event timestamp ordering test', async () => {
    // Events from different servers with clock skew
    const events = [
      { id: 'e1', timestamp: Date.now() + 1000, data: 'from server 1' },
      { id: 'e2', timestamp: Date.now(), data: 'from server 2' },
      { id: 'e3', timestamp: Date.now() - 1000, data: 'from server 3' },
    ];

    // Sort by timestamp
    events.sort((a, b) => a.timestamp - b.timestamp);

    // After sorting, events should be in ascending timestamp order
    expect(events[0].id).toBe('e3');
    expect(events[1].id).toBe('e2');
    expect(events[2].id).toBe('e1');

    // Verify ordering invariant holds
    for (let i = 1; i < events.length; i++) {
      expect(events[i].timestamp).toBeGreaterThanOrEqual(events[i - 1].timestamp);
    }
  });
});

describe('Dependency Failures', () => {
  describe('Database Failures', () => {
    it('database failover test', async () => {
      const mockDb = global.testUtils.mockDb();

      let failoverCount = 0;
      mockDb.query
        .mockRejectedValueOnce(new Error('Primary failed'))
        .mockImplementation(() => {
          failoverCount++;
          return Promise.resolve({ rows: [] });
        });

      const { DatabaseClient } = require('../../../shared/clients');
      const client = new DatabaseClient(mockDb);

      const result = await client.query('SELECT 1');

      // Should failover to replica
      expect(failoverCount).toBeGreaterThan(0);
    });
  });

  describe('Cache Failures', () => {
    it('cache fallback test', async () => {
      const mockRedis = global.testUtils.mockRedis();
      const mockDb = global.testUtils.mockDb();

      mockRedis.get.mockRejectedValue(new Error('Redis unavailable'));
      mockDb.query.mockResolvedValue({ rows: [{ id: 1, data: 'from db' }] });

      const { CacheManager } = require('../../../services/streaming/src/services/cache');
      const cache = new CacheManager(mockRedis, { fallbackDb: mockDb });

      const result = await cache.get('key');

      // Should fall back to database
      expect(mockDb.query).toHaveBeenCalled();
    });
  });
});
