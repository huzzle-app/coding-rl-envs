/**
 * Recommendations Service Unit Tests
 *
 * Tests bugs B5 (event ordering), B6 (projection race), H2 (hot key)
 */

describe('RecommendationEventProcessor', () => {
  let RecommendationEventProcessor;
  let processor;

  beforeEach(() => {
    jest.resetModules();
    const recommendations = require('../../../services/recommendations/src/index');
    RecommendationEventProcessor = recommendations.RecommendationEventProcessor;
    processor = new RecommendationEventProcessor();
  });

  describe('event ordering', () => {
    
    it('event ordering test', async () => {
      const events = [
        { type: 'VIDEO_WATCHED', timestamp: 3, data: { userId: 'u1', videoId: 'v1', watchDuration: 100, totalDuration: 200 } },
        { type: 'VIDEO_WATCHED', timestamp: 1, data: { userId: 'u1', videoId: 'v2', watchDuration: 50, totalDuration: 100 } },
        { type: 'VIDEO_WATCHED', timestamp: 2, data: { userId: 'u1', videoId: 'v3', watchDuration: 75, totalDuration: 150 } },
      ];

      await processor.replayEvents(events);

      
      // But they're processed in array order
      expect(processor.projectionVersion).toBe(3);

      // The projection should reflect correct temporal ordering
      // This would matter for features like "last watched"
    });

    
    it('concurrent events test', async () => {
      const results = [];

      processor.processEvent = async (event) => {
        results.push(`start-${event.data.videoId}`);
        await global.testUtils.delay(Math.random() * 50);
        results.push(`end-${event.data.videoId}`);
      };

      const events = [
        { type: 'VIDEO_WATCHED', timestamp: 1, data: { videoId: 'v1' } },
        { type: 'VIDEO_WATCHED', timestamp: 2, data: { videoId: 'v2' } },
        { type: 'VIDEO_WATCHED', timestamp: 3, data: { videoId: 'v3' } },
      ];

      await processor.replayEvents(events);

      // Events should be serialized
      expect(results).toEqual([
        'start-v1', 'end-v1',
        'start-v2', 'end-v2',
        'start-v3', 'end-v3',
      ]);
    });
  });

  describe('projection rebuild race', () => {
    
    it('projection rebuild test', async () => {
      // Start rebuild
      const rebuildPromise = processor.rebuildProjection([
        { type: 'VIDEO_WATCHED', timestamp: 1, data: { userId: 'u1', videoId: 'v1', watchDuration: 100, totalDuration: 200 } },
        { type: 'VIDEO_WATCHED', timestamp: 2, data: { userId: 'u1', videoId: 'v2', watchDuration: 100, totalDuration: 200 } },
      ]);

      // Concurrent live event during rebuild
      await processor.processEvent({
        type: 'VIDEO_WATCHED',
        timestamp: 3,
        data: { userId: 'u2', videoId: 'v3', watchDuration: 100, totalDuration: 200 },
      });

      await rebuildPromise;

      
      // Projection should either include v3 or not, consistently
      expect(processor.projectionVersion).toBeGreaterThan(0);
    });

    
    it('concurrent rebuild test', async () => {
      let rebuildCount = 0;
      const originalRebuild = processor.rebuildProjection.bind(processor);

      processor.rebuildProjection = async (events) => {
        rebuildCount++;
        if (rebuildCount > 1) {
          throw new Error('Concurrent rebuild detected');
        }
        await originalRebuild(events);
        rebuildCount--;
      };

      const events = [
        { type: 'VIDEO_WATCHED', timestamp: 1, data: { userId: 'u1', videoId: 'v1', watchDuration: 100, totalDuration: 200 } },
      ];

      
      await expect(Promise.all([
        processor.rebuildProjection(events),
        processor.rebuildProjection(events),
      ])).rejects.toThrow('Concurrent rebuild');
    });
  });
});

describe('RecommendationCache', () => {
  let RecommendationCache;
  let cache;

  beforeEach(() => {
    jest.resetModules();
    const recommendations = require('../../../services/recommendations/src/index');
    RecommendationCache = recommendations.RecommendationCache;
    cache = new RecommendationCache();
  });

  describe('hot key prevention', () => {
    
    it('hot key test', async () => {
      // Simulate many concurrent requests for popular videos
      const requests = Array(100).fill(null).map(() =>
        cache.getPopularVideos()
      );

      await Promise.all(requests);

      
      // Should be sharded across multiple keys
      const hitsByKey = {};
      for (const [key, hits] of cache.hits.entries()) {
        hitsByKey[key] = hits;
      }

      // Should have hits spread across multiple keys
      const keyCount = Object.keys(hitsByKey).length;
      expect(keyCount).toBeGreaterThan(1);
    });

    
    it('popular video sharding test', async () => {
      const videos = Array(100).fill(null).map((_, i) => ({
        videoId: `v${i}`,
        score: Math.random() * 1000,
      }));

      await cache.setPopularVideos(videos);

      // Verify sharding
      const keys = [];
      cache.cache.forEach((_, key) => keys.push(key));

      
      expect(keys.length).toBeGreaterThan(1);
    });

    it('cache miss handling test', async () => {
      const result = await cache.getPopularVideos();
      expect(result).toBeUndefined();
    });
  });
});

describe('Recommendations API', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const recommendations = require('../../../services/recommendations/src/index');
    app = recommendations.app;
    request = global.testUtils.mockRequest(app);
  });

  it('should record view events', async () => {
    const response = await request.post('/events/view').send({
      userId: 'user-1',
      videoId: 'video-1',
      watchDuration: 120,
      totalDuration: 180,
    });

    expect(response.status).toBe(202);
  });

  it('should get recommendations', async () => {
    // Record some views
    await request.post('/events/view').send({
      userId: 'user-1',
      videoId: 'video-1',
      watchDuration: 120,
      totalDuration: 180,
    });

    await request.post('/events/like').send({
      userId: 'user-1',
      videoId: 'video-2',
    });

    const response = await request.get('/recommendations/user-2?limit=10');

    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('recommendations');
  });

  it('should get similar videos', async () => {
    // Record views from same user
    await request.post('/events/view').send({
      userId: 'user-1',
      videoId: 'video-1',
      watchDuration: 100,
      totalDuration: 200,
    });

    await request.post('/events/view').send({
      userId: 'user-1',
      videoId: 'video-2',
      watchDuration: 100,
      totalDuration: 200,
    });

    const response = await request.get('/recommendations/video-1/similar');

    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('similar');
  });
});
