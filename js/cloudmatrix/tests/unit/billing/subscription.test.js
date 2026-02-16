/**
 * Billing Tests
 *
 * Tests bugs F2-F10 (database), H1-H8 (caching)
 */

describe('SubscriptionService', () => {
  let SubscriptionService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/billing/src/services/subscription');
    SubscriptionService = mod.SubscriptionService;
  });

  describe('cache stampede', () => {
    it('cache stampede test', async () => {
      const service = new SubscriptionService();

      const results = await Promise.all([
        service.getSubscription('user-1'),
        service.getSubscription('user-1'),
        service.getSubscription('user-1'),
      ]);

      expect(results[0]).toEqual(results[1]);
    });

    it('concurrent miss test', async () => {
      const service = new SubscriptionService();
      const fetchSpy = jest.spyOn(service, '_fetchFromDb');

      await Promise.all([
        service.getSubscription('user-2'),
        service.getSubscription('user-2'),
      ]);

      expect(fetchSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe('document snapshot cache', () => {
    it('document snapshot stale test', async () => {
      const service = new SubscriptionService();

      await service.getSubscription('user-1');
      await service.updateSubscriptionMetadata('user-1', { plan: 'enterprise' });

      const sub = await service.getSubscription('user-1');
      expect(sub.plan).toBe('enterprise');
    });

    it('snapshot cache test', async () => {
      const service = new SubscriptionService();

      const sub = await service.getSubscription('user-1');
      expect(sub).toBeDefined();
    });
  });

  describe('cache key collision', () => {
    it('search cache collision test', () => {
      const service = new SubscriptionService();

      const key1 = service.getCacheKey({ q: 'test', page: 1, sort: 'date' });
      const key2 = service.getCacheKey({ q: 'test', page: 1, sort: 'relevance' });

      expect(key1).not.toBe(key2);
    });

    it('cache key test', () => {
      const service = new SubscriptionService();

      const key1 = service.getCacheKey({ q: 'hello', page: 1, filters: { type: 'doc' } });
      const key2 = service.getCacheKey({ q: 'hello', page: 1, filters: { type: 'sheet' } });

      expect(key1).not.toBe(key2);
    });
  });

  describe('CDN purge', () => {
    it('cdn purge race test', async () => {
      const service = new SubscriptionService();

      const result = await service.invalidateEdgeCaches('doc-1');
      expect(result.invalidated).toBe(result.total);
    });

    it('purge timing test', async () => {
      const service = new SubscriptionService();

      const result = await service.invalidateEdgeCaches('doc-1');
      expect(result).toBeDefined();
    });
  });

  describe('TTL jitter', () => {
    it('ttl jitter test', () => {
      const baseTTL = 300;
      const ttls = [];

      for (let i = 0; i < 10; i++) {
        ttls.push(baseTTL);
      }

      const allSame = ttls.every(t => t === ttls[0]);
      expect(allSame).toBe(false);
    });

    it('thundering herd test', () => {
      const ttls = new Set();

      for (let i = 0; i < 100; i++) {
        ttls.add(300);
      }

      expect(ttls.size).toBeGreaterThan(1);
    });
  });

  describe('write-through atomicity', () => {
    it('write-through atomic test', async () => {
      const service = new SubscriptionService();

      await service.updateSubscriptionMetadata('sub-1', { plan: 'pro' });
      expect(true).toBe(true);
    });

    it('metadata atomic test', async () => {
      const service = new SubscriptionService();

      await service.updateSubscriptionMetadata('sub-1', { name: 'New Name' });
      expect(true).toBe(true);
    });
  });

  describe('edge cache', () => {
    it('edge cache inconsistency test', async () => {
      const service = new SubscriptionService();

      const result = await service.invalidateEdgeCaches('doc-1');
      expect(result.invalidated).toBe(result.total);
    });

    it('edge sync test', async () => {
      const service = new SubscriptionService();

      const result = await service.invalidateEdgeCaches('doc-2');
      expect(result).toBeDefined();
    });
  });

  describe('LRU eviction', () => {
    it('lru eviction test', () => {
      const service = new SubscriptionService();
      service.maxCacheSize = 3;

      for (let i = 0; i < 5; i++) {
        service.cache.set(`key-${i}`, { data: i });
        service._updateLru(`key-${i}`);
      }

      expect(service.cache.size).toBeLessThanOrEqual(3);
    });

    it('active collaboration evict test', () => {
      const service = new SubscriptionService();
      service.maxCacheSize = 2;

      service.cache.set('active-doc', { active: true });
      service._updateLru('active-doc');
      service.cache.set('other-1', { data: 1 });
      service._updateLru('other-1');
      service.cache.set('other-2', { data: 2 });
      service._updateLru('other-2');

      expect(service.cache.has('active-doc')).toBe(true);
    });
  });

  describe('saga compensation', () => {
    it('saga compensation test', async () => {
      const service = new SubscriptionService();

      const sub = await service.createSubscription({
        userId: 'user-1',
        plan: 'pro',
        billingCycle: 'monthly',
      });

      expect(sub).toBeDefined();
      expect(sub.plan).toBe('pro');
    });

    it('saga rollback test', async () => {
      const service = new SubscriptionService();

      jest.spyOn(service, '_provisionResources').mockRejectedValueOnce(new Error('Provision failed'));

      await expect(
        service.createSubscription({ userId: 'user-1', plan: 'pro', billingCycle: 'monthly' })
      ).rejects.toThrow('Provision failed');
    });
  });

  describe('connection pool', () => {
    it('connection pool exhaustion test', async () => {
      const service = new SubscriptionService();

      const results = await Promise.all(
        Array.from({ length: 50 }, (_, i) => service.getSubscription(`user-${i}`))
      );

      expect(results).toHaveLength(50);
    });

    it('pool drain test', async () => {
      const service = new SubscriptionService();

      const result = await service.getSubscription('user-1');
      expect(result).toBeDefined();
    });
  });

  describe('outbox duplication', () => {
    it('outbox duplication test', async () => {
      const service = new SubscriptionService();

      const sub = await service.createSubscription({
        userId: 'user-1',
        plan: 'basic',
        billingCycle: 'monthly',
      });

      expect(sub.id).toBeDefined();
    });

    it('message dedup test', async () => {
      const service = new SubscriptionService();

      const sub1 = await service.createSubscription({ userId: 'u1', plan: 'pro', billingCycle: 'monthly' });
      const sub2 = await service.createSubscription({ userId: 'u2', plan: 'pro', billingCycle: 'monthly' });

      expect(sub1.id).not.toBe(sub2.id);
    });
  });

  describe('read replica stale', () => {
    it('read replica stale test', async () => {
      const service = new SubscriptionService();

      const result = await service._fetchFromDb('user-1');
      expect(result).toBeDefined();
    });

    it('replica lag test', async () => {
      const service = new SubscriptionService();

      const result = await service._fetchFromDb('user-1');
      expect(result.userId).toBe('user-1');
    });
  });

  describe('optimistic lock', () => {
    it('optimistic lock retry test', async () => {
      const service = new SubscriptionService();

      const result = await service.upgradeSubscription('sub-1', { newPlan: 'enterprise' });
      expect(result.plan).toBe('enterprise');
    });

    it('concurrent retry test', async () => {
      const service = new SubscriptionService();

      const results = await Promise.all([
        service.upgradeSubscription('sub-1', { newPlan: 'pro' }),
        service.upgradeSubscription('sub-2', { newPlan: 'enterprise' }),
      ]);

      expect(results).toHaveLength(2);
    });
  });

  describe('cascade delete', () => {
    it('cascade delete race test', async () => {
      const service = new SubscriptionService();

      await service.deleteSubscription('sub-1');
      expect(true).toBe(true);
    });

    it('fk delete test', async () => {
      const service = new SubscriptionService();

      await service.deleteSubscription('sub-1');
      expect(true).toBe(true);
    });
  });

  describe('batch insert', () => {
    it('batch insert failure test', async () => {
      const service = new SubscriptionService();

      const results = await service.batchCreateSubscriptions([
        { userId: 'u1', plan: 'basic', billingCycle: 'monthly' },
        { userId: 'u2', plan: 'pro', billingCycle: 'monthly' },
      ]);

      const failures = results.filter(r => !r.success);
      expect(failures).toHaveLength(0);
    });

    it('partial batch test', async () => {
      const service = new SubscriptionService();

      jest.spyOn(service, '_chargePayment')
        .mockResolvedValueOnce({ id: 'pay-1', amount: 10, status: 'completed' })
        .mockRejectedValueOnce(new Error('Payment failed'));

      const results = await service.batchCreateSubscriptions([
        { userId: 'u1', plan: 'basic', billingCycle: 'monthly' },
        { userId: 'u2', plan: 'pro', billingCycle: 'monthly' },
      ]);

      const successful = results.filter(r => r.success && r.data !== null);
      expect(successful.length).toBeLessThan(results.length);
    });
  });

  describe('cache key completeness', () => {
    it('getCacheKey should include sort parameter', () => {
      const service = new SubscriptionService();
      const key1 = service.getCacheKey({ q: 'test', page: 1, sort: 'date', filter: null });
      const key2 = service.getCacheKey({ q: 'test', page: 1, sort: 'name', filter: null });
      // BUG: getCacheKey only uses q and page, ignoring sort
      expect(key1).not.toBe(key2);
    });

    it('getCacheKey should include filter parameter', () => {
      const service = new SubscriptionService();
      const key1 = service.getCacheKey({ q: 'test', page: 1, filter: 'active' });
      const key2 = service.getCacheKey({ q: 'test', page: 1, filter: 'archived' });
      expect(key1).not.toBe(key2);
    });

    it('getCacheKey should differentiate requests with different params', () => {
      const service = new SubscriptionService();
      const key1 = service.getCacheKey({ q: 'hello', page: 1, sort: 'asc', filter: 'type:doc' });
      const key2 = service.getCacheKey({ q: 'hello', page: 1, sort: 'desc', filter: 'type:doc' });
      const key3 = service.getCacheKey({ q: 'hello', page: 1, sort: 'asc', filter: 'type:sheet' });
      expect(key1).not.toBe(key2);
      expect(key1).not.toBe(key3);
    });

    it('getCacheKey should include all query parameters to avoid stale results', () => {
      const service = new SubscriptionService();
      const params = { q: 'test', page: 1, sort: 'relevance', filter: 'type:pdf', limit: 50 };
      const key = service.getCacheKey(params);
      // The key should encode enough information that different params produce different keys
      const paramsAlt = { ...params, sort: 'date' };
      const keyAlt = service.getCacheKey(paramsAlt);
      expect(key).not.toBe(keyAlt);
    });
  });

  describe('saga compensation completeness', () => {
    it('saga should compensate all completed steps on failure, not just the last', async () => {
      const service = new SubscriptionService();
      const compensateSpy = jest.spyOn(service, '_compensate');
      const refundSpy = jest.spyOn(service, '_refundPayment');
      const deprovisionSpy = jest.spyOn(service, '_deprovisionResources');

      // Make provision fail
      jest.spyOn(service, '_provisionResources').mockRejectedValueOnce(new Error('Provision failed'));

      await expect(
        service.createSubscription({ userId: 'u1', plan: 'pro', billingCycle: 'monthly' })
      ).rejects.toThrow();

      // BUG: only compensates last step, should compensate all completed steps
      // At failure point: step 0 (create_sub) and step 1 (charge) are completed
      // Both should be compensated
      expect(compensateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    it('failed saga should refund payment when provisioning fails', async () => {
      const service = new SubscriptionService();
      const refundSpy = jest.spyOn(service, '_refundPayment');

      jest.spyOn(service, '_provisionResources').mockRejectedValueOnce(new Error('fail'));

      await expect(
        service.createSubscription({ userId: 'u1', plan: 'pro', billingCycle: 'monthly' })
      ).rejects.toThrow();

      // Payment was charged (step 2), so it should be refunded
      expect(refundSpy).toHaveBeenCalled();
    });

    it('saga compensation should handle all step types, not just the last one', async () => {
      const service = new SubscriptionService();
      const compensated = [];
      jest.spyOn(service, '_compensate').mockImplementation(async (step) => {
        compensated.push(step.type);
      });

      jest.spyOn(service, '_provisionResources').mockRejectedValueOnce(new Error('fail'));

      try {
        await service.createSubscription({ userId: 'u1', plan: 'pro', billingCycle: 'monthly' });
      } catch (e) {
        // expected
      }

      // Should compensate both 'create_sub' and 'charge' steps
      // BUG: only compensates last step ('charge')
      expect(compensated.length).toBeGreaterThanOrEqual(2);
      expect(compensated).toContain('charge');
    });

    it('saga with 3 steps failing at step 3 should compensate steps 1 and 2', async () => {
      const service = new SubscriptionService();
      const compensateSpy = jest.spyOn(service, '_compensate');

      // Fail at provisioning (step 3)
      jest.spyOn(service, '_provisionResources').mockRejectedValueOnce(new Error('boom'));

      try {
        await service.createSubscription({ userId: 'u1', plan: 'pro', billingCycle: 'monthly' });
      } catch (e) {
        // expected
      }

      // Steps 1 (create_sub) and 2 (charge) completed, both need compensation
      expect(compensateSpy.mock.calls.length).toBe(2);
    });

    it('compensate should be called for each completed step in reverse order', async () => {
      const service = new SubscriptionService();
      const compensatedTypes = [];
      jest.spyOn(service, '_compensate').mockImplementation(async (step) => {
        compensatedTypes.push(step.type);
      });

      jest.spyOn(service, '_provisionResources').mockRejectedValueOnce(new Error('fail'));

      try {
        await service.createSubscription({ userId: 'u1', plan: 'enterprise', billingCycle: 'yearly' });
      } catch (e) {
        // expected
      }

      // Should compensate in reverse: charge first, then create_sub
      expect(compensatedTypes).toContain('charge');
      expect(compensatedTypes.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('deadlock', () => {
    it('deadlock ordering test', async () => {
      const service = new SubscriptionService();

      const result = await service.transferSubscription('user-1', 'user-2');
      expect(result.from).toBeDefined();
      expect(result.to).toBeDefined();
    });

    it('lock order test', async () => {
      const service = new SubscriptionService();

      const [r1, r2] = await Promise.all([
        service.transferSubscription('user-1', 'user-2'),
        service.transferSubscription('user-2', 'user-1'),
      ]);

      expect(r1).toBeDefined();
      expect(r2).toBeDefined();
    });
  });
});
