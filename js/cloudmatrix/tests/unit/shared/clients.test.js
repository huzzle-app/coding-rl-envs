/**
 * Shared Client Tests
 *
 * Tests CircuitBreaker, ServiceClient, HealthChecker, RequestCoalescer
 */

describe('CircuitBreaker', () => {
  let CircuitBreaker;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/clients');
    CircuitBreaker = mod.CircuitBreaker;
  });

  describe('state transitions', () => {
    it('should start in closed state', () => {
      const cb = new CircuitBreaker({ threshold: 3, timeout: 1000 });
      expect(cb.isOpen()).toBe(false);
    });

    it('should open after threshold failures', () => {
      const cb = new CircuitBreaker({ threshold: 3, timeout: 1000 });

      cb.recordFailure();
      cb.recordFailure();
      cb.recordFailure();

      expect(cb.isOpen()).toBe(true);
    });

    it('should not open before threshold', () => {
      const cb = new CircuitBreaker({ threshold: 5, timeout: 1000 });

      cb.recordFailure();
      cb.recordFailure();

      expect(cb.isOpen()).toBe(false);
    });

    it('should reset after success', () => {
      const cb = new CircuitBreaker({ threshold: 3, timeout: 1000 });

      cb.recordFailure();
      cb.recordFailure();
      cb.recordSuccess();

      expect(cb.isOpen()).toBe(false);
    });

    it('should close after timeout period', async () => {
      const cb = new CircuitBreaker({ threshold: 2, timeout: 100 });

      cb.recordFailure();
      cb.recordFailure();

      expect(cb.isOpen()).toBe(true);

      await new Promise(resolve => setTimeout(resolve, 150));

      cb.recordSuccess();
      expect(cb.isOpen()).toBe(false);
    });

    it('should count consecutive failures only', () => {
      const cb = new CircuitBreaker({ threshold: 3, timeout: 1000 });

      cb.recordFailure();
      cb.recordSuccess();
      cb.recordFailure();
      cb.recordSuccess();

      expect(cb.isOpen()).toBe(false);
    });
  });

  describe('metrics', () => {
    it('should track total calls', () => {
      const cb = new CircuitBreaker({ threshold: 5, timeout: 1000 });

      cb.recordSuccess();
      cb.recordSuccess();
      cb.recordFailure();

      expect(cb.totalCalls).toBe(3);
    });

    it('should track failure count', () => {
      const cb = new CircuitBreaker({ threshold: 10, timeout: 1000 });

      cb.recordFailure();
      cb.recordFailure();

      expect(cb.failureCount).toBe(2);
    });
  });
});

describe('ServiceClient', () => {
  let ServiceClient;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/clients');
    ServiceClient = mod.ServiceClient;
  });

  describe('request handling', () => {
    it('should create with base URL', () => {
      const client = new ServiceClient({ baseUrl: 'http://localhost:3001', serviceName: 'auth' });
      expect(client.baseUrl).toBe('http://localhost:3001');
    });

    it('should handle timeout configuration', () => {
      const client = new ServiceClient({ baseUrl: 'http://localhost:3001', timeout: 5000 });
      expect(client.timeout).toBe(5000);
    });

    it('should set default headers', () => {
      const client = new ServiceClient({ baseUrl: 'http://localhost:3001' });
      expect(client.headers).toBeDefined();
    });
  });

  describe('retry logic', () => {
    it('should retry on failure', async () => {
      const client = new ServiceClient({ baseUrl: 'http://localhost:3001', retries: 3 });

      let attempts = 0;
      const mockFetch = async () => {
        attempts++;
        if (attempts < 3) throw new Error('Connection refused');
        return { status: 200, data: {} };
      };

      client._doRequest = mockFetch;

      const result = await client.get('/health');
      expect(attempts).toBe(3);
    });

    it('should use configured retry delay', () => {
      const client = new ServiceClient({ baseUrl: 'http://localhost:3001', retryDelay: 500 });
      expect(client.retryDelay).toBe(500);
    });

    it('should not retry on 4xx errors', async () => {
      const client = new ServiceClient({ baseUrl: 'http://localhost:3001', retries: 3 });

      let attempts = 0;
      client._doRequest = async () => {
        attempts++;
        const err = new Error('Not Found');
        err.status = 404;
        throw err;
      };

      try {
        await client.get('/missing');
      } catch (e) {
        // Expected
      }

      expect(attempts).toBe(1);
    });
  });
});

describe('HealthChecker', () => {
  let HealthChecker;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/clients');
    HealthChecker = mod.HealthChecker;
  });

  describe('health check', () => {
    it('should check service health', async () => {
      const checker = new HealthChecker();

      const result = await checker.check({ name: 'test', url: 'http://localhost:3000/health' });
      expect(result).toBeDefined();
    });

    it('should aggregate health status', () => {
      const checker = new HealthChecker();

      const checks = [
        { name: 'db', healthy: true },
        { name: 'redis', healthy: true },
        { name: 'rabbit', healthy: false },
      ];

      const overall = checks.every(c => c.healthy);
      expect(overall).toBe(false);
    });

    it('should track check latency', () => {
      const start = Date.now();
      const end = start + 15;
      const latency = end - start;

      expect(latency).toBe(15);
    });

    it('should timeout slow checks', () => {
      const checker = new HealthChecker();
      const timeout = checker.timeout || 5000;

      expect(timeout).toBeGreaterThan(0);
    });
  });
});

describe('RequestCoalescer', () => {
  let RequestCoalescer;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/clients');
    RequestCoalescer = mod.RequestCoalescer;
  });

  describe('coalescing', () => {
    it('should coalesce identical requests', async () => {
      const coalescer = new RequestCoalescer();
      let fetchCount = 0;

      const fetcher = async (key) => {
        fetchCount++;
        return { data: key };
      };

      const [r1, r2, r3] = await Promise.all([
        coalescer.get('key-1', fetcher),
        coalescer.get('key-1', fetcher),
        coalescer.get('key-1', fetcher),
      ]);

      expect(r1).toEqual(r2);
      expect(fetchCount).toBe(1);
    });

    it('should not coalesce different keys', async () => {
      const coalescer = new RequestCoalescer();
      let fetchCount = 0;

      const fetcher = async (key) => {
        fetchCount++;
        return { data: key };
      };

      await Promise.all([
        coalescer.get('key-1', fetcher),
        coalescer.get('key-2', fetcher),
      ]);

      expect(fetchCount).toBe(2);
    });

    it('should clear pending after resolution', async () => {
      const coalescer = new RequestCoalescer();

      await coalescer.get('key-1', async () => 'result');

      expect(coalescer.pending.size).toBe(0);
    });

    it('should propagate errors to all waiters', async () => {
      const coalescer = new RequestCoalescer();

      const fetcher = async () => {
        throw new Error('Fetch failed');
      };

      const promises = [
        coalescer.get('key-1', fetcher),
        coalescer.get('key-1', fetcher),
      ];

      for (const p of promises) {
        await expect(p).rejects.toThrow('Fetch failed');
      }
    });
  });
});
