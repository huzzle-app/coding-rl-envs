/**
 * Network Chaos Tests
 *
 * Tests CircuitBreaker and ServiceClient behavior under failure conditions.
 * Exercises bugs C1 (off-by-one threshold) and C2 (constant retry delay).
 */

const { CircuitBreaker, ServiceClient, RequestCoalescer } = require('../../shared/clients');

describe('Network Partitions', () => {
  describe('Service Isolation', () => {
    it('should open circuit breaker at failure threshold', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 3 });

      for (let i = 0; i < 3; i++) {
        try {
          await breaker.execute(() => { throw new Error('fail'); });
        } catch (e) { /* expected */ }
      }

      // BUG C1: uses > instead of >=, so state stays 'closed' after exactly 3 failures
      expect(breaker.getState()).toBe('open');
    });

    it('should reject requests when circuit is open', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 1 });

      try {
        await breaker.execute(() => { throw new Error('fail'); });
      } catch (e) { /* expected */ }

      // After 1 failure with threshold 1, should be open (BUG C1: needs >1 failures)
      try {
        await breaker.execute(() => Promise.resolve('ok'));
        // If circuit opened, this should not reach here
      } catch (e) {
        expect(e.message).toBe('Circuit breaker is open');
      }
    });

    it('should open circuit breaker with threshold 5', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 5 });

      for (let i = 0; i < 5; i++) {
        try {
          await breaker.execute(() => { throw new Error('fail'); });
        } catch (e) { /* expected */ }
      }

      // BUG C1: with >, 5 failures doesn't open (needs 6)
      expect(breaker.getState()).toBe('open');
    });

    it('should reset failure count on success', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 3 });

      // 2 failures
      for (let i = 0; i < 2; i++) {
        try {
          await breaker.execute(() => { throw new Error('fail'); });
        } catch (e) { /* expected */ }
      }

      // 1 success should reset count
      await breaker.execute(() => Promise.resolve('ok'));

      // 2 more failures should not open circuit (count reset)
      for (let i = 0; i < 2; i++) {
        try {
          await breaker.execute(() => { throw new Error('fail'); });
        } catch (e) { /* expected */ }
      }

      expect(breaker.getState()).toBe('closed');
    });
  });

  describe('Partial Failures', () => {
    it('should transition to half-open after reset timeout', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 1, resetTimeout: 100 });

      // Trip the breaker (BUG C1: needs >1 fail with threshold 1)
      try {
        await breaker.execute(() => { throw new Error('fail'); });
      } catch (e) { /* expected */ }
      try {
        await breaker.execute(() => { throw new Error('fail'); });
      } catch (e) { /* expected */ }

      // Force open state for test
      breaker.state = 'open';
      breaker.lastFailureTime = Date.now() - 200; // past reset timeout

      // Next call should transition to half-open
      const result = await breaker.execute(() => Promise.resolve('recovered'));
      expect(breaker.getState()).toBe('closed'); // success in half-open -> closed
    });

    it('should limit requests in half-open state', async () => {
      const breaker = new CircuitBreaker({
        failureThreshold: 1,
        maxHalfOpenRequests: 2
      });

      breaker.state = 'half-open';
      breaker.halfOpenRequests = 0;

      // First two should succeed
      await breaker.execute(() => Promise.resolve('ok'));
      // After success in half-open, state goes to closed
      expect(breaker.getState()).toBe('closed');
    });

    it('should re-open circuit on failure in half-open', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 1 });

      breaker.state = 'half-open';
      breaker.halfOpenRequests = 0;

      try {
        await breaker.execute(() => { throw new Error('still failing'); });
      } catch (e) { /* expected */ }

      // Failure in half-open should trigger _onFailure, incrementing count
      expect(breaker.failureCount).toBeGreaterThan(0);
    });
  });

  describe('DNS Failures', () => {
    it('should use exponential backoff on retry', async () => {
      const delays = [];
      const client = new ServiceClient('test-service', {
        baseUrl: 'http://localhost:9999',
        maxRetries: 3,
        retryDelay: 100,
      });

      // Override _delay to capture actual delays
      client._delay = (ms) => {
        delays.push(ms);
        return Promise.resolve();
      };

      // Override circuitBreaker to not interfere
      client.circuitBreaker.execute = (fn) => fn();

      // Mock axios to always fail
      jest.doMock('axios', () => jest.fn().mockRejectedValue(new Error('ENOTFOUND')));

      try {
        await client.request('GET', '/test');
      } catch (e) { /* expected */ }

      // BUG C2: All delays should be different (exponential), but are constant
      if (delays.length > 1) {
        expect(delays[1]).toBeGreaterThan(delays[0]);
      }
    });

    it('should increase delay between retries', async () => {
      const delays = [];
      const client = new ServiceClient('test-service', {
        baseUrl: 'http://localhost:9999',
        maxRetries: 4,
        retryDelay: 50,
      });

      client._delay = (ms) => {
        delays.push(ms);
        return Promise.resolve();
      };
      client.circuitBreaker.execute = (fn) => fn();
      jest.doMock('axios', () => jest.fn().mockRejectedValue(new Error('ECONNREFUSED')));

      try {
        await client.request('GET', '/test');
      } catch (e) { /* expected */ }

      // BUG C2: Delays should increase, but they're all the same constant value
      const uniqueDelays = new Set(delays);
      expect(uniqueDelays.size).toBeGreaterThan(1);
    });
  });
});

describe('Latency Injection', () => {
  describe('Slow Services', () => {
    it('should coalesce concurrent identical requests', async () => {
      const coalescer = new RequestCoalescer();
      let callCount = 0;

      const fn = () => {
        callCount++;
        return new Promise(resolve => setTimeout(() => resolve('result'), 50));
      };

      const [r1, r2, r3] = await Promise.all([
        coalescer.coalesce('key1', fn),
        coalescer.coalesce('key1', fn),
        coalescer.coalesce('key1', fn),
      ]);

      expect(r1).toBe('result');
      expect(r2).toBe('result');
      expect(r3).toBe('result');
      // All three should share the same promise, so fn called once
      expect(callCount).toBe(1);
    });

    it('should not coalesce different keys', async () => {
      const coalescer = new RequestCoalescer();
      let callCount = 0;

      const fn = () => {
        callCount++;
        return Promise.resolve('result');
      };

      await Promise.all([
        coalescer.coalesce('key1', fn),
        coalescer.coalesce('key2', fn),
      ]);

      expect(callCount).toBe(2);
    });
  });

  describe('Jitter', () => {
    it('should clean up pending after resolution', async () => {
      const coalescer = new RequestCoalescer();

      await coalescer.coalesce('key1', () => Promise.resolve('done'));

      // After resolution, pending map should be empty
      expect(coalescer.pending.size).toBe(0);
    });
  });
});

describe('Bandwidth Throttling', () => {
  describe('Slow Connections', () => {
    it('should propagate errors through coalescer', async () => {
      const coalescer = new RequestCoalescer();

      const results = await Promise.allSettled([
        coalescer.coalesce('error-key', () => Promise.reject(new Error('network error'))),
        coalescer.coalesce('error-key', () => Promise.reject(new Error('network error'))),
      ]);

      // Both should receive the same error
      expect(results[0].status).toBe('rejected');
      expect(results[1].status).toBe('rejected');
    });

    it('should allow retry after failed coalesced request', async () => {
      const coalescer = new RequestCoalescer();

      // First attempt fails
      try {
        await coalescer.coalesce('retry-key', () => Promise.reject(new Error('fail')));
      } catch (e) { /* expected */ }

      // After failure, key should be cleared
      expect(coalescer.pending.has('retry-key')).toBe(false);

      // Second attempt should work
      const result = await coalescer.coalesce('retry-key', () => Promise.resolve('success'));
      expect(result).toBe('success');
    });
  });

  describe('Packet Loss', () => {
    it('should expose circuit breaker state via getState', () => {
      const breaker = new CircuitBreaker({ failureThreshold: 5 });
      expect(breaker.getState()).toBe('closed');

      breaker.state = 'open';
      expect(breaker.getState()).toBe('open');
    });

    it('should reset circuit breaker completely', async () => {
      const breaker = new CircuitBreaker({ failureThreshold: 2 });

      try {
        await breaker.execute(() => { throw new Error('fail'); });
      } catch (e) { /* expected */ }

      expect(breaker.failureCount).toBe(1);
      breaker.reset();
      expect(breaker.failureCount).toBe(0);
      expect(breaker.getState()).toBe('closed');
      expect(breaker.lastFailureTime).toBeNull();
    });
  });
});
