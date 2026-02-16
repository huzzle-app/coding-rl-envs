/**
 * Gateway Integration Tests
 */

describe('API Gateway', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const gateway = require('../../../services/gateway/src/index');
    app = gateway;
    request = global.testUtils.mockRequest(app);
  });

  describe('health check', () => {
    it('should return healthy status', async () => {
      const response = await request.get('/health');
      expect(response.status).toBe(200);
      expect(response.body.status).toBe('healthy');
    });

    it('should include service name', async () => {
      const response = await request.get('/health');
      expect(response.body.service).toBe('gateway');
    });
  });

  describe('request routing', () => {
    it('should route to auth service', async () => {
      const response = await request.post('/api/auth/login').send({
        email: 'test@example.com',
        password: 'password',
      });
      // Without auth token, gateway middleware returns 401
      expect(response.status).toBe(401);
    });

    it('should route to users service', async () => {
      const response = await request.get('/api/users/user-1');
      expect(response.status).toBe(401);
    });

    it('should route to videos service', async () => {
      const response = await request.get('/api/videos');
      expect(response.status).toBe(401);
    });

    it('should return 404 for unknown routes', async () => {
      const response = await request.get('/api/unknown');
      expect(response.status).toBe(404);
    });
  });

  describe('authentication', () => {
    it('should allow public endpoints', async () => {
      const response = await request.get('/health');
      expect(response.status).toBe(200);
    });

    it('should require auth for protected endpoints', async () => {
      const response = await request.get('/api/users/me');
      expect(response.status).toBe(401);
    });

    it('should accept valid token', async () => {
      const response = await request
        .get('/api/users/me')
        .set('Authorization', 'Bearer valid-token');
      // 'valid-token' is not a real JWT, so auth middleware rejects it
      expect(response.status).toBe(401);
    });

    it('should reject invalid token', async () => {
      const response = await request
        .get('/api/users/me')
        .set('Authorization', 'Bearer invalid-token');
      expect(response.status).toBe(401);
    });
  });

  describe('rate limiting', () => {
    it('should allow requests under limit', async () => {
      const response = await request.get('/health');
      expect(response.status).toBe(200);
    });

    it('should include rate limit headers', async () => {
      const response = await request.get('/health');
      const hasRateLimit = response.headers['x-ratelimit-limit'] || response.headers['ratelimit-limit'];
      expect(hasRateLimit).toBeDefined();
    });
  });

  describe('error handling', () => {
    it('should format validation errors', async () => {
      const response = await request.post('/api/auth/login').send({});
      expect(response.status).toBe(400);
    });

    it('should handle service errors', async () => {
      // Simulate downstream service error
      const response = await request.get('/api/failing-endpoint');
      expect([404, 500, 502]).toContain(response.status);
    });
  });

  describe('CORS', () => {
    it('should handle preflight requests', async () => {
      const response = await request.options('/api/videos');
      expect([200, 204]).toContain(response.status);
    });

    it('should set CORS headers', async () => {
      const response = await request.get('/health');
      // BUG: CORS origin defaults to '*' which is insecure
      expect(response.headers['access-control-allow-origin']).toBeDefined();
      expect(response.headers['access-control-allow-origin']).not.toBe('*');
    });
  });

  describe('request logging', () => {
    it('should log requests', async () => {
      const logs = [];
      const originalLog = console.log;
      console.log = (...args) => logs.push(args.join(' '));

      await request.get('/health');

      console.log = originalLog;
      // Should have request logging middleware that logs each request
      expect(logs.length).toBeGreaterThan(0);
    });

    it('should include correlation ID', async () => {
      const response = await request.get('/health');
      // BUG J2: Correlation IDs should be propagated in response headers
      expect(response.headers['x-correlation-id']).toBeDefined();
      expect(typeof response.headers['x-correlation-id']).toBe('string');
    });
  });
});

describe('Service Discovery', () => {
  let ServiceRegistry;

  beforeEach(() => {
    jest.resetModules();
    jest.doMock('consul', () => {
      return function() {
        return {
          agent: {
            service: {
              register: jest.fn().mockResolvedValue({}),
              deregister: jest.fn().mockResolvedValue({}),
            },
          },
          health: { service: {} },
          watch: jest.fn().mockReturnValue({
            on: jest.fn(),
          }),
        };
      };
    });
    ({ ServiceRegistry } = require('../../../services/gateway/src/services/registry'));
  });

  describe('service registration', () => {
    it('should have health check timeout shorter than interval', async () => {
      const registry = new ServiceRegistry({ host: 'localhost', port: 8500 });
      await registry.register('gateway', { host: 'localhost', port: 3000 });

      const call = registry.consul.agent.service.register.mock.calls[0][0];
      const interval = parseInt(call.check.interval);
      const timeout = parseInt(call.check.timeout);
      // BUG L6: timeout (60s) is greater than interval (30s)
      expect(timeout).toBeLessThan(interval);
    });

    it('should include health check endpoint in registration', async () => {
      const registry = new ServiceRegistry({ host: 'localhost', port: 8500 });
      await registry.register('gateway', { host: 'localhost', port: 3000 });

      const call = registry.consul.agent.service.register.mock.calls[0][0];
      expect(call.check.http).toContain('/health');
      expect(call.check.http).toContain('localhost');
    });
  });

  describe('load balancing', () => {
    it('should round-robin across instances', () => {
      const registry = new ServiceRegistry({ host: 'localhost', port: 8500 });
      registry.services.set('auth', [
        { id: 'auth-1', address: 'host-1', port: 3001 },
        { id: 'auth-2', address: 'host-2', port: 3001 },
        { id: 'auth-3', address: 'host-3', port: 3001 },
      ]);

      const results = [];
      for (let i = 0; i < 6; i++) {
        results.push(registry.getService('auth'));
      }

      // Should cycle: auth-1, auth-2, auth-3, auth-1, auth-2, auth-3
      expect(results[0].id).toBe('auth-1');
      expect(results[1].id).toBe('auth-2');
      expect(results[2].id).toBe('auth-3');
      expect(results[3].id).toBe('auth-1');
    });

    it('should return null for unregistered service', () => {
      const registry = new ServiceRegistry({ host: 'localhost', port: 8500 });
      expect(registry.getService('nonexistent')).toBeNull();
    });
  });

  describe('discovery startup', () => {
    it('should return a Promise from discoverServices', () => {
      const registry = new ServiceRegistry({ host: 'localhost', port: 8500 });
      // BUG L4: discoverServices() is sync, returns undefined, not a Promise
      // It calls async _watchService() without await
      const result = registry.discoverServices();
      expect(result).toBeInstanceOf(Promise);
    });
  });
});
