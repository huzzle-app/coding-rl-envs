/**
 * Transcode Service Unit Tests
 *
 * Tests video transcoding, job management, worker coordination
 */

describe('TranscodeService', () => {
  let TranscodeService;
  let mockExec;

  beforeEach(() => {
    jest.resetModules();

    mockExec = jest.fn((cmd, callback) => {
      callback(null, { stdout: 'success', stderr: '' });
    });

    jest.doMock('child_process', () => ({
      exec: mockExec,
    }));

    const transcode = require('../../../../services/transcode/src/services/transcode');
    TranscodeService = transcode.TranscodeService;
  });

  describe('Job Creation', () => {
    it('create job test', async () => {
      const service = new TranscodeService();

      const job = await service.createJob({
        videoId: 'video-123',
        inputUrl: 's3://bucket/input.mp4',
        profiles: ['1080p', '720p'],
      });

      expect(job).toHaveProperty('id');
      expect(job.status).toBe('pending');
    });

    it('job validation test', async () => {
      const service = new TranscodeService();

      await expect(
        service.createJob({ videoId: 'video-123' })
      ).rejects.toThrow('inputUrl is required');
    });
  });

  describe('Transcoding', () => {
    
    it('bitrate calculation test', async () => {
      const service = new TranscodeService();

      const bitrate = service.calculateBitrate({
        width: 1920,
        height: 1080,
        frameRate: 30,
        codec: 'h264',
      });

      expect(bitrate).toBeGreaterThan(4000000);
      expect(bitrate).toBeLessThan(10000000);
    });

    
    it('command injection prevention test', async () => {
      const service = new TranscodeService();

      await service.transcode({
        inputPath: '/videos/test; rm -rf /',
        outputPath: '/output/test.mp4',
      });

      const command = mockExec.mock.calls[0][0];
      expect(command).not.toContain('; rm');
    });
  });

  describe('Profile Generation', () => {
    it('generate profiles test', async () => {
      const service = new TranscodeService();

      const profiles = service.generateProfiles({
        width: 1920,
        height: 1080,
      });

      expect(profiles).toContainEqual(
        expect.objectContaining({ name: '1080p' })
      );
      expect(profiles).toContainEqual(
        expect.objectContaining({ name: '720p' })
      );
    });

    
    it('HDR preservation test', async () => {
      const service = new TranscodeService();

      const profiles = service.generateProfiles({
        width: 3840,
        height: 2160,
        hdr: true,
        colorSpace: 'bt2020',
      });

      const profile4k = profiles.find(p => p.name === '2160p');
      expect(profile4k.hdr).toBe(true);
      expect(profile4k.colorSpace).toBe('bt2020');
    });
  });

  describe('HLS Segmentation', () => {
    
    it('keyframe alignment test', async () => {
      const service = new TranscodeService();

      const segments = await service.generateSegments({
        inputPath: '/videos/test.mp4',
        segmentDuration: 6,
      });

      for (const segment of segments) {
        expect(segment.startsWithKeyframe).toBe(true);
      }
    });
  });
});

describe('TranscodeWorker', () => {
  let TranscodeWorker;
  let mockRedis;
  let mockRabbit;

  beforeEach(() => {
    jest.resetModules();
    mockRedis = global.testUtils.mockRedis();
    mockRabbit = global.testUtils.mockRabbit();

    const worker = require('../../../../services/transcode/src/worker');
    TranscodeWorker = worker.TranscodeWorker;
  });

  describe('Job Processing', () => {
    it('process job test', async () => {
      const worker = new TranscodeWorker(mockRedis, mockRabbit);

      const job = {
        id: 'job-123',
        videoId: 'video-123',
        inputUrl: 's3://bucket/input.mp4',
      };

      const result = await worker.processJob(job);
      expect(result.status).toBe('completed');
    });
  });

  describe('Worker Coordination', () => {
    
    it('single worker per job test', async () => {
      const worker1 = new TranscodeWorker(mockRedis, mockRabbit);
      const worker2 = new TranscodeWorker(mockRedis, mockRabbit);

      const job = { id: 'job-123', videoId: 'video-123' };

      const [claim1, claim2] = await Promise.all([
        worker1.claimJob(job),
        worker2.claimJob(job),
      ]);

      const claimCount = [claim1, claim2].filter(Boolean).length;
      expect(claimCount).toBe(1);
    });
  });
});

describe('BitrateCalculator', () => {
  let BitrateCalculator;

  beforeEach(() => {
    jest.resetModules();
    const bitrate = require('../../../../services/transcode/src/services/bitrate');
    BitrateCalculator = bitrate.BitrateCalculator;
  });

  describe('Calculation', () => {
    
    it('float precision test', () => {
      const calc = new BitrateCalculator();

      const results = [];
      for (let i = 0; i < 10; i++) {
        results.push(calc.calculate(1920, 1080, 30));
      }

      const unique = new Set(results);
      expect(unique.size).toBe(1);
    });

    it('resolution scaling test', () => {
      const calc = new BitrateCalculator();

      const bitrate1080 = calc.calculate(1920, 1080, 30);
      const bitrate720 = calc.calculate(1280, 720, 30);

      expect(bitrate1080).toBeGreaterThan(bitrate720);
    });

    it('codec efficiency test', () => {
      const calc = new BitrateCalculator();

      const bitrateH264 = calc.calculate(1920, 1080, 30, 'h264');
      const bitrateH265 = calc.calculate(1920, 1080, 30, 'h265');

      expect(bitrateH265).toBeLessThan(bitrateH264);
    });
  });
});
