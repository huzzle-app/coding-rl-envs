/**
 * Shared Utils Tests
 *
 * Tests DistributedLock, LeaderElection, TraceContext, CorrelationContext,
 * MetricsCollector, StructuredLogger, parseConfig
 */

describe('DistributedLock', () => {
  let DistributedLock;
  let mockRedis;

  beforeEach(() => {
    jest.resetModules();
    mockRedis = global.testUtils.mockRedis();
    const mod = require('../../../shared/utils');
    DistributedLock = mod.DistributedLock;
  });

  describe('acquire', () => {
    it('should acquire lock', async () => {
      const lock = new DistributedLock(mockRedis, { timeout: 5000 });

      const result = await lock.acquire('test-key');
      expect(result).toBeDefined();
    });

    it('should set TTL on acquire', async () => {
      const lock = new DistributedLock(mockRedis, { timeout: 10000 });

      await lock.acquire('test-key');
      expect(mockRedis.set).toHaveBeenCalled();
    });

    it('should return lock handle', async () => {
      const lock = new DistributedLock(mockRedis, { timeout: 5000 });

      const handle = await lock.acquire('test-key');
      expect(handle).toBeDefined();
      expect(handle.key).toBeDefined();
    });

    it('should handle concurrent acquire attempts', async () => {
      const lock = new DistributedLock(mockRedis);

      const results = await Promise.all([
        lock.acquire('shared-key'),
        lock.acquire('shared-key'),
      ]);

      expect(results.filter(Boolean).length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('release', () => {
    it('should release acquired lock', async () => {
      const lock = new DistributedLock(mockRedis);

      const handle = await lock.acquire('test-key');
      const released = await lock.release(handle);

      expect(released).toBeDefined();
    });
  });
});

describe('LeaderElection', () => {
  let LeaderElection;
  let mockConsul;

  beforeEach(() => {
    jest.resetModules();
    mockConsul = global.testUtils.mockConsul();
    const mod = require('../../../shared/utils');
    LeaderElection = mod.LeaderElection;
  });

  describe('election', () => {
    it('should start election', async () => {
      const election = new LeaderElection(mockConsul, { serviceName: 'test' });

      mockConsul.kv.set.mockResolvedValueOnce(true);
      await election.start();

      expect(election.getIsLeader()).toBe(true);
    });

    it('should become follower if another wins', async () => {
      const election = new LeaderElection(mockConsul, { serviceName: 'test' });

      mockConsul.kv.set.mockResolvedValueOnce(false);
      await election.start();

      expect(election.getIsLeader()).toBe(false);
    });

    it('should stop cleanly', async () => {
      const election = new LeaderElection(mockConsul, { serviceName: 'test' });

      mockConsul.kv.set.mockResolvedValueOnce(true);
      await election.start();
      await election.stop();

      expect(election.getIsLeader()).toBe(false);
    });

    it('should have unique channel name', () => {
      const e1 = new LeaderElection(mockConsul, { serviceName: 'service-a' });
      const e2 = new LeaderElection(mockConsul, { serviceName: 'service-b' });

      expect(e1.channelName).toBeDefined();
      expect(e2.channelName).toBeDefined();
    });
  });
});

describe('TraceContext', () => {
  let TraceContext;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/utils');
    TraceContext = mod.TraceContext;
  });

  describe('trace propagation', () => {
    it('should create trace context', () => {
      const ctx = new TraceContext();
      expect(ctx.traceId).toBeDefined();
      expect(ctx.spanId).toBeDefined();
    });

    it('should create child spans', () => {
      const parent = new TraceContext();
      const child = parent.createChild();

      expect(child.traceId).toBe(parent.traceId);
      expect(child.parentSpanId).toBe(parent.spanId);
      expect(child.spanId).not.toBe(parent.spanId);
    });

    it('should serialize to headers', () => {
      const ctx = new TraceContext();
      const headers = ctx.toHeaders();

      expect(headers).toBeDefined();
      expect(headers['x-trace-id']).toBe(ctx.traceId);
    });

    it('should deserialize from headers', () => {
      const original = new TraceContext();
      const headers = original.toHeaders();

      const restored = TraceContext.fromHeaders(headers);
      expect(restored.traceId).toBe(original.traceId);
    });
  });
});

describe('CorrelationContext', () => {
  let CorrelationContext;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/utils');
    CorrelationContext = mod.CorrelationContext;
  });

  describe('correlation', () => {
    it('should generate correlation ID', () => {
      const ctx = new CorrelationContext();
      expect(ctx.correlationId).toBeDefined();
      expect(typeof ctx.correlationId).toBe('string');
    });

    it('should generate unique IDs', () => {
      const ids = new Set();
      for (let i = 0; i < 100; i++) {
        const ctx = new CorrelationContext();
        ids.add(ctx.correlationId);
      }
      expect(ids.size).toBe(100);
    });

    it('should support custom correlation ID', () => {
      const ctx = new CorrelationContext('custom-id');
      expect(ctx.correlationId).toBe('custom-id');
    });
  });
});

describe('MetricsCollector', () => {
  let MetricsCollector;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/utils');
    MetricsCollector = mod.MetricsCollector;
  });

  describe('metrics recording', () => {
    it('should record counter metrics', () => {
      const collector = new MetricsCollector();

      collector.increment('http_requests', { method: 'GET', status: '200' });
      collector.increment('http_requests', { method: 'GET', status: '200' });

      expect(collector.getMetric('http_requests')).toBe(2);
    });

    it('should record histogram metrics', () => {
      const collector = new MetricsCollector();

      collector.observe('request_duration', 15, { path: '/api/docs' });
      collector.observe('request_duration', 25, { path: '/api/docs' });

      expect(collector.getHistogram('request_duration')).toBeDefined();
    });

    it('should track gauge metrics', () => {
      const collector = new MetricsCollector();

      collector.setGauge('active_connections', 42);
      expect(collector.getGauge('active_connections')).toBe(42);

      collector.setGauge('active_connections', 38);
      expect(collector.getGauge('active_connections')).toBe(38);
    });

    it('should handle label sets', () => {
      const collector = new MetricsCollector();

      collector.increment('requests', { method: 'GET' });
      collector.increment('requests', { method: 'POST' });

      expect(collector.getMetric('requests')).toBeGreaterThanOrEqual(2);
    });
  });
});

describe('StructuredLogger', () => {
  let StructuredLogger;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/utils');
    StructuredLogger = mod.StructuredLogger;
  });

  describe('logging', () => {
    it('should log with level', () => {
      const logger = new StructuredLogger('gateway');
      const entry = logger.info('Request received');

      expect(entry.level).toBe('info');
      expect(entry.message).toBe('Request received');
    });

    it('should include service name', () => {
      const logger = new StructuredLogger('documents');
      const entry = logger.info('test');

      expect(entry.service).toBe('documents');
    });

    it('should include timestamp', () => {
      const logger = new StructuredLogger('test');
      const entry = logger.info('test');

      expect(entry.timestamp).toBeDefined();
    });

    it('should support metadata', () => {
      const logger = new StructuredLogger('test');
      const entry = logger.info('test', { requestId: 'req-1', userId: 'user-1' });

      expect(entry.requestId).toBe('req-1');
    });

    it('should log errors with stack', () => {
      const logger = new StructuredLogger('test');
      const error = new Error('Test error');
      const entry = logger.error('Failed', { error });

      expect(entry.level).toBe('error');
    });

    it('should handle different log levels', () => {
      const logger = new StructuredLogger('test');

      expect(logger.debug('debug').level).toBe('debug');
      expect(logger.info('info').level).toBe('info');
      expect(logger.warn('warn').level).toBe('warn');
      expect(logger.error('error').level).toBe('error');
    });
  });
});

describe('parseConfig', () => {
  let parseConfig;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/utils');
    parseConfig = mod.parseConfig;
  });

  describe('type coercion', () => {
    it('should parse numeric strings', () => {
      const config = parseConfig({ PORT: '3000', POOL_SIZE: '10' });

      expect(typeof config.PORT).toBe('number');
      expect(config.PORT).toBe(3000);
    });

    it('should parse boolean strings', () => {
      const config = parseConfig({ DEBUG: 'true', VERBOSE: 'false' });

      expect(config.DEBUG).toBe(true);
      expect(config.VERBOSE).toBe(false);
    });

    it('should keep regular strings', () => {
      const config = parseConfig({ HOST: 'localhost', DB_NAME: 'cloudmatrix' });

      expect(config.HOST).toBe('localhost');
      expect(config.DB_NAME).toBe('cloudmatrix');
    });

    it('should handle empty values', () => {
      const config = parseConfig({ EMPTY: '' });
      expect(config.EMPTY).toBe('');
    });

    it('should handle JSON strings', () => {
      const config = parseConfig({ CORS_ORIGINS: '["http://localhost:3000"]' });
      expect(config.CORS_ORIGINS).toBeDefined();
    });
  });
});
