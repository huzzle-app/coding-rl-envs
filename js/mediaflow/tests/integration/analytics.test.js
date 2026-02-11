/**
 * Analytics Service Integration Tests
 */

describe('Analytics Service', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const analytics = require('../../../services/analytics/src/index');
    app = analytics.app;
    request = global.testUtils.mockRequest(app);
  });

  describe('view tracking', () => {
    it('should record view event', async () => {
      const response = await request.post('/analytics/view').send({
        userId: 'user-1',
        videoId: 'video-1',
        duration: 120,
      });

      expect(response.status).toBe(202);
    });

    it('should accept timestamp', async () => {
      const response = await request.post('/analytics/view').send({
        userId: 'user-1',
        videoId: 'video-1',
        duration: 120,
        timestamp: Date.now(),
      });

      expect(response.status).toBe(202);
    });
  });

  describe('video analytics', () => {
    it('should get video analytics', async () => {
      await request.post('/analytics/view').send({
        userId: 'user-1',
        videoId: 'video-test',
        duration: 120,
      });

      const response = await request.get('/analytics/videos/video-test');
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('totalViews');
    });

    it('should count unique viewers', async () => {
      await request.post('/analytics/view').send({ userId: 'user-1', videoId: 'video-2', duration: 60 });
      await request.post('/analytics/view').send({ userId: 'user-2', videoId: 'video-2', duration: 60 });
      await request.post('/analytics/view').send({ userId: 'user-1', videoId: 'video-2', duration: 60 });

      const response = await request.get('/analytics/videos/video-2');
      expect(response.body.uniqueViewers).toBe(2);
    });

    it('should calculate total watch time', async () => {
      await request.post('/analytics/view').send({ userId: 'user-1', videoId: 'video-3', duration: 100 });
      await request.post('/analytics/view').send({ userId: 'user-2', videoId: 'video-3', duration: 50 });

      const response = await request.get('/analytics/videos/video-3');
      expect(response.body.totalWatchTime).toBe(150);
    });

    it('should filter by date range', async () => {
      const response = await request.get('/analytics/videos/video-1?startDate=2024-01-01&endDate=2024-12-31');
      expect(response.status).toBe(200);
    });
  });

  describe('user analytics', () => {
    it('should get user analytics', async () => {
      await request.post('/analytics/view').send({
        userId: 'user-test',
        videoId: 'video-1',
        duration: 60,
      });

      const response = await request.get('/analytics/users/user-test');
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('totalViews');
    });

    it('should count unique videos', async () => {
      await request.post('/analytics/view').send({ userId: 'user-4', videoId: 'video-a', duration: 60 });
      await request.post('/analytics/view').send({ userId: 'user-4', videoId: 'video-b', duration: 60 });

      const response = await request.get('/analytics/users/user-4');
      expect(response.body.uniqueVideos).toBe(2);
    });

    it('should list recent videos', async () => {
      await request.post('/analytics/view').send({ userId: 'user-5', videoId: 'recent-1', duration: 60 });
      await request.post('/analytics/view').send({ userId: 'user-5', videoId: 'recent-2', duration: 60 });

      const response = await request.get('/analytics/users/user-5');
      expect(response.body.recentVideos.length).toBeGreaterThan(0);
    });
  });

  describe('session management', () => {
    it('should create session', async () => {
      const response = await request.post('/analytics/sessions').send({
        userId: 'user-1',
        deviceInfo: { browser: 'Chrome' },
      });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('sessionId');
    });

    it('should record session event', async () => {
      const createResponse = await request.post('/analytics/sessions').send({
        userId: 'user-1',
        deviceInfo: {},
      });
      const sessionId = createResponse.body.sessionId;

      const response = await request.post(`/analytics/sessions/${sessionId}/events`).send({
        type: 'click',
        data: { element: 'play-button' },
      });

      expect(response.status).toBe(202);
    });

    it('should end session', async () => {
      const createResponse = await request.post('/analytics/sessions').send({
        userId: 'user-1',
        deviceInfo: {},
      });
      const sessionId = createResponse.body.sessionId;

      const response = await request.delete(`/analytics/sessions/${sessionId}`);
      expect(response.status).toBe(204);
    });

    it('should return 404 for unknown session', async () => {
      const response = await request.delete('/analytics/sessions/unknown-session');
      expect(response.status).toBe(404);
    });
  });

  describe('metrics', () => {
    it('should get aggregated metrics', async () => {
      const response = await request.get('/analytics/metrics');
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('counters');
    });
  });

  describe('realtime', () => {
    it('should get realtime data', async () => {
      const response = await request.get('/analytics/realtime');
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('viewsLastHour');
      expect(response.body).toHaveProperty('activeSessions');
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
