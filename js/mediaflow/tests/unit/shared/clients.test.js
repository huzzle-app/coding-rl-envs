/**
 * Service Clients Unit Tests
 *
 * Tests bugs L1 (circular import), C1 (circuit breaker), C2 (retry storms), C3 (coalescing)
 */

describe('CircuitBreaker', () => {
  let CircuitBreaker;

  beforeEach(() => {
    jest.resetModules();
  });

  
  describe('circular import', () => {
    it('circular import test', () => {
      expect(() => {
        require('../../../shared/clients');
      }).not.toThrow();
    });

    it('config loading test', () => {
      let module;
      let error;

      try {
        module = require('../../../shared/clients');
      } catch (e) {
        error = e;
      }

      expect(error).toBeUndefined();
      expect(module).toBeDefined();
      expect(module.CircuitBreaker).toBeDefined();
    });
  });

  describe('circuit breaker threshold', () => {
    beforeEach(() => {
      const clients = require('../../../shared/clients');
      CircuitBreaker = clients.CircuitBreaker;
    });

    
    it('circuit breaker threshold test', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 3 });

      const failingFn = () => Promise.reject(new Error('fail'));

      // Fail 3 times (AT threshold)
      for (let i = 0; i < 3; i++) {
        try {
          await cb.execute(failingFn);
        } catch (e) {
          // Expected
        }
      }

      
      // But with > instead of >=, it's still closed
      expect(cb.getState()).toBe('open');
    });

    it('failure count test', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 5 });

      const failingFn = () => Promise.reject(new Error('fail'));

      // Fail exactly threshold times
      for (let i = 0; i < 5; i++) {
        try {
          await cb.execute(failingFn);
        } catch (e) {
          // Expected
        }
      }

      // Should be open at exactly threshold
      expect(cb.getState()).toBe('open');
    });

    it('should reset on success', async () => {
      const cb = new CircuitBreaker({ failureThreshold: 3 });

      const failingFn = () => Promise.reject(new Error('fail'));
      const successFn = () => Promise.resolve('ok');

      // Fail twice
      for (let i = 0; i < 2; i++) {
        try {
          await cb.execute(failingFn);
        } catch (e) {}
      }

      // Succeed
      await cb.execute(successFn);

      // Should be back to closed
      expect(cb.getState()).toBe('closed');
    });
  });
});

describe('ServiceClient', () => {
  let ServiceClient;

  beforeEach(() => {
    jest.resetModules();
    const clients = require('../../../shared/clients');
    ServiceClient = clients.ServiceClient;
  });

  describe('retry behavior', () => {
    
    it('exponential delay test', async () => {
      const client = new ServiceClient('test', {
        baseUrl: 'http://localhost',
        maxRetries: 3,
        retryDelay: 100,
      });

      const delays = [];
      const originalDelay = client._delay;
      client._delay = jest.fn(async (ms) => {
        delays.push(ms);
        return originalDelay.call(client, 10); // Fast for test
      });

      const mockAxios = require('axios');
      mockAxios.mockRejectedValue(new Error('network error'));

      try {
        await client.get('/test');
      } catch (e) {}

      
      // delays should be [100, 200, 400] not [100, 100, 100]
      expect(delays[1]).toBeGreaterThan(delays[0]);
    });

    it('retry backoff test', async () => {
      const client = new ServiceClient('test', {
        baseUrl: 'http://localhost',
        maxRetries: 2,
        retryDelay: 50,
      });

      const delays = [];
      client._delay = jest.fn(async (ms) => {
        delays.push(ms);
      });

      const mockAxios = require('axios');
      mockAxios.mockRejectedValue(new Error('fail'));

      try {
        await client.get('/test');
      } catch (e) {}

      // Should have increasing delays
      if (delays.length > 1) {
        expect(delays[1]).toBeGreaterThan(delays[0]);
      }
    });
  });
});

describe('RequestCoalescer', () => {
  let RequestCoalescer;

  beforeEach(() => {
    jest.resetModules();
    const clients = require('../../../shared/clients');
    RequestCoalescer = clients.RequestCoalescer;
  });

  
  it('request coalescing test', async () => {
    const coalescer = new RequestCoalescer();

    let callCount = 0;
    const expensiveFn = async () => {
      callCount++;
      await new Promise(r => setTimeout(r, 50));
      return { data: 'result' };
    };

    // Same key should coalesce
    const [r1, r2] = await Promise.all([
      coalescer.coalesce('key1', expensiveFn),
      coalescer.coalesce('key1', expensiveFn),
    ]);

    // Should only have called once
    expect(callCount).toBe(1);
    expect(r1).toEqual(r2);
  });

  it('duplicate request test', async () => {
    const coalescer = new RequestCoalescer();

    let callCount = 0;
    const fn = async () => {
      callCount++;
      return callCount;
    };

    // Different keys should not coalesce
    const [r1, r2] = await Promise.all([
      coalescer.coalesce('key1', fn),
      coalescer.coalesce('key2', fn),
    ]);

    expect(callCount).toBe(2);
    expect(r1).not.toEqual(r2);
  });
});
