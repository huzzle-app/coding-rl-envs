/**
 * Webhook Delivery Tests
 *
 * Tests WebhookDeliveryEngine, SignatureVerifier, RetryScheduler, EventFilter from actual source code.
 * Exercises bugs: delivery retry logic, signature verification, event filtering patterns.
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

const { WebhookDeliveryEngine, SignatureVerifier, RetryScheduler, EventFilter } = require('../../../services/webhooks/src/index');

describe('WebhookDeliveryEngine', () => {
  let engine;

  beforeEach(() => {
    engine = new WebhookDeliveryEngine({ maxRetries: 3, timeoutMs: 5000, batchSize: 5 });
  });

  describe('enqueue', () => {
    it('should enqueue a delivery', () => {
      const delivery = engine.enqueue('wh-1', 'document.created', { docId: 'doc-1' });
      expect(delivery).toBeDefined();
      expect(delivery.webhookId).toBe('wh-1');
      expect(delivery.event).toBe('document.created');
      expect(delivery.status).toBe('pending');
      expect(delivery.attempts).toBe(0);
    });

    it('should assign unique ids to deliveries', () => {
      const d1 = engine.enqueue('wh-1', 'a', {});
      const d2 = engine.enqueue('wh-1', 'b', {});
      expect(d1.id).not.toBe(d2.id);
    });

    it('should track pending count', () => {
      engine.enqueue('wh-1', 'a', {});
      engine.enqueue('wh-2', 'b', {});
      expect(engine.getPendingCount()).toBe(2);
    });
  });

  describe('processDeliveries', () => {
    it('should process pending deliveries successfully', async () => {
      engine.enqueue('wh-1', 'document.created', { docId: 'doc-1' });
      const results = await engine.processDeliveries();
      expect(results).toHaveLength(1);
      expect(results[0].status).toBe('delivered');
      expect(results[0].attempts).toBe(1);
    });

    it('should move delivered items to log and remove from pending', async () => {
      engine.enqueue('wh-1', 'a', {});
      await engine.processDeliveries();
      expect(engine.getPendingCount()).toBe(0);
      expect(engine.deliveryLog).toHaveLength(1);
    });

    it('should respect batch size', async () => {
      for (let i = 0; i < 10; i++) {
        engine.enqueue(`wh-${i}`, 'event', {});
      }
      const results = await engine.processDeliveries();
      expect(results.length).toBeLessThanOrEqual(5);
    });

    it('should retry failed deliveries up to maxRetries', async () => {
      engine.enqueue('wh-1', 'a', {});
      engine._deliver = jest.fn().mockRejectedValue(new Error('timeout'));

      // First attempt fails
      let results = await engine.processDeliveries();
      expect(results[0].status).toBe('pending');
      expect(results[0].attempts).toBe(1);

      // Force nextAttemptAt to now for immediate retry
      engine.pendingDeliveries[0].nextAttemptAt = Date.now();
      results = await engine.processDeliveries();
      expect(results[0].attempts).toBe(2);

      // Third attempt -> should fail permanently (maxRetries=3)
      engine.pendingDeliveries[0].nextAttemptAt = Date.now();
      results = await engine.processDeliveries();
      expect(results[0].status).toBe('failed');
      expect(engine.getPendingCount()).toBe(0);
    });
  });

  describe('delivery status and history', () => {
    it('should retrieve delivery status by id', async () => {
      const delivery = engine.enqueue('wh-1', 'a', {});
      const status = engine.getDeliveryStatus(delivery.id);
      expect(status).toBeDefined();
      expect(status.status).toBe('pending');
    });

    it('should retrieve delivery history for a webhook', async () => {
      engine.enqueue('wh-1', 'a', {});
      engine.enqueue('wh-1', 'b', {});
      engine.enqueue('wh-2', 'c', {});
      await engine.processDeliveries();

      const history = engine.getDeliveryHistory('wh-1');
      expect(history).toHaveLength(2);
    });

    it('should return null for unknown delivery id', () => {
      expect(engine.getDeliveryStatus('nonexistent')).toBeNull();
    });
  });

  describe('failure rate', () => {
    it('should calculate failure rate', async () => {
      engine.enqueue('wh-1', 'a', {});
      engine.enqueue('wh-1', 'b', {});
      await engine.processDeliveries();

      // All succeeded
      expect(engine.getFailureRate('wh-1')).toBe(0);
    });

    it('should return 0 for unknown webhook', () => {
      expect(engine.getFailureRate('nonexistent')).toBe(0);
    });
  });

  describe('log cleanup', () => {
    it('should clear old log entries', async () => {
      engine.enqueue('wh-1', 'a', {});
      await engine.processDeliveries();

      // Hack: set createdAt to old time
      engine.deliveryLog[0].createdAt = Date.now() - 100000000;
      engine.clearLog(86400000);
      expect(engine.deliveryLog).toHaveLength(0);
    });
  });
});

describe('SignatureVerifier', () => {
  let verifier;

  beforeEach(() => {
    verifier = new SignatureVerifier({ timestampTolerance: 300 });
  });

  describe('sign', () => {
    it('should generate a signature with timestamp', () => {
      const result = verifier.sign({ test: 'data' }, 'secret-key');
      expect(result.signature).toContain('t=');
      expect(result.signature).toContain('v1=');
      expect(result.timestamp).toBeDefined();
    });

    it('should produce different signatures for different secrets', () => {
      const sig1 = verifier.sign('payload', 'secret-1');
      const sig2 = verifier.sign('payload', 'secret-2');
      expect(sig1.signature).not.toBe(sig2.signature);
    });
  });

  describe('verify', () => {
    it('should verify a valid signature', () => {
      const payload = { event: 'test' };
      const secret = 'my-secret';
      const { signature } = verifier.sign(payload, secret);
      expect(verifier.verify(payload, signature, secret)).toBe(true);
    });

    it('should reject an invalid signature', () => {
      const payload = { event: 'test' };
      const { signature } = verifier.sign(payload, 'correct-secret');
      expect(verifier.verify(payload, signature, 'wrong-secret')).toBe(false);
    });

    it('should reject replayed signatures beyond tolerance', () => {
      const payload = 'test-data';
      const secret = 'secret';
      const { signature } = verifier.sign(payload, secret);

      // Tamper the timestamp to be old
      const oldTimestamp = Math.floor(Date.now() / 1000) - 600;
      const tamperedSig = signature.replace(/t=\d+/, `t=${oldTimestamp}`);
      expect(verifier.verify(payload, tamperedSig, secret)).toBe(false);
    });

    it('should reject malformed signature strings', () => {
      expect(verifier.verify('payload', 'garbage', 'secret')).toBe(false);
    });
  });

  describe('getTimestamp', () => {
    it('should extract timestamp from signature', () => {
      const { signature, timestamp } = verifier.sign('data', 'key');
      expect(verifier.getTimestamp(signature)).toBe(timestamp);
    });

    it('should return null for invalid signature', () => {
      expect(verifier.getTimestamp('invalid')).toBeNull();
    });
  });
});

describe('RetryScheduler', () => {
  let scheduler;

  beforeEach(() => {
    scheduler = new RetryScheduler({ maxRetries: 5, baseDelay: 1000, maxDelay: 60000, jitterFactor: 0 });
  });

  describe('calculateNextRetry', () => {
    it('should use exponential backoff', () => {
      const d0 = scheduler.calculateNextRetry(0);
      const d1 = scheduler.calculateNextRetry(1);
      const d2 = scheduler.calculateNextRetry(2);

      expect(d0).toBe(1000);
      expect(d1).toBe(2000);
      expect(d2).toBe(4000);
    });

    it('should cap at maxDelay', () => {
      const d10 = scheduler.calculateNextRetry(10);
      expect(d10).toBeLessThanOrEqual(60000);
    });
  });

  describe('scheduleRetry', () => {
    it('should schedule a retry', () => {
      const result = scheduler.scheduleRetry('del-1', 0);
      expect(result).not.toBeNull();
      expect(result.deliveryId).toBe('del-1');
      expect(result.delay).toBe(1000);
    });

    it('should return null when maxRetries exceeded', () => {
      const result = scheduler.scheduleRetry('del-1', 5);
      expect(result).toBeNull();
    });

    it('should store in schedules map', () => {
      scheduler.scheduleRetry('del-1', 0);
      expect(scheduler.getNextRetry('del-1')).not.toBeNull();
    });
  });

  describe('cancelRetry', () => {
    it('should cancel a scheduled retry', () => {
      scheduler.scheduleRetry('del-1', 0);
      expect(scheduler.cancelRetry('del-1')).toBe(true);
      expect(scheduler.getNextRetry('del-1')).toBeNull();
    });
  });

  describe('pending count', () => {
    it('should track pending retries', () => {
      scheduler.scheduleRetry('del-1', 0);
      scheduler.scheduleRetry('del-2', 1);
      expect(scheduler.getPendingCount()).toBe(2);
    });
  });

  describe('cleanupCompleted', () => {
    it('should remove completed deliveries from schedule', () => {
      scheduler.scheduleRetry('del-1', 0);
      scheduler.scheduleRetry('del-2', 0);
      scheduler.cleanupCompleted(['del-1']);
      expect(scheduler.getPendingCount()).toBe(1);
    });
  });
});

describe('TenantIsolation - checkQuota', () => {
  let TenantIsolation;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/admin/src/index');
    TenantIsolation = mod.TenantIsolation;
  });

  it('checkQuota should allow usage at exactly limit-1', () => {
    const isolation = new TenantIsolation();
    isolation.createTenant('t1', { maxDocuments: 10 });
    isolation.recordUsage('t1', 'documents', 9);

    const result = isolation.checkQuota('t1', 'documents', 1);
    // usage=9, amount=1, limit=10: total=10 which is AT the limit
    // BUG: uses >= instead of >, blocking at exactly the limit
    expect(result.allowed).toBe(true);
  });

  it('checkQuota should deny when usage would exceed limit', () => {
    const isolation = new TenantIsolation();
    isolation.createTenant('t1', { maxDocuments: 10 });
    isolation.recordUsage('t1', 'documents', 10);

    const result = isolation.checkQuota('t1', 'documents', 1);
    // usage=10 + amount=1 = 11 > 10, should be denied
    expect(result.allowed).toBe(false);
  });

  it('checkQuota off-by-one: usage + amount == limit should be allowed', () => {
    const isolation = new TenantIsolation();
    isolation.createTenant('t1', { maxUsers: 5 });
    isolation.recordUsage('t1', 'users', 4);

    // 4 + 1 = 5, exactly at limit, should be allowed (filling to capacity)
    // BUG: >= makes 5 >= 5 true, so it's denied
    const result = isolation.checkQuota('t1', 'users', 1);
    expect(result.allowed).toBe(true);
  });

  it('checkQuota at exactly the quota boundary should permit usage', () => {
    const isolation = new TenantIsolation();
    isolation.createTenant('t1', { maxApiCalls: 100 });
    isolation.recordUsage('t1', 'apiCalls', 99);

    // 99 + 1 = 100, at limit, should be allowed
    const result = isolation.checkQuota('t1', 'apiCalls', 1);
    expect(result.allowed).toBe(true);
  });

  it('checkQuota remaining should be 0 when at capacity, not negative', () => {
    const isolation = new TenantIsolation();
    isolation.createTenant('t1', { maxDocuments: 5 });
    isolation.recordUsage('t1', 'documents', 4);

    const result = isolation.checkQuota('t1', 'documents', 1);
    // At capacity: remaining should be 0
    expect(result.allowed).toBe(true);
    expect(result.remaining).toBe(0);
  });
});

describe('EventFilter', () => {
  let filter;

  beforeEach(() => {
    filter = new EventFilter();
  });

  describe('exact matching', () => {
    it('should match exact event names', () => {
      filter.setFilter('wh-1', ['document.created']);
      expect(filter.matchesFilter('wh-1', 'document.created')).toBe(true);
      expect(filter.matchesFilter('wh-1', 'document.updated')).toBe(false);
    });
  });

  describe('wildcard matching', () => {
    it('should match wildcard patterns with .*', () => {
      filter.setFilter('wh-1', ['document.*']);
      expect(filter.matchesFilter('wh-1', 'document.created')).toBe(true);
      expect(filter.matchesFilter('wh-1', 'document.updated')).toBe(true);
      expect(filter.matchesFilter('wh-1', 'user.created')).toBe(false);
    });

    it('should match global wildcard *', () => {
      filter.setFilter('wh-1', ['*']);
      expect(filter.matchesFilter('wh-1', 'anything.here')).toBe(true);
    });
  });

  describe('no filter', () => {
    it('should allow all events when no filter set', () => {
      expect(filter.matchesFilter('wh-1', 'anything')).toBe(true);
    });

    it('should allow all events when empty filter', () => {
      filter.setFilter('wh-1', []);
      expect(filter.matchesFilter('wh-1', 'anything')).toBe(true);
    });
  });

  describe('getMatchingWebhooks', () => {
    it('should return webhooks matching an event', () => {
      filter.setFilter('wh-1', ['document.*']);
      filter.setFilter('wh-2', ['user.*']);
      filter.setFilter('wh-3', ['document.created']);

      const matches = filter.getMatchingWebhooks('document.created', ['wh-1', 'wh-2', 'wh-3']);
      expect(matches).toContain('wh-1');
      expect(matches).toContain('wh-3');
      expect(matches).not.toContain('wh-2');
    });
  });

  describe('removeFilter', () => {
    it('should remove filter for a webhook', () => {
      filter.setFilter('wh-1', ['document.*']);
      filter.removeFilter('wh-1');
      expect(filter.getFilter('wh-1')).toEqual([]);
    });
  });
});
