const test = require('node:test');
const assert = require('node:assert/strict');

const { PriorityQueue, RateLimiter } = require('../../src/core/queue');
const { TokenStore, signManifest, verifyManifest } = require('../../src/core/security');
const { CheckpointManager, CircuitBreaker, CB_STATES } = require('../../src/core/resilience');
const { WorkflowEngine } = require('../../src/core/workflow');
const { RollingWindowScheduler } = require('../../src/core/scheduling');
const { ResponseTimeTracker } = require('../../src/core/statistics');
const { NotificationPlanner, shouldThrottle } = require('../../services/notifications/service');

const TOTAL_CASES = 540;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`concurrency-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 9;

    if (bucket === 0) {
      // PriorityQueue: dequeue must return HIGHEST priority (first after sort)
      const pq = new PriorityQueue();
      pq.enqueue({ id: 'low', priority: 1 });
      pq.enqueue({ id: 'high', priority: 100 });
      pq.enqueue({ id: 'med', priority: 50 });
      const first = pq.dequeue();
      assert.equal(first.id, 'high',
        `dequeue must return highest priority item, got '${first.id}' (p=${first.priority})`);
      const second = pq.dequeue();
      assert.equal(second.id, 'med',
        `second dequeue must return next highest, got '${second.id}'`);
    }

    if (bucket === 1) {
      // TokenStore: revokeAllForUser must actually delete ALL tokens
      const store = new TokenStore();
      const userId = `user-${idx}`;
      const tokens = [];
      for (let i = 0; i < 5; i++) {
        tokens.push(store.issue(userId, 'dispatch'));
      }
      store.issue('other-user', 'admin');
      const revokedCount = store.revokeAllForUser(userId);
      assert.equal(revokedCount, 5);
      // ALL of the user's tokens must be gone
      for (const t of tokens) {
        const v = store.validate(t);
        assert.equal(v.valid, false, `token ${tokens.indexOf(t)} should be revoked`);
      }
      assert.equal(store.activeCount(), 1, 'only other-user token should remain');
    }

    if (bucket === 2) {
      // Manifest sign/verify serialization: key order must not matter
      const secret = 'a-very-secure-secret-key-1234';
      const manifest = { zebra: 'z', alpha: 'a', mango: 'm' };
      const sig = signManifest(manifest, secret);
      assert.equal(verifyManifest(manifest, sig, secret), true,
        'verifyManifest must match signManifest for same object');
      // Same logical object, different key insertion order
      const manifest2 = { alpha: 'a', mango: 'm', zebra: 'z' };
      assert.equal(verifyManifest(manifest2, sig, secret), true,
        'verifyManifest must be key-order independent');
    }

    if (bucket === 3) {
      // CheckpointManager: creating with custom interval must not affect other instances
      const cm1 = new CheckpointManager(200);
      cm1.record('s1', 0);
      const cm2 = new CheckpointManager();
      cm2.record('s2', 0);
      // cm2 should use default (1000), not cm1's 200
      assert.equal(cm2.shouldCheckpoint(500), false,
        'cm2 must not be affected by cm1 custom interval');
      assert.equal(cm2.shouldCheckpoint(1000), true,
        'cm2 should checkpoint at default interval 1000');
    }

    if (bucket === 4) {
      // ResponseTimeTracker must record consecutive equal values
      const tracker = new ResponseTimeTracker(100);
      tracker.record(42);
      tracker.record(42);
      tracker.record(42);
      assert.equal(tracker.count(), 3,
        'tracker must record all samples including consecutive duplicates');
      assert.equal(tracker.average(), 42);
    }

    if (bucket === 5) {
      // PriorityQueue with custom comparator: deadline-based scheduling
      const pq = new PriorityQueue((a, b) => a.deadline - b.deadline);
      const items = [];
      for (let i = 0; i < 8; i++) {
        const dl = ((idx + 1) * 17 + i * 41) % 1000;
        items.push({ id: `task-${i}`, deadline: dl });
        pq.enqueue({ id: `task-${i}`, deadline: dl });
      }
      items.sort((a, b) => a.deadline - b.deadline);
      // dequeue must return items in ascending deadline order
      for (let i = 0; i < 8; i++) {
        const out = pq.dequeue();
        assert.equal(out.id, items[i].id,
          `pos ${i}: expected ${items[i].id} (dl=${items[i].deadline}), got ${out.id} (dl=${out.deadline})`);
      }
    }

    if (bucket === 6) {
      // shouldThrottle must enforce limits regardless of severity
      const result = shouldThrottle({ recentCount: 15, maxPerWindow: 10, severity: 7 });
      assert.equal(result, true,
        'severity 7 at 1.5x limit must be throttled — no severity exemptions');
      const result2 = shouldThrottle({ recentCount: 10, maxPerWindow: 10, severity: 5 });
      assert.equal(result2, true,
        'exactly at limit must be throttled regardless of severity');
    }

    if (bucket === 7) {
      // PriorityQueue drain must return items in priority order
      const pq = new PriorityQueue((a, b) => b.priority - a.priority);
      for (let i = 0; i < 8; i++) {
        pq.enqueue({ id: `d-${i}`, priority: (i * 7 + idx) % 20 });
      }
      const drained = pq.drain(3);
      assert.equal(drained.length, 3);
      assert.equal(pq.size(), 5);
      for (let i = 0; i < drained.length - 1; i++) {
        assert.ok(drained[i].priority >= drained[i + 1].priority,
          `drain order broken at ${i}: ${drained[i].priority} < ${drained[i + 1].priority}`);
      }
    }

    if (bucket === 8) {
      // RollingWindowScheduler saturation then purge
      const scheduler = new RollingWindowScheduler(60, 3);
      const ts = Date.now();
      scheduler.schedule('v1', ts);
      scheduler.schedule('v2', ts);
      scheduler.schedule('v3', ts);
      const r4 = scheduler.schedule('v4', ts);
      assert.equal(r4.accepted, false);
      assert.equal(scheduler.utilisation(ts), 1.0);
    }
  });
}
