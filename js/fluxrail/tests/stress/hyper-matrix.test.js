const { test } = require('node:test');
const assert = require('node:assert');

const { chooseRoute, assignPriority, mergeAssignmentMaps } = require('../../src/core/dispatch');
const { rebalance, shedRequired, dynamicBuffer } = require('../../src/core/capacity');
const { overrideAllowed, escalationLevel, retentionBucket, evaluatePolicy } = require('../../src/core/policy');
const { retryBackoffMs, circuitOpen, replayState } = require('../../src/core/resilience');
const { replayBudget, dedupeEvents, orderedReplay } = require('../../src/core/replay');
const { allowed, tokenFresh, fingerprint } = require('../../src/core/security');
const { percentile, boundedRatio, movingAverage } = require('../../src/core/statistics');
const { transitionAllowed, nextStateFor } = require('../../src/core/workflow');
const { nextPolicy, shouldThrottle, penaltyScore } = require('../../src/core/queue');
const { selectHub, deterministicPartition, churnRate } = require('../../src/core/routing');
const { buildLedgerEntries, balanceExposure, detectSequenceGap } = require('../../src/core/ledger');
const { signPayload, verifyPayload, requiresStepUp } = require('../../src/core/authorization');
const { projectedCost, marginRatio, budgetPressure } = require('../../src/core/economics');
const { breachRisk, breachSeverity } = require('../../src/core/sla');

const TOTAL_CASES = 8000;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`hyper-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 16;

    switch (bucket) {
      case 0: {
        // dispatch: chooseRoute should pick lowest latency
        const latencies = { routeA: 10 + (idx % 50), routeB: 5 + (idx % 30), routeC: 20 + (idx % 40) };
        const route = chooseRoute(latencies);
        const minLatency = Math.min(...Object.values(latencies));
        const expectedRoute = Object.entries(latencies).filter(([, v]) => v === minLatency).sort()[0][0];
        assert.strictEqual(route, expectedRoute, `chooseRoute: expected ${expectedRoute}, got ${route}`);

        // assignPriority should add urgency, not subtract
        const priority = assignPriority(8, 15);
        assert.ok(priority >= 90, `assignPriority: expected >= 90 for severity 8, got ${priority}`);
        break;
      }

      case 1: {
        // capacity: rebalance should subtract reserve, not add
        const available = 100;
        const demand = 80;
        const reserve = 30;
        const allocated = rebalance(available, demand, reserve);
        const expected = Math.min(demand, available - reserve);
        assert.strictEqual(allocated, expected, `rebalance: expected ${expected}, got ${allocated}`);

        // shedRequired should use >= not >
        assert.strictEqual(shedRequired(100, 100), true, `shedRequired: expected true at exact limit`);
        break;
      }

      case 2: {
        // policy: overrideAllowed should use >= for approvals
        const allowed12chars = overrideAllowed('reason123456', 2, 120);
        assert.strictEqual(allowed12chars, true, `overrideAllowed: expected true with 2 approvals`);

        // escalationLevel should add 1 for regulatory, not 2
        const level = escalationLevel(5, 5, true);
        assert.ok(level <= 4, `escalationLevel: expected <= 4, got ${level}`);
        break;
      }

      case 3: {
        // resilience: retryBackoff should be baseMs * 2^(attempt-1)
        const backoff = retryBackoffMs(1, 100);
        assert.strictEqual(backoff, 100, `retryBackoff: attempt 1 should be 100, got ${backoff}`);

        const backoff2 = retryBackoffMs(2, 100);
        assert.strictEqual(backoff2, 200, `retryBackoff: attempt 2 should be 200, got ${backoff2}`);
        break;
      }

      case 4: {
        // replay: replayBudget should be positive
        const budget = replayBudget(100, 10);
        assert.ok(budget > 0, `replayBudget: expected positive, got ${budget}`);

        // orderedReplay should sort ascending by version
        const events = [
          { id: 'a', version: 3, idempotencyKey: 'k1' },
          { id: 'b', version: 1, idempotencyKey: 'k2' },
          { id: 'c', version: 2, idempotencyKey: 'k3' }
        ];
        const ordered = orderedReplay(events);
        assert.strictEqual(ordered[0].version, 1, `orderedReplay: first should be version 1`);
        break;
      }

      case 5: {
        // security: allowed should return true for valid role/action
        assert.strictEqual(allowed('operator', 'read'), true, `allowed: operator should read`);
        assert.strictEqual(allowed('admin', 'override'), true, `allowed: admin should override`);

        // fingerprint should be lowercase
        const fp = fingerprint('TENANT', 'TRACE', 'EVENT');
        assert.strictEqual(fp, 'tenant:trace:event', `fingerprint: expected lowercase`);
        break;
      }

      case 6: {
        // statistics: percentile should sort ascending
        const values = [40, 10, 30, 20];
        const p50 = percentile(values, 0.5);
        // For ascending sort: [10, 20, 30, 40], p50 is index 2 = 30
        assert.ok(p50 <= 30, `percentile: p50 of [10,20,30,40] should be <=30, got ${p50}`);

        // boundedRatio should clamp to [0,1]
        const ratio = boundedRatio(200, 100);
        assert.ok(ratio <= 1, `boundedRatio: should clamp to <=1, got ${ratio}`);
        break;
      }

      case 7: {
        // workflow: nextStateFor should return 'drafted' for unknown
        const state = nextStateFor('unknown_event');
        assert.strictEqual(state, 'drafted', `nextStateFor: unknown should be 'drafted', got ${state}`);

        // capacity_ok should return capacity_checked
        const capState = nextStateFor('capacity_ok');
        assert.strictEqual(capState, 'capacity_checked', `nextStateFor: capacity_ok should be 'capacity_checked'`);
        break;
      }

      case 8: {
        // queue: shouldThrottle should use >= not >
        assert.strictEqual(shouldThrottle(50, 50, 100), true, `shouldThrottle: expected true at exact limit`);
        break;
      }

      case 9: {
        // routing: selectHub should pick least congested
        const congestion = { hubA: 100, hubB: 50, hubC: 75 };
        const hub = selectHub(congestion);
        assert.strictEqual(hub, 'hubB', `selectHub: expected hubB (lowest), got ${hub}`);

        // selectHub empty should return 'unassigned'
        const empty = selectHub({});
        assert.strictEqual(empty, 'unassigned', `selectHub: empty should be 'unassigned', got ${empty}`);
        break;
      }

      case 10: {
        // ledger: balanceExposure should add deltas
        const entries = [
          { account: 'a', delta: 100 },
          { account: 'a', delta: 50 }
        ];
        const exposure = balanceExposure(entries);
        assert.strictEqual(exposure.a, 150, `balanceExposure: expected 150, got ${exposure.a}`);
        break;
      }

      case 11: {
        // authorization: verifyPayload should fail for wrong signature
        const valid = verifyPayload('payload', 'wrong-sig', 'secret');
        assert.strictEqual(valid, false, `verifyPayload: wrong sig should be false`);
        break;
      }

      case 12: {
        // economics: projectedCost should multiply surge
        const cost = projectedCost(10, 5, 2);
        assert.strictEqual(cost, 100, `projectedCost: 10*5*2 should be 100, got ${cost}`);

        // budgetPressure should add backlog
        const pressure = budgetPressure(50, 100, 25);
        assert.strictEqual(pressure, 0.75, `budgetPressure: (50+25)/100 should be 0.75, got ${pressure}`);
        break;
      }

      case 13: {
        // sla: breachRisk should subtract buffer
        const risk = breachRisk(450, 500, 100);
        assert.strictEqual(risk, true, `breachRisk: 450 > 500-100 should be true`);

        // breachSeverity: delta 0 should be 'none'
        const severity = breachSeverity(500, 500);
        assert.strictEqual(severity, 'none', `breachSeverity: delta 0 should be 'none', got ${severity}`);
        break;
      }

      case 14: {
        // more capacity tests
        const buffer = dynamicBuffer(1.0, 0.05, 0.15);
        assert.ok(buffer >= 0.05 && buffer <= 0.15, `dynamicBuffer: should be clamped, got ${buffer}`);
        break;
      }

      case 15: {
        // more routing tests
        const partition = deterministicPartition('tenant123', 10);
        assert.ok(partition >= 0 && partition < 10, `deterministicPartition: should be 0-9, got ${partition}`);

        // churnRate empty should be 0
        const churn = churnRate({}, {});
        assert.strictEqual(churn, 0, `churnRate: empty should be 0, got ${churn}`);
        break;
      }
    }
  });
}
