/**
 * Resource Exhaustion Chaos Tests
 *
 * Tests CacheManager and DistributedCache under resource pressure.
 * Exercises bugs H1 (no stampede protection), H2 (hot key concentration),
 * H4 (no TTL jitter), H5 (write-through not atomic).
 */

const { CacheManager, DistributedCache, WriteThroughCache } = require('../../services/streaming/src/services/cache');

describe('Memory Exhaustion', () => {
  let mockRedis;

  beforeEach(() => {
    mockRedis = {
      get: jest.fn().mockResolvedValue(null),
      set: jest.fn().mockResolvedValue('OK'),
      setex: jest.fn().mockResolvedValue('OK'),
      del: jest.fn().mockResolvedValue(1),
      keys: jest.fn().mockResolvedValue([]),
    };
  });

  describe('Heap Limits', () => {
    it('should apply TTL jitter to prevent thundering herd', async () => {
      const cache = new CacheManager(mockRedis, { defaultTTL: 300 });
      const ttls = [];

      // Track all TTLs used
      mockRedis.setex = jest.fn().mockImplementation((key, ttl, value) => {
        ttls.push(ttl);
        return Promise.resolve('OK');
      });

      // Set multiple keys with same TTL
      for (let i = 0; i < 20; i++) {
        await cache.set(`key-${i}`, { data: i });
      }

      // BUG H4: jitterPercent is 0, so all TTLs are identical
      // With proper jitter, TTLs should vary
      const uniqueTTLs = new Set(ttls);
      expect(uniqueTTLs.size).toBeGreaterThan(1);
    });

    it('should have non-zero jitter percent', () => {
      const cache = new CacheManager(mockRedis);

      // BUG H4: jitterPercent is 0, should be 0.1-0.2
      expect(cache.jitterPercent).toBeGreaterThan(0);
    });

    it('should protect against cache stampede', async () => {
      const cache = new CacheManager(mockRedis, { defaultTTL: 300 });
      let computeCount = 0;

      const computeFn = () => {
        computeCount++;
        return new Promise(resolve => setTimeout(() => resolve({ value: 'computed' }), 50));
      };

      // Multiple concurrent getOrCompute for same key
      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(cache.getOrCompute('popular-key', computeFn));
      }

      await Promise.all(promises);

      // BUG H1: Without stampede protection, all 10 calls compute independently
      // With proper locking/singleflight, only 1 compute should happen
      expect(computeCount).toBe(1);
    });

    it('should clean up on invalidation', async () => {
      const cache = new CacheManager(mockRedis);

      await cache.set('key1', { data: 'value' });
      await cache.invalidate('key1');

      expect(mockRedis.del).toHaveBeenCalledWith('key1');
    });
  });

  describe('Buffer Limits', () => {
    it('should invalidate by pattern', async () => {
      const cache = new CacheManager(mockRedis);

      mockRedis.keys.mockResolvedValue(['video:1', 'video:2', 'video:3']);
      await cache.invalidatePattern('video:*');

      expect(mockRedis.keys).toHaveBeenCalledWith('video:*');
      expect(mockRedis.del).toHaveBeenCalledWith('video:1', 'video:2', 'video:3');
    });

    it('should handle empty pattern result', async () => {
      const cache = new CacheManager(mockRedis);

      mockRedis.keys.mockResolvedValue([]);
      await cache.invalidatePattern('nonexistent:*');

      expect(mockRedis.del).not.toHaveBeenCalled();
    });
  });
});

describe('CPU Exhaustion', () => {
  describe('Compute Limits', () => {
    it('should distribute keys across nodes in consistent hash ring', () => {
      const nodes = [
        { id: 'node-1', client: { get: jest.fn(), setex: jest.fn() } },
        { id: 'node-2', client: { get: jest.fn(), setex: jest.fn() } },
        { id: 'node-3', client: { get: jest.fn(), setex: jest.fn() } },
      ];

      const cache = new DistributedCache(nodes);

      // Test distribution of keys across nodes
      const nodeAssignments = new Map();
      for (let i = 0; i < 100; i++) {
        const node = cache.getNode(`key-${i}`);
        const count = nodeAssignments.get(node.id) || 0;
        nodeAssignments.set(node.id, count + 1);
      }

      // All nodes should have at least some keys
      expect(nodeAssignments.size).toBe(3);
      for (const [nodeId, count] of nodeAssignments) {
        expect(count).toBeGreaterThan(0);
      }
    });

    it('should spread hot keys across multiple nodes', () => {
      const nodes = [
        { id: 'node-1', client: { get: jest.fn(), setex: jest.fn() } },
        { id: 'node-2', client: { get: jest.fn(), setex: jest.fn() } },
        { id: 'node-3', client: { get: jest.fn(), setex: jest.fn() } },
      ];

      const cache = new DistributedCache(nodes);

      // BUG H2: Popular keys with similar names all hash to same node
      const popularKeys = ['trending-video-1', 'trending-video-2', 'trending-video-3',
                          'trending-video-4', 'trending-video-5'];
      const hotNodes = new Set();
      for (const key of popularKeys) {
        const node = cache.getNode(key);
        hotNodes.add(node.id);
      }

      // With proper hot key spreading, keys should go to different nodes
      expect(hotNodes.size).toBeGreaterThan(1);
    });

    it('should return consistent node for same key', () => {
      const nodes = [
        { id: 'node-1', client: { get: jest.fn(), setex: jest.fn() } },
        { id: 'node-2', client: { get: jest.fn(), setex: jest.fn() } },
      ];

      const cache = new DistributedCache(nodes);

      const node1 = cache.getNode('consistent-key');
      const node2 = cache.getNode('consistent-key');

      expect(node1.id).toBe(node2.id);
    });
  });

  describe('Event Loop Blocking', () => {
    it('should handle hash ring wraparound', () => {
      const nodes = [
        { id: 'node-1', client: { get: jest.fn(), setex: jest.fn() } },
      ];

      const cache = new DistributedCache(nodes);

      // Any key should resolve to the single node
      const node = cache.getNode('any-key');
      expect(node.id).toBe('node-1');
    });

    it('should build hash ring with virtual nodes', () => {
      const nodes = [
        { id: 'node-1', client: { get: jest.fn(), setex: jest.fn() } },
        { id: 'node-2', client: { get: jest.fn(), setex: jest.fn() } },
      ];

      const cache = new DistributedCache(nodes);

      // Ring should have 100 virtual nodes per physical node
      expect(cache.ring.size).toBe(200);
    });
  });
});

describe('Connection Exhaustion', () => {
  describe('Pool Limits', () => {
    it('should write through to both cache and db', async () => {
      const mockCache = {
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue(undefined),
      };
      const mockDb = {
        get: jest.fn().mockResolvedValue({ id: 1, name: 'test' }),
        set: jest.fn().mockResolvedValue(undefined),
      };

      const wtCache = new WriteThroughCache(mockCache, mockDb);

      await wtCache.set('key1', { data: 'value' });

      // BUG H5: cache and db writes are not atomic
      expect(mockCache.set).toHaveBeenCalledWith('key1', { data: 'value' });
      expect(mockDb.set).toHaveBeenCalledWith('key1', { data: 'value' });
    });

    it('should read from cache first on write-through cache', async () => {
      const mockCache = {
        get: jest.fn().mockResolvedValue({ data: 'cached' }),
        set: jest.fn().mockResolvedValue(undefined),
      };
      const mockDb = {
        get: jest.fn(),
        set: jest.fn(),
      };

      const wtCache = new WriteThroughCache(mockCache, mockDb);
      const result = await wtCache.get('key1');

      expect(result).toEqual({ data: 'cached' });
      expect(mockDb.get).not.toHaveBeenCalled();
    });

    it('should fall back to db on cache miss', async () => {
      const mockCache = {
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue(undefined),
      };
      const mockDb = {
        get: jest.fn().mockResolvedValue({ data: 'from-db' }),
        set: jest.fn(),
      };

      const wtCache = new WriteThroughCache(mockCache, mockDb);
      const result = await wtCache.get('key1');

      expect(result).toEqual({ data: 'from-db' });
      expect(mockCache.set).toHaveBeenCalledWith('key1', { data: 'from-db' });
    });
  });

  describe('Socket Limits', () => {
    it('should handle null redis gracefully in CacheManager', async () => {
      const cache = new CacheManager(null);
      const result = await cache.get('key1');
      expect(result).toBeNull();
    });

    it('should handle null redis on set', async () => {
      const cache = new CacheManager(null);
      // Should not throw
      await expect(cache.set('key1', 'value')).resolves.not.toThrow();
    });
  });
});

describe('File Descriptor Exhaustion', () => {
  describe('FD Limits', () => {
    it('should parse cached JSON values correctly', async () => {
      const mockRedis = {
        get: jest.fn().mockResolvedValue(JSON.stringify({ id: 1, name: 'test' })),
        setex: jest.fn().mockResolvedValue('OK'),
      };

      const cache = new CacheManager(mockRedis);
      const result = await cache.get('key1');

      expect(result).toEqual({ id: 1, name: 'test' });
    });

    it('should serialize values when setting cache', async () => {
      const mockRedis = {
        setex: jest.fn().mockResolvedValue('OK'),
      };

      const cache = new CacheManager(mockRedis, { defaultTTL: 600 });
      await cache.set('key1', { id: 1 });

      expect(mockRedis.setex).toHaveBeenCalledWith('key1', 600, JSON.stringify({ id: 1 }));
    });
  });
});

describe('Disk Exhaustion', () => {
  describe('Storage Limits', () => {
    it('should use default TTL when not specified', async () => {
      const mockRedis = {
        setex: jest.fn().mockResolvedValue('OK'),
      };

      const cache = new CacheManager(mockRedis, { defaultTTL: 300 });
      await cache.set('key1', 'value');

      // Should use default TTL of 300
      expect(mockRedis.setex).toHaveBeenCalledWith('key1', 300, expect.any(String));
    });

    it('should use custom TTL when provided', async () => {
      const mockRedis = {
        setex: jest.fn().mockResolvedValue('OK'),
      };

      const cache = new CacheManager(mockRedis, { defaultTTL: 300 });
      await cache.set('key1', 'value', 600);

      expect(mockRedis.setex).toHaveBeenCalledWith('key1', 600, expect.any(String));
    });

    it('should return computed value on cache miss in getOrCompute', async () => {
      const mockRedis = {
        get: jest.fn().mockResolvedValue(null),
        setex: jest.fn().mockResolvedValue('OK'),
      };

      const cache = new CacheManager(mockRedis);
      const result = await cache.getOrCompute('missing', () => Promise.resolve({ computed: true }));

      expect(result).toEqual({ computed: true });
      expect(mockRedis.setex).toHaveBeenCalled();
    });
  });
});
