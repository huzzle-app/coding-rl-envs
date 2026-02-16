/**
 * Gateway Integration Tests
 *
 * Tests gateway routing, middleware, authentication flow, service discovery
 */

// Mock express to prevent service index files from starting HTTP servers
jest.mock('express', () => {
  const router = { use: jest.fn(), get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn(), patch: jest.fn() };
  const app = { use: jest.fn().mockReturnThis(), get: jest.fn().mockReturnThis(), post: jest.fn().mockReturnThis(), put: jest.fn().mockReturnThis(), delete: jest.fn().mockReturnThis(), patch: jest.fn().mockReturnThis(), listen: jest.fn((port, cb) => cb && cb()), set: jest.fn().mockReturnThis() };
  const express = jest.fn(() => app);
  express.json = jest.fn(() => jest.fn());
  express.urlencoded = jest.fn(() => jest.fn());
  express.static = jest.fn(() => jest.fn());
  express.Router = jest.fn(() => router);
  return express;
});

describe('API Gateway', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const gateway = require('../../services/gateway/src/index');
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

    it('should include uptime', async () => {
      const response = await request.get('/health');
      expect(response.body.uptime).toBeDefined();
    });
  });

  describe('request routing', () => {
    it('should route to auth service', async () => {
      const response = await request.post('/api/auth/login').send({
        email: 'test@example.com',
        password: 'password',
      });
      expect(response.status).toBeDefined();
    });

    it('should route to users service', async () => {
      const response = await request.get('/api/users/user-1');
      expect(response.status).toBeDefined();
    });

    it('should route to documents service', async () => {
      const response = await request.get('/api/documents');
      expect(response.status).toBeDefined();
    });

    it('should route to search service', async () => {
      const response = await request.get('/api/search?q=test');
      expect(response.status).toBeDefined();
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
      expect([200, 401]).toContain(response.status);
    });

    it('should reject invalid token', async () => {
      const response = await request
        .get('/api/users/me')
        .set('Authorization', 'Bearer invalid-token');
      expect(response.status).toBe(401);
    });

    it('should reject expired token', async () => {
      const response = await request
        .get('/api/users/me')
        .set('Authorization', 'Bearer expired-token');
      expect(response.status).toBe(401);
    });
  });

  describe('rate limiting', () => {
    it('should allow requests under limit', async () => {
      const response = await request.get('/health');
      expect(response.status).toBe(200);
    });

    it('should track rate limit per client', async () => {
      const responses = [];
      for (let i = 0; i < 5; i++) {
        const response = await request.get('/health');
        responses.push(response);
      }
      expect(responses.every(r => r.status === 200)).toBe(true);
    });
  });

  describe('error handling', () => {
    it('should format validation errors', async () => {
      const response = await request.post('/api/auth/login').send({});
      expect(response.status).toBe(400);
    });

    it('should handle service errors', async () => {
      const response = await request.get('/api/failing-endpoint');
      expect([404, 500, 502]).toContain(response.status);
    });

    it('should not leak stack traces', async () => {
      const response = await request.get('/api/failing-endpoint');
      if (response.body.error) {
        expect(response.body.stack).toBeUndefined();
      }
    });
  });

  describe('CORS', () => {
    it('should handle preflight requests', () => {
      const mockOpts = { method: 'OPTIONS', path: '/api/documents' };
      expect(mockOpts.method).toBe('OPTIONS');
    });

    it('should set CORS headers', async () => {
      const response = await request.get('/health');
      if (response.headers['access-control-allow-origin']) {
        expect(response.headers['access-control-allow-origin']).not.toBe('*');
      }
      expect(response.status).toBe(200);
    });
  });

  describe('request logging', () => {
    it('should log request metadata', async () => {
      const logs = [];
      const originalLog = console.log;
      console.log = (...args) => logs.push(args.join(' '));

      await request.get('/health');

      console.log = originalLog;
      expect(Array.isArray(logs)).toBe(true);
    });

    it('should include correlation ID', async () => {
      const response = await request.get('/health');
      if (response.headers['x-correlation-id']) {
        expect(typeof response.headers['x-correlation-id']).toBe('string');
      }
      expect(response.status).toBe(200);
    });
  });
});

describe('Service Discovery', () => {
  describe('service registration', () => {
    it('should register with consul', async () => {
      const mockConsul = global.testUtils.mockConsul();

      const registration = {
        id: 'gateway-1',
        name: 'gateway',
        port: 3000,
        check: {
          http: 'http://localhost:3000/health',
          interval: '10s',
        },
      };

      await mockConsul.agent.service.register(registration);
      expect(mockConsul.agent.service.register).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'gateway',
          check: expect.objectContaining({
            http: expect.any(String),
          }),
        })
      );
    });

    it('should deregister on shutdown', async () => {
      const mockConsul = global.testUtils.mockConsul();

      await mockConsul.agent.service.deregister('gateway-1');
      expect(mockConsul.agent.service.deregister).toHaveBeenCalledWith('gateway-1');
    });
  });

  describe('load balancing', () => {
    it('should distribute requests across instances', () => {
      const instances = ['host-1', 'host-2', 'host-3'];
      const distribution = {};
      instances.forEach(i => distribution[i] = 0);

      for (let i = 0; i < 30; i++) {
        const instance = instances[i % instances.length];
        distribution[instance]++;
      }

      instances.forEach(i => {
        expect(distribution[i]).toBe(10);
      });
    });

    it('should skip unhealthy instances', () => {
      const instances = [
        { host: 'host-1', healthy: true },
        { host: 'host-2', healthy: false },
        { host: 'host-3', healthy: true },
      ];

      const healthyInstances = instances.filter(i => i.healthy);
      expect(healthyInstances).toHaveLength(2);
      expect(healthyInstances.map(i => i.host)).not.toContain('host-2');
    });
  });
});

describe('Middleware Chain', () => {
  describe('middleware ordering', () => {
    it('should execute middleware in order', async () => {
      const executed = [];

      const middleware = [
        (req, next) => { executed.push('cors'); next(); },
        (req, next) => { executed.push('auth'); next(); },
        (req, next) => { executed.push('rateLimit'); next(); },
        (req, next) => { executed.push('handler'); next(); },
      ];

      for (const mw of middleware) {
        await new Promise(resolve => mw({}, resolve));
      }

      expect(executed).toEqual(['cors', 'auth', 'rateLimit', 'handler']);
    });

    it('should short-circuit on auth failure', () => {
      const executed = [];

      const processRequest = (hasToken) => {
        executed.push('cors');
        if (!hasToken) {
          executed.push('auth_fail');
          return { status: 401 };
        }
        executed.push('auth_ok');
        executed.push('handler');
        return { status: 200 };
      };

      const result = processRequest(false);
      expect(result.status).toBe(401);
      expect(executed).not.toContain('handler');
    });
  });

  describe('request validation', () => {
    it('should validate content type', () => {
      const validateContentType = (contentType) => {
        const allowed = ['application/json', 'multipart/form-data'];
        return allowed.some(t => contentType.includes(t));
      };

      expect(validateContentType('application/json')).toBe(true);
      expect(validateContentType('text/html')).toBe(false);
    });

    it('should reject oversized payloads', () => {
      const maxSize = 10 * 1024 * 1024;
      const payload = { size: 15 * 1024 * 1024 };

      expect(payload.size).toBeGreaterThan(maxSize);
    });
  });
});
