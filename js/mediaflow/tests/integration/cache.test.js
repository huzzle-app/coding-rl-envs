/**
 * Cache Integration Tests
 *
 * Tests bugs H1 (stampede), H2 (hot keys), H4 (TTL jitter)
 */

describe('CacheManager', () => {
  let CacheManager;
  let mockRedis;

  beforeEach(() => {
    jest.resetModules();

    mockRedis = global.testUtils.mockRedis();

    const cache = require('../../../services/streaming/src/services/cache');
    CacheManager = cache.CacheManager;
  });

  describe('cache stampede', () => {
    
    it('cache stampede test', async () => {
      const manager = new CacheManager(mockRedis);

      let computeCount = 0;
      const expensiveCompute = async () => {
        computeCount++;
        await global.testUtils.delay(50);
        return { data: 'result' };
      };

      // Simulate cache miss with many concurrent requests
      mockRedis.get.mockResolvedValue(null);

      const requests = Array(10).fill(null).map(() =>
        manager.getOrCompute('popular-key', expensiveCompute)
      );

      await Promise.all(requests);

      
      // Should only compute once
      expect(computeCount).toBe(1);
    });

    it('concurrent miss test', async () => {
      const manager = new CacheManager(mockRedis);

      let computeCount = 0;
      const compute = async () => {
        computeCount++;
        return { timestamp: Date.now() };
      };

      mockRedis.get.mockResolvedValue(null);

      // Concurrent requests for same key
      await Promise.all([
        manager.getOrCompute('key', compute),
        manager.getOrCompute('key', compute),
        manager.getOrCompute('key', compute),
      ]);

      // Should coalesce into single compute
      expect(computeCount).toBe(1);
    });
  });

  describe('TTL jitter', () => {
    
    it('TTL jitter test', async () => {
      const manager = new CacheManager(mockRedis, { defaultTTL: 300 });

      const ttls = [];

      mockRedis.setex = jest.fn(async (key, ttl) => {
        ttls.push(ttl);
        return 'OK';
      });

      // Set multiple keys with same TTL
      for (let i = 0; i < 10; i++) {
        await manager.set(`key-${i}`, { data: i });
      }

      
      // Should have jitter (variation)
      const uniqueTTLs = new Set(ttls);
      expect(uniqueTTLs.size).toBeGreaterThan(1);
    });

    it('thundering herd test', async () => {
      const manager = new CacheManager(mockRedis, { defaultTTL: 300 });

      const ttls = [];

      mockRedis.setex = jest.fn(async (key, ttl) => {
        ttls.push(ttl);
        return 'OK';
      });

      // Bulk cache population
      await Promise.all(
        Array(100).fill(null).map((_, i) =>
          manager.set(`key-${i}`, { data: i })
        )
      );

      // TTLs should not all expire at same time
      const minTTL = Math.min(...ttls);
      const maxTTL = Math.max(...ttls);
      expect(maxTTL - minTTL).toBeGreaterThan(0);
    });
  });
});

describe('CDNManager', () => {
  let CDNManager;

  beforeEach(() => {
    jest.resetModules();
    const cdn = require('../../../services/streaming/src/services/cdn');
    CDNManager = cdn.CDNManager;
  });

  describe('cache purge', () => {
    
    it('CDN purge test', async () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
        distributionId: 'dist-123',
      });

      const purgeResult = await manager.purge(['/video/123/*']);

      // Purge should wait for propagation
      const status = await manager.getPurgeStatus(purgeResult.invalidationId);

      
      // Should wait or return when complete
      expect(status.status).toBe('complete');
    });

    it('cache invalidation test', async () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
      });

      const result = await manager.purge(['/manifest/video-1', '/segments/video-1/*']);

      expect(result.invalidationId).toBeDefined();

      // Wait for completion
      await global.testUtils.delay(6000);

      const status = await manager.getPurgeStatus(result.invalidationId);
      expect(status.status).toBe('complete');
    });
  });
});
