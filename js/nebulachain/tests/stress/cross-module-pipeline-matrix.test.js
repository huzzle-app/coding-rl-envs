const test = require('node:test');
const assert = require('node:assert/strict');

const { allocateOptimalBerth, planWindow, BerthSlot } = require('../../src/core/scheduling');
const { replayAndAnalyze, percentile, mean } = require('../../src/core/statistics');
const { chooseRoute } = require('../../src/core/routing');
const { replay } = require('../../src/core/resilience');
const { canTransition } = require('../../src/core/workflow');
const { nextPolicy, shouldDeescalate } = require('../../src/core/policy');
const { shouldShed } = require('../../src/core/queue');

const TOTAL_CASES = 320;
const BUCKET_SIZE = 40;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  const bucket = Math.floor(idx / BUCKET_SIZE);

  test(`cross-module-pipeline-${String(idx).padStart(5, '0')}`, () => {
    // -------------------------------------------------------------------
    // Bucket 0: allocateOptimalBerth — single vessel, route must be lowest latency
    // Red-herring: bug manifests in scheduling but root cause is in routing.js
    // -------------------------------------------------------------------
    if (bucket === 0) {
      const vessels = [{ id: `v-${idx}`, draft: 8, length: 150, tonnage: 5000 }];
      const routeOptions = [
        { channel: 'express', latency: 2 + (idx % 5) },
        { channel: 'standard', latency: 8 + (idx % 3) },
        { channel: 'economy', latency: 15 + (idx % 4) },
      ];
      const berths = [new BerthSlot(`B-${idx}`, 15, 200)];
      const result = allocateOptimalBerth(vessels, routeOptions, berths, []);
      assert.ok(result[0].allocated, 'vessel must be allocated');
      const minLatency = Math.min(...routeOptions.map(r => r.latency));
      assert.equal(result[0].routeLatency, minLatency,
        `berth allocation must use lowest-latency route (${minLatency}), got ${result[0].routeLatency}`);
    }

    // -------------------------------------------------------------------
    // Bucket 1: allocateOptimalBerth — with blocked routes
    // -------------------------------------------------------------------
    else if (bucket === 1) {
      const vessels = [{ id: `v-${idx}`, draft: 10, length: 180, tonnage: 8000 }];
      const blocked = idx % 3 === 0 ? ['express'] : [];
      const routeOptions = [
        { channel: 'express', latency: 1 },
        { channel: 'coastal', latency: 3 + (idx % 6) },
        { channel: 'deep-sea', latency: 7 + (idx % 3) },
      ];
      const berths = [new BerthSlot(`B-${idx}`, 15, 250)];
      const result = allocateOptimalBerth(vessels, routeOptions, berths, blocked);
      assert.ok(result[0].allocated);
      if (blocked.length > 0) {
        assert.notEqual(result[0].route, 'express', 'blocked route must not be selected');
      }
      const candidates = routeOptions.filter(r => !blocked.includes(r.channel));
      const minLatency = Math.min(...candidates.map(r => r.latency));
      assert.equal(result[0].routeLatency, minLatency,
        `must select lowest latency among non-blocked (${minLatency}), got ${result[0].routeLatency}`);
    }

    // -------------------------------------------------------------------
    // Bucket 2: allocateOptimalBerth — multiple vessels compete for berths
    // -------------------------------------------------------------------
    else if (bucket === 2) {
      const vessels = [
        { id: `v1-${idx}`, draft: 8, length: 150, tonnage: 3000 },
        { id: `v2-${idx}`, draft: 12, length: 200, tonnage: 7000 },
      ];
      const routeOptions = [
        { channel: 'alpha', latency: 3 + (idx % 4) },
        { channel: 'beta', latency: 1 + (idx % 2) },
      ];
      const berths = [
        new BerthSlot(`B1-${idx}`, 15, 250),
        new BerthSlot(`B2-${idx}`, 15, 250),
      ];
      const results = allocateOptimalBerth(vessels, routeOptions, berths, []);
      assert.equal(results.length, 2);
      const minLatency = Math.min(...routeOptions.map(r => r.latency));
      for (const r of results) {
        assert.ok(r.allocated, `vessel ${r.vesselId} must be allocated`);
        assert.equal(r.routeLatency, minLatency,
          `each vessel must get lowest-latency route (${minLatency}), got ${r.routeLatency}`);
      }
    }

    // -------------------------------------------------------------------
    // Bucket 3: replayAndAnalyze — verify max sequence per entity
    // Red-herring: bug manifests in statistics but root cause is in resilience.js
    // -------------------------------------------------------------------
    else if (bucket === 3) {
      const seqHigh = (idx % 10) + 5;
      const events = [
        { id: `e-${idx % 20}`, sequence: 1 },
        { id: `e-${idx % 20}`, sequence: seqHigh },
        { id: `f-${idx % 15}`, sequence: 2 },
      ];
      const analysis = replayAndAnalyze(events);
      assert.equal(analysis.eventCount, 2, 'should deduplicate to 2 entities');
      const eEvent = analysis.events.find(e => e.id === `e-${idx % 20}`);
      assert.ok(eEvent, 'entity e must be in replay');
      assert.equal(eEvent.sequence, seqHigh,
        `replay must keep highest sequence (${seqHigh}) for disaster recovery, got ${eEvent.sequence}`);
      assert.equal(analysis.maxSequence, seqHigh,
        `max sequence must be ${seqHigh}, got ${analysis.maxSequence}`);
    }

    // -------------------------------------------------------------------
    // Bucket 4: replayAndAnalyze — multi-entity statistics
    // -------------------------------------------------------------------
    else if (bucket === 4) {
      const events = [
        { id: `x-${idx}`, sequence: 1 },
        { id: `x-${idx}`, sequence: 10 },
        { id: `y-${idx}`, sequence: 5 },
        { id: `y-${idx}`, sequence: 15 },
        { id: `z-${idx}`, sequence: 3 },
      ];
      const analysis = replayAndAnalyze(events);
      assert.equal(analysis.eventCount, 3, 'should have 3 deduplicated entities');
      // Correct replay keeps highest: x=10, y=15, z=3 -> max=15
      assert.equal(analysis.maxSequence, 15,
        `max sequence must be 15 (highest from y), got ${analysis.maxSequence}`);
      assert.ok(analysis.meanSequence > 0, 'mean sequence must be positive');
    }

    // -------------------------------------------------------------------
    // Bucket 5: planWindow + chooseRoute pipeline (scheduling x routing)
    // Procedural diversity: different urgency/route combinations per idx
    // -------------------------------------------------------------------
    else if (bucket === 5) {
      const vessels = [
        { id: `v1-${idx}`, urgency: 50 + (idx % 20), eta: `0${idx % 8}:30` },
        { id: `v2-${idx}`, urgency: 30 + (idx % 15), eta: `0${(idx + 2) % 8}:15` },
        { id: `v3-${idx}`, urgency: 70 + (idx % 10), eta: `0${(idx + 4) % 8}:45` },
      ];
      const planned = planWindow(vessels, 2);
      assert.equal(planned.length, 2);
      assert.ok(planned[0].urgency >= planned[1].urgency, 'must be sorted by urgency desc');

      const routeOptions = [
        { channel: 'fast', latency: 2 },
        { channel: 'normal', latency: 5 + (idx % 4) },
      ];
      const route = chooseRoute(routeOptions, []);
      assert.equal(route.latency, 2,
        `chooseRoute must pick lowest latency (2), got ${route.latency} via ${route.channel}`);
    }

    // -------------------------------------------------------------------
    // Bucket 6: canTransition + nextPolicy + shouldDeescalate + shouldShed
    // Procedural diversity: exercises threshold boundaries across modules
    // -------------------------------------------------------------------
    else if (bucket === 6) {
      assert.equal(canTransition('queued', 'allocated'), true);
      assert.equal(canTransition('allocated', 'departed'), true);
      assert.equal(canTransition('arrived', 'queued'), false);

      // Policy: failureBurst=2 must escalate (threshold boundary bug)
      const from = idx % 2 === 0 ? 'normal' : 'watch';
      const expected = idx % 2 === 0 ? 'watch' : 'restricted';
      const pol = nextPolicy(from, 2);
      assert.equal(pol, expected,
        `nextPolicy('${from}', 2) must escalate to '${expected}', got '${pol}'`);

      // De-escalation at exact threshold (>= boundary bug)
      const deesc = shouldDeescalate('watch', 10, 10);
      assert.equal(deesc, true,
        'must deescalate at exact success threshold (10 >= 10)');

      // Queue shedding
      assert.equal(shouldShed((idx % 30) + 1, 40, false), false);
      assert.equal(shouldShed(41, 40, false), true);
    }

    // -------------------------------------------------------------------
    // Bucket 7: Full pipeline — replay + analyze + route + schedule
    // Procedural diversity: end-to-end data flow through 4 modules
    // -------------------------------------------------------------------
    else {
      const events = [
        { id: `ship-${idx % 12}`, sequence: 1 },
        { id: `ship-${idx % 12}`, sequence: 5 },
        { id: `cargo-${idx % 8}`, sequence: 2 },
      ];
      const analysis = replayAndAnalyze(events);
      // Should keep highest: ship=5, cargo=2 -> max=5
      assert.equal(analysis.maxSequence, 5,
        `max sequence must be 5, got ${analysis.maxSequence}`);

      const routeOptions = [
        { channel: 'priority', latency: 1 + (idx % 3) },
        { channel: 'bulk', latency: 6 + (idx % 5) },
      ];
      const route = chooseRoute(routeOptions, []);
      const minLatency = Math.min(...routeOptions.map(r => r.latency));
      assert.equal(route.latency, minLatency,
        `route must have min latency ${minLatency}, got ${route.latency}`);

      // Use analysis results as urgency for scheduling
      const vessels = analysis.events.map((e, i) => ({
        id: e.id,
        urgency: e.sequence * 10,
        eta: `0${i}:00`,
      }));
      const planned = planWindow(vessels, 1);
      assert.equal(planned.length, 1);
      const maxUrgency = Math.max(...vessels.map(v => v.urgency));
      assert.equal(planned[0].urgency, maxUrgency,
        `planWindow must select highest urgency vessel (${maxUrgency})`);
    }
  });
}
