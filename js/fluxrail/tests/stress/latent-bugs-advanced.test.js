const { test } = require('node:test');
const assert = require('node:assert/strict');

const { batchDispatch, dispatchRetryPolicy, priorityDecay, routeScorer } = require('../../src/core/dispatch');
const { demandProjection, capacityFragmentation, overcommitRatio, capacityWatermark } = require('../../src/core/capacity');
const { runningBalance, ledgerIntegrity, crossAccountTransfer, accountAgePartition } = require('../../src/core/ledger');
const { replaySegment, snapshotDelta } = require('../../src/core/replay');
const { standardDeviation, exponentialMovingAverage } = require('../../src/core/statistics');
const { sessionValidator } = require('../../src/core/security');
const { slaCompliance, uptimeCalculation, meanTimeToRecover } = require('../../src/core/sla');

// ===== routeScorer: must sort descending AND use correct weight distribution =====
// Route scoring requires: (1) descending sort so best route is first, AND
// (2) latency weighted at 0.4, capacity at 0.35, failure at 0.25.
// Both properties must hold for correct route selection.

test('latent-adv-001: routeScorer returns best route first', () => {
  const routes = [
    { id: 'slow', latency: 80, availableCapacity: 20, failures: 3 },
    { id: 'fast', latency: 10, availableCapacity: 90, failures: 0 }
  ];
  const scored = routeScorer(routes);
  assert.equal(scored[0].id, 'fast', 'highest-scoring route should be first');
});

test('latent-adv-002: routeScorer ranks zero-failure high-capacity routes highest', () => {
  const routes = [
    { id: 'a', latency: 50, availableCapacity: 50, failures: 0 },
    { id: 'b', latency: 50, availableCapacity: 80, failures: 0 },
    { id: 'c', latency: 50, availableCapacity: 30, failures: 0 }
  ];
  const scored = routeScorer(routes);
  assert.equal(scored[0].id, 'b', 'highest capacity should rank first');
});

test('latent-adv-003: routeScorer all routes have scores', () => {
  const routes = [{ id: 'x', latency: 0, availableCapacity: 100, failures: 0 }];
  const scored = routeScorer(routes);
  assert.ok(scored[0].score > 0);
});

test('latent-adv-004: routeScorer empty returns empty', () => {
  assert.deepEqual(routeScorer([]), []);
});

test('latent-adv-005: routeScorer penalizes high failures', () => {
  const routes = [
    { id: 'reliable', latency: 50, availableCapacity: 50, failures: 0 },
    { id: 'flaky', latency: 50, availableCapacity: 50, failures: 4 }
  ];
  const scored = routeScorer(routes);
  assert.equal(scored[0].id, 'reliable');
});

test('latent-adv-005a: routeScorer weights latency higher than capacity', () => {
  const routes = [
    { id: 'low-latency', latency: 10, availableCapacity: 40, failures: 0 },
    { id: 'high-capacity', latency: 70, availableCapacity: 95, failures: 0 }
  ];
  const scored = routeScorer(routes);
  // latencyScore: 90 vs 30; capacityScore: 40 vs 95; failureScore: 100 vs 100
  // Correct (lat=0.4, cap=0.35): low-lat=36+14+25=75, high-cap=12+33.25+25=70.25
  assert.equal(scored[0].id, 'low-latency',
    'latency weight (0.4) > capacity weight (0.35): low-latency route should win');
});

test('latent-adv-005b: routeScorer composite score uses documented weights', () => {
  const routes = [{ id: 'x', latency: 0, availableCapacity: 0, failures: 0 }];
  const scored = routeScorer(routes);
  // latencyScore=100, capacityScore=0, failureScore=100
  // Correct: 100*0.4 + 0*0.35 + 100*0.25 = 40+0+25 = 65
  assert.equal(scored[0].score, 65,
    'composite = latencyScore*0.4 + capacityScore*0.35 + failureScore*0.25');
});

test('latent-adv-005c: routeScorer differentiates latency vs capacity tradeoff', () => {
  const routes = [
    { id: 'balanced', latency: 40, availableCapacity: 60, failures: 1 },
    { id: 'fast-fragile', latency: 5, availableCapacity: 30, failures: 3 },
    { id: 'slow-robust', latency: 60, availableCapacity: 80, failures: 0 }
  ];
  const scored = routeScorer(routes);
  // slow-robust: latencyScore=40, capacityScore=80, failureScore=100
  // Correct: 40*0.4+80*0.35+100*0.25 = 16+28+25 = 69
  // balanced: latencyScore=60, capacityScore=60, failureScore=80
  // Correct: 60*0.4+60*0.35+80*0.25 = 24+21+20 = 65
  // fast-fragile: latencyScore=95, capacityScore=30, failureScore=40
  // Correct: 95*0.4+30*0.35+40*0.25 = 38+10.5+10 = 58.5
  assert.equal(scored[0].id, 'slow-robust');
  assert.equal(scored[1].id, 'balanced');
  assert.equal(scored[2].id, 'fast-fragile');
});

// ===== demandProjection: must use weighted average with consistent defaults =====
// Projection should divide by sum of weights (total / wSum), not count.
// Missing/undefined weights must default consistently in both numerator and denominator.

test('latent-adv-006: demandProjection with equal weights gives arithmetic mean', () => {
  assert.equal(demandProjection([10, 20, 30], [1, 1, 1]), 20);
});

test('latent-adv-007: demandProjection with heavy first weight', () => {
  const result = demandProjection([100, 0], [9, 1]);
  assert.equal(result, 90, 'weighted: (100*9 + 0*1) / 10 = 90');
});

test('latent-adv-008: demandProjection single value', () => {
  assert.equal(demandProjection([50], [1]), 50);
});

test('latent-adv-009: demandProjection with varying weights', () => {
  const result = demandProjection([10, 30], [3, 1]);
  assert.equal(result, 15, '(10*3 + 30*1) / 4 = 15');
});

test('latent-adv-010: demandProjection empty returns 0', () => {
  assert.equal(demandProjection([], []), 0);
});

test('latent-adv-010a: demandProjection with sparse weights defaults consistently', () => {
  // When weight is undefined, both numerator and denominator should use same default (1)
  const result = demandProjection([100, 200, 300], [2, undefined, 3]);
  // Expected: (100*2 + 200*1 + 300*3) / (2+1+3) = 1300/6 ≈ 216.67
  const expected = Math.round((1300 / 6) * 100) / 100;
  assert.equal(result, expected,
    'undefined weight should default to 1 for both value multiplication and weight sum');
});

test('latent-adv-010b: demandProjection with null weight element', () => {
  const result = demandProjection([50, 150], [null, 4]);
  // null weight should default: (50*1 + 150*4) / (1+4) = 650/5 = 130
  assert.equal(result, 130);
});

test('latent-adv-010c: demandProjection weights shorter than values', () => {
  const result = demandProjection([100, 200, 300], [2]);
  // w[1] and w[2] are undefined → default to 1
  // Expected: (100*2 + 200*1 + 300*1) / (2+1+1) = 700/4 = 175
  assert.equal(result, 175);
});

// ===== crossAccountTransfer: adds amount to BOTH accounts (should subtract from source) =====
// A transfer should debit the source account (negative delta) and credit
// the destination account (positive delta). The bug adds positive delta to both.

test('latent-adv-011: crossAccountTransfer debits source', () => {
  const entries = [{ id: 'e1', account: 'A', delta: 1000, seq: 1 }];
  const result = crossAccountTransfer(entries, 'A', 'B', 200);
  const sourceEntry = result.find(e => e.account === 'A' && e.id.startsWith('xfer'));
  assert.equal(sourceEntry.delta, -200, 'source should be debited (negative delta)');
});

test('latent-adv-012: crossAccountTransfer credits destination', () => {
  const entries = [{ id: 'e1', account: 'A', delta: 1000, seq: 1 }];
  const result = crossAccountTransfer(entries, 'A', 'B', 200);
  const destEntry = result.find(e => e.account === 'B' && e.id.startsWith('xfer'));
  assert.equal(destEntry.delta, 200, 'destination should be credited (positive delta)');
});

test('latent-adv-013: crossAccountTransfer preserves original entries', () => {
  const entries = [
    { id: 'e1', account: 'A', delta: 500, seq: 1 },
    { id: 'e2', account: 'B', delta: 300, seq: 2 }
  ];
  const result = crossAccountTransfer(entries, 'A', 'B', 100);
  assert.equal(result.length, 4);
});

test('latent-adv-014: crossAccountTransfer net zero across accounts', () => {
  const entries = [];
  const result = crossAccountTransfer(entries, 'X', 'Y', 500);
  const totalDelta = result.reduce((s, e) => s + Number(e.delta), 0);
  assert.equal(totalDelta, 0, 'transfer must be net zero: source -500 + dest +500 = 0');
});

test('latent-adv-015: crossAccountTransfer sequential seq numbers', () => {
  const entries = [{ id: 'e1', account: 'A', delta: 100, seq: 5 }];
  const result = crossAccountTransfer(entries, 'A', 'B', 50);
  const xferEntries = result.filter(e => e.id.startsWith('xfer'));
  assert.equal(xferEntries[0].seq, 6);
  assert.equal(xferEntries[1].seq, 7);
});

// ===== sessionValidator: compares expiresAt < issuedAt (should be expiresAt < nowMs) =====
// The validator checks if a session is expired by comparing expiresAt to issuedAt
// instead of comparing to the current time. This means sessions that are currently
// expired but were validly issued pass validation.

test('latent-adv-016: expired session detected', () => {
  const session = { userId: 'u1', token: 'tok', issuedAt: 1000, expiresAt: 2000 };
  const result = sessionValidator(session, 3000);
  assert.equal(result.valid, false, 'session expired at 2000, now is 3000');
});

test('latent-adv-017: valid unexpired session passes', () => {
  const session = { userId: 'u1', token: 'tok', issuedAt: 1000, expiresAt: 5000 };
  const result = sessionValidator(session);
  assert.equal(result.valid, true);
});

test('latent-adv-018: missing userId fails', () => {
  assert.equal(sessionValidator({ token: 'tok' }).valid, false);
});

test('latent-adv-019: revoked session fails', () => {
  assert.equal(sessionValidator({ userId: 'u1', token: 't', revoked: true }).valid, false);
});

// ===== meanTimeToRecover: divides by incidents.length instead of count =====
// Only resolved incidents should count in the denominator. If 3 incidents exist
// but only 2 are resolved, MTTR = totalRecoveryTime / 2, not / 3.

test('latent-adv-020: MTTR with all resolved incidents', () => {
  const incidents = [
    { detectedAt: 100, resolvedAt: 200 },
    { detectedAt: 300, resolvedAt: 500 }
  ];
  const result = meanTimeToRecover(incidents);
  assert.equal(result, 150, 'MTTR = (100 + 200) / 2 = 150');
});

test('latent-adv-021: MTTR ignores unresolved incidents in denominator', () => {
  const incidents = [
    { detectedAt: 100, resolvedAt: 400 },
    { detectedAt: 200 },
    { detectedAt: 300 }
  ];
  const result = meanTimeToRecover(incidents);
  assert.equal(result, 300, 'only 1 resolved incident: MTTR = 300 / 1 = 300');
});

test('latent-adv-022: MTTR empty returns 0', () => {
  assert.equal(meanTimeToRecover([]), 0);
});

test('latent-adv-023: MTTR all unresolved returns 0', () => {
  assert.equal(meanTimeToRecover([{ detectedAt: 100 }, { detectedAt: 200 }]), 0);
});

// ===== standardDeviation: must include ALL values and use Bessel's correction =====
// Sample standard deviation requires summing (value - mean)² for EVERY value
// in the dataset, then dividing by (N-1). Skipping any element or using wrong
// divisor produces incorrect results.

test('latent-adv-024: sample std dev of [2, 4, 4, 4, 5, 5, 7, 9]', () => {
  const values = [2, 4, 4, 4, 5, 5, 7, 9];
  const result = standardDeviation(values);
  const mean = 5;
  const sumSqDiff = values.reduce((s, v) => s + Math.pow(v - mean, 2), 0);
  const expected = Math.round(Math.sqrt(sumSqDiff / (values.length - 1)) * 10000) / 10000;
  assert.equal(result, expected, 'should use N-1 (sample) not N (population)');
});

test('latent-adv-025: sample std dev of two values', () => {
  const result = standardDeviation([0, 10]);
  const expected = Math.round(Math.sqrt(50) * 10000) / 10000;
  assert.equal(result, expected, 'sample std dev of [0,10]: sqrt((25+25)/1) = sqrt(50)');
});

test('latent-adv-026: std dev of identical values is 0', () => {
  assert.equal(standardDeviation([5, 5, 5, 5]), 0);
});

test('latent-adv-027: std dev single value returns 0', () => {
  assert.equal(standardDeviation([42]), 0);
});

// ===== exponentialMovingAverage: alpha weighting must match convention =====
// EMA formula: EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
// High alpha = responsive to new data. Swapping alpha and (1-alpha) inverts
// this property — high alpha becomes sluggish, low alpha becomes responsive.
// Bug only manifests when alpha != 0.5 (where both formulas are identical).

test('latent-adv-027a: EMA with high alpha responds quickly to step change', () => {
  const values = [10, 10, 10, 10, 50, 50, 50];
  const ema = exponentialMovingAverage(values, 0.9);
  // Correct: ema[4] = 0.9*50 + 0.1*10 = 46 (fast response)
  // Bug:     ema[4] = 0.1*50 + 0.9*10 = 14 (sluggish)
  assert.ok(ema[4] > 40,
    `EMA with alpha=0.9 should respond quickly to jump, got ${ema[4]}`);
});

test('latent-adv-027b: EMA with low alpha is smooth', () => {
  const values = [10, 50, 10, 50, 10, 50];
  const ema = exponentialMovingAverage(values, 0.1);
  // Correct: alpha=0.1 means 10% new, 90% old — very smooth
  // Last few values should be close to the smoothed average (~20-ish)
  // Bug: alpha=0.1 would give 90% new, 10% old — very jumpy
  const lastThree = ema.slice(-3);
  const range = Math.max(...lastThree) - Math.min(...lastThree);
  assert.ok(range < 15,
    `EMA with alpha=0.1 should be smooth (range < 15), got range ${range}`);
});

test('latent-adv-027c: EMA at alpha=0.5 is symmetric', () => {
  const values = [100, 0];
  const ema = exponentialMovingAverage(values, 0.5);
  // At alpha=0.5, both formulas give same result: 0.5*0 + 0.5*100 = 50
  assert.equal(ema[1], 50, 'alpha=0.5 should give equal weighting');
});

test('latent-adv-027d: EMA convergence direction with high alpha', () => {
  const values = [0, 0, 0, 100, 100, 100, 100, 100];
  const ema = exponentialMovingAverage(values, 0.8);
  // With correct alpha=0.8: after several 100s, EMA should be near 100
  assert.ok(ema[7] > 95,
    `after 5 consecutive 100s with alpha=0.8, EMA should converge near 100, got ${ema[7]}`);
});

// ===== runningBalance: must NOT mutate input entries =====
// The running balance function computes cumulative balances from entries.
// It must create new snapshot objects without modifying the original entries.
// If it mutates entry.delta, subsequent operations on the same entries array
// will see corrupted values.

test('latent-adv-027e: runningBalance does not modify input entries', () => {
  const entries = [
    { account: 'ops', delta: 100, seq: 1 },
    { account: 'ops', delta: -30, seq: 2 },
    { account: 'ops', delta: 50, seq: 3 }
  ];
  const originalDeltas = entries.map(e => e.delta);
  runningBalance(entries);
  const afterDeltas = entries.map(e => e.delta);
  assert.deepEqual(afterDeltas, originalDeltas,
    'input entries must not be mutated by runningBalance');
});

test('latent-adv-027f: entries reusable after runningBalance call', () => {
  const entries = [
    { account: 'A', delta: 500, seq: 1 },
    { account: 'A', delta: -200, seq: 2 }
  ];
  runningBalance(entries);
  // If entries were mutated, second call produces different results
  const snapshots = runningBalance(entries);
  assert.equal(snapshots[0].balance, 500,
    'first entry should still show delta=500');
  assert.equal(snapshots[1].balance, 300,
    'second entry should show cumulative 500 + (-200) = 300');
});

test('latent-adv-027g: runningBalance + balanceExposure consistency', () => {
  const { balanceExposure } = require('../../src/core/ledger');
  const entries = [
    { account: 'X', delta: 100, seq: 1 },
    { account: 'Y', delta: 200, seq: 2 },
    { account: 'X', delta: -50, seq: 3 }
  ];
  const entriesCopy = entries.map(e => ({ ...e }));
  runningBalance(entries);
  // balanceExposure should still see original deltas
  const exposure = balanceExposure(entries);
  const exposureCopy = balanceExposure(entriesCopy);
  assert.deepEqual(exposure, exposureCopy,
    'balanceExposure after runningBalance should match fresh copy');
});

// ===== replaySegment: uses >= startVersion (should be > for exclusive start) =====
// After processing events up to version N, we replay from N+1. Using >= re-includes
// the already-processed event at version N.

test('latent-adv-028: replaySegment excludes start version', () => {
  const events = [
    { id: 'e1', version: 5, idempotencyKey: 'k1' },
    { id: 'e2', version: 10, idempotencyKey: 'k2' },
    { id: 'e3', version: 15, idempotencyKey: 'k3' }
  ];
  const result = replaySegment(events, 5, 15);
  assert.equal(result.length, 2, 'start=5 should exclude version 5, include 10 and 15');
  assert.equal(result[0].version, 10);
});

test('latent-adv-029: replaySegment includes end version', () => {
  const events = [
    { id: 'e1', version: 1, idempotencyKey: 'k1' },
    { id: 'e2', version: 2, idempotencyKey: 'k2' },
    { id: 'e3', version: 3, idempotencyKey: 'k3' }
  ];
  const result = replaySegment(events, 1, 2);
  assert.ok(result.some(e => e.version === 2));
});

test('latent-adv-030: replaySegment empty range', () => {
  const events = [
    { id: 'e1', version: 10, idempotencyKey: 'k1' }
  ];
  assert.equal(replaySegment(events, 10, 10).length, 0);
});

// ===== uptimeCalculation: counts intervals with status !== 'up' as downtime =====
// but doesn't handle 'maintenance' status which should count as uptime for SLA purposes

test('latent-adv-031: uptime with all-up intervals', () => {
  const intervals = [
    { startTime: 0, endTime: 100, status: 'up' },
    { startTime: 100, endTime: 200, status: 'up' }
  ];
  assert.equal(uptimeCalculation(intervals), 1);
});

test('latent-adv-032: uptime with some downtime', () => {
  const intervals = [
    { startTime: 0, endTime: 75, status: 'up' },
    { startTime: 75, endTime: 100, status: 'down' }
  ];
  assert.equal(uptimeCalculation(intervals), 0.75);
});

test('latent-adv-033: uptime empty returns 1', () => {
  assert.equal(uptimeCalculation([]), 1);
});

// ===== capacityFragmentation: correct fragmentation calculation =====

test('latent-adv-034: no fragmentation with single pool', () => {
  assert.equal(capacityFragmentation([{ free: 100 }]), 0);
});

test('latent-adv-035: even fragmentation across pools', () => {
  const pools = [{ free: 50 }, { free: 50 }];
  assert.equal(capacityFragmentation(pools), 0.5, '1 - 50/100 = 0.5');
});

test('latent-adv-036: high fragmentation many small pools', () => {
  const pools = Array.from({ length: 10 }, () => ({ free: 10 }));
  assert.equal(capacityFragmentation(pools), 0.9);
});

test('latent-adv-037: zero free capacity returns 0', () => {
  assert.equal(capacityFragmentation([{ free: 0 }, { free: 0 }]), 0);
});

// ===== runningBalance: sequential balance snapshots =====

test('latent-adv-038: running balance accumulates correctly', () => {
  const entries = [
    { account: 'ops', delta: 100, seq: 1 },
    { account: 'ops', delta: -30, seq: 2 },
    { account: 'ops', delta: 50, seq: 3 }
  ];
  const snapshots = runningBalance(entries);
  assert.equal(snapshots[0].balance, 100);
  assert.equal(snapshots[1].balance, 70);
  assert.equal(snapshots[2].balance, 120);
});

test('latent-adv-039: running balance multi-account', () => {
  const entries = [
    { account: 'A', delta: 100, seq: 1 },
    { account: 'B', delta: 200, seq: 2 },
    { account: 'A', delta: -50, seq: 3 }
  ];
  const snapshots = runningBalance(entries);
  assert.equal(snapshots[2].balance, 50);
});

test('latent-adv-040: running balance empty returns empty', () => {
  assert.deepEqual(runningBalance([]), []);
});

// ===== ledgerIntegrity: duplicate detection =====

test('latent-adv-041: detects duplicate IDs', () => {
  const entries = [
    { id: 'e1', delta: 100 },
    { id: 'e1', delta: 200 }
  ];
  const result = ledgerIntegrity(entries);
  assert.equal(result.valid, false);
  assert.equal(result.errors[0].type, 'duplicate_id');
});

test('latent-adv-042: valid entries pass integrity', () => {
  const entries = [
    { id: 'e1', delta: 100 },
    { id: 'e2', delta: -50 }
  ];
  assert.equal(ledgerIntegrity(entries).valid, true);
});

test('latent-adv-043: empty passes integrity', () => {
  assert.equal(ledgerIntegrity([]).valid, true);
});

// ===== snapshotDelta: diff computation =====

test('latent-adv-044: detects added keys', () => {
  const delta = snapshotDelta({}, { a: 1 });
  assert.deepEqual(delta.a, { before: undefined, after: 1 });
});

test('latent-adv-045: detects removed keys', () => {
  const delta = snapshotDelta({ a: 1 }, {});
  assert.deepEqual(delta.a, { before: 1, after: undefined });
});

test('latent-adv-046: no changes returns empty', () => {
  assert.deepEqual(snapshotDelta({ a: 1 }, { a: 1 }), {});
});

test('latent-adv-047: detects value changes', () => {
  const delta = snapshotDelta({ a: 1 }, { a: 2 });
  assert.deepEqual(delta.a, { before: 1, after: 2 });
});

// ===== accountAgePartition: boundary precision =====

test('latent-adv-048: partitions at cutoff correctly', () => {
  const entries = [
    { seq: 1, account: 'A' },
    { seq: 5, account: 'A' },
    { seq: 10, account: 'A' }
  ];
  const result = accountAgePartition(entries, 5);
  assert.equal(result.old.length, 1);
  assert.equal(result.recent.length, 2);
});

test('latent-adv-049: all old entries', () => {
  const entries = [{ seq: 1 }, { seq: 2 }];
  const result = accountAgePartition(entries, 100);
  assert.equal(result.old.length, 2);
  assert.equal(result.recent.length, 0);
});

test('latent-adv-050: all recent entries', () => {
  const entries = [{ seq: 10 }, { seq: 20 }];
  const result = accountAgePartition(entries, 5);
  assert.equal(result.old.length, 0);
  assert.equal(result.recent.length, 2);
});

// ===== Matrix expansion for latent bugs =====

for (let i = 0; i < 25; i++) {
  test(`latent-adv-matrix-${String(51 + i).padStart(3, '0')}: route scoring batch ${i}`, () => {
    const routes = Array.from({ length: 3 + (i % 4) }, (_, j) => ({
      id: `r${j}`,
      latency: 10 + j * 15 + i,
      availableCapacity: 90 - j * 20,
      failures: j
    }));
    const scored = routeScorer(routes);
    assert.equal(scored.length, routes.length);
    for (let k = 0; k < scored.length - 1; k++) {
      assert.ok(scored[k].score >= scored[k + 1].score,
        `route ${k} score ${scored[k].score} should be >= route ${k+1} score ${scored[k + 1].score}`);
    }
  });
}

for (let i = 0; i < 20; i++) {
  test(`latent-adv-matrix-${String(76 + i).padStart(3, '0')}: transfer net-zero ${i}`, () => {
    const amount = 100 + i * 50;
    const result = crossAccountTransfer([], `src-${i}`, `dst-${i}`, amount);
    const totalDelta = result.reduce((s, e) => s + Number(e.delta), 0);
    assert.equal(totalDelta, 0, `transfer of ${amount} must be net zero`);
  });
}

for (let i = 0; i < 15; i++) {
  test(`latent-adv-matrix-${String(96 + i).padStart(3, '0')}: demand projection weighted ${i}`, () => {
    const vals = [100, 200];
    const w = [i + 1, 1];
    const result = demandProjection(vals, w);
    const expected = Math.round(((100 * (i + 1) + 200) / (i + 2)) * 100) / 100;
    assert.equal(result, expected);
  });
}

for (let i = 0; i < 15; i++) {
  test(`latent-adv-matrix-${String(111 + i).padStart(3, '0')}: MTTR partial resolution ${i}`, () => {
    const resolved = Array.from({ length: i + 1 }, (_, j) => ({
      detectedAt: j * 100,
      resolvedAt: j * 100 + 50
    }));
    const unresolved = Array.from({ length: 3 }, (_, j) => ({
      detectedAt: (i + 1 + j) * 100
    }));
    const all = [...resolved, ...unresolved];
    const result = meanTimeToRecover(all);
    const expected = Math.round((50 * (i + 1)) / (i + 1));
    assert.equal(result, expected,
      `with ${i + 1} resolved and 3 unresolved, MTTR should be 50 not ${result}`);
  });
}

for (let i = 0; i < 10; i++) {
  test(`latent-adv-matrix-${String(126 + i).padStart(3, '0')}: EMA convergence alpha=${(0.1 + i * 0.09).toFixed(2)} ${i}`, () => {
    const alpha = 0.1 + i * 0.09;
    const values = [0, 0, 0, 100, 100, 100, 100, 100, 100, 100];
    const ema = exponentialMovingAverage(values, alpha);
    // After many 100s, EMA should converge toward 100
    assert.ok(ema[9] > 80,
      `EMA with alpha=${alpha.toFixed(2)} should converge near 100 after 7 steps, got ${ema[9]}`);
    // Higher alpha should converge faster
    if (i > 0) {
      const prevAlpha = 0.1 + (i - 1) * 0.09;
      const prevEma = exponentialMovingAverage(values, prevAlpha);
      assert.ok(ema[5] >= prevEma[5] - 1,
        `higher alpha should converge at least as fast`);
    }
  });
}

for (let i = 0; i < 10; i++) {
  test(`latent-adv-matrix-${String(136 + i).padStart(3, '0')}: runningBalance immutability ${i}`, () => {
    const n = 3 + i;
    const entries = Array.from({ length: n }, (_, j) => ({
      account: 'acc', delta: (j + 1) * 10, seq: j + 1
    }));
    const originalDeltas = entries.map(e => e.delta);
    runningBalance(entries);
    assert.deepEqual(entries.map(e => e.delta), originalDeltas,
      'runningBalance must not mutate input entries');
  });
}

for (let i = 0; i < 10; i++) {
  test(`latent-adv-matrix-${String(146 + i).padStart(3, '0')}: correlation bounded ${i}`, () => {
    const n = 5 + i;
    const xs = Array.from({ length: n }, (_, j) => j * (i + 1) + Math.sin(j));
    const ys = Array.from({ length: n }, (_, j) => j * 2 + Math.cos(j) * (i + 1));
    const r = correlationCoefficient(xs, ys);
    assert.ok(r >= -1 && r <= 1,
      `Pearson r must be in [-1, 1], got ${r} for ${n}-element arrays`);
  });
}
