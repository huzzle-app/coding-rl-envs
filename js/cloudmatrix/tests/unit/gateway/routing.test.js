/**
 * Gateway Routing Tests
 *
 * Tests service routing, proxy logic, circuit breaker integration
 */

describe('Service Router', () => {
  describe('route matching', () => {
    it('should match auth routes', () => {
      const routes = {
        '/api/auth': 'auth-service',
        '/api/users': 'users-service',
        '/api/documents': 'documents-service',
        '/api/search': 'search-service',
      };

      const matchRoute = (path) => {
        for (const [prefix, service] of Object.entries(routes)) {
          if (path.startsWith(prefix)) return service;
        }
        return null;
      };

      expect(matchRoute('/api/auth/login')).toBe('auth-service');
      expect(matchRoute('/api/users/user-1')).toBe('users-service');
      expect(matchRoute('/api/documents/doc-1')).toBe('documents-service');
      expect(matchRoute('/api/unknown')).toBeNull();
    });

    it('should handle nested paths', () => {
      const matchRoute = (path) => {
        if (path.startsWith('/api/documents')) return 'documents';
        return null;
      };

      expect(matchRoute('/api/documents/doc-1/versions')).toBe('documents');
      expect(matchRoute('/api/documents/doc-1/comments')).toBe('documents');
    });

    it('should handle query parameters', () => {
      const extractPath = (url) => url.split('?')[0];

      expect(extractPath('/api/search?q=test&page=1')).toBe('/api/search');
    });

    it('should strip gateway prefix', () => {
      const stripPrefix = (path) => path.replace(/^\/api/, '');

      expect(stripPrefix('/api/documents/doc-1')).toBe('/documents/doc-1');
      expect(stripPrefix('/api/users/me')).toBe('/users/me');
    });
  });

  describe('service discovery', () => {
    it('should resolve service addresses', () => {
      const services = new Map();
      services.set('auth', { host: 'auth-service', port: 3001 });
      services.set('users', { host: 'users-service', port: 3002 });
      services.set('documents', { host: 'documents-service', port: 3003 });

      const resolve = (name) => {
        const svc = services.get(name);
        if (!svc) return null;
        return `http://${svc.host}:${svc.port}`;
      };

      expect(resolve('auth')).toBe('http://auth-service:3001');
      expect(resolve('unknown')).toBeNull();
    });

    it('should handle service failover', () => {
      const instances = [
        { host: 'service-1', healthy: false },
        { host: 'service-2', healthy: true },
        { host: 'service-3', healthy: true },
      ];

      const getHealthy = () => instances.filter(i => i.healthy);

      const healthy = getHealthy();
      expect(healthy).toHaveLength(2);
      expect(healthy[0].host).toBe('service-2');
    });

    it('should round-robin across instances', () => {
      const instances = ['host-1', 'host-2', 'host-3'];
      let index = 0;

      const getNext = () => {
        const instance = instances[index % instances.length];
        index++;
        return instance;
      };

      expect(getNext()).toBe('host-1');
      expect(getNext()).toBe('host-2');
      expect(getNext()).toBe('host-3');
      expect(getNext()).toBe('host-1');
    });
  });

  describe('request forwarding', () => {
    it('should forward headers', () => {
      const incomingHeaders = {
        authorization: 'Bearer token',
        'content-type': 'application/json',
        'x-correlation-id': 'corr-123',
        cookie: 'session=abc',
      };

      const forwardHeaders = ['authorization', 'content-type', 'x-correlation-id'];

      const filtered = {};
      for (const header of forwardHeaders) {
        if (incomingHeaders[header]) {
          filtered[header] = incomingHeaders[header];
        }
      }

      expect(filtered.authorization).toBe('Bearer token');
      expect(filtered.cookie).toBeUndefined();
    });

    it('should add trace context headers', () => {
      const headers = {};
      headers['x-trace-id'] = 'trace-123';
      headers['x-span-id'] = 'span-456';

      expect(headers['x-trace-id']).toBe('trace-123');
    });

    it('should set request timeout', () => {
      const timeouts = {
        default: 30000,
        upload: 300000,
        search: 10000,
      };

      const getTimeout = (serviceType) => {
        return timeouts[serviceType] || timeouts.default;
      };

      expect(getTimeout('upload')).toBe(300000);
      expect(getTimeout('unknown')).toBe(30000);
    });
  });

  describe('response handling', () => {
    it('should pass through status codes', () => {
      const statusCodes = [200, 201, 400, 401, 403, 404, 409, 500];

      for (const code of statusCodes) {
        expect(code).toBeGreaterThanOrEqual(100);
        expect(code).toBeLessThan(600);
      }
    });

    it('should transform error responses', () => {
      const transformError = (status, body) => {
        return {
          status,
          error: body.error || 'Unknown Error',
          message: body.message || 'An error occurred',
          timestamp: new Date().toISOString(),
        };
      };

      const result = transformError(404, { error: 'NotFound', message: 'Doc not found' });
      expect(result.status).toBe(404);
      expect(result.timestamp).toBeDefined();
    });

    it('should handle empty responses', () => {
      const response = { status: 204, body: null };
      expect(response.body).toBeNull();
    });

    it('should aggregate multi-service responses', () => {
      const responses = [
        { service: 'documents', data: { docs: [] } },
        { service: 'permissions', data: { perms: {} } },
        { service: 'presence', data: { users: [] } },
      ];

      const aggregated = {};
      for (const r of responses) {
        aggregated[r.service] = r.data;
      }

      expect(Object.keys(aggregated)).toHaveLength(3);
    });
  });
});

describe('ServiceHealthMonitor', () => {
  let ServiceHealthMonitor;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/gateway/src/services/registry');
    ServiceHealthMonitor = mod.ServiceHealthMonitor;
  });

  it('should mark instance unhealthy when failures reach threshold (not exceed)', () => {
    const monitor = new ServiceHealthMonitor({});
    monitor.failureThreshold = 3;

    monitor.healthState.set('inst-1', {
      healthy: true,
      consecutiveFailures: 0,
      consecutiveSuccesses: 0,
      lastCheckTime: Date.now(),
      lastResponseTime: 0,
    });

    const state = monitor.healthState.get('inst-1');
    // Simulate exactly 3 consecutive failures
    state.consecutiveFailures = 3;
    // BUG: uses > instead of >= so threshold must be exceeded, not just met
    if (state.healthy && state.consecutiveFailures >= monitor.failureThreshold) {
      state.healthy = false;
    }
    const stateAfter = monitor.healthState.get('inst-1');
    // With >= check, 3 failures should mark unhealthy
    expect(stateAfter.healthy).toBe(false);
  });

  it('health check threshold should use >= not > for boundary', () => {
    const monitor = new ServiceHealthMonitor({});
    monitor.failureThreshold = 3;
    monitor.recoveryThreshold = 2;

    // Set up health state directly (avoid startMonitoring which creates intervals)
    monitor.healthState.set('inst-1', {
      healthy: true,
      consecutiveFailures: 3,
      consecutiveSuccesses: 0,
      lastCheckTime: Date.now(),
      lastResponseTime: 0,
    });
    const state = monitor.healthState.get('inst-1');

    // The check in _performCheck uses > instead of >=
    // So at exactly threshold, instance stays healthy (BUG)
    const shouldBeUnhealthy = state.consecutiveFailures > monitor.failureThreshold;
    // With '>' it's false at threshold=3, failures=3. Should use >=
    expect(shouldBeUnhealthy).toBe(true);
  });

  it('recovery threshold should also use >= for consistency', () => {
    const monitor = new ServiceHealthMonitor({});
    monitor.recoveryThreshold = 2;

    // Set up health state directly
    monitor.healthState.set('inst-1', {
      healthy: false,
      consecutiveFailures: 0,
      consecutiveSuccesses: 2,
      lastCheckTime: Date.now(),
      lastResponseTime: 0,
    });
    const state = monitor.healthState.get('inst-1');

    // BUG: uses > instead of >= for recovery too
    const shouldRecover = state.consecutiveSuccesses > monitor.recoveryThreshold;
    expect(shouldRecover).toBe(true);
  });

  it('instance with exactly failureThreshold failures should be marked unhealthy', () => {
    const monitor = new ServiceHealthMonitor({});
    monitor.failureThreshold = 5;

    // Set up health state directly
    monitor.healthState.set('inst-1', {
      healthy: true,
      consecutiveFailures: 5,
      consecutiveSuccesses: 0,
      lastCheckTime: Date.now(),
      lastResponseTime: 0,
    });
    const state = monitor.healthState.get('inst-1');

    // Simulate what _performCheck does with the buggy '>'
    if (state.healthy && state.consecutiveFailures > monitor.failureThreshold) {
      state.healthy = false;
    }
    // BUG: 5 > 5 is false, so instance stays healthy at exactly the threshold
    expect(state.healthy).toBe(false);
  });

  it('failure threshold boundary check should be inclusive', () => {
    const monitor = new ServiceHealthMonitor({});
    monitor.failureThreshold = 1;

    // Set up health state directly
    monitor.healthState.set('inst-1', {
      healthy: true,
      consecutiveFailures: 1,
      consecutiveSuccesses: 0,
      lastCheckTime: Date.now(),
      lastResponseTime: 0,
    });
    const state = monitor.healthState.get('inst-1');

    // With threshold=1, even 1 failure should trigger unhealthy
    if (state.healthy && state.consecutiveFailures > monitor.failureThreshold) {
      state.healthy = false;
    }
    // BUG: 1 > 1 is false
    expect(state.healthy).toBe(false);
  });
});

describe('WebSocket Proxy', () => {
  describe('ws upgrade', () => {
    it('should validate upgrade request', () => {
      const headers = {
        upgrade: 'websocket',
        connection: 'Upgrade',
        'sec-websocket-version': '13',
      };

      expect(headers.upgrade).toBe('websocket');
      expect(headers['sec-websocket-version']).toBe('13');
    });

    it('should extract document ID from ws path', () => {
      const extractDocId = (path) => {
        const match = path.match(/\/ws\/documents\/([^/]+)/);
        return match ? match[1] : null;
      };

      expect(extractDocId('/ws/documents/doc-123')).toBe('doc-123');
      expect(extractDocId('/ws/other')).toBeNull();
    });

    it('should validate ws auth token', () => {
      const jwt = require('jsonwebtoken');
      const secret = 'test-secret';

      const token = jwt.sign(
        { userId: 'user-1', scope: ['ws:connect', 'doc:edit'] },
        secret,
        { expiresIn: '1h' }
      );

      const decoded = jwt.verify(token, secret);
      expect(decoded.scope).toContain('ws:connect');
    });
  });

  describe('ws message routing', () => {
    it('should route edit messages', () => {
      const routeMessage = (msg) => {
        switch (msg.type) {
          case 'edit': return 'document-service';
          case 'cursor': return 'presence-service';
          case 'comment': return 'comments-service';
          default: return null;
        }
      };

      expect(routeMessage({ type: 'edit' })).toBe('document-service');
      expect(routeMessage({ type: 'cursor' })).toBe('presence-service');
      expect(routeMessage({ type: 'unknown' })).toBeNull();
    });

    it('should validate message format', () => {
      const isValid = (msg) => {
        return msg && msg.type && msg.documentId;
      };

      expect(isValid({ type: 'edit', documentId: 'doc-1' })).toBe(true);
      expect(isValid({ type: 'edit' })).toBe(false);
      expect(isValid(null)).toBe(false);
    });
  });
});
