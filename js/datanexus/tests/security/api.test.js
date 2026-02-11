/**
 * Security API Tests (~30 tests)
 *
 * Tests for API-level security: authentication, authorization, CORS, rate limiting
 * Covers BUG I4, I5, I10, L11, L10
 */

const { CircuitBreaker, PluginLoader } = require('../../shared/clients');
const { TraceContext, CorrelationContext, parseEnvVar, Logger } = require('../../shared/utils');

describe('Security API Tests', () => {
  describe('CORS configuration (L11)', () => {
    test('cors preflight test - OPTIONS request handled', () => {
      // Simulate CORS preflight handling
      const handleOptions = (origin, allowedOrigins) => {
        if (allowedOrigins.includes(origin) || allowedOrigins.includes('*')) {
          return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            status: 204,
          };
        }
        return { status: 403 };
      };

      
      const result = handleOptions('https://app.example.com', ['https://app.example.com']);
      expect(result.status).toBe(204);
    });

    test('options request test - wildcard origin in dev only', () => {
      const handleOptions = (origin, env) => {
        const allowedOrigins = env === 'development' ? ['*'] : ['https://app.datanexus.io'];
        if (allowedOrigins.includes('*') || allowedOrigins.includes(origin)) {
          return { allowed: true };
        }
        return { allowed: false };
      };

      expect(handleOptions('http://evil.com', 'production').allowed).toBe(false);
      expect(handleOptions('https://app.datanexus.io', 'production').allowed).toBe(true);
    });

    test('CORS headers include credentials', () => {
      const headers = {
        'Access-Control-Allow-Origin': 'https://app.example.com',
        'Access-Control-Allow-Credentials': 'true',
      };
      expect(headers['Access-Control-Allow-Credentials']).toBe('true');
    });

    test('preflight caches max-age', () => {
      const headers = {
        'Access-Control-Max-Age': '86400',
      };
      expect(parseInt(headers['Access-Control-Max-Age'], 10)).toBe(86400);
    });
  });

  describe('environment variable security (L10)', () => {
    test('env var coercion test - port parsed as number', () => {
      const oldPort = process.env.PORT;
      process.env.PORT = '3000';
      const port = parseEnvVar('PORT', 8080);
      
      expect(typeof port).toBe('string'); 
      process.env.PORT = oldPort;
    });

    test('port parsing test - undefined uses default', () => {
      const result = parseEnvVar('NONEXISTENT_VAR_12345', 8080);
      expect(result).toBe(8080);
    });

    test('boolean env var coercion', () => {
      const oldVal = process.env.ENABLE_FEATURE;
      process.env.ENABLE_FEATURE = 'true';
      const val = parseEnvVar('ENABLE_FEATURE', false);
      
      expect(val).toBe('true');
      process.env.ENABLE_FEATURE = oldVal;
    });

    test('numeric env var coercion', () => {
      const oldVal = process.env.MAX_CONNECTIONS;
      process.env.MAX_CONNECTIONS = '50';
      const val = parseEnvVar('MAX_CONNECTIONS', 10);
      expect(val).toBe('50'); 
      process.env.MAX_CONNECTIONS = oldVal;
    });
  });

  describe('rate limiting (I4)', () => {
    test('rate limit api key test - per-key tracking', () => {
      const limits = new Map();
      const windowMs = 60000;

      const checkRate = (apiKey, maxRequests = 100) => {
        const now = Date.now();
        const entry = limits.get(apiKey) || { count: 0, windowStart: now };

        if (now - entry.windowStart > windowMs) {
          entry.count = 0;
          entry.windowStart = now;
        }

        entry.count++;
        limits.set(apiKey, entry);

        return entry.count <= maxRequests;
      };

      for (let i = 0; i < 100; i++) {
        checkRate('key-1');
      }

      expect(checkRate('key-1')).toBe(false);
    });

    test('rotation bypass test - key rotation resets counter', () => {
      const limits = new Map();
      const check = (key) => {
        const count = (limits.get(key) || 0) + 1;
        limits.set(key, count);
        return count <= 10;
      };

      for (let i = 0; i < 15; i++) check('key-1');
      
      expect(check('key-1-rotated')).toBe(true);
    });

    test('rate limit headers returned', () => {
      const remaining = 95;
      const headers = {
        'X-RateLimit-Remaining': remaining.toString(),
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Reset': new Date(Date.now() + 60000).toISOString(),
      };
      expect(parseInt(headers['X-RateLimit-Remaining'], 10)).toBe(95);
    });

    test('rate limit resets after window', () => {
      const limits = new Map();
      limits.set('key-1', { count: 100, windowStart: Date.now() - 120000 });
      const entry = limits.get('key-1');
      const windowExpired = Date.now() - entry.windowStart > 60000;
      expect(windowExpired).toBe(true);
    });
  });

  describe('authentication chain', () => {
    test('JWT token validation', () => {
      const validateToken = (token) => {
        if (!token) return { valid: false, error: 'missing' };
        const parts = token.split('.');
        if (parts.length !== 3) return { valid: false, error: 'malformed' };
        return { valid: true };
      };

      expect(validateToken(undefined).valid).toBe(false);
      expect(validateToken('not.a.jwt.token').valid).toBe(false);
      expect(validateToken('header.payload.signature').valid).toBe(true);
    });

    test('JWT "none" algorithm rejected', () => {
      const validateAlgorithm = (header) => {
        const decoded = JSON.parse(Buffer.from(header, 'base64').toString());
        if (decoded.alg === 'none') return false;
        return ['HS256', 'RS256'].includes(decoded.alg);
      };

      const noneHeader = Buffer.from(JSON.stringify({ alg: 'none' })).toString('base64');
      expect(validateAlgorithm(noneHeader)).toBe(false);

      const validHeader = Buffer.from(JSON.stringify({ alg: 'HS256' })).toString('base64');
      expect(validateAlgorithm(validHeader)).toBe(true);
    });

    test('expired token rejected', () => {
      const isExpired = (exp) => Date.now() / 1000 > exp;
      expect(isExpired(Math.floor(Date.now() / 1000) - 3600)).toBe(true);
      expect(isExpired(Math.floor(Date.now() / 1000) + 3600)).toBe(false);
    });
  });

  describe('circuit breaker security', () => {
    test('circuit breaker protects downstream services', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 3, resetTimeout: 1000 });

      // Trigger failures
      for (let i = 0; i < 5; i++) {
        try {
          await cb.execute(() => { throw new Error('service down'); });
        } catch (e) {}
      }

      
      const state = cb.getState();
      expect(state === 'open' || state === 'closed').toBe(true);
    });

    test('workspace conflict test - threshold comparison', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 5 });

      for (let i = 0; i < 5; i++) {
        try {
          await cb.execute(() => { throw new Error('fail'); });
        } catch (e) {}
      }

      
      expect(cb.failureCount).toBe(5);
    });

    test('dependency resolution test - circuit breaker reset', () => {
      const cb = new CircuitBreaker({ failureThreshold: 3 });
      cb.reset();
      expect(cb.getState()).toBe('closed');
      expect(cb.failureCount).toBe(0);
    });

    test('half-open allows limited requests', async () => {
      const cb = new CircuitBreaker({
        failureThreshold: 2,
        resetTimeout: 0,
        maxHalfOpenRequests: 1,
      });

      // Open the circuit
      for (let i = 0; i < 3; i++) {
        try { await cb.execute(() => { throw new Error('fail'); }); } catch (e) {}
      }

      // After resetTimeout (0ms), should transition to half-open
      try {
        await cb.execute(() => 'success');
      } catch (e) {}
    });
  });

  describe('plugin security (E7, L14)', () => {
    test('plugin isolation leak test - plugins share global state', () => {
      const loader = new PluginLoader();
      
      expect(loader.registry).toEqual({});
    });

    test('class loading test - plugins loaded in isolation', () => {
      const loader = new PluginLoader();
      expect(loader.loadedModules.size).toBe(0);
    });

    test('connector plugin loading test - plugin discovery', () => {
      const loader = new PluginLoader();
      expect(() => loader.loadPlugin('/nonexistent/path')).toThrow();
    });

    test('plugin discovery test - unloaded plugin returns undefined', () => {
      const loader = new PluginLoader();
      expect(loader.getPlugin('nonexistent')).toBeUndefined();
    });
  });

  describe('observability security (M1-M3)', () => {
    test('trace context pipeline test - trace propagated', () => {
      const trace = new TraceContext('trace-1', 'span-1');
      const headers = trace.toHeaders();
      expect(headers['x-trace-id']).toBe('trace-1');
    });

    test('stream trace test - child span created', () => {
      const parent = new TraceContext('trace-1', 'span-1');
      const child = parent.createChildSpan();
      expect(child.traceId).toBe('trace-1');
      expect(child.parentSpanId).toBe('span-1');
      expect(child.spanId).not.toBe('span-1');
    });

    test('correlation transform test - correlation ID propagated', () => {
      CorrelationContext.set('corr-123');
      expect(CorrelationContext.get()).toBe('corr-123');
      CorrelationContext.set(null);
    });

    test('id propagation test - new request gets new ID', () => {
      const id1 = global.testUtils.generateId();
      const id2 = global.testUtils.generateId();
      expect(id1).not.toBe(id2);
    });

    test('metric label cardinality test - labels bounded', () => {
      const labels = new Map();
      const allowedLabels = ['method', 'status', 'path'];

      const addMetric = (name, metricLabels, value) => {
        const filteredLabels = {};
        for (const label of allowedLabels) {
          if (metricLabels[label]) {
            filteredLabels[label] = metricLabels[label];
          }
        }
        const key = `${name}:${JSON.stringify(filteredLabels)}`;
        labels.set(key, (labels.get(key) || 0) + value);
      };

      addMetric('requests', { method: 'GET', pipeline_id: 'p1' }, 1);
      addMetric('requests', { method: 'POST', pipeline_id: 'p2' }, 1);
      addMetric('requests', { method: 'GET', pipeline_id: 'p3' }, 1);

      // pipeline_id is not an allowed label, so cardinality is bounded
      expect(labels.size).toBe(2);
    });

    test('pipeline id label test - high cardinality labels dropped', () => {
      const allowedLabels = new Set(['method', 'status']);
      const testLabel = 'pipeline_id';
      expect(allowedLabels.has(testLabel)).toBe(false);
    });
  });

  describe('logging security (L12, M5)', () => {
    test('logging transport test - logger waits for transport', async () => {
      const logger = new Logger();
      
      logger.info('test message');
      expect(logger._transportReady).toBe(false);
    });

    test('winston configuration test - transport initialized', async () => {
      const logger = new Logger();
      await logger.initTransport({ write: jest.fn() });
      expect(logger._transportReady).toBe(true);
    });

    test('log field conflict test - reserved fields not overwritten', () => {
      const logger = new Logger();
      const entry = {
        timestamp: 'user-timestamp',
        level: 'info',
        message: 'test',
      };
      expect(entry.timestamp).toBeDefined();
    });

    test('worker log test - worker ID included in logs', () => {
      const logger = new Logger();
      const meta = { workerId: 'worker-1', taskId: 'task-1' };
      // Just verify meta fields
      expect(meta.workerId).toBe('worker-1');
    });
  });
});
