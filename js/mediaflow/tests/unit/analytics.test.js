/**
 * Analytics Service Unit Tests
 *
 * Tests bugs J1 (trace context), J3 (metric overflow), J4 (log sampling)
 */

describe('TraceContext', () => {
  let TraceContext;
  let traceContext;

  beforeEach(() => {
    jest.resetModules();
    const analytics = require('../../../services/analytics/src/index');
    TraceContext = analytics.TraceContext;
    traceContext = new TraceContext();
  });

  describe('trace propagation', () => {
    
    it('trace extraction test', () => {
      const mockRequest = {
        headers: {
          'x-trace-id': 'trace-12345',
          'x-span-id': 'span-67890',
        },
      };

      const context = traceContext.extractFromRequest(mockRequest);

      
      expect(context).not.toBeNull();
      expect(context.traceId).toBe('trace-12345');
      expect(context.spanId).toBe('span-67890');
    });

    
    it('trace injection test', () => {
      const spanId = traceContext.startSpan('test-span');

      const mockRequest = { headers: {} };
      const injected = traceContext.injectToRequest(mockRequest, spanId);

      
      expect(injected.headers['x-trace-id']).toBeDefined();
      expect(injected.headers['x-span-id']).toBe(spanId);
    });

    it('span lifecycle test', () => {
      const spanId = traceContext.startSpan('test-operation');
      expect(traceContext.spans.has(spanId)).toBe(true);

      const span = traceContext.spans.get(spanId);
      expect(span.name).toBe('test-operation');
      expect(span.endTime).toBeNull();

      traceContext.endSpan(spanId);
      expect(span.endTime).not.toBeNull();
    });

    it('parent-child span test', () => {
      const parentSpan = traceContext.startSpan('parent');
      const childSpan = traceContext.startSpan('child', parentSpan);

      const child = traceContext.spans.get(childSpan);
      expect(child.parentId).toBe(parentSpan);
    });
  });
});

describe('MetricAggregator', () => {
  let MetricAggregator;
  let metrics;

  beforeEach(() => {
    jest.resetModules();
    const analytics = require('../../../services/analytics/src/index');
    MetricAggregator = analytics.MetricAggregator;
    metrics = new MetricAggregator();
  });

  describe('overflow protection', () => {
    
    it('counter overflow test', () => {
      const largeValue = Number.MAX_SAFE_INTEGER;

      metrics.incrementCounter('views', largeValue);
      metrics.incrementCounter('views', 1000);

      const aggregated = metrics.aggregate();

      
      expect(aggregated.counters['views']).toBe(largeValue + 1000);
    });

    
    it('histogram memory test', () => {
      // Add many values
      for (let i = 0; i < 100000; i++) {
        metrics.recordHistogram('latency', Math.random() * 1000);
      }

      const aggregated = metrics.aggregate();

      
      // Histogram array grows unbounded
      expect(aggregated.histograms['latency'].count).toBeLessThanOrEqual(10000);
    });

    
    it('histogram sum overflow test', () => {
      const largeValue = Number.MAX_SAFE_INTEGER / 2;

      metrics.recordHistogram('duration', largeValue);
      metrics.recordHistogram('duration', largeValue);
      metrics.recordHistogram('duration', largeValue);

      const aggregated = metrics.aggregate();

      
      expect(Number.isFinite(aggregated.histograms['duration'].sum)).toBe(true);
      expect(aggregated.histograms['duration'].sum).toBeGreaterThan(0);
    });
  });

  describe('metric aggregation', () => {
    it('counter increment test', () => {
      metrics.incrementCounter('requests', 1);
      metrics.incrementCounter('requests', 5);

      const aggregated = metrics.aggregate();
      expect(aggregated.counters['requests']).toBe(6);
    });

    it('tagged metrics test', () => {
      metrics.incrementCounter('requests', 1, { endpoint: '/api/v1' });
      metrics.incrementCounter('requests', 2, { endpoint: '/api/v2' });
      metrics.incrementCounter('requests', 3, { endpoint: '/api/v1' });

      const aggregated = metrics.aggregate();

      expect(aggregated.counters['requests{endpoint:/api/v1}']).toBe(4);
      expect(aggregated.counters['requests{endpoint:/api/v2}']).toBe(2);
    });

    it('gauge test', () => {
      metrics.setGauge('connections', 10);
      metrics.setGauge('connections', 15);
      metrics.setGauge('connections', 12);

      const aggregated = metrics.aggregate();
      expect(aggregated.gauges['connections']).toBe(12);
    });

    it('histogram percentiles test', () => {
      for (let i = 1; i <= 100; i++) {
        metrics.recordHistogram('latency', i);
      }

      const aggregated = metrics.aggregate();
      expect(aggregated.histograms['latency'].min).toBe(1);
      expect(aggregated.histograms['latency'].max).toBe(100);
      expect(aggregated.histograms['latency'].avg).toBe(50.5);
    });
  });
});

describe('LogSampler', () => {
  let LogSampler;
  let sampler;

  beforeEach(() => {
    jest.resetModules();
    const analytics = require('../../../services/analytics/src/index');
    LogSampler = analytics.LogSampler;
    sampler = new LogSampler(0.1); // 10% sampling
  });

  describe('error preservation', () => {
    
    it('error logging test', () => {
      const logs = [];
      const originalLog = console.log;
      console.log = (msg) => logs.push(JSON.parse(msg));

      // Log many errors
      for (let i = 0; i < 100; i++) {
        sampler.log('error', `Error ${i}`, { code: 500 });
      }

      console.log = originalLog;

      
      // With 10% sampling, only ~10 would be logged
      expect(logs.length).toBe(100);
    });

    
    it('critical log test', () => {
      const logs = [];
      const originalLog = console.log;
      console.log = (msg) => logs.push(JSON.parse(msg));

      // Critical logs should always be captured
      for (let i = 0; i < 10; i++) {
        sampler.log('critical', `Critical error ${i}`);
      }

      console.log = originalLog;

      expect(logs.length).toBe(10);
    });

    it('info sampling test', () => {
      const logs = [];
      const originalLog = console.log;
      console.log = (msg) => logs.push(JSON.parse(msg));

      // Info logs can be sampled
      for (let i = 0; i < 1000; i++) {
        sampler.log('info', `Info ${i}`);
      }

      console.log = originalLog;

      // With 10% sampling, expect ~100 logs (+/- variance)
      expect(logs.length).toBeGreaterThan(50);
      expect(logs.length).toBeLessThan(200);
    });
  });
});

describe('Analytics API', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const analytics = require('../../../services/analytics/src/index');
    app = analytics.app;
    request = global.testUtils.mockRequest(app);
  });

  it('should record view events', async () => {
    const response = await request.post('/analytics/view').send({
      userId: 'user-1',
      videoId: 'video-1',
      duration: 120,
    });

    expect(response.status).toBe(202);
  });

  it('should get video analytics', async () => {
    await request.post('/analytics/view').send({
      userId: 'user-1',
      videoId: 'video-1',
      duration: 120,
    });

    const response = await request.get('/analytics/videos/video-1');

    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('totalViews');
    expect(response.body.totalViews).toBe(1);
  });

  it('should manage sessions', async () => {
    const createResponse = await request.post('/analytics/sessions').send({
      userId: 'user-1',
      deviceInfo: { browser: 'Chrome' },
    });

    expect(createResponse.status).toBe(201);
    expect(createResponse.body).toHaveProperty('sessionId');

    const sessionId = createResponse.body.sessionId;

    // Record event
    const eventResponse = await request
      .post(`/analytics/sessions/${sessionId}/events`)
      .send({
        type: 'click',
        data: { elementId: 'play-button' },
      });

    expect(eventResponse.status).toBe(202);

    // End session
    const endResponse = await request.delete(`/analytics/sessions/${sessionId}`);
    expect(endResponse.status).toBe(204);
  });

  it('should return realtime metrics', async () => {
    const response = await request.get('/analytics/realtime');

    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('viewsLastHour');
    expect(response.body).toHaveProperty('activeSessions');
  });
});
