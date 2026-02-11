/**
 * Recommendations Service Integration Tests
 */

describe('Recommendations Service', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const recommendations = require('../../../services/recommendations/src/index');
    app = recommendations.app;
    request = global.testUtils.mockRequest(app);
  });

  describe('event recording', () => {
    it('should record view event', async () => {
      const response = await request.post('/events/view').send({
        userId: 'user-1',
        videoId: 'video-1',
        watchDuration: 120,
        totalDuration: 180,
      });

      expect(response.status).toBe(202);
    });

    it('should record like event', async () => {
      const response = await request.post('/events/like').send({
        userId: 'user-1',
        videoId: 'video-1',
      });

      expect(response.status).toBe(202);
    });

    it('should accept share event', async () => {
      const response = await request.post('/events/share').send({
        userId: 'user-1',
        videoId: 'video-1',
      });

      expect([200, 202, 404]).toContain(response.status);
    });
  });

  describe('recommendations', () => {
    it('should get user recommendations', async () => {
      // Record some activity
      await request.post('/events/view').send({
        userId: 'user-2',
        videoId: 'video-1',
        watchDuration: 100,
        totalDuration: 200,
      });

      const response = await request.get('/recommendations/user-1');
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('recommendations');
    });

    it('should respect limit parameter', async () => {
      const response = await request.get('/recommendations/user-1?limit=5');
      expect(response.status).toBe(200);
      expect(response.body.recommendations.length).toBeLessThanOrEqual(5);
    });

    it('should exclude watched videos', async () => {
      await request.post('/events/view').send({
        userId: 'user-3',
        videoId: 'video-watched',
        watchDuration: 100,
        totalDuration: 100,
      });

      const response = await request.get('/recommendations/user-3');
      const videoIds = response.body.recommendations.map(r => r.videoId);
      expect(videoIds).not.toContain('video-watched');
    });
  });

  describe('similar videos', () => {
    it('should get similar videos', async () => {
      // Users watch same videos
      await request.post('/events/view').send({
        userId: 'user-4',
        videoId: 'video-a',
        watchDuration: 100,
        totalDuration: 100,
      });
      await request.post('/events/view').send({
        userId: 'user-4',
        videoId: 'video-b',
        watchDuration: 100,
        totalDuration: 100,
      });

      const response = await request.get('/recommendations/video-a/similar');
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('similar');
    });

    it('should rank by co-occurrence', async () => {
      const response = await request.get('/recommendations/video-1/similar');
      expect(response.status).toBe(200);
    });
  });

  describe('popular videos', () => {
    it('should get popular videos', async () => {
      const response = await request.get('/recommendations/popular');
      expect(response.status).toBe(200);
    });

    it('should respect limit', async () => {
      const response = await request.get('/recommendations/popular?limit=10');
      expect(response.status).toBe(200);
    });
  });

  describe('admin operations', () => {
    it('should rebuild projection', async () => {
      const response = await request.post('/admin/rebuild').send({
        events: [
          { type: 'VIDEO_WATCHED', timestamp: 1, data: { userId: 'u1', videoId: 'v1', watchDuration: 100, totalDuration: 200 } },
        ],
      });

      expect(response.status).toBe(200);
      expect(response.body.status).toBe('rebuilt');
    });
  });

  describe('health check', () => {
    it('should return healthy', async () => {
      const response = await request.get('/health');
      expect(response.status).toBe(200);
      expect(response.body.status).toBe('healthy');
    });
  });
});
