/**
 * CDN Manager Unit Tests
 */

describe('CDNManager', () => {
  let CDNManager;

  beforeEach(() => {
    jest.resetModules();
    const cdn = require('../../../../services/streaming/src/services/cdn');
    CDNManager = cdn.CDNManager;
  });

  describe('cache invalidation', () => {
    it('should create invalidation request', async () => {
      const manager = new CDNManager({ provider: 'cloudfront', distributionId: 'dist-123' });
      const result = await manager.purge(['/video/123/*']);
      expect(result.invalidationId).toBeDefined();
    });

    it('should handle multiple paths', async () => {
      const manager = new CDNManager({ provider: 'cloudfront' });
      const paths = ['/video/1/*', '/video/2/*', '/video/3/*'];
      const result = await manager.purge(paths);
      expect(result.paths).toHaveLength(3);
    });

    it('should batch large purge requests', async () => {
      const manager = new CDNManager({ provider: 'cloudfront' });
      const paths = Array(100).fill(null).map((_, i) => `/video/${i}/*`);
      const result = await manager.purge(paths);
      expect(result.batches).toBeGreaterThan(0);
    });

    it('should return purge status', async () => {
      const manager = new CDNManager({ provider: 'cloudfront' });
      const result = await manager.purge(['/video/123/*']);
      const status = await manager.getPurgeStatus(result.invalidationId);
      expect(['in_progress', 'complete']).toContain(status.status);
    });

    it('should wait for completion if requested', async () => {
      const manager = new CDNManager({ provider: 'cloudfront' });
      const result = await manager.purge(['/video/123/*'], { waitForCompletion: true });
      expect(result.status).toBe('complete');
    });
  });

  describe('signed URLs', () => {
    it('should generate signed URL', async () => {
      const manager = new CDNManager({ provider: 'cloudfront', keyPairId: 'KEY123' });
      const url = await manager.generateSignedUrl('/video/123/manifest.m3u8', { expiresIn: 3600 });
      expect(url).toContain('Signature=');
    });

    it('should include expiration', async () => {
      const manager = new CDNManager({ provider: 'cloudfront' });
      const expiry = Math.floor(Date.now() / 1000) + 3600;
      const url = await manager.generateSignedUrl('/video/123/manifest.m3u8', { expiresAt: expiry });
      expect(url).toContain(`Expires=${expiry}`);
    });

    it('should include key pair ID', async () => {
      const manager = new CDNManager({ provider: 'cloudfront', keyPairId: 'KEY123' });
      const url = await manager.generateSignedUrl('/video/123/manifest.m3u8');
      expect(url).toContain('Key-Pair-Id=KEY123');
    });

    it('should support custom policy', async () => {
      const manager = new CDNManager({ provider: 'cloudfront' });
      const url = await manager.generateSignedUrl('/video/123/*', {
        policy: { ipRange: '192.168.1.0/24' },
      });
      expect(url).toContain('Policy=');
    });
  });

  describe('origin configuration', () => {
    it('should configure S3 origin', () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
        origin: { type: 's3', bucket: 'my-bucket' },
      });
      expect(manager.config.origin.type).toBe('s3');
    });

    it('should configure custom origin', () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
        origin: { type: 'custom', domain: 'origin.example.com' },
      });
      expect(manager.config.origin.type).toBe('custom');
    });
  });

  describe('cache behaviors', () => {
    it('should set default TTL', () => {
      const manager = new CDNManager({ defaultTTL: 86400 });
      expect(manager.config.defaultTTL).toBe(86400);
    });

    it('should set max TTL', () => {
      const manager = new CDNManager({ maxTTL: 604800 });
      expect(manager.config.maxTTL).toBe(604800);
    });

    it('should configure cache key policy', () => {
      const manager = new CDNManager({
        cacheKey: { includeQueryStrings: ['quality', 'token'] },
      });
      expect(manager.config.cacheKey.includeQueryStrings).toContain('quality');
    });
  });
});

describe('CacheManager', () => {
  let CacheManager;
  let mockRedis;

  beforeEach(() => {
    jest.resetModules();
    mockRedis = global.testUtils.mockRedis();
    const cache = require('../../../../services/streaming/src/services/cache');
    CacheManager = cache.CacheManager;
  });

  describe('basic operations', () => {
    it('should get cached value', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({ data: 'test' }));
      const manager = new CacheManager(mockRedis);
      const value = await manager.get('key');
      expect(value).toEqual({ data: 'test' });
    });

    it('should set value with TTL', async () => {
      const manager = new CacheManager(mockRedis);
      await manager.set('key', { data: 'test' }, 300);
      expect(mockRedis.setex).toHaveBeenCalledWith('key', 300, expect.any(String));
    });

    it('should delete value', async () => {
      const manager = new CacheManager(mockRedis);
      await manager.delete('key');
      expect(mockRedis.del).toHaveBeenCalledWith('key');
    });

    it('should check existence', async () => {
      mockRedis.get.mockResolvedValue('value');
      const manager = new CacheManager(mockRedis);
      const exists = await manager.exists('key');
      expect(exists).toBe(true);
    });
  });

  describe('getOrCompute', () => {
    it('should return cached value if exists', async () => {
      mockRedis.get.mockResolvedValue(JSON.stringify({ data: 'cached' }));
      const manager = new CacheManager(mockRedis);
      const compute = jest.fn();

      const value = await manager.getOrCompute('key', compute);

      expect(value).toEqual({ data: 'cached' });
      expect(compute).not.toHaveBeenCalled();
    });

    it('should compute and cache if missing', async () => {
      mockRedis.get.mockResolvedValue(null);
      const manager = new CacheManager(mockRedis);
      const compute = jest.fn().mockResolvedValue({ data: 'computed' });

      const value = await manager.getOrCompute('key', compute);

      expect(value).toEqual({ data: 'computed' });
      expect(compute).toHaveBeenCalled();
      expect(mockRedis.setex).toHaveBeenCalled();
    });
  });
});
