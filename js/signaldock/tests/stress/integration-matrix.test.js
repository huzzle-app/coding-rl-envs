const test = require('node:test');
const assert = require('node:assert/strict');

const { planWindowPrioritized, BerthSlot } = require('../../src/core/scheduling');
const { RouteTable, chooseRoute } = require('../../src/core/routing');
const { PolicyEngine, policyForLoad, POLICY_METADATA } = require('../../src/core/policy');
const { PriorityQueue, shouldShed, adaptiveThreshold, DEFAULT_HARD_LIMIT } = require('../../src/core/queue');
const { WorkflowEngine } = require('../../src/core/workflow');
const { CircuitBreaker, CB_STATES, replayWithWindowing, replay } = require('../../src/core/resilience');
const { computeAccessLevel, signManifest, verifyManifestChain, TokenStore } = require('../../src/core/security');
const { ResponseTimeTracker, mean, correlate } = require('../../src/core/statistics');
const { DispatchTicket, VesselManifest, Severity, mergeBatchTickets } = require('../../src/models/dispatch-ticket');
const { serviceHealthRollup, buildDependencyMatrix, SERVICE_DEFINITIONS } = require('../../shared/contracts/contracts');

const CASES = 400;
const SECRET = 'signaldock-integration-test-key';

for (let idx = 0; idx < CASES; idx += 1) {
  test(`integration-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 8;

    if (variant === 0) {
      // planWindowPrioritized: overrides must be applied BEFORE vessel selection
      const vessels = [
        { id: 'low-vessel', urgency: 1, eta: '08:00' },
        { id: `mid-${idx}`, urgency: 5 + (idx % 3), eta: '09:00' },
        { id: 'high-vessel', urgency: 10, eta: '07:00' },
      ];
      // Override low-vessel to have highest urgency
      const overrides = [{ id: 'low-vessel', urgency: 20 + (idx % 10) }];
      const result = planWindowPrioritized(vessels, 2, overrides);
      const ids = result.map(v => v.id);
      // With overrides applied BEFORE selection, low-vessel (urgency→20+) should be in top 2
      assert.ok(ids.includes('low-vessel'),
        `'low-vessel' overridden to urgency ${overrides[0].urgency} should be selected, got [${ids}]`);
    }

    if (variant === 1) {
      // Security + Policy: access control governs policy changes
      const scopes = ['dispatch', 'policy-admin'];
      const canModifyPolicy = computeAccessLevel(scopes, 'policy') === 'granted';
      // 'policy' should NOT match 'policy-admin' via substring
      // exact 'policy' is not in scopes, only 'policy-admin'
      assert.equal(computeAccessLevel(scopes, 'policy'), 'denied',
        "'policy' is not an exact scope, should be denied");
      assert.equal(computeAccessLevel(scopes, 'dispatch'), 'granted',
        "'dispatch' is an exact scope, should be granted");
    }

    if (variant === 2) {
      // Resilience + Statistics: replay events and compute metrics
      const events = [];
      const n = 10 + (idx % 20);
      for (let i = 0; i < n; i++) {
        events.push({ id: `e-${i % 5}`, sequence: i, latency: 10 + (i * 3) });
      }
      const replayed = replayWithWindowing(events, 4);
      const fullReplay = replay(events);
      // Should produce same unique events regardless of windowing
      assert.equal(replayed.length, fullReplay.length,
        `windowed (${replayed.length}) != full (${fullReplay.length})`);
    }

    if (variant === 3) {
      // adaptiveThreshold: shedRate as fraction (0-1), not percentage (0-100)
      const depth = 6 + (idx % 5);
      const hardLimit = 10;
      const shedRate = 0.3 + (idx % 5) * 0.1;
      const result = adaptiveThreshold(depth, hardLimit, shedRate);
      // Correct: threshold = hardLimit * (1 - shedRate) e.g. 10*(1-0.5)=5
      // Buggy: threshold = hardLimit * (1 - shedRate/100) e.g. 10*(1-0.005)=9.95
      const expectedThreshold = hardLimit * (1 - shedRate);
      assert.ok(Math.abs(result.threshold - expectedThreshold) < 0.01,
        `threshold should be ~${expectedThreshold.toFixed(1)} (limit*(1-rate)), got ${result.threshold.toFixed(1)}`);
    }

    if (variant === 4) {
      // Manifest chain + merge tickets: cross-module data flow
      const batchA = [
        new DispatchTicket(`merge-${idx}-1`, 5, 30),
        new DispatchTicket(`merge-${idx}-dup`, 3, 60),
      ];
      const batchB = [
        new DispatchTicket(`merge-${idx}-2`, 6, 20),
        new DispatchTicket(`merge-${idx}-dup`, 6, 20),
      ];
      const merged = mergeBatchTickets(batchA, batchB, true);
      // Dedup should keep higher severity for duplicates
      const dup = merged.find(t => t.id === `merge-${idx}-dup`);
      assert.ok(dup, 'duplicate ticket should exist in merged result');
      assert.equal(dup.severity, 6,
        `merged duplicate should keep higher severity 6, got ${dup.severity}`);
    }

    if (variant === 5) {
      // serviceHealthRollup: transitive dependency propagation
      // policy is down → routing depends on policy → analytics depends on routing
      // analytics should be unhealthy via transitive dependency chain
      const healthStatuses = {
        gateway: true,
        routing: true,   // routing itself is up, but its dep (policy) is down
        policy: false,    // root cause: policy is down
        resilience: true,
        analytics: true,  // analytics depends on routing (which transitively depends on policy)
        audit: true,
        notifications: true,
        security: true,
      };
      const rollup = serviceHealthRollup(healthStatuses);
      // Direct dependency: routing → policy (down) → routing should be unhealthy
      assert.equal(rollup.routing.healthy, false,
        'routing depends on unhealthy policy, should not be healthy');
      // Transitive dependency: analytics → routing → policy (down)
      // analytics should propagate routing's unhealthy status
      assert.equal(rollup.analytics.healthy, false,
        'analytics depends on routing (transitively on down policy), should not be healthy');
    }

    if (variant === 6) {
      // buildDependencyMatrix: bidirectional dependency tracking
      const matrix = buildDependencyMatrix();
      // gateway depends on routing: matrix.gateway.routing should be true
      assert.ok(matrix.gateway && matrix.gateway.routing,
        'gateway should list routing as dependency');
      // routing depends on policy: matrix.routing.policy should be true
      assert.ok(matrix.routing && matrix.routing.policy,
        'routing should list policy as dependency');
      // Bidirectional: policy should show routing as a dependent
      assert.ok(matrix.policy && matrix.policy.routing,
        'policy should show routing as reverse dependency');
    }

    if (variant === 7) {
      // Correlate route latencies with queue depths
      const latencies = [5, 8, 12, 15, 20].map(v => v + (idx % 5));
      const depths = latencies.map(l => l * 2 + 3);
      const r = correlate(latencies, depths);
      // Perfect positive correlation expected
      assert.ok(Math.abs(r - 1.0) < 0.01,
        `latency-depth correlation should be ~1.0, got ${r}`);
      // Mean should be computed correctly for integration
      const m = mean(latencies);
      const expected = latencies.reduce((s, v) => s + v, 0) / latencies.length;
      assert.ok(Math.abs(m - expected) < 0.01,
        `mean should be ${expected}, got ${m}`);
    }
  });
}
