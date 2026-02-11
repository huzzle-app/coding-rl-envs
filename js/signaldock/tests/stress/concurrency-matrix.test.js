const test = require('node:test');
const assert = require('node:assert/strict');

const { PriorityQueue, RateLimiter } = require('../../src/core/queue');
const { RollingWindowScheduler } = require('../../src/core/scheduling');
const { ResponseTimeTracker } = require('../../src/core/statistics');
const { CircuitBreaker, CB_STATES, CheckpointManager } = require('../../src/core/resilience');

const CASES = 400;

for (let idx = 0; idx < CASES; idx += 1) {
  test(`concurrency-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 7;

    if (variant === 0) {
      // PriorityQueue.drainWhile: should drain ALL matching items
      const queue = new PriorityQueue((a, b) => a.priority - b.priority);
      const n = 6 + (idx % 5);
      const threshold = 3 + (idx % 3);
      for (let i = 0; i < n; i++) {
        queue.enqueue({ id: `item-${i}`, priority: i + 1 });
      }
      const drained = queue.drainWhile(item => item.priority <= threshold);
      assert.equal(drained.length, threshold,
        `should drain ${threshold} items with priority <= ${threshold}, got ${drained.length}`);
      // All drained items should match predicate
      for (const item of drained) {
        assert.ok(item.priority <= threshold,
          `drained item priority ${item.priority} should be <= ${threshold}`);
      }
      // Remaining items should NOT match predicate
      const remaining = queue.toArray();
      for (const item of remaining) {
        assert.ok(item.priority > threshold,
          `remaining item priority ${item.priority} should be > ${threshold}`);
      }
    }

    if (variant === 1) {
      // PriorityQueue.merge: merged queue should maintain sort order
      const queueA = new PriorityQueue((a, b) => b.priority - a.priority);
      const queueB = new PriorityQueue((a, b) => b.priority - a.priority);
      const itemsA = [5, 3, 1].map(p => ({ id: `a-${p}`, priority: p + (idx % 10) }));
      const itemsB = [4, 2].map(p => ({ id: `b-${p}`, priority: p + (idx % 10) }));
      for (const item of itemsA) queueA.enqueue(item);
      for (const item of itemsB) queueB.enqueue(item);
      queueA.merge(queueB);
      // After merge, dequeue should return items in priority order
      let prev = Infinity;
      const total = itemsA.length + itemsB.length;
      for (let i = 0; i < total; i++) {
        const item = queueA.dequeue();
        assert.ok(item !== null, `dequeue ${i} should not be null`);
        assert.ok(item.priority <= prev,
          `dequeue order violated: ${item.priority} > previous ${prev}`);
        prev = item.priority;
      }
    }

    if (variant === 2) {
      // RateLimiter.tryAcquireBurst: failed burst should NOT consume tokens
      const maxTokens = 10;
      const limiter = new RateLimiter(maxTokens, 0);
      // Try to acquire more than available
      const result = limiter.tryAcquireBurst(maxTokens + 5);
      assert.equal(result.acquired, false, 'burst exceeding capacity should fail');
      // Tokens should remain unchanged after failed attempt
      assert.equal(limiter.availableTokens(), maxTokens,
        `after failed burst, tokens should be ${maxTokens}, got ${limiter.availableTokens()}`);
    }

    if (variant === 3) {
      // scheduleMultiple: rejected vessels should NOT leak last accepted position
      const maxPerWindow = 2 + (idx % 3);
      const scheduler = new RollingWindowScheduler(60, maxPerWindow);
      const timestamp = Date.now();
      // Create more vessels than window capacity
      const vesselCount = maxPerWindow + 2 + (idx % 3);
      const vessels = Array.from({ length: vesselCount }, (_, i) => ({
        id: `vessel-${idx}-${i}`,
      }));
      const results = scheduler.scheduleMultiple(vessels, timestamp);
      assert.equal(results.length, vesselCount);
      // Rejected vessels should NOT carry stale position from accepted vessels
      const acceptedPositions = new Set(
        results.filter(r => r.accepted).map(r => r.position)
      );
      for (const r of results) {
        if (!r.accepted) {
          assert.ok(!acceptedPositions.has(r.position),
            `rejected ${r.vesselId} has stale position ${r.position} from an accepted vessel`);
        }
      }
    }

    if (variant === 4) {
      // ResponseTimeTracker.recordBatch: window integrity after multiple batches
      const windowSize = 10;
      const tracker = new ResponseTimeTracker(windowSize);
      // Record initial samples
      for (let i = 0; i < 5; i++) tracker.record(i * 100);
      assert.equal(tracker.count(), 5);
      // Record a batch that exceeds window
      const largeBatch = Array.from({ length: 15 }, (_, i) => (i + 1) * 50);
      tracker.recordBatch(largeBatch);
      assert.ok(tracker.count() <= windowSize,
        `after recordBatch, count ${tracker.count()} should be <= window ${windowSize}`);
    }

    if (variant === 5) {
      // CheckpointManager: concurrent merge from multiple sources
      const base = new CheckpointManager();
      const source1 = new CheckpointManager();
      const source2 = new CheckpointManager();
      base.record('stream-a', 10);
      base.record('stream-b', 20);
      source1.record('stream-a', 30 + (idx % 20));
      source1.record('stream-c', 50);
      source2.record('stream-a', 20 + (idx % 20));
      source2.record('stream-b', 40 + (idx % 10));
      // Merge both sources
      base.merge(source1);
      base.merge(source2);
      // stream-a should be max(10, 30+idx%20, 20+idx%20) = 30+idx%20
      const expectedA = Math.max(10, 30 + (idx % 20), 20 + (idx % 20));
      assert.equal(base.getCheckpoint('stream-a'), expectedA,
        `stream-a should be ${expectedA}, got ${base.getCheckpoint('stream-a')}`);
      // stream-b should be max(20, 40+idx%10) = 40+idx%10
      const expectedB = Math.max(20, 40 + (idx % 10));
      assert.equal(base.getCheckpoint('stream-b'), expectedB,
        `stream-b should be ${expectedB}`);
    }

    if (variant === 6) {
      // PriorityQueue drainWhile then enqueue: queue should still work
      const queue = new PriorityQueue((a, b) => a.priority - b.priority);
      for (let i = 0; i < 8; i++) {
        queue.enqueue({ id: `item-${i}`, priority: (i * 7 + idx) % 20 });
      }
      const before = queue.toArray().length;
      queue.drainWhile(item => item.priority < 5);
      // Add more items after drain
      queue.enqueue({ id: 'new-1', priority: 1 });
      queue.enqueue({ id: 'new-2', priority: 15 });
      // Queue should still maintain ordering
      const items = queue.toArray();
      for (let i = 1; i < items.length; i++) {
        assert.ok(items[i - 1].priority <= items[i].priority,
          `queue order broken after drain+enqueue: [${i-1}]=${items[i-1].priority} > [${i}]=${items[i].priority}`);
      }
    }
  });
}
