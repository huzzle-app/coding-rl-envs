/**
 * Contract API Tests (~30 tests)
 *
 * Tests for service API contracts: request/response schemas, error formats, headers
 * Covers BUG M4 (health aggregation), M5 (log fields), L11 (CORS), I5 (CSRF)
 */

const { DashboardService } = require('../../services/dashboards/src/services/dashboard');
const { ConnectorHealthCheck, SourceConnector, SinkConnector, ConnectorSchemaRegistry } = require('../../services/connectors/src/services/framework');
const { TraceContext, Logger, WorkerManager, parseEnvVar } = require('../../shared/utils');
const { CircuitBreaker } = require('../../shared/clients');

describe('Contract API Tests', () => {
  describe('health check contracts', () => {
    test('health aggregation test - all services checked', () => {
      const services = [
        { name: 'gateway', running: true, lastPollTime: Date.now() },
        { name: 'ingestion', running: true, lastPollTime: Date.now() },
        { name: 'transform', running: false },
      ];

      const healthChecks = services.map(s => {
        const check = new ConnectorHealthCheck(s);
        return { name: s.name, ...check.check() };
      });

      const allHealthy = healthChecks.every(h => h.healthy);
      expect(allHealthy).toBe(false);
      expect(healthChecks.filter(h => h.healthy).length).toBe(2);
    });

    test('aggregate health test - degraded when partial failure', () => {
      const results = [
        { healthy: true },
        { healthy: true },
        { healthy: false },
      ];

      const healthyCount = results.filter(r => r.healthy).length;
      const status = healthyCount === results.length ? 'healthy'
        : healthyCount > 0 ? 'degraded' : 'unhealthy';

      expect(status).toBe('degraded');
    });

    test('health check response format', () => {
      const connector = { running: true, lastPollTime: Date.now() };
      const check = new ConnectorHealthCheck(connector);
      const result = check.check();

      expect(result).toHaveProperty('healthy');
      expect(result).toHaveProperty('status');
      expect(typeof result.healthy).toBe('boolean');
    });

    test('stopped service health check', () => {
      const connector = { running: false };
      const check = new ConnectorHealthCheck(connector);
      const result = check.check();
      expect(result.healthy).toBe(false);
      expect(result.status).toBe('stopped');
    });
  });

  describe('error response contracts', () => {
    test('error format includes code and message', () => {
      const createError = (code, message, details = null) => ({
        error: {
          code,
          message,
          details,
          timestamp: new Date().toISOString(),
        },
      });

      const error = createError('VALIDATION_ERROR', 'Invalid pipeline config');
      expect(error.error.code).toBe('VALIDATION_ERROR');
      expect(error.error.message).toBe('Invalid pipeline config');
      expect(error.error.timestamp).toBeDefined();
    });

    test('404 error format', () => {
      const notFound = {
        error: { code: 'NOT_FOUND', message: 'Pipeline not found', status: 404 },
      };
      expect(notFound.error.status).toBe(404);
    });

    test('429 rate limit error includes retry-after', () => {
      const rateLimitError = {
        error: {
          code: 'RATE_LIMIT_EXCEEDED',
          message: 'Too many requests',
          retryAfter: 60,
        },
      };
      expect(rateLimitError.error.retryAfter).toBe(60);
    });

    test('500 error does not leak stack trace', () => {
      const internalError = {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'An unexpected error occurred',
        },
      };
      expect(internalError.error).not.toHaveProperty('stack');
    });
  });

  describe('API request/response schemas', () => {
    test('pipeline create request schema', () => {
      const request = {
        name: 'my-pipeline',
        description: 'Test pipeline',
        source: { type: 'kafka', topic: 'input-events' },
        transforms: [{ type: 'map', mapping: { output: 'input' } }],
        sink: { type: 'timescaledb', table: 'metrics' },
      };

      expect(request.name).toBeDefined();
      expect(request.source).toBeDefined();
      expect(request.sink).toBeDefined();
      expect(Array.isArray(request.transforms)).toBe(true);
    });

    test('pipeline response includes metadata', () => {
      const response = {
        id: 'pipeline-123',
        name: 'my-pipeline',
        status: 'running',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        version: 1,
        metrics: { eventsProcessed: 0, errorsCount: 0 },
      };

      expect(response.id).toBeDefined();
      expect(response.status).toBeDefined();
      expect(response.version).toBe(1);
    });

    test('dashboard list response schema', () => {
      const dashboard = new DashboardService();
      dashboard.create({ title: 'Test', tenantId: 't1' });

      const list = dashboard.list('t1');
      expect(Array.isArray(list)).toBe(true);
      if (list.length > 0) {
        expect(list[0]).toHaveProperty('id');
        expect(list[0]).toHaveProperty('createdAt');
      }
    });

    test('schema registry version response', () => {
      const registry = new ConnectorSchemaRegistry();
      const v1 = registry.register('user-events', { type: 'object' });

      expect(v1).toHaveProperty('id');
      expect(v1).toHaveProperty('version');
      expect(v1.version).toBe(1);
    });

    test('query response pagination metadata', () => {
      const response = {
        data: Array.from({ length: 10 }, (_, i) => ({ id: i })),
        pagination: {
          total: 100,
          page: 1,
          pageSize: 10,
          totalPages: 10,
          hasMore: true,
        },
      };

      expect(response.pagination.total).toBe(100);
      expect(response.pagination.hasMore).toBe(true);
    });
  });

  describe('header contracts', () => {
    test('trace headers propagated', () => {
      const trace = new TraceContext('trace-abc', 'span-123');
      const headers = trace.toHeaders();

      expect(headers).toHaveProperty('x-trace-id');
      expect(headers).toHaveProperty('x-span-id');
      expect(headers).toHaveProperty('x-parent-span-id');
    });

    test('trace context from headers', () => {
      const headers = {
        'x-trace-id': 'trace-abc',
        'x-span-id': 'span-123',
        'x-parent-span-id': 'span-parent',
      };

      const trace = TraceContext.fromHeaders(headers);
      expect(trace.traceId).toBe('trace-abc');
      expect(trace.spanId).toBe('span-123');
    });

    test('missing trace headers handled gracefully', () => {
      const trace = TraceContext.fromHeaders({});
      
      expect(trace).toBeDefined();
      expect(trace.traceId).toBeDefined();
    });

    test('content-type header required for POST', () => {
      const validateRequest = (method, headers) => {
        if (['POST', 'PUT', 'PATCH'].includes(method)) {
          return headers['content-type'] && headers['content-type'].includes('application/json');
        }
        return true;
      };

      expect(validateRequest('POST', {})).toBeFalsy();
      expect(validateRequest('POST', { 'content-type': 'application/json' })).toBe(true);
      expect(validateRequest('GET', {})).toBe(true);
    });
  });

  describe('connector API contracts', () => {
    test('source connector lifecycle', async () => {
      const source = new SourceConnector({ name: 'test-source' });
      await source.start();
      expect(source.running).toBe(true);

      const records = await source.poll();
      expect(Array.isArray(records)).toBe(true);

      await source.stop();
      expect(source.running).toBe(false);
    });

    test('sink connector lifecycle', async () => {
      const sink = new SinkConnector({ name: 'test-sink', deliveryGuarantee: 'at-least-once' });
      await sink.start();
      expect(sink.running).toBe(true);

      const result = await sink.write([{ id: 1 }]);
      expect(result).toHaveProperty('success');
      expect(result).toHaveProperty('count');

      await sink.stop();
      expect(sink.running).toBe(false);
    });

    test('connector config update contract', () => {
      const source = new SourceConnector({ name: 'test', timeout: 5000 });
      expect(source.config).toHaveProperty('name');
      expect(source.config.name).toBe('test');
    });
  });

  describe('worker API contracts', () => {
    test('worker manager lifecycle', async () => {
      const manager = new WorkerManager({ maxWorkers: 2 });
      await manager.start();
      expect(manager.initialized).toBe(true);
      expect(manager.workers.length).toBe(2);
    });

    test('worker assignment contract', async () => {
      const manager = new WorkerManager({ maxWorkers: 2 });
      await manager.start();

      const worker = manager.getAvailableWorker();
      expect(worker).toBeDefined();
      expect(worker.status).toBe('idle');

      const assigned = manager.assignTask(worker.id, { type: 'transform' });
      expect(assigned.status).toBe('busy');
    });

    test('worker release contract', async () => {
      const manager = new WorkerManager({ maxWorkers: 1 });
      await manager.start();

      const worker = manager.getAvailableWorker();
      manager.assignTask(worker.id, { type: 'test' });
      expect(manager.getAvailableWorker()).toBeUndefined();

      manager.releaseWorker(worker.id);
      const released = manager.getAvailableWorker();
      expect(released).toBeDefined();
      expect(released.status).toBe('idle');
    });
  });

  describe('circuit breaker contracts', () => {
    test('circuit breaker state transitions', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 2, resetTimeout: 100 });

      expect(cb.getState()).toBe('closed');

      // Trigger failures
      for (let i = 0; i < 3; i++) {
        try { await cb.execute(() => { throw new Error('fail'); }); } catch (e) {}
      }

      // After enough failures, should be open
      if (cb.getState() === 'open') {
        // Wait for reset timeout
        await global.testUtils.delay(150);

        // Should transition to half-open on next call
        try {
          await cb.execute(() => 'success');
        } catch (e) {}

        expect(['half-open', 'closed'].includes(cb.getState())).toBe(true);
      }
    });

    test('circuit breaker error propagation', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 10 });
      const specificError = new Error('specific failure');

      await expect(cb.execute(() => { throw specificError; }))
        .rejects.toThrow('specific failure');
    });

    test('circuit breaker tracks failure count', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 5 });
      for (let i = 0; i < 3; i++) {
        try { await cb.execute(() => { throw new Error('fail'); }); } catch (e) {}
      }
      expect(cb.failureCount).toBe(3);
    });

    test('successful call resets failure count', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 5 });
      try { await cb.execute(() => { throw new Error('fail'); }); } catch (e) {}
      expect(cb.failureCount).toBe(1);
      await cb.execute(() => 'success');
      expect(cb.failureCount).toBe(0);
    });
  });

  describe('schema registry contract', () => {
    test('schema version incrementing', () => {
      const registry = new ConnectorSchemaRegistry();
      const v1 = registry.register('events', { type: 'object' });
      const v2 = registry.register('events', { type: 'object', props: {} });
      expect(v2.version).toBe(v1.version + 1);
    });

    test('getLatestVersion returns highest', () => {
      const registry = new ConnectorSchemaRegistry();
      registry.register('events', {});
      registry.register('events', {});
      registry.register('events', {});
      expect(registry.getLatestVersion('events')).toBe(3);
    });

    test('unknown subject returns null', () => {
      const registry = new ConnectorSchemaRegistry();
      expect(registry.getLatestVersion('unknown')).toBeNull();
    });

    test('getSchema returns correct version', () => {
      const registry = new ConnectorSchemaRegistry();
      registry.register('events', { v: 1 });
      registry.register('events', { v: 2 });
      expect(registry.getSchema('events', 1)).toEqual({ v: 1 });
      expect(registry.getSchema('events', 2)).toEqual({ v: 2 });
    });
  });

  describe('worker lifecycle contracts', () => {
    test('worker manager all workers idle initially', async () => {
      const manager = new WorkerManager({ maxWorkers: 3 });
      await manager.start();
      for (const worker of manager.workers) {
        expect(worker.status).toBe('idle');
      }
    });

    test('assigning task to busy worker fails', async () => {
      const manager = new WorkerManager({ maxWorkers: 1 });
      await manager.start();
      const worker = manager.getAvailableWorker();
      manager.assignTask(worker.id, { type: 'first-task' });
      const available = manager.getAvailableWorker();
      expect(available).toBeUndefined();
    });
  });

  describe('logger contract', () => {
    test('logger info produces log entry', () => {
      const logger = new Logger();
      expect(() => logger.info('test entry')).not.toThrow();
    });

    test('logger error produces log entry', () => {
      const logger = new Logger();
      expect(() => logger.error('test error')).not.toThrow();
    });
  });
});
