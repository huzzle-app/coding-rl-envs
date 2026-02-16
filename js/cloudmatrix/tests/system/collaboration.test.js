/**
 * System Collaboration Tests
 *
 * Tests full collaboration flows using actual source code classes.
 * Exercises observability bugs M1-M5 and cross-module integration behavior.
 */

const { CRDTDocument, OperationalTransform, WebSocketManager, DocumentLifecycle, ConnectionPool, CursorTransformEngine } = require('../../shared/realtime');
const { BaseEvent, EventBus, SagaOrchestrator, EventStore } = require('../../shared/events');
const { TraceContext, CorrelationContext, MetricsCollector, StructuredLogger } = require('../../shared/utils');
const { CircuitBreaker, HealthChecker, BulkheadIsolation } = require('../../shared/clients');

describe('Collaboration System Flow', () => {
  describe('CRDT Document Operations', () => {
    it('should apply insert operations', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state.text = '';
      doc.applyOperation({ type: 'insert', position: 0, content: 'Hello' });
      expect(doc.state.text).toBe('Hello');
    });

    it('should merge remote state with local', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { title: 'Local Title' };
      doc.clock = { title: 5 };

      const remoteState = { title: 'Remote Title', body: 'Content' };
      const remoteClock = { title: 10, body: 3 };

      const merged = doc.merge(remoteState, remoteClock);
      expect(merged.title).toBe('Remote Title'); // Remote has higher clock
      expect(merged.body).toBe('Content');
    });

    // BUG: CRDT merge uses <= comparison (remoteTime <= localTime → skip)
    // When timestamps are equal, both sides think they win, leading to divergence
    it('should handle equal timestamps deterministically', () => {
      const doc1 = new CRDTDocument('doc-1');
      doc1.state = { field: 'A' };
      doc1.clock = { field: 5 };

      const doc2 = new CRDTDocument('doc-1');
      doc2.state = { field: 'B' };
      doc2.clock = { field: 5 };

      // Both merge with equal timestamps - should produce same result
      doc1.merge({ field: 'B' }, { field: 5 });
      doc2.merge({ field: 'A' }, { field: 5 });

      // BUG: Both skip the remote update due to <= comparison
      // so doc1 keeps 'A' and doc2 keeps 'B' - divergence!
      expect(doc1.state.field).toBe(doc2.state.field);
    });
  });

  describe('Document Lifecycle Flow', () => {
    it('should complete full lifecycle draft -> review -> approved -> published', () => {
      const lc = new DocumentLifecycle('doc-1');
      expect(lc.getState()).toBe('draft');

      lc.transition('review', 'author-1');
      lc.transition('approved', 'reviewer-1');
      lc.transition('published', 'author-1');

      expect(lc.getState()).toBe('published');
      expect(lc.getHistory()).toHaveLength(3);
    });

    it('should reject invalid transitions', () => {
      const lc = new DocumentLifecycle('doc-1');
      expect(() => lc.transition('published', 'u1')).toThrow();
    });
  });

  describe('Connection Pool Flow', () => {
    it('should manage connection lifecycle', async () => {
      const pool = new ConnectionPool(2);
      const conn1 = await pool.acquire();
      const conn2 = await pool.acquire();

      expect(pool.getStats().active).toBe(2);

      pool.release(conn1);
      pool.release(conn2);

      expect(pool.getStats().active).toBe(0);
    });
  });
});

describe('Event System Flow', () => {
  describe('EventBus pub/sub', () => {
    it('should deliver events to subscribers', async () => {
      const bus = new EventBus();
      const received = [];

      await bus.subscribe('doc.created', (event) => {
        received.push(event);
      });

      await bus.publish(new BaseEvent('doc.created', { docId: 'doc-1' }));

      expect(received).toHaveLength(1);
      expect(received[0].data.docId).toBe('doc-1');
    });

    it('should support wildcard subscriptions', async () => {
      const bus = new EventBus();
      const received = [];

      await bus.subscribe('doc.*', (event) => {
        received.push(event);
      });

      await bus.publish(new BaseEvent('doc.created', {}));
      await bus.publish(new BaseEvent('doc.updated', {}));
      await bus.publish(new BaseEvent('user.created', {}));

      expect(received).toHaveLength(2);
    });
  });

  describe('BaseEvent', () => {
    it('should generate unique event ids', () => {
      const e1 = new BaseEvent('test', {});
      const e2 = new BaseEvent('test', {});
      expect(e1.id).not.toBe(e2.id);
    });

    // BUG: BaseEvent stores timestamp in metadata.timestamp, not as top-level property.
    // Consumers expect evt.timestamp but must use evt.metadata.timestamp instead.
    it('should include timestamp as top-level property', () => {
      const evt = new BaseEvent('test', { key: 'val' });
      expect(evt.timestamp).toBeDefined();
      expect(typeof evt.timestamp).toBe('number');
    });

    // BUG: BaseEvent generates idempotency key using only type + first key
    // This causes collisions for events of the same type with same first key
    it('should generate unique idempotency keys for different data', () => {
      const e1 = new BaseEvent('doc.updated', { docId: 'doc-1', field: 'title' });
      const e2 = new BaseEvent('doc.updated', { docId: 'doc-1', field: 'body' });
      expect(e1.idempotencyKey).not.toBe(e2.idempotencyKey);
    });
  });
});

describe('Observability', () => {
  describe('TraceContext', () => {
    it('should create trace context with traceId and spanId', () => {
      const trace = new TraceContext();
      expect(trace.traceId).toBeDefined();
      expect(trace.spanId).toBeDefined();
    });

    it('should create child spans preserving traceId', () => {
      const parent = new TraceContext();
      const child = parent.createChildSpan('child-op');
      expect(child.traceId).toBe(parent.traceId);
      expect(child.parentSpanId).toBe(parent.spanId);
    });

    // BUG: TraceContext is lost when crossing WebSocket boundaries
    // because the trace is not serialized/deserialized with WS messages
    it('should serialize trace context for cross-boundary propagation', () => {
      const trace = new TraceContext();
      const serialized = trace.serialize();
      expect(serialized).toBeDefined();
      expect(typeof serialized).toBe('string');

      const restored = TraceContext.deserialize(serialized);
      expect(restored.traceId).toBe(trace.traceId);
    });
  });

  describe('CorrelationContext', () => {
    it('should store and retrieve correlation id per request', () => {
      const ctx = new CorrelationContext();
      ctx.set('req-1', 'corr-aaa');
      ctx.set('req-2', 'corr-bbb');

      expect(ctx.get('req-1')).toBe('corr-aaa');
      expect(ctx.get('req-2')).toBe('corr-bbb');
    });

    // BUG: CorrelationContext uses global state
    // Concurrent requests can overwrite each other's correlation IDs
    it('should not have concurrent requests interfere with each other', () => {
      const ctx = new CorrelationContext();
      ctx.set('req-1', 'corr-A');
      ctx.set('req-2', 'corr-B');

      // req-1's correlation should still be A, not overwritten by req-2
      expect(ctx.get('req-1')).toBe('corr-A');
      expect(ctx.get('req-2')).toBe('corr-B');
    });
  });

  describe('MetricsCollector', () => {
    it('should record metrics with labels', () => {
      const collector = new MetricsCollector();
      collector.increment('http_requests', { method: 'GET', status: '200' });
      collector.increment('http_requests', { method: 'GET', status: '200' });

      const value = collector.get('http_requests', { method: 'GET', status: '200' });
      expect(value).toBe(2);
    });

    // BUG: MetricsCollector allows high-cardinality labels (like docId)
    // which causes cardinality explosion in production
    it('should reject high-cardinality labels', () => {
      const collector = new MetricsCollector();
      // Recording with docId as a label should be rejected or sanitized
      // to prevent unbounded cardinality
      for (let i = 0; i < 1000; i++) {
        collector.increment('doc_views', { docId: `doc-${i}` });
      }

      const keys = collector.getMetricNames();
      // If the collector allowed all labels, there would be 1000 unique metric series
      // A proper implementation would either reject or limit high-cardinality labels
      expect(keys.length).toBeLessThan(100);
    });
  });

  describe('StructuredLogger', () => {
    it('should create structured log entries', () => {
      const logger = new StructuredLogger('gateway');
      const entry = logger.info('Request received', { path: '/api/docs' });
      expect(entry.service).toBe('gateway');
      expect(entry.level).toBe('info');
      expect(entry.message).toBe('Request received');
    });

    // BUG: StructuredLogger uses spread to merge metadata
    // If metadata contains 'message' or 'level', it overwrites the log fields
    it('should not allow metadata to overwrite core log fields', () => {
      const logger = new StructuredLogger('test-service');
      const entry = logger.info('Original message', { message: 'Injected', level: 'error' });
      // Core fields should be preserved
      expect(entry.message).toBe('Original message');
      expect(entry.level).toBe('info');
    });
  });

  describe('Health Check Flow', () => {
    it('should create health checker', () => {
      const checker = new HealthChecker();
      expect(typeof checker.addCheck).toBe('function');
      expect(typeof checker.runChecks).toBe('function');
    });

    it('should report unhealthy when checks fail', async () => {
      const checker = new HealthChecker();
      checker.addCheck('db', async () => { throw new Error('Connection refused'); });

      const results = await checker.runChecks();
      expect(results.healthy).toBe(false);
    });
  });
});

describe('Circuit Breaker Integration', () => {
  it('should open circuit after failures', async () => {
    const cb = new CircuitBreaker({ failureThreshold: 3, resetTimeout: 1000 });
    const failingFn = async () => { throw new Error('Service down'); };

    // Trip the circuit
    for (let i = 0; i < 3; i++) {
      try { await cb.execute(failingFn); } catch (e) {}
    }

    expect(cb.getState()).toBe('open');
  });

  it('should allow requests in closed state', async () => {
    const cb = new CircuitBreaker({ failureThreshold: 5 });
    const result = await cb.execute(async () => 'success');
    expect(result).toBe('success');
    expect(cb.getState()).toBe('closed');
  });
});

describe('Bulkhead Isolation', () => {
  it('should limit concurrent executions', async () => {
    const bulkhead = new BulkheadIsolation(2);

    const slow = () => new Promise(resolve => setTimeout(() => resolve('done'), 50));
    const results = await Promise.all([
      bulkhead.execute(slow),
      bulkhead.execute(slow),
    ]);

    expect(results).toEqual(['done', 'done']);
  });

  // BUG: BulkheadIsolation increments running BEFORE checking the limit
  // This causes the running count to be inflated, so _processQueue sees
  // running >= maxConcurrent even when no tasks are executing, and queued
  // tasks never get processed.
  it('should enforce strict concurrency limit', async () => {
    const bulkhead = new BulkheadIsolation(2);

    let concurrent = 0;
    let maxObservedConcurrent = 0;

    const task = () => new Promise(resolve => {
      concurrent++;
      maxObservedConcurrent = Math.max(maxObservedConcurrent, concurrent);
      setTimeout(() => {
        concurrent--;
        resolve('done');
      }, 30);
    });

    // With maxConcurrent=2, execute 3 tasks.
    // The first 2 should run immediately, the 3rd should queue and run after one finishes.
    // Add a timeout to prevent hang if queue processing is broken.
    const timeout = new Promise((_, rej) =>
      setTimeout(() => rej(new Error('Bulkhead queue processing hung')), 500)
    );

    const results = await Promise.race([
      Promise.all([
        bulkhead.execute(task),
        bulkhead.execute(task),
        bulkhead.execute(task),
      ]),
      timeout,
    ]);

    expect(results).toEqual(['done', 'done', 'done']);
    // BUG: running++ before check inflates running count, so _processQueue
    // never processes queued tasks → the 3rd task hangs forever
    expect(maxObservedConcurrent).toBeLessThanOrEqual(2);
  });
});

describe('Multi-Service Integration', () => {
  describe('Event-Driven Document Flow', () => {
    it('should propagate events across bus with correct typing', async () => {
      const bus = new EventBus();
      const events = [];

      await bus.subscribe('*', (evt) => events.push(evt));

      await bus.publish(new BaseEvent('document.created', { docId: 'd1' }));
      await bus.publish(new BaseEvent('document.shared', { docId: 'd1', userId: 'u2' }));
      await bus.publish(new BaseEvent('notification.sent', { userId: 'u2' }));

      expect(events).toHaveLength(3);
      expect(events[0].type).toBe('document.created');
      expect(events[2].type).toBe('notification.sent');
    });
  });

  describe('Lifecycle State Machine Integration', () => {
    it('should track document through lifecycle with events', async () => {
      const lc = new DocumentLifecycle('doc-1');
      const bus = new EventBus();
      const events = [];

      await bus.subscribe('lifecycle.*', (evt) => events.push(evt));

      lc.transition('review', 'author-1');
      await bus.publish(new BaseEvent('lifecycle.review', { docId: 'doc-1' }));

      lc.transition('approved', 'reviewer-1');
      await bus.publish(new BaseEvent('lifecycle.approved', { docId: 'doc-1' }));

      expect(lc.getState()).toBe('approved');
      expect(events).toHaveLength(2);
    });
  });
});
