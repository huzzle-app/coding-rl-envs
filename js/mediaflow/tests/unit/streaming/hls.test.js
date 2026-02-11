/**
 * HLS Streaming Unit Tests
 */

describe('HLSService', () => {
  let HLSService;
  let mockStorage;

  beforeEach(() => {
    jest.resetModules();
    mockStorage = global.testUtils.mockHttp();
    const hls = require('../../../../services/streaming/src/services/hls');
    HLSService = hls.HLSService;
  });

  describe('master playlist generation', () => {
    it('should generate valid master playlist', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['1080p', '720p'],
      });

      expect(manifest.master).toContain('#EXTM3U');
      expect(manifest.master).toContain('#EXT-X-STREAM-INF');
    });

    it('should include all profiles', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['1080p', '720p', '480p'],
      });

      expect(manifest.master).toContain('1080p/playlist.m3u8');
      expect(manifest.master).toContain('720p/playlist.m3u8');
      expect(manifest.master).toContain('480p/playlist.m3u8');
    });

    it('should include bandwidth info', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['1080p'],
      });

      expect(manifest.master).toContain('BANDWIDTH=');
    });

    it('should include resolution info', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['1080p'],
      });

      expect(manifest.master).toContain('RESOLUTION=');
    });
  });

  describe('variant playlist generation', () => {
    it('should generate valid variant playlist', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['720p'],
        totalDuration: 60,
        segmentDuration: 6,
      });

      expect(manifest.variants['720p']).toContain('#EXTM3U');
      expect(manifest.variants['720p']).toContain('#EXTINF');
    });

    it('should have correct segment count', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['720p'],
        totalDuration: 60,
        segmentDuration: 6,
      });

      const segmentCount = (manifest.variants['720p'].match(/#EXTINF/g) || []).length;
      expect(segmentCount).toBe(10);
    });

    it('should set target duration', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['720p'],
        segmentDuration: 6,
      });

      expect(manifest.variants['720p']).toContain('#EXT-X-TARGETDURATION:6');
    });

    it('should include end list marker', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['720p'],
      });

      expect(manifest.variants['720p']).toContain('#EXT-X-ENDLIST');
    });

    it('should handle discontinuity', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateManifest('video-1', {
        profiles: ['720p'],
        segments: [
          { duration: 6, discontinuity: false },
          { duration: 6, discontinuity: true },
        ],
      });

      expect(manifest.variants['720p']).toContain('#EXT-X-DISCONTINUITY');
    });
  });

  describe('live streaming', () => {
    it('should generate live manifest', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateLiveManifest('live-1', {
        windowSize: 30,
        segmentDuration: 6,
      });

      expect(manifest).toContain('#EXT-X-PLAYLIST-TYPE:EVENT');
    });

    it('should respect window size', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateLiveManifest('live-1', {
        windowSize: 30,
        segmentDuration: 6,
      });

      const segmentCount = (manifest.match(/#EXTINF/g) || []).length;
      expect(segmentCount).toBeLessThanOrEqual(6);
    });

    it('should support DVR window', async () => {
      const service = new HLSService(mockStorage);
      const manifest = await service.generateLiveManifest('live-1', {
        dvrWindowSize: 3600,
        segmentDuration: 6,
      });

      const segmentCount = (manifest.match(/#EXTINF/g) || []).length;
      expect(segmentCount).toBeGreaterThan(10);
    });
  });

  describe('adaptive bitrate', () => {
    it('should recommend quality based on bandwidth', () => {
      const service = new HLSService(mockStorage);
      const quality = service.recommendQuality({
        bandwidth: 10000000,
        profiles: {
          '1080p': { bitrate: 5000000 },
          '720p': { bitrate: 2500000 },
        },
      });

      expect(quality).toBe('1080p');
    });

    it('should use conservative estimate with history', () => {
      const service = new HLSService(mockStorage);
      const quality = service.recommendQuality({
        bandwidthHistory: [
          { bandwidth: 5000000 },
          { bandwidth: 2000000 },
          { bandwidth: 3000000 },
        ],
        profiles: {
          '1080p': { bitrate: 5000000 },
          '720p': { bitrate: 2500000 },
          '480p': { bitrate: 1000000 },
        },
      });

      expect(['720p', '480p']).toContain(quality);
    });

    it('should fall back to lowest quality', () => {
      const service = new HLSService(mockStorage);
      const quality = service.recommendQuality({
        bandwidth: 100000,
        profiles: {
          '1080p': { bitrate: 5000000 },
          '720p': { bitrate: 2500000 },
          '480p': { bitrate: 1000000 },
        },
      });

      expect(quality).toBe('480p');
    });
  });
});

describe('StorageService', () => {
  let StorageService;
  let mockS3;

  beforeEach(() => {
    jest.resetModules();
    mockS3 = {
      getObject: jest.fn().mockResolvedValue({ Body: Buffer.from('data') }),
      putObject: jest.fn().mockResolvedValue({}),
      deleteObject: jest.fn().mockResolvedValue({}),
      listObjectsV2: jest.fn().mockResolvedValue({ Contents: [] }),
    };
    const storage = require('../../../../services/streaming/src/services/storage');
    StorageService = storage.StorageService;
  });

  describe('file operations', () => {
    it('should get segment', async () => {
      const service = new StorageService(mockS3);
      await service.getSegment('video-1', 'segment-001.ts');
      expect(mockS3.getObject).toHaveBeenCalled();
    });

    it('should support range requests', async () => {
      const service = new StorageService(mockS3);
      await service.getSegment('video-1', 'segment-001.ts', { range: 'bytes=0-1000' });
      expect(mockS3.getObject).toHaveBeenCalledWith(
        expect.objectContaining({ Range: 'bytes=0-1000' })
      );
    });

    it('should put file', async () => {
      const service = new StorageService(mockS3);
      await service.putFile('video-1/test.ts', Buffer.from('data'));
      expect(mockS3.putObject).toHaveBeenCalled();
    });

    it('should delete file', async () => {
      const service = new StorageService(mockS3);
      await service.deleteFile('video-1/test.ts');
      expect(mockS3.deleteObject).toHaveBeenCalled();
    });

    it('should list files', async () => {
      const service = new StorageService(mockS3);
      await service.listFiles('video-1/');
      expect(mockS3.listObjectsV2).toHaveBeenCalled();
    });
  });
});
