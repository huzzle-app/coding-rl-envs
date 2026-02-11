const test = require('node:test');
const assert = require('node:assert/strict');

const { BerthSlot, RollingWindowScheduler, BERTH_STATES } = require('../../src/core/scheduling');
const { CheckpointManager, CircuitBreaker, CB_STATES } = require('../../src/core/resilience');
const { computeAccessLevel, TokenStore } = require('../../src/core/security');
const { ResponseTimeTracker } = require('../../src/core/statistics');
const { adaptiveThreshold, PriorityQueue } = require('../../src/core/queue');
const { DispatchTicket, VesselManifest } = require('../../src/models/dispatch-ticket');

const CASES = 500;

for (let idx = 0; idx < CASES; idx += 1) {
  test(`latent-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 8;

    if (variant === 0) {
      // Reference mutation: canAcceptWithTide must not mutate vessel.draft
      const berthDraft = 18 + (idx % 4);
      const tideLevel = 2;
      const vesselDraft = 14 + (idx % 3);
      const berth = new BerthSlot(`B-${idx}`, berthDraft, 200);
      const vessel = { draft: vesselDraft, length: 150 };
      const originalDraft = vessel.draft;
      berth.canAcceptWithTide(vessel, tideLevel);
      assert.equal(vessel.draft, originalDraft,
        `vessel.draft mutated from ${originalDraft} to ${vessel.draft} after canAcceptWithTide`);
    }

    if (variant === 1) {
      // Reference mutation: calling canAcceptWithTide twice must give same result
      const berth = new BerthSlot(`B2-${idx}`, 20, 200);
      const vessel = { draft: 16, length: 150 };
      const result1 = berth.canAcceptWithTide(vessel, 2);
      const result2 = berth.canAcceptWithTide(vessel, 2);
      assert.equal(result1, result2,
        `canAcceptWithTide called twice on same inputs should give same result`);
    }

    if (variant === 2) {
      // CheckpointManager merge should keep maximum sequence per stream
      const mgr1 = new CheckpointManager();
      const mgr2 = new CheckpointManager();
      const streamA = `stream-${idx % 20}`;
      const seqA1 = 10 + (idx % 50);
      const seqA2 = seqA1 + 5 + (idx % 30);
      mgr1.record(streamA, seqA1);
      mgr1.record('streamB', 100);
      mgr2.record(streamA, seqA2);
      mgr2.record('streamB', 50);
      mgr1.merge(mgr2);
      assert.equal(mgr1.getCheckpoint(streamA), seqA2,
        `merge should keep max: expected ${seqA2} for ${streamA}`);
      assert.equal(mgr1.getCheckpoint('streamB'), 100,
        'merge should keep max(100, 50) = 100 for streamB');
    }

    if (variant === 3) {
      // snapshotDelta should return empty object, not falsy, when no deltas exist
      const mgr = new CheckpointManager();
      mgr.record('s1', 5);
      mgr.record('s2', 10);
      const delta = mgr.snapshotDelta(100);
      assert.equal(typeof delta, 'object',
        'snapshotDelta should return object for empty delta, not number');
      if (typeof delta === 'object' && delta !== null) {
        assert.equal(Object.keys(delta).length, 0);
      }
    }

    if (variant === 4) {
      // computeAccessLevel: exact-match only, no substring
      const scopes = ['readonly', 'write', `scope-${idx % 5}`];
      const required = 'read';
      const result = computeAccessLevel(scopes, required);
      assert.equal(result, 'denied',
        `'read' should not match 'readonly' via substring: got ${result}`);
    }

    if (variant === 5) {
      // adaptiveThreshold: ratio treated as 0-1 fraction, not percentage
      const depth = 80 + (idx % 20);
      const hardLimit = 100;
      const shedRate = 0.3 + (idx % 5) * 0.1;
      const result = adaptiveThreshold(depth, hardLimit, shedRate);
      const expectedThreshold = hardLimit * (1 - shedRate);
      assert.ok(Math.abs(result.threshold - expectedThreshold) < 0.01,
        `threshold should be ~${expectedThreshold.toFixed(1)} (limit*(1-rate)), got ${result.threshold.toFixed(1)}`);
    }

    if (variant === 6) {
      // ResponseTimeTracker.recordBatch should not exceed window size
      const windowSize = 5 + (idx % 10);
      const tracker = new ResponseTimeTracker(windowSize);
      const batchSize = windowSize + 2 + (idx % 5);
      const batch = Array.from({ length: batchSize }, (_, i) => i * 10 + idx);
      tracker.recordBatch(batch);
      assert.ok(tracker.count() <= windowSize,
        `after recordBatch(${batchSize}), count ${tracker.count()} should be <= window ${windowSize}`);
    }

    if (variant === 7) {
      // VesselManifest draftClearance must use actual draft, not tonnage estimate
      const berthDraft = 18;
      const tideLevel = 2;
      const vessel = new VesselManifest(`V-${idx}`, 'bulk', 50000);
      vessel.draft = 15;
      const result = vessel.draftClearance(berthDraft, tideLevel);
      const expected = berthDraft + tideLevel - vessel.draft;
      assert.equal(result.clearance, expected,
        `clearance should use actual draft: ${expected}, got ${result.clearance}`);
    }
  });
}
