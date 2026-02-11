const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const { planWindow, planWindowWithConflicts, BerthSlot, RollingWindowScheduler, BERTH_STATES, estimateTurnaround } = require('../../src/core/scheduling');
const { chooseRoute, planMultiLeg, RouteTable, estimateRouteCost, channelScore, compareRoutes } = require('../../src/core/routing');
const { PolicyEngine, checkSlaCompliance, nextPolicy, previousPolicy, shouldDeescalate, ORDER, POLICY_METADATA } = require('../../src/core/policy');
const { shouldShed, PriorityQueue, RateLimiter, queueHealth, estimateWaitTime, DEFAULT_HARD_LIMIT } = require('../../src/core/queue');
const { replay, deduplicate, replayConverges, CheckpointManager, CircuitBreaker, CB_STATES } = require('../../src/core/resilience');
const { percentile, mean, variance, stddev, median, movingAverage, generateHeatmap, ResponseTimeTracker } = require('../../src/core/statistics');
const { canTransition, WorkflowEngine, shortestPath, allowedTransitions, isValidState, GRAPH, TERMINAL_STATES } = require('../../src/core/workflow');
const { DispatchTicket, VesselManifest, Severity, SLA_BY_SEVERITY, createBatchTickets } = require('../../src/models/dispatch-ticket');
const { digest, signManifest, verifyManifest, verifySignature, TokenStore, sanitisePath, isAllowedOrigin } = require('../../src/core/security');

const TOTAL_CASES = 360;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`latent-multistep-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 9;

    if (bucket === 0) {
      // Latent: PriorityQueue dequeue returns wrong end when items are sorted
      // Only detectable by comparing peek() vs dequeue() or checking order
      const pq = new PriorityQueue((a, b) => a.deadline - b.deadline);
      pq.enqueue({ id: 'late', deadline: 999 });
      pq.enqueue({ id: 'early', deadline: 1 });
      pq.enqueue({ id: 'mid', deadline: 500 });
      const peeked = pq.peek();
      const dequeued = pq.dequeue();
      assert.equal(peeked.id, dequeued.id,
        `peek and dequeue must return same item: peek=${peeked.id} dequeue=${dequeued.id}`);
      assert.equal(dequeued.id, 'early',
        'earliest deadline must be dequeued first');
    }

    if (bucket === 1) {
      // Multi-step masking pair test:
      // Bug A: evaluate() resets _consecutiveSuccesses on stable path
      // Bug B: shouldDeescalate uses > instead of >= (needs 11, not 10)
      // Must fix BOTH for this to pass
      const pe = new PolicyEngine();
      pe._lastEscalation = 0;
      pe.evaluate(5); // escalate to watch
      assert.equal(pe.current, 'watch');
      // Accumulate exactly 10 successes with interleaved stable evaluates
      for (let i = 0; i < 5; i++) pe.recordSuccess();
      pe.evaluate(0); // stable — must NOT reset counter
      for (let i = 0; i < 5; i++) pe.recordSuccess();
      // At this point we've recorded 10 total successes
      assert.equal(pe.current, 'normal',
        'deescalation requires fixing both: evaluate stable reset AND shouldDeescalate >= threshold');
    }

    if (bucket === 2) {
      // Latent: replay keeps latest (highest) sequence per ID for disaster recovery
      const events = [
        { id: 'sensor-A', sequence: 5 },
        { id: 'sensor-A', sequence: 10 },
        { id: 'sensor-A', sequence: 3 },
        { id: 'sensor-B', sequence: 1 },
      ];
      const result = replay(events);
      const sensorA = result.find(e => e.id === 'sensor-A');
      assert.equal(sensorA.sequence, 10,
        `disaster recovery requires latest state (seq=10), got ${sensorA.sequence}`);
    }

    if (bucket === 3) {
      // Multi-step: berth lifecycle with domain constraints
      const berth = new BerthSlot('B1', 15, 200);
      assert.ok(berth.canAccept({ draft: 14, length: 180 }));
      berth.reserve('vessel-1', 2);
      assert.equal(berth.state, BERTH_STATES.RESERVED);
      assert.ok(!berth.canAccept({ draft: 10, length: 100 }));
      berth.reservedUntil = Date.now() - 1000;
      assert.ok(berth.isExpiredReservation());
      berth.release();
      assert.equal(berth.state, BERTH_STATES.AVAILABLE);
      assert.ok(berth.canAccept({ draft: 10, length: 100 }));
    }

    if (bucket === 4) {
      // Latent: TokenStore revokeAllForUser must delete ALL tokens
      // Bug only shows with multiple tokens (odd-indexed tokens survive)
      const store = new TokenStore();
      const tokens = [];
      for (let i = 0; i < 4; i++) {
        tokens.push(store.issue('alice', 'dispatch', 60000));
      }
      store.issue('bob', 'admin', 60000);
      store.revokeAllForUser('alice');
      // Token at index 1 and 3 (odd) would survive the even-index-only delete bug
      for (const t of tokens) {
        assert.equal(store.validate(t).valid, false,
          'ALL of alice tokens must be revoked');
      }
      assert.equal(store.activeCount(), 1, 'only bob token should remain');
    }

    if (bucket === 5) {
      // Domain: SLA compliance cascade — rate computation must be correct
      const dispatches = [];
      for (let i = 0; i < 20; i++) {
        dispatches.push({ elapsed: i < 19 ? 3 : 100 });
      }
      const result = checkSlaCompliance('normal', dispatches, 10);
      assert.equal(result.violationCount, 1);
      assert.ok(result.complianceRate >= 0.95);
      assert.equal(result.compliant, true);
    }

    if (bucket === 6) {
      // Latent: ResponseTimeTracker must not deduplicate consecutive equal samples
      // In real systems, many requests may have identical response times
      const tracker = new ResponseTimeTracker(100);
      const values = [100, 100, 100, 200, 200, 200, 300];
      for (const v of values) tracker.record(v);
      assert.equal(tracker.count(), 7,
        `all 7 samples must be recorded, got ${tracker.count()}`);
      // p50 of [100,100,100,200,200,200,300] should be 200
      const p = tracker.p50();
      assert.equal(p, 200, `p50 with all samples = 200, got ${p}`);
    }

    if (bucket === 7) {
      // Multi-step: circuit breaker recovery then fresh failure counting
      const cb = new CircuitBreaker(3, 100);
      cb.recordFailure();
      cb.recordFailure();
      cb.recordFailure();
      assert.equal(cb.state, CB_STATES.OPEN);
      cb._lastFailureAt = Date.now() - 200;
      assert.equal(cb.state, CB_STATES.HALF_OPEN);
      cb.recordSuccess();
      cb.recordSuccess();
      cb.recordSuccess();
      assert.equal(cb.state, CB_STATES.CLOSED);
      // After recovery, failure count should be fresh
      // A single failure should NOT re-open the breaker
      cb.recordFailure();
      assert.equal(cb.state, CB_STATES.CLOSED,
        'single failure after recovery must stay closed');
      assert.equal(cb._failures, 1);
    }

    if (bucket === 8) {
      // Latent: sign then verify with non-alphabetical keys
      // Only fails if verifyManifest uses different serialization than signManifest
      const secret = 'test-secret-key-16char';
      const manifests = [
        { zulu: 1, alpha: 2, mike: 3 },
        { b: 'x', a: 'y', c: 'z' },
        { port: 'east', vessel: 'MV-1', cargo: 'grain' },
      ];
      for (const m of manifests) {
        const sig = signManifest(m, secret);
        assert.equal(verifyManifest(m, sig, secret), true,
          `sign/verify roundtrip failed for keys: ${Object.keys(m).join(',')}`);
      }
    }
  });
}
