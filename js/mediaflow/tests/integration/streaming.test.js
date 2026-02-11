/**
 * Streaming Integration Tests
 *
 * Tests HLS streaming, CDN, adaptive bitrate
 */

describe('HLS Streaming', () => {
  let StreamingService;
  let mockStorage;

  beforeEach(() => {
    jest.resetModules();
    mockStorage = global.testUtils.mockHttp();

    const streaming = require('../../../services/streaming/src/services/hls');
    StreamingService = streaming.HLSService;
  });

  describe('Manifest Generation', () => {
    
    it('manifest generation test', async () => {
      const service = new StreamingService(mockStorage);

      const manifest = await service.generateManifest('video-123', {
        profiles: ['1080p', '720p', '480p'],
        segmentDuration: 6,
      });

      // Should have master playlist
      expect(manifest.master).toContain('#EXTM3U');
      expect(manifest.master).toContain('#EXT-X-STREAM-INF');

      // Should have variant playlists
      expect(manifest.variants['1080p']).toContain('#EXTINF');
    });

    
    it('segment duration test', async () => {
      const service = new StreamingService(mockStorage);

      const manifest = await service.generateManifest('video-123', {
        segmentDuration: 4,
        totalDuration: 120,
      });

      // Should have correct number of segments
      // 120 seconds / 4 second segments = 30 segments
      const segmentCount = (manifest.variants['720p'].match(/#EXTINF/g) || []).length;
      expect(segmentCount).toBe(30);
    });

    it('discontinuity handling test', async () => {
      const service = new StreamingService(mockStorage);

      const manifest = await service.generateManifest('video-123', {
        segments: [
          { duration: 6, discontinuity: false },
          { duration: 6, discontinuity: true }, // Ad break
          { duration: 6, discontinuity: false },
        ],
      });

      expect(manifest.variants['720p']).toContain('#EXT-X-DISCONTINUITY');
    });
  });

  describe('Adaptive Bitrate', () => {
    
    it('ABR bandwidth test', async () => {
      const service = new StreamingService(mockStorage);

      const recommendation = service.recommendQuality({
        bandwidth: 5000000, // 5 Mbps
        profiles: {
          '1080p': { bitrate: 5000000 },
          '720p': { bitrate: 2500000 },
          '480p': { bitrate: 1000000 },
        },
      });

      
      expect(recommendation).toBe('720p');
    });

    it('quality switching test', async () => {
      const service = new StreamingService(mockStorage);

      const history = [
        { bandwidth: 5000000 },
        { bandwidth: 2000000 },
        { bandwidth: 3000000 },
      ];

      const recommendation = service.recommendQuality({
        bandwidthHistory: history,
        profiles: {
          '1080p': { bitrate: 5000000 },
          '720p': { bitrate: 2500000 },
          '480p': { bitrate: 1000000 },
        },
      });

      expect(['720p', '480p']).toContain(recommendation);
    });
  });
});

describe('CDN Integration', () => {
  let CDNManager;

  beforeEach(() => {
    jest.resetModules();
    const cdn = require('../../../services/streaming/src/services/cdn');
    CDNManager = cdn.CDNManager;
  });

  describe('Cache Purge', () => {
    
    it('purge completion test', async () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
        distributionId: 'dist-123',
      });

      const result = await manager.purge(['/video/123/*']);

      expect(result.status).toBe('complete');
    });

    it('batch purge test', async () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
      });

      const paths = Array(100).fill(null).map((_, i) => `/video/${i}/*`);

      const result = await manager.purge(paths);

      expect(result.invalidationId).toBeDefined();
    });
  });

  describe('Signed URLs', () => {
    it('signed URL generation test', async () => {
      const manager = new CDNManager({
        provider: 'cloudfront',
        keyPairId: 'KEY123',
      });

      const signedUrl = await manager.generateSignedUrl('/video/123/manifest.m3u8', {
        expiresIn: 3600,
      });

      expect(signedUrl).toContain('Signature=');
      expect(signedUrl).toContain('Expires=');
    });
  });
});

describe('Storage Integration', () => {
  let StorageService;

  beforeEach(() => {
    jest.resetModules();
    const storage = require('../../../services/streaming/src/services/storage');
    StorageService = storage.StorageService;
  });

  describe('Segment Retrieval', () => {
    it('segment fetch test', async () => {
      const mockS3 = {
        getObject: jest.fn().mockResolvedValue({
          Body: Buffer.from('segment-data'),
          ContentType: 'video/mp2t',
        }),
      };

      const storage = new StorageService(mockS3);
      const segment = await storage.getSegment('video-123', 'segment-001.ts');

      expect(segment).toBeDefined();
      expect(mockS3.getObject).toHaveBeenCalled();
    });
  });

  describe('Path Validation', () => {
    
    it('path traversal prevention test', async () => {
      const mockS3 = { getObject: jest.fn() };
      const storage = new StorageService(mockS3, { basePath: '/videos' });

      await expect(
        storage.getFile('../../../etc/passwd')
      ).rejects.toThrow();

      expect(mockS3.getObject).not.toHaveBeenCalled();
    });
  });
});
