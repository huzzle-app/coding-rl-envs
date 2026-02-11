/**
 * Gateway Routing Unit Tests
 */

describe('ServiceRegistry', () => {
  let ServiceRegistry;

  beforeEach(() => {
    jest.resetModules();
    const registry = require('../../../../services/gateway/src/services/registry');
    ServiceRegistry = registry.ServiceRegistry;
  });

  describe('service registration', () => {
    it('should register service', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001 });
      expect(registry.getService('auth')).toBeDefined();
    });

    it('should update existing service', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001 });
      await registry.register('auth', { host: 'localhost', port: 3002 });
      expect(registry.getService('auth').port).toBe(3002);
    });

    it('should deregister service', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001 });
      await registry.deregister('auth');
      expect(registry.getService('auth')).toBeUndefined();
    });

    it('should list all services', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001 });
      await registry.register('users', { host: 'localhost', port: 3002 });
      const services = registry.listServices();
      expect(services).toHaveLength(2);
    });
  });

  describe('health checking', () => {
    it('should mark unhealthy service', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001 });
      await registry.markUnhealthy('auth');
      expect(registry.getService('auth').healthy).toBe(false);
    });

    it('should mark healthy service', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001, healthy: false });
      await registry.markHealthy('auth');
      expect(registry.getService('auth').healthy).toBe(true);
    });

    it('should filter healthy services', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { host: 'localhost', port: 3001, healthy: true });
      await registry.register('users', { host: 'localhost', port: 3002, healthy: false });
      const healthy = registry.getHealthyServices();
      expect(healthy).toHaveLength(1);
    });
  });

  describe('load balancing', () => {
    it('should round robin instances', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { instances: [
        { host: 'host1', port: 3001 },
        { host: 'host2', port: 3001 },
        { host: 'host3', port: 3001 },
      ]});

      const first = registry.getNextInstance('auth');
      const second = registry.getNextInstance('auth');
      const third = registry.getNextInstance('auth');

      expect(first.host).not.toBe(second.host);
      expect(second.host).not.toBe(third.host);
    });

    it('should skip unhealthy instances', async () => {
      const registry = new ServiceRegistry();
      await registry.register('auth', { instances: [
        { host: 'host1', port: 3001, healthy: false },
        { host: 'host2', port: 3001, healthy: true },
      ]});

      const instance = registry.getNextInstance('auth');
      expect(instance.host).toBe('host2');
    });
  });
});

describe('RequestRouter', () => {
  let RequestRouter;

  beforeEach(() => {
    jest.resetModules();
    const router = require('../../../../services/gateway/src/services/router');
    RequestRouter = router.RequestRouter;
  });

  describe('route matching', () => {
    it('should match exact path', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users', 'users');
      expect(router.match('/api/users')).toBe('users');
    });

    it('should match wildcard path', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users/*', 'users');
      expect(router.match('/api/users/123')).toBe('users');
    });

    it('should match path with params', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users/:id', 'users');
      const match = router.matchWithParams('/api/users/123');
      expect(match.service).toBe('users');
      expect(match.params.id).toBe('123');
    });

    it('should return null for no match', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users', 'users');
      expect(router.match('/api/videos')).toBeNull();
    });

    it('should prioritize exact matches', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users/*', 'users-wildcard');
      router.addRoute('/api/users/me', 'users-me');
      expect(router.match('/api/users/me')).toBe('users-me');
    });
  });

  describe('method filtering', () => {
    it('should match by method', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users', 'users-get', { method: 'GET' });
      router.addRoute('/api/users', 'users-post', { method: 'POST' });
      expect(router.match('/api/users', 'GET')).toBe('users-get');
      expect(router.match('/api/users', 'POST')).toBe('users-post');
    });

    it('should match any method if not specified', () => {
      const router = new RequestRouter();
      router.addRoute('/api/users', 'users');
      expect(router.match('/api/users', 'DELETE')).toBe('users');
    });
  });
});

describe('RateLimiter', () => {
  let RateLimiter;

  beforeEach(() => {
    jest.resetModules();
    const limiter = require('../../../../services/gateway/src/middleware/ratelimit');
    RateLimiter = limiter.RateLimiter;
  });

  describe('token bucket', () => {
    it('should allow requests under limit', async () => {
      const limiter = new RateLimiter({ limit: 10, window: 60 });
      const allowed = await limiter.checkLimit('user-1');
      expect(allowed).toBe(true);
    });

    it('should block requests over limit', async () => {
      const limiter = new RateLimiter({ limit: 2, window: 60 });
      await limiter.checkLimit('user-1');
      await limiter.checkLimit('user-1');
      const allowed = await limiter.checkLimit('user-1');
      expect(allowed).toBe(false);
    });

    it('should track per user', async () => {
      const limiter = new RateLimiter({ limit: 1, window: 60 });
      await limiter.checkLimit('user-1');
      const allowed = await limiter.checkLimit('user-2');
      expect(allowed).toBe(true);
    });

    it('should return remaining count', async () => {
      const limiter = new RateLimiter({ limit: 10, window: 60 });
      await limiter.checkLimit('user-1');
      const remaining = await limiter.getRemaining('user-1');
      expect(remaining).toBe(9);
    });
  });
});
