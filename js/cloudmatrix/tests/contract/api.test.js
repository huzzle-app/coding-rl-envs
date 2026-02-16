/**
 * API Contract Tests
 *
 * Tests that actual service classes conform to expected interfaces and produce correct shapes.
 * Imports real source code to validate class APIs, method signatures, and return value contracts.
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

const { EventSourcingEngine, SnapshotManager, BranchMerger } = require('../../services/versions/src/index');
const { WebhookDeliveryEngine, SignatureVerifier, RetryScheduler, EventFilter } = require('../../services/webhooks/src/index');
const { NotificationAggregator, DeliveryScheduler, PreferenceEngine } = require('../../services/notifications/src/index');
const { InvoiceCalculator, UsageMeter, SubscriptionLifecycle } = require('../../services/billing/src/services/subscription');
const { TimeSeriesAggregator, FunnelAnalyzer, CohortTracker } = require('../../services/analytics/src/index');
const { errorHandler } = require('../../services/gateway/src/middleware/error');
const { CircuitBreaker, ServiceClient, HealthChecker, RequestCoalescer, BulkheadIsolation, RetryPolicy } = require('../../shared/clients');
const { BaseEvent, EventBus, SagaOrchestrator, EventStore, SchemaRegistry } = require('../../shared/events');
const { DistributedLock, TraceContext, CorrelationContext, MetricsCollector, StructuredLogger, TokenBucketRateLimiter, ConsistentHashRing, BloomFilter } = require('../../shared/utils');

describe('Versions Service Contract', () => {
  describe('EventSourcingEngine interface', () => {
    it('should expose appendEvent, getEvents, rebuildState, compact methods', () => {
      const engine = new EventSourcingEngine();
      expect(typeof engine.appendEvent).toBe('function');
      expect(typeof engine.getEvents).toBe('function');
      expect(typeof engine.rebuildState).toBe('function');
      expect(typeof engine.compact).toBe('function');
      expect(typeof engine.getStreamLength).toBe('function');
    });

    it('appendEvent should return event with id, sequenceNumber, streamId, timestamp', () => {
      const engine = new EventSourcingEngine();
      const evt = engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      expect(evt).toHaveProperty('id');
      expect(evt).toHaveProperty('sequenceNumber');
      expect(evt).toHaveProperty('streamId');
      expect(evt).toHaveProperty('timestamp');
      expect(typeof evt.id).toBe('string');
      expect(typeof evt.sequenceNumber).toBe('number');
    });
  });

  describe('SnapshotManager interface', () => {
    it('should expose createSnapshot, getSnapshot, getLatest, diff methods', () => {
      const mgr = new SnapshotManager();
      expect(typeof mgr.createSnapshot).toBe('function');
      expect(typeof mgr.getSnapshot).toBe('function');
      expect(typeof mgr.getLatest).toBe('function');
      expect(typeof mgr.diff).toBe('function');
    });

    it('createSnapshot should return snapshot with id, version, content, createdAt, size', () => {
      const mgr = new SnapshotManager();
      const snap = mgr.createSnapshot('d1', { title: 'Test' });
      expect(snap).toHaveProperty('id');
      expect(snap).toHaveProperty('version');
      expect(snap).toHaveProperty('content');
      expect(snap).toHaveProperty('createdAt');
      expect(snap).toHaveProperty('size');
    });
  });

  describe('BranchMerger interface', () => {
    it('should expose createBranch, appendToBranch, merge methods', () => {
      const merger = new BranchMerger();
      expect(typeof merger.createBranch).toBe('function');
      expect(typeof merger.appendToBranch).toBe('function');
      expect(typeof merger.merge).toBe('function');
      expect(typeof merger.listBranches).toBe('function');
    });

    it('merge should return result with merged, conflicts, branchEvents, mainEvents', () => {
      const merger = new BranchMerger();
      merger.createBranch('f1', 0, 's1');
      const result = merger.merge('f1', []);
      expect(result).toHaveProperty('merged');
      expect(result).toHaveProperty('conflicts');
      expect(typeof result.merged).toBe('boolean');
      expect(Array.isArray(result.conflicts)).toBe(true);
    });
  });
});

describe('Webhooks Service Contract', () => {
  describe('WebhookDeliveryEngine interface', () => {
    it('should expose enqueue, processDeliveries, getDeliveryStatus, getDeliveryHistory methods', () => {
      const engine = new WebhookDeliveryEngine();
      expect(typeof engine.enqueue).toBe('function');
      expect(typeof engine.processDeliveries).toBe('function');
      expect(typeof engine.getDeliveryStatus).toBe('function');
      expect(typeof engine.getDeliveryHistory).toBe('function');
    });

    it('enqueue should return delivery with id, webhookId, event, payload, status, attempts', () => {
      const engine = new WebhookDeliveryEngine();
      const delivery = engine.enqueue('wh-1', 'doc.created', { id: 'd1' });
      expect(delivery).toHaveProperty('id');
      expect(delivery).toHaveProperty('webhookId');
      expect(delivery).toHaveProperty('event');
      expect(delivery).toHaveProperty('payload');
      expect(delivery).toHaveProperty('status');
      expect(delivery).toHaveProperty('attempts');
      expect(delivery.status).toBe('pending');
    });
  });

  describe('SignatureVerifier interface', () => {
    it('should expose sign and verify methods', () => {
      const verifier = new SignatureVerifier();
      expect(typeof verifier.sign).toBe('function');
      expect(typeof verifier.verify).toBe('function');
    });

    it('sign should return object with signature and timestamp', () => {
      const verifier = new SignatureVerifier();
      const result = verifier.sign('payload', 'secret');
      expect(result).toHaveProperty('signature');
      expect(result).toHaveProperty('timestamp');
      expect(typeof result.signature).toBe('string');
      expect(typeof result.timestamp).toBe('number');
    });
  });

  describe('RetryScheduler interface', () => {
    it('should expose calculateNextRetry, scheduleRetry, cancelRetry methods', () => {
      const sched = new RetryScheduler();
      expect(typeof sched.calculateNextRetry).toBe('function');
      expect(typeof sched.scheduleRetry).toBe('function');
      expect(typeof sched.cancelRetry).toBe('function');
    });
  });

  describe('EventFilter interface', () => {
    it('should expose setFilter, matchesFilter, getMatchingWebhooks methods', () => {
      const filter = new EventFilter();
      expect(typeof filter.setFilter).toBe('function');
      expect(typeof filter.matchesFilter).toBe('function');
      expect(typeof filter.getMatchingWebhooks).toBe('function');
    });
  });
});

describe('Billing Service Contract', () => {
  describe('InvoiceCalculator interface', () => {
    it('should expose calculateLineItem, calculateInvoiceTotal, setTaxRate methods', () => {
      const calc = new InvoiceCalculator();
      expect(typeof calc.calculateLineItem).toBe('function');
      expect(typeof calc.calculateInvoiceTotal).toBe('function');
      expect(typeof calc.setTaxRate).toBe('function');
    });

    it('calculateLineItem should return object with description, unitPrice, quantity, total', () => {
      const calc = new InvoiceCalculator();
      const item = calc.calculateLineItem('Plan', 25, 1);
      expect(item).toHaveProperty('description');
      expect(item).toHaveProperty('unitPrice');
      expect(item).toHaveProperty('quantity');
      expect(item).toHaveProperty('total');
    });

    it('calculateInvoiceTotal should return object with subtotal, discount, tax, total', () => {
      const calc = new InvoiceCalculator();
      const items = [calc.calculateLineItem('Plan', 100, 1)];
      const result = calc.calculateInvoiceTotal(items);
      expect(result).toHaveProperty('subtotal');
      expect(result).toHaveProperty('discount');
      expect(result).toHaveProperty('tax');
      expect(result).toHaveProperty('total');
    });
  });

  describe('SubscriptionLifecycle interface', () => {
    it('should expose getState, transition, getHistory, wasRefunded methods', () => {
      const lc = new SubscriptionLifecycle('s1');
      expect(typeof lc.getState).toBe('function');
      expect(typeof lc.transition).toBe('function');
      expect(typeof lc.getHistory).toBe('function');
      expect(typeof lc.wasRefunded).toBe('function');
    });

    it('should start in trial state', () => {
      const lc = new SubscriptionLifecycle('s1');
      expect(lc.getState()).toBe('trial');
    });
  });
});

describe('Analytics Service Contract', () => {
  describe('TimeSeriesAggregator interface', () => {
    it('should expose record, query, getAverage, getPercentile, getRate methods', () => {
      const agg = new TimeSeriesAggregator({ bucketSize: 1000 });
      expect(typeof agg.record).toBe('function');
      expect(typeof agg.query).toBe('function');
      expect(typeof agg.getAverage).toBe('function');
      expect(typeof agg.getPercentile).toBe('function');
      expect(typeof agg.getRate).toBe('function');
    });
  });

  describe('FunnelAnalyzer interface', () => {
    it('should expose defineFunnel, trackEvent, analyzeFunnel methods', () => {
      const funnel = new FunnelAnalyzer();
      expect(typeof funnel.defineFunnel).toBe('function');
      expect(typeof funnel.trackEvent).toBe('function');
      expect(typeof funnel.analyzeFunnel).toBe('function');
    });
  });

  describe('CohortTracker interface', () => {
    it('should expose defineCohort, addToCohort, getRetention, compareCohorts methods', () => {
      const tracker = new CohortTracker();
      expect(typeof tracker.defineCohort).toBe('function');
      expect(typeof tracker.addToCohort).toBe('function');
      expect(typeof tracker.getRetention).toBe('function');
      expect(typeof tracker.compareCohorts).toBe('function');
    });
  });
});

describe('Notification Service Contract', () => {
  describe('NotificationAggregator interface', () => {
    it('should expose buffer, flush, flushAll, addRule methods', () => {
      const agg = new NotificationAggregator();
      expect(typeof agg.buffer).toBe('function');
      expect(typeof agg.flush).toBe('function');
      expect(typeof agg.flushAll).toBe('function');
      expect(typeof agg.addRule).toBe('function');
    });
  });

  describe('DeliveryScheduler interface', () => {
    it('should expose schedule, processNext, processAll, registerHandler methods', () => {
      const sched = new DeliveryScheduler();
      expect(typeof sched.schedule).toBe('function');
      expect(typeof sched.processNext).toBe('function');
      expect(typeof sched.processAll).toBe('function');
      expect(typeof sched.registerHandler).toBe('function');
    });

    it('getStats should return queued, delivered, failed counts', () => {
      const sched = new DeliveryScheduler();
      const stats = sched.getStats();
      expect(stats).toHaveProperty('queued');
      expect(stats).toHaveProperty('delivered');
      expect(stats).toHaveProperty('failed');
    });
  });

  describe('PreferenceEngine interface', () => {
    it('should expose setPreference, getPreference, shouldDeliver, getDeliveryChannels methods', () => {
      const prefs = new PreferenceEngine();
      expect(typeof prefs.setPreference).toBe('function');
      expect(typeof prefs.getPreference).toBe('function');
      expect(typeof prefs.shouldDeliver).toBe('function');
      expect(typeof prefs.getDeliveryChannels).toBe('function');
    });
  });
});

describe('Shared Modules Contract', () => {
  describe('CircuitBreaker interface', () => {
    it('should expose execute, getState, reset methods', () => {
      const cb = new CircuitBreaker({ failureThreshold: 5 });
      expect(typeof cb.execute).toBe('function');
      expect(typeof cb.getState).toBe('function');
      expect(typeof cb.reset).toBe('function');
    });
  });

  describe('EventBus interface', () => {
    it('should expose publish, subscribe methods', () => {
      const bus = new EventBus();
      expect(typeof bus.publish).toBe('function');
      expect(typeof bus.subscribe).toBe('function');
    });
  });

  describe('BaseEvent interface', () => {
    it('should create event with type, data, timestamp, id', () => {
      const evt = new BaseEvent('test.event', { key: 'value' });
      expect(evt).toHaveProperty('type');
      expect(evt).toHaveProperty('data');
      expect(evt).toHaveProperty('timestamp');
      expect(evt).toHaveProperty('id');
    });
  });

  describe('TokenBucketRateLimiter interface', () => {
    it('should expose tryConsume method', () => {
      const limiter = new TokenBucketRateLimiter({ maxTokens: 10, refillRate: 1 });
      expect(typeof limiter.tryConsume).toBe('function');
    });
  });

  describe('BloomFilter interface', () => {
    it('should expose add and mightContain methods', () => {
      const bloom = new BloomFilter({ size: 1000, hashCount: 3 });
      expect(typeof bloom.add).toBe('function');
      expect(typeof bloom.mightContain).toBe('function');
    });
  });

  describe('ConsistentHashRing interface', () => {
    it('should expose addNode, removeNode, getNode methods', () => {
      const ring = new ConsistentHashRing();
      expect(typeof ring.addNode).toBe('function');
      expect(typeof ring.removeNode).toBe('function');
      expect(typeof ring.getNode).toBe('function');
    });
  });

  describe('Error Handler Contract', () => {
    it('should be a function that accepts (err, req, res, next)', () => {
      expect(typeof errorHandler).toBe('function');
      expect(errorHandler.length).toBe(4);
    });
  });
});
