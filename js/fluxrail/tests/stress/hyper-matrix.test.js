const { test } = require('node:test');
const assert = require('node:assert');

const { chooseRoute, assignPriority, mergeAssignmentMaps, routeScorer, batchDispatch, priorityDecay } = require('../../src/core/dispatch');
const { rebalance, shedRequired, dynamicBuffer, demandProjection, exponentialForecast, reservationPlanner } = require('../../src/core/capacity');
const { overrideAllowed, escalationLevel, retentionBucket, evaluatePolicy, riskScoreAggregator } = require('../../src/core/policy');
const { retryBackoffMs, circuitOpen, replayState } = require('../../src/core/resilience');
const { replayBudget, dedupeEvents, orderedReplay, replayWithCheckpoint } = require('../../src/core/replay');
const { allowed, tokenFresh, fingerprint, auditChainValidator } = require('../../src/core/security');
const { percentile, boundedRatio, movingAverage, weightedAverage, standardDeviation, correlationCoefficient } = require('../../src/core/statistics');
const { transitionAllowed, nextStateFor } = require('../../src/core/workflow');
const { nextPolicy, shouldThrottle, penaltyScore } = require('../../src/core/queue');
const { selectHub, deterministicPartition, churnRate, routeLatencyEstimate } = require('../../src/core/routing');
const { buildLedgerEntries, balanceExposure, detectSequenceGap, netExposureByTenant, crossAccountTransfer } = require('../../src/core/ledger');
const { signPayload, verifyPayload, requiresStepUp } = require('../../src/core/authorization');
const { projectedCost, marginRatio, budgetPressure, costAllocation, discountedCashFlow } = require('../../src/core/economics');
const { breachRisk, breachSeverity, meanTimeToRecover } = require('../../src/core/sla');

// ── Anti-reward-hacking sentinel: functions must not return constants ──
test('hyper-sentinel-000: anti-gaming behavioral diversity', () => {
  // chooseRoute must respond to different inputs
  const r1 = chooseRoute({ a: 10, b: 20 });
  const r2 = chooseRoute({ a: 20, b: 10 });
  assert.notStrictEqual(r1, r2, 'chooseRoute must vary with inputs');

  // rebalance must respond to different inputs
  const rb1 = rebalance(100, 50, 10);
  const rb2 = rebalance(100, 80, 10);
  assert.notStrictEqual(rb1, rb2, 'rebalance must vary with inputs');

  // percentile must respond to different percentile values
  const p25 = percentile([10, 20, 30, 40, 50], 0.25);
  const p75 = percentile([10, 20, 30, 40, 50], 0.75);
  assert.notStrictEqual(p25, p75, 'percentile must vary with p');

  // balanceExposure must respond to different deltas
  const e1 = balanceExposure([{ account: 'x', delta: 100 }]);
  const e2 = balanceExposure([{ account: 'x', delta: -100 }]);
  assert.notStrictEqual(e1.x, e2.x, 'balanceExposure must vary with delta');

  // projectedCost must respond to different inputs
  const c1 = projectedCost(10, 5, 2);
  const c2 = projectedCost(20, 5, 2);
  assert.notStrictEqual(c1, c2, 'projectedCost must vary with units');

  // selectHub must respond to different congestion levels
  const h1 = selectHub({ a: 10, b: 90 });
  const h2 = selectHub({ a: 90, b: 10 });
  assert.notStrictEqual(h1, h2, 'selectHub must vary with congestion');

  // breachSeverity must vary across deltas
  const s1 = breachSeverity(600, 500);
  const s2 = breachSeverity(400, 500);
  assert.notStrictEqual(s1, s2, 'breachSeverity must vary with delta');
});

const TOTAL_CASES = 8000;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`hyper-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 16;
    // Sub-variation within each bucket for input diversity
    const subIdx = Math.floor(idx / 16);

    switch (bucket) {
      case 0: {
        // dispatch: chooseRoute should pick lowest latency
        const latencies = { routeA: 10 + (idx % 50), routeB: 5 + (idx % 30), routeC: 20 + (idx % 40) };
        const route = chooseRoute(latencies);
        const minLatency = Math.min(...Object.values(latencies));
        const expectedRoute = Object.entries(latencies).filter(([, v]) => v === minLatency).sort()[0][0];
        assert.strictEqual(route, expectedRoute, `chooseRoute: expected ${expectedRoute}, got ${route}`);

        // assignPriority should add urgency, not subtract
        const sev = 5 + (subIdx % 4);
        const sla = 10 + (subIdx % 25);
        const priority = assignPriority(sev, sla);
        const expectedBase = sev >= 8 ? 90 : sev >= 5 ? 65 : 35;
        const expectedUrgency = sla <= 15 ? 15 : sla <= 30 ? 8 : 0;
        const expectedPriority = Math.min(100, expectedBase + expectedUrgency);
        assert.strictEqual(priority, expectedPriority,
          `assignPriority(${sev},${sla}): expected ${expectedPriority}, got ${priority}`);
        break;
      }

      case 1: {
        // capacity: rebalance should subtract reserve, not add
        const available = 60 + (subIdx % 80);
        const demand = 40 + (subIdx % 50);
        const reserve = 15 + (subIdx % 30);
        const allocated = rebalance(available, demand, reserve);
        const expected = Math.min(Math.max(demand, 0), Math.max(0, available - reserve));
        assert.strictEqual(allocated, expected,
          `rebalance(${available},${demand},${reserve}): expected ${expected}, got ${allocated}`);

        // shedRequired should use >= not >
        const limit = 50 + (subIdx % 100);
        assert.strictEqual(shedRequired(limit, limit), true,
          `shedRequired(${limit},${limit}): expected true at exact limit`);
        break;
      }

      case 2: {
        // policy: overrideAllowed should accept exactly 2 approvals (>= 2, not > 2)
        const reasonLen = 12 + (subIdx % 10);
        const reason = 'r'.repeat(reasonLen);
        const allowed2 = overrideAllowed(reason, 2, 60 + (subIdx % 60));
        assert.strictEqual(allowed2, true,
          `overrideAllowed: expected true with 2 approvals and reason length ${reasonLen}`);

        // escalationLevel: regulatory should add 1, not 2
        const sev = 3 + (subIdx % 6);
        const units = 5 + (subIdx % 10);
        const level = escalationLevel(sev, units, true);
        const expectedBase = sev >= 8 ? 3 : sev >= 5 ? 2 : 1;
        const expectedLevel = Math.min(expectedBase + (units >= 10 ? 1 : 0) + 1, 5);
        assert.strictEqual(level, expectedLevel,
          `escalationLevel(${sev},${units},true): expected ${expectedLevel}, got ${level}`);
        break;
      }

      case 3: {
        // resilience: retryBackoff should be baseMs * 2^(attempt-1)
        const attempt = 1 + (subIdx % 5);
        const baseMs = 50 + (subIdx % 200);
        const backoff = retryBackoffMs(attempt, baseMs);
        const expectedBackoff = baseMs * Math.pow(2, attempt - 1);
        assert.strictEqual(backoff, expectedBackoff,
          `retryBackoff(${attempt},${baseMs}): expected ${expectedBackoff}, got ${backoff}`);
        break;
      }

      case 4: {
        // replay: replayBudget should be positive
        const count = 10 + (subIdx % 200);
        const timeout = 5 + (subIdx % 30);
        const budget = replayBudget(count, timeout);
        assert.ok(budget > 0,
          `replayBudget(${count},${timeout}): expected positive, got ${budget}`);

        // orderedReplay should sort ascending by version
        const v1 = 1 + (subIdx % 10);
        const v2 = v1 + 1 + (subIdx % 5);
        const v3 = v2 + 1 + (subIdx % 5);
        const events = [
          { id: 'c', version: v3, idempotencyKey: 'k3' },
          { id: 'a', version: v1, idempotencyKey: 'k1' },
          { id: 'b', version: v2, idempotencyKey: 'k2' }
        ];
        const ordered = orderedReplay(events);
        assert.strictEqual(ordered[0].version, v1,
          `orderedReplay: first should be version ${v1}, got ${ordered[0].version}`);
        assert.strictEqual(ordered[2].version, v3,
          `orderedReplay: last should be version ${v3}`);
        break;
      }

      case 5: {
        // security: allowed should return true for valid role/action pairs
        const pairs = [
          ['operator', 'read'], ['operator', 'submit'],
          ['reviewer', 'approve'], ['admin', 'override']
        ];
        const [role, action] = pairs[subIdx % pairs.length];
        assert.strictEqual(allowed(role, action), true,
          `allowed('${role}','${action}'): expected true`);

        // fingerprint should normalize to lowercase
        const parts = ['TenantX', 'TraceY', 'EventZ'].map(s =>
          s + String(subIdx % 100));
        const fp = fingerprint(parts[0], parts[1], parts[2]);
        const expectedFp = parts.map(s => s.trim().toLowerCase()).join(':');
        assert.strictEqual(fp, expectedFp,
          `fingerprint: expected lowercase '${expectedFp}', got '${fp}'`);
        break;
      }

      case 6: {
        // statistics: percentile should sort ascending
        const base = (subIdx % 20) * 5;
        const values = [base + 40, base + 10, base + 30, base + 20];
        const p50 = percentile(values, 0.5);
        const sorted = [...values].sort((a, b) => a - b);
        const expectedP50 = sorted[Math.round(0.5 * (sorted.length - 1))];
        assert.strictEqual(p50, expectedP50,
          `percentile p50 of ${JSON.stringify(values)}: expected ${expectedP50}, got ${p50}`);

        // boundedRatio should clamp to [0,1]
        const num = 100 + (subIdx % 300);
        const den = 50 + (subIdx % 100);
        const ratio = boundedRatio(num, den);
        assert.ok(ratio <= 1,
          `boundedRatio(${num},${den}): should clamp to <=1, got ${ratio}`);
        break;
      }

      case 7: {
        // workflow: nextStateFor('capacity_ok') should return 'capacity_checked'
        const capState = nextStateFor('capacity_ok');
        assert.strictEqual(capState, 'capacity_checked',
          `nextStateFor('capacity_ok'): expected 'capacity_checked', got '${capState}'`);

        // nextStateFor unknown should return 'drafted', not 'canceled'
        const unknowns = ['unknown_event', 'garbage', 'foo_' + subIdx, 'xyz'];
        const event = unknowns[subIdx % unknowns.length];
        const state = nextStateFor(event);
        assert.strictEqual(state, 'drafted',
          `nextStateFor('${event}'): expected 'drafted', got '${state}'`);
        break;
      }

      case 8: {
        // queue: shouldThrottle should use >= not > at exact boundary
        const limit = 50 + (subIdx % 150);
        const half = Math.floor(limit / 2);
        assert.strictEqual(shouldThrottle(half, limit - half, limit), true,
          `shouldThrottle(${half},${limit - half},${limit}): expected true at exact limit`);

        // evaluatePolicy: margin should be a BONUS, not penalty
        const margin = 0.1 + (subIdx % 10) * 0.05;
        const withMargin = evaluatePolicy({ securityIncidents: 0, backlog: 5, staleMinutes: 10, margin });
        const withoutMargin = evaluatePolicy({ securityIncidents: 0, backlog: 5, staleMinutes: 10, margin: 0 });
        assert.ok(withMargin.score >= withoutMargin.score,
          `evaluatePolicy: margin ${margin} should increase score, not decrease it`);
        break;
      }

      case 9: {
        // routing: selectHub should pick least congested
        const cA = 30 + (subIdx % 70);
        const cB = 10 + (subIdx % 30);
        const cC = 60 + (subIdx % 40);
        const congestion = { hubA: cA, hubB: cB, hubC: cC };
        const hub = selectHub(congestion);
        const minVal = Math.min(cA, cB, cC);
        const expectedHub = Object.entries(congestion)
          .filter(([, v]) => v === minVal).sort()[0][0];
        assert.strictEqual(hub, expectedHub,
          `selectHub: expected ${expectedHub} (min congestion), got ${hub}`);

        // churnRate should return changed/total, not total/changed
        const prev = { a: 1, b: 2, c: 3 };
        const cur = { a: 1, b: 99, c: 3 };
        const churn = churnRate(prev, cur);
        assert.ok(churn > 0 && churn < 1,
          `churnRate: 1/3 changed should give 0 < churn < 1, got ${churn}`);
        const expectedChurn = 1 / 3;
        assert.ok(Math.abs(churn - expectedChurn) < 0.01,
          `churnRate: expected ~${expectedChurn.toFixed(4)}, got ${churn}`);
        break;
      }

      case 10: {
        // ledger: balanceExposure should add deltas, not subtract
        const d1 = 50 + (subIdx % 200);
        const d2 = 25 + (subIdx % 150);
        const entries = [
          { account: 'acc', delta: d1 },
          { account: 'acc', delta: d2 }
        ];
        const exposure = balanceExposure(entries);
        assert.strictEqual(exposure.acc, d1 + d2,
          `balanceExposure: expected ${d1 + d2}, got ${exposure.acc}`);

        // netExposureByTenant should use signed sum, not abs
        const pos = 100 + (subIdx % 200);
        const neg = -(50 + (subIdx % 100));
        const tenantEntries = [
          { tenant: 't1', delta: pos },
          { tenant: 't1', delta: neg }
        ];
        const netExp = netExposureByTenant(tenantEntries);
        assert.strictEqual(netExp.t1, pos + neg,
          `netExposureByTenant: expected ${pos + neg} (net), got ${netExp.t1} (abs used?)`);
        break;
      }

      case 11: {
        // authorization: verifyPayload should fail for wrong signature
        const payload = 'test-payload-' + subIdx;
        const secret = 'secret-' + (subIdx % 10);
        const valid = verifyPayload(payload, 'wrong-sig-' + subIdx, secret);
        assert.strictEqual(valid, false,
          `verifyPayload('${payload}', wrong-sig, '${secret}'): should be false`);

        // verifyPayload should succeed for correct signature
        const correctSig = signPayload(payload, secret);
        const validCorrect = verifyPayload(payload, correctSig, secret);
        assert.strictEqual(validCorrect, true,
          `verifyPayload with correct sig should be true`);
        break;
      }

      case 12: {
        // economics: projectedCost should multiply surge, not add
        const units = 5 + (subIdx % 20);
        const rate = 3 + (subIdx % 10);
        const surge = 2 + (subIdx % 3);
        const cost = projectedCost(units, rate, surge);
        const expected = Math.round(units * rate * surge);
        assert.strictEqual(cost, expected,
          `projectedCost(${units},${rate},${surge}): expected ${expected}, got ${cost}`);

        // budgetPressure should add backlog, not subtract
        const alloc = 30 + (subIdx % 40);
        const cap = 100 + (subIdx % 50);
        const backlog = 10 + (subIdx % 30);
        const pressure = budgetPressure(alloc, cap, backlog);
        const expectedPressure = Math.max(0, Number(((alloc + backlog) / cap).toFixed(4)));
        assert.strictEqual(pressure, expectedPressure,
          `budgetPressure(${alloc},${cap},${backlog}): expected ${expectedPressure}, got ${pressure}`);
        break;
      }

      case 13: {
        // sla: breachRisk should subtract buffer (risk = eta > sla - buffer)
        const eta = 400 + (subIdx % 200);
        const sla = 500 + (subIdx % 100);
        const buffer = 50 + (subIdx % 100);
        const risk = breachRisk(eta, sla, buffer);
        const expectedRisk = eta > sla - buffer;
        assert.strictEqual(risk, expectedRisk,
          `breachRisk(${eta},${sla},${buffer}): expected ${expectedRisk}, got ${risk}`);

        // breachSeverity: delta <= 0 should be 'none' (not just delta < 0)
        const severity = breachSeverity(sla, sla);
        assert.strictEqual(severity, 'none',
          `breachSeverity(${sla},${sla}): delta=0 should be 'none', got '${severity}'`);
        break;
      }

      case 14: {
        // capacity: dynamicBuffer should clamp to [floor, cap]
        const vol = 0.5 + (subIdx % 50) * 0.1;
        const floor = 0.05;
        const cap = 0.15;
        const buffer = dynamicBuffer(vol, floor, cap);
        const raw = 0.05 + vol * 0.02;
        const expectedBuffer = Math.max(floor, Math.min(raw, cap));
        assert.strictEqual(buffer, expectedBuffer,
          `dynamicBuffer(${vol},${floor},${cap}): expected ${expectedBuffer}, got ${buffer}`);

        // demandProjection should divide by weight sum, not array length
        const weights = [2, 1];
        const historical = [100 + (subIdx % 50), 200 + (subIdx % 50)];
        const proj = demandProjection(historical, weights);
        const wSum = weights.reduce((s, w) => s + w, 0);
        const wTotal = historical.reduce((s, v, i) => s + v * weights[i], 0);
        const expectedProj = Math.round((wTotal / wSum) * 100) / 100;
        assert.strictEqual(proj, expectedProj,
          `demandProjection: expected ${expectedProj} (weighted), got ${proj}`);
        break;
      }

      case 15: {
        // routing: deterministicPartition should be 0-indexed [0, shardCount)
        const tenant = 'tenant' + subIdx;
        const shards = 8 + (subIdx % 16);
        const partition = deterministicPartition(tenant, shards);
        assert.ok(partition >= 0 && partition < shards,
          `deterministicPartition('${tenant}',${shards}): expected 0..${shards - 1}, got ${partition}`);

        // churnRate: empty should return 0 (no keys = no churn)
        const churn = churnRate({}, {});
        assert.strictEqual(churn, 0,
          `churnRate({},{}): expected 0, got ${churn}`);

        // routeLatencyEstimate should not divide processingMs by 1000
        const hops = [{ latencyMs: 10 + (subIdx % 20), processingMs: 50 + (subIdx % 50) }];
        const est = routeLatencyEstimate(hops);
        const expectedEst = hops[0].latencyMs + hops[0].processingMs;
        assert.strictEqual(est, expectedEst,
          `routeLatencyEstimate: expected ${expectedEst}ms, got ${est}ms (processingMs divided by 1000?)`);
        break;
      }
    }
  });
}
