const { test } = require('node:test');
const assert = require('node:assert/strict');

const { buildDispatchManifest, dispatchWindowSchedule } = require('../../src/core/dispatch');
const { reconcileAccounts, netExposureByTenant } = require('../../src/core/ledger');
const { detectOutliers, weightedAverage } = require('../../src/core/statistics');
const { compactEvents } = require('../../src/core/replay');

// ===== buildDispatchManifest: totalUnits becomes stale after trim =====
// The function sums units correctly during insertion, but when items exceed
// maxPerRoute and the list is trimmed to the highest-priority items, it
// doesn't recalculate totalUnits. The total still reflects ALL original
// items including the removed ones.

test('latent-manifest-001: totalUnits correct without trimming', () => {
  const assignments = [
    { route: 'north', units: 10, priority: 5 },
    { route: 'north', units: 20, priority: 3 },
    { route: 'south', units: 5, priority: 1 }
  ];
  const manifest = buildDispatchManifest(assignments, 100);
  assert.equal(manifest.north.totalUnits, 30);
  assert.equal(manifest.south.totalUnits, 5);
});

test('latent-manifest-002: totalUnits must be recalculated after trimming', () => {
  const assignments = [
    { route: 'hub', units: 100, priority: 10 },
    { route: 'hub', units: 50, priority: 5 },
    { route: 'hub', units: 200, priority: 1 }
  ];
  const manifest = buildDispatchManifest(assignments, 2);
  const keptUnits = manifest.hub.items.reduce((s, i) => s + Number(i.units), 0);
  assert.equal(manifest.hub.totalUnits, keptUnits,
    'totalUnits should equal sum of kept items, not all original items');
});

test('latent-manifest-003: trimming drops lowest priority but totalUnits should reflect only kept items', () => {
  const assignments = [
    { route: 'A', units: 10, priority: 1 },
    { route: 'A', units: 20, priority: 2 },
    { route: 'A', units: 30, priority: 3 },
    { route: 'A', units: 40, priority: 4 },
    { route: 'A', units: 50, priority: 5 }
  ];
  const manifest = buildDispatchManifest(assignments, 3);
  assert.equal(manifest.A.items.length, 3);
  assert.equal(manifest.A.totalUnits, 120, 'should be 50+40+30=120, not 150');
});

test('latent-manifest-004: totalUnits consistent after trim with uniform priorities', () => {
  const assignments = Array.from({ length: 10 }, (_, i) => ({
    route: 'hub', units: 10, priority: 5
  }));
  const manifest = buildDispatchManifest(assignments, 4);
  assert.equal(manifest.hub.items.length, 4);
  assert.equal(manifest.hub.totalUnits, 40, 'should be 4*10=40, not 10*10=100');
});

test('latent-manifest-005: no trim needed means totalUnits is accurate', () => {
  const assignments = [
    { route: 'X', units: 100 },
    { route: 'X', units: 200 }
  ];
  const manifest = buildDispatchManifest(assignments, 5);
  assert.equal(manifest.X.totalUnits, 300);
});

test('latent-manifest-006: mixed routes only stale on trimmed route', () => {
  const assignments = [
    { route: 'small', units: 10, priority: 1 },
    { route: 'big', units: 100, priority: 3 },
    { route: 'big', units: 200, priority: 2 },
    { route: 'big', units: 300, priority: 1 }
  ];
  const manifest = buildDispatchManifest(assignments, 2);
  assert.equal(manifest.small.totalUnits, 10, 'small route untrimmed, should be correct');
  const bigKept = manifest.big.items.reduce((s, i) => s + Number(i.units), 0);
  assert.equal(manifest.big.totalUnits, bigKept,
    'big route trimmed, totalUnits must match kept items');
});

test('latent-manifest-007: maxPerRoute=1 with many items has correct totalUnits', () => {
  const assignments = Array.from({ length: 8 }, (_, i) => ({
    route: 'hub', units: (i + 1) * 100, priority: i + 1
  }));
  const manifest = buildDispatchManifest(assignments, 1);
  assert.equal(manifest.hub.items.length, 1);
  assert.equal(manifest.hub.totalUnits, 800,
    'only highest priority item (800 units) should be counted');
});

// ===== dispatchWindowSchedule: interval miscalculation =====

test('latent-schedule-008: two slots in 60 min at 30 and 60', () => {
  const result = dispatchWindowSchedule([{ id: 'a' }, { id: 'b' }], 60);
  assert.equal(result[0].scheduledAt, 30);
  assert.equal(result[1].scheduledAt, 60);
});

test('latent-schedule-009: single slot gets entire window', () => {
  const result = dispatchWindowSchedule([{ id: 'x' }], 100);
  assert.equal(result[0].scheduledAt, 100);
});

test('latent-schedule-010: three slots evenly at 30, 60, 90', () => {
  const result = dispatchWindowSchedule([{ id: '1' }, { id: '2' }, { id: '3' }], 90);
  assert.equal(result[0].scheduledAt, 30);
  assert.equal(result[1].scheduledAt, 60);
  assert.equal(result[2].scheduledAt, 90);
});

test('latent-schedule-011: last slot is exactly at window end', () => {
  const slots = Array.from({ length: 5 }, (_, i) => ({ id: `s${i}` }));
  const result = dispatchWindowSchedule(slots, 200);
  assert.equal(result[result.length - 1].scheduledAt, 200);
});

test('latent-schedule-012: four slots in 120 min at 30, 60, 90, 120', () => {
  const result = dispatchWindowSchedule(
    [{ id: '1' }, { id: '2' }, { id: '3' }, { id: '4' }], 120
  );
  assert.equal(result[0].scheduledAt, 30);
  assert.equal(result[3].scheduledAt, 120);
});

// ===== reconcileAccounts: debits stored as negative =====

test('latent-reconcile-013: debits tracked as positive absolute values', () => {
  const entries = [
    { account: 'ops', delta: -100 },
    { account: 'ops', delta: -50 }
  ];
  const result = reconcileAccounts(entries);
  assert.equal(result.ops.debits, 150, 'debits should be positive absolute values');
});

test('latent-reconcile-014: credits and debits tracked separately', () => {
  const entries = [
    { account: 'a', delta: 200 },
    { account: 'a', delta: -80 }
  ];
  const result = reconcileAccounts(entries);
  assert.equal(result.a.credits, 200);
  assert.equal(result.a.debits, 80);
  assert.equal(result.a.net, 120);
});

test('latent-reconcile-015: adjustment factor applies to net', () => {
  const entries = [{ account: 'x', delta: 100 }, { account: 'x', delta: 50 }];
  const adjustments = [{ account: 'x', factor: 1.1 }];
  const result = reconcileAccounts(entries, adjustments);
  assert.equal(result.x.net, 165);
});

// ===== compactEvents: keeps first version on dedup instead of last =====
// When multiple events share the same idempotencyKey within a window,
// compaction should keep the LATEST (last) version, not the first.
// This is a classic event-sourcing "last write wins" semantic.

test('latent-compact-016: duplicate key keeps latest version', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'k1', timestamp: 10, data: 'old' },
    { id: 'e2', idempotencyKey: 'k1', timestamp: 20, data: 'new' }
  ];
  const result = compactEvents(events, 100);
  assert.equal(result.length, 1);
  assert.equal(result[0].data, 'new',
    'should keep latest version (last write wins), not first version');
});

test('latent-compact-017: three versions of same key keeps last', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'k1', timestamp: 5, version: 1 },
    { id: 'e2', idempotencyKey: 'k1', timestamp: 10, version: 2 },
    { id: 'e3', idempotencyKey: 'k1', timestamp: 15, version: 3 }
  ];
  const result = compactEvents(events, 100);
  assert.equal(result.length, 1);
  assert.equal(result[0].version, 3);
});

test('latent-compact-018: different keys both kept', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'k1', timestamp: 10, data: 'a' },
    { id: 'e2', idempotencyKey: 'k2', timestamp: 20, data: 'b' }
  ];
  const result = compactEvents(events, 100);
  assert.equal(result.length, 2);
});

test('latent-compact-019: mixed unique and duplicate keys', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'k1', timestamp: 10, version: 1 },
    { id: 'e2', idempotencyKey: 'k2', timestamp: 20, version: 1 },
    { id: 'e3', idempotencyKey: 'k1', timestamp: 30, version: 2 }
  ];
  const result = compactEvents(events, 100);
  assert.equal(result.length, 2);
  const k1Event = result.find((e) => e.idempotencyKey === 'k1');
  assert.equal(k1Event.version, 2, 'k1 should be version 2 (latest)');
});

test('latent-compact-020: update replaces stale state correctly', () => {
  const events = [
    { id: 'e1', idempotencyKey: 'order-123', timestamp: 100, status: 'pending' },
    { id: 'e2', idempotencyKey: 'order-123', timestamp: 200, status: 'confirmed' },
    { id: 'e3', idempotencyKey: 'order-123', timestamp: 300, status: 'shipped' }
  ];
  const result = compactEvents(events, 500);
  assert.equal(result.length, 1);
  assert.equal(result[0].status, 'shipped',
    'compacted state should be "shipped" not "pending"');
});

// ===== netExposureByTenant: uses abs() making gross not net =====
// In risk management, NET exposure accounts for offsetting positions.
// A tenant with +100 and -80 has NET exposure of +20, not GROSS of 180.

test('latent-exposure-021: net exposure with offsetting positions', () => {
  const entries = [
    { tenant: 'acme', delta: 100 },
    { tenant: 'acme', delta: -80 }
  ];
  const result = netExposureByTenant(entries);
  assert.equal(result.acme, 20,
    'net exposure should be 100 + (-80) = 20, not |100| + |80| = 180');
});

test('latent-exposure-022: fully hedged position has zero net exposure', () => {
  const entries = [
    { tenant: 'corp', delta: 500 },
    { tenant: 'corp', delta: -500 }
  ];
  const result = netExposureByTenant(entries);
  assert.equal(result.corp, 0,
    'fully offsetting positions should be net zero');
});

test('latent-exposure-023: negative-only positions show negative exposure', () => {
  const entries = [
    { tenant: 'beta', delta: -100 },
    { tenant: 'beta', delta: -200 }
  ];
  const result = netExposureByTenant(entries);
  assert.equal(result.beta, -300,
    'all-negative deltas should sum to -300, not +300');
});

test('latent-exposure-024: mixed tenants with negative deltas', () => {
  const entries = [
    { tenant: 't1', delta: -100 },
    { tenant: 't2', delta: 300 },
    { tenant: 't1', delta: 200 }
  ];
  const result = netExposureByTenant(entries);
  assert.equal(result.t1, 100);
  assert.equal(result.t2, 300);
});

test('latent-exposure-025: single negative entry preserved as negative', () => {
  const entries = [{ tenant: 'solo', delta: -42 }];
  const result = netExposureByTenant(entries);
  assert.equal(result.solo, -42);
});

// ===== detectOutliers: ceil vs floor on Q3 changes detection boundary =====
// Using ceil for Q3 pushes it one position higher in the sorted array,
// widening the IQR and raising the upper fence. Values that should be
// flagged as outliers are missed because the upper bound is too generous.

test('latent-outlier-026: value just above correct upper fence detected', () => {
  const values = [1, 3, 5, 7, 9, 11, 20];
  const outliers = detectOutliers(values, 1.5);
  assert.ok(outliers.includes(20),
    '20 should be outlier: correct Q3=9, IQR=6, upper=18');
});

test('latent-outlier-027: borderline outlier missed by widened IQR', () => {
  const values = [1, 2, 3, 4, 5, 6, 7, 13];
  const outliers = detectOutliers(values, 1.5);
  assert.ok(outliers.includes(13),
    '13 should be outlier: correct Q3=6, IQR=4, upper=12');
});

test('latent-outlier-028: clear outlier detected regardless', () => {
  const values = [1, 2, 3, 4, 5, 6, 7, 100];
  const outliers = detectOutliers(values, 1.5);
  assert.ok(outliers.includes(100));
});

test('latent-outlier-029: tight dataset has no outliers', () => {
  const values = [10, 11, 12, 13, 14, 15, 16, 17];
  assert.equal(detectOutliers(values, 1.5).length, 0);
});

test('latent-outlier-030: odd-length dataset quartile precision', () => {
  const values = [2, 4, 6, 8, 10, 12, 14, 16, 25];
  const outliers = detectOutliers(values, 1.5);
  assert.ok(outliers.includes(25),
    'correct Q3=14, IQR=10, upper=29 - borderline but should still detect with ceil shift');
});

// ===== weightedAverage: divides by count instead of weight sum =====

test('latent-wavg-031: equal weights gives arithmetic mean', () => {
  assert.equal(weightedAverage([10, 20, 30], [1, 1, 1]), 20);
});

test('latent-wavg-032: unequal weights', () => {
  assert.equal(weightedAverage([100, 0], [3, 1]), 75);
});

test('latent-wavg-033: single value returns that value', () => {
  assert.equal(weightedAverage([42], [5]), 42);
});

test('latent-wavg-034: heavily weighted first element', () => {
  assert.equal(weightedAverage([10, 0], [9, 1]), 9);
});

test('latent-wavg-035: weights summing to more than count', () => {
  assert.equal(weightedAverage([50, 100], [2, 3]), 80);
});

// ===== Matrix expansion =====

for (let i = 0; i < 8; i++) {
  test(`latent-matrix-${String(36 + i).padStart(3, '0')}: manifest trim recalc batch ${i}`, () => {
    const n = 5 + i;
    const assignments = Array.from({ length: n }, (_, j) => ({
      route: 'main', units: (j + 1) * 10, priority: j + 1
    }));
    const manifest = buildDispatchManifest(assignments, 3);
    const keptTotal = manifest.main.items.reduce((s, item) => s + Number(item.units), 0);
    assert.equal(manifest.main.totalUnits, keptTotal,
      `after trimming ${n} items to 3, totalUnits must equal sum of kept items`);
  });
}

for (let i = 0; i < 7; i++) {
  test(`latent-matrix-${String(44 + i).padStart(3, '0')}: net exposure sign preservation ${i}`, () => {
    const delta = -50 * (i + 1);
    const entries = [{ tenant: `t${i}`, delta }];
    const result = netExposureByTenant(entries);
    assert.equal(result[`t${i}`], delta,
      `negative delta ${delta} should be preserved, not abs()'d to ${Math.abs(delta)}`);
  });
}
