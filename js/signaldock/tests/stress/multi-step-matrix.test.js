const test = require('node:test');
const assert = require('node:assert/strict');

const { replayWithWindowing, replay, CheckpointManager, CircuitBreaker, CB_STATES } = require('../../src/core/resilience');
const { PolicyEngine } = require('../../src/core/policy');
const { WorkflowEngine } = require('../../src/core/workflow');
const { verifyManifestChain, signManifest } = require('../../src/core/security');
const { planMultiLegWithCost, estimateRouteCost } = require('../../src/core/routing');
const { correlate } = require('../../src/core/statistics');

const CASES = 400;
const SECRET = 'signaldock-secret-key-for-tests';

for (let idx = 0; idx < CASES; idx += 1) {
  test(`multistep-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 7;

    if (variant === 0) {
      // replayWithWindowing must deduplicate across windows
      const baseId = `evt-${idx % 30}`;
      const events = [
        { id: baseId, sequence: 1 },
        { id: `other-${idx}`, sequence: 5 },
        { id: baseId, sequence: 3 + (idx % 10) },
      ];
      const windowed = replayWithWindowing(events, 2);
      const fullReplay = replay(events);
      assert.equal(windowed.length, fullReplay.length,
        `windowed replay (${windowed.length}) should match full replay (${fullReplay.length})`);
    }

    if (variant === 1) {
      // PolicyEngine.evaluateWithHistory: rapid escalation detection
      const engine = new PolicyEngine();
      engine._lastEscalation = 0;
      const now = Date.now();
      engine._history = [
        { from: 'normal', to: 'watch', at: now - 1000, failureBurst: 3 },
        { from: 'watch', to: 'restricted', at: now - 500, failureBurst: 5 },
        { from: 'restricted', to: 'halted', at: now - 100, failureBurst: 8 },
      ];
      engine._currentPolicy = 'restricted';
      engine._lastEscalation = now - 400000;
      const result = engine.evaluateWithHistory(2, 10);
      assert.equal(result.reason, 'rapid_escalation',
        `expected rapid_escalation with 3 recent escalations, got ${result.reason}`);
    }

    if (variant === 2) {
      // batchTransitionSequential: must fail-fast on invalid transition
      const engine = new WorkflowEngine();
      const entityId = `ship-${idx}`;
      engine.register(entityId, 'queued');
      // 'departed' is invalid from 'queued', but 'allocated' is valid from 'queued'
      // A fail-fast batch should stop after the first invalid transition
      const results = engine.batchTransitionSequential([entityId], ['departed', 'allocated']);
      assert.equal(results[0].success, false, 'queued->departed should fail');
      assert.equal(engine.getState(entityId), 'queued',
        `entity should stay at 'queued' after failed batch, got '${engine.getState(entityId)}'`);
    }

    if (variant === 3) {
      // verifyManifestChain: chain must propagate hashes between links
      const data = [
        { id: 0, data: `cargo-${idx}-alpha` },
        { id: 1, data: `cargo-${idx}-beta` },
        { id: 2, data: `cargo-${idx}-gamma` },
      ];
      let previousHash = '';
      const chain = data.map((d, i) => {
        const payload = previousHash + d.data;
        const sig = signManifest(payload, SECRET);
        previousHash = sig;
        return { id: i, data: d.data, signature: sig };
      });
      const result = verifyManifestChain(chain, SECRET);
      assert.equal(result.valid, true,
        `valid chain should verify, failed at index ${result.failedAt}`);
      assert.equal(result.chainLength, 3);
    }

    if (variant === 4) {
      // correlate depends on mean which divides by n+1 instead of n
      const x = [1, 3, 5].map(v => v + (idx % 10));
      const y = [2, 1, 4].map(v => v + (idx % 5));
      const r = correlate(x, y);
      // Compute correct correlation manually
      const n = x.length;
      const mx = x.reduce((s, v) => s + v, 0) / n;
      const my = y.reduce((s, v) => s + v, 0) / n;
      let sxy = 0, sx2 = 0, sy2 = 0;
      for (let i = 0; i < n; i++) {
        sxy += (x[i] - mx) * (y[i] - my);
        sx2 += (x[i] - mx) ** 2;
        sy2 += (y[i] - my) ** 2;
      }
      const expected = sxy / Math.sqrt(sx2 * sy2);
      assert.ok(Math.abs(r - expected) < 0.01,
        `correlate should be ~${expected.toFixed(3)}, got ${r.toFixed(3)}`);
    }

    if (variant === 5) {
      // planMultiLegWithCost uses input option[0] latency instead of selected
      const legs = [
        { legId: 'L1', options: [
          { channel: 'slow', latency: 100 },
          { channel: 'fast', latency: 2 + (idx % 5) },
        ]},
      ];
      const baseCost = 50;
      const result = planMultiLegWithCost(legs, [], baseCost);
      assert.ok(result.success);
      const selectedLatency = result.legs[0].latency;
      const expectedCost = estimateRouteCost({ latency: selectedLatency }, baseCost);
      assert.equal(result.totalCost, expectedCost,
        `cost should use selected latency ${selectedLatency}, not option[0] latency 100`);
    }

    if (variant === 6) {
      // Multi-step: CheckpointManager merge then snapshot
      const mgr1 = new CheckpointManager();
      const mgr2 = new CheckpointManager();
      mgr1.record('s1', 10 + idx);
      mgr1.record('s2', 20);
      mgr2.record('s1', 50 + idx);
      mgr2.record('s3', 30);
      mgr1.merge(mgr2);
      const delta = mgr1.snapshotDelta(40 + idx);
      assert.equal(typeof delta, 'object', 'delta should be object');
      if (typeof delta === 'object' && delta !== null) {
        assert.ok('s1' in delta, `s1 with seq ${50+idx} should be in delta`);
        assert.equal(delta['s1'], 50 + idx);
      }
    }
  });
}
