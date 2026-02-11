const { test } = require('node:test');
const assert = require('node:assert/strict');

const { tieredPricing, compoundMargin } = require('../../src/core/economics');
const { exponentialForecast } = require('../../src/core/capacity');
const { compositeBreachScore, penaltyEscalation } = require('../../src/core/sla');
const { scopedPermission } = require('../../src/core/security');
const { geoAwareRoute } = require('../../src/core/routing');

// ===== tieredPricing: flat rate vs marginal rate per tier =====

test('domain-tiered-001: basic tiered pricing applies marginal rates', () => {
  const tiers = [
    { upTo: 100, rate: 1.0 },
    { upTo: 500, rate: 0.8 },
    { upTo: Infinity, rate: 0.5 }
  ];
  const cost = tieredPricing(200, tiers);
  const expected = 100 * 1.0 + 100 * 0.8;
  assert.equal(cost, expected);
});

test('domain-tiered-002: all units in first tier', () => {
  const tiers = [
    { upTo: 100, rate: 2.0 },
    { upTo: 500, rate: 1.0 }
  ];
  assert.equal(tieredPricing(50, tiers), 100);
});

test('domain-tiered-003: units spanning three tiers', () => {
  const tiers = [
    { upTo: 10, rate: 5.0 },
    { upTo: 50, rate: 3.0 },
    { upTo: Infinity, rate: 1.0 }
  ];
  const cost = tieredPricing(100, tiers);
  assert.equal(cost, 10 * 5.0 + 40 * 3.0 + 50 * 1.0);
});

test('domain-tiered-004: exact tier boundary uses lower rate', () => {
  const tiers = [
    { upTo: 100, rate: 2.0 },
    { upTo: 200, rate: 1.0 }
  ];
  assert.equal(tieredPricing(100, tiers), 200);
});

test('domain-tiered-005: large volume with steep tier drops', () => {
  const tiers = [
    { upTo: 1000, rate: 10 },
    { upTo: 5000, rate: 5 },
    { upTo: Infinity, rate: 1 }
  ];
  assert.equal(tieredPricing(6000, tiers), 1000 * 10 + 4000 * 5 + 1000 * 1);
});

test('domain-tiered-006: zero units returns zero', () => {
  assert.equal(tieredPricing(0, [{ upTo: 100, rate: 5 }]), 0);
});

test('domain-tiered-007: single tier applies to all units', () => {
  assert.equal(tieredPricing(50, [{ upTo: Infinity, rate: 3 }]), 150);
});

// ===== compoundMargin: additive vs multiplicative compounding =====

test('domain-compound-008: two periods compound multiplicatively', () => {
  const periods = [{ margin: 0.1 }, { margin: 0.1 }];
  const result = compoundMargin(periods);
  const expected = Math.round((1.1 * 1.1 - 1) * 10000) / 10000;
  assert.equal(result, expected);
});

test('domain-compound-009: negative margin reduces compounded total', () => {
  const periods = [{ margin: 0.2 }, { margin: -0.1 }];
  const result = compoundMargin(periods);
  const expected = Math.round((1.2 * 0.9 - 1) * 10000) / 10000;
  assert.equal(result, expected);
});

test('domain-compound-010: three periods compound correctly', () => {
  const periods = [{ margin: 0.05 }, { margin: 0.10 }, { margin: 0.03 }];
  const result = compoundMargin(periods);
  const expected = Math.round((1.05 * 1.10 * 1.03 - 1) * 10000) / 10000;
  assert.equal(result, expected);
});

test('domain-compound-011: zero margin period has no effect on compound', () => {
  const periods = [{ margin: 0.1 }, { margin: 0 }, { margin: 0.1 }];
  const result = compoundMargin(periods);
  const expected = Math.round((1.1 * 1.0 * 1.1 - 1) * 10000) / 10000;
  assert.equal(result, expected);
});

test('domain-compound-012: single period returns that margin', () => {
  assert.equal(compoundMargin([{ margin: 0.15 }]), 0.15);
});

// ===== exponentialForecast: alpha inverted =====

test('domain-forecast-013: alpha=1 returns last observation', () => {
  assert.equal(exponentialForecast([10, 20, 30], 1.0), 30);
});

test('domain-forecast-014: alpha=0 returns first observation', () => {
  assert.equal(exponentialForecast([10, 20, 30], 0.0), 10);
});

test('domain-forecast-015: high alpha weights recent data more', () => {
  const history = [100, 100, 100, 200];
  const highAlpha = exponentialForecast(history, 0.9);
  const lowAlpha = exponentialForecast(history, 0.1);
  assert.ok(highAlpha > lowAlpha,
    `high alpha ${highAlpha} should be closer to 200 than low alpha ${lowAlpha}`);
});

test('domain-forecast-016: alpha=0.5 two values averages them', () => {
  assert.equal(exponentialForecast([0, 100], 0.5), 50);
});

test('domain-forecast-017: constant history returns constant', () => {
  assert.equal(exponentialForecast([50, 50, 50, 50], 0.3), 50);
  assert.equal(exponentialForecast([50, 50, 50, 50], 0.7), 50);
});

test('domain-forecast-018: trending up with high alpha tracks closely', () => {
  const result = exponentialForecast([10, 20, 30, 40, 50], 0.8);
  assert.ok(result >= 40, `forecast ${result} should track recent (>=40)`);
});

// ===== compositeBreachScore: average vs max for correlated dimensions =====

test('domain-breach-019: single dimension returns its score', () => {
  assert.equal(compositeBreachScore([{ score: 0.8, weight: 1 }]), 0.8);
});

test('domain-breach-020: correlated high dims should take max not average', () => {
  const dimensions = [
    { score: 0.9, weight: 1, correlated: true },
    { score: 0.85, weight: 1, correlated: true }
  ];
  const result = compositeBreachScore(dimensions);
  assert.equal(result, 0.9, 'correlated dimensions should report worst case');
});

test('domain-breach-021: independent dimensions average correctly', () => {
  assert.equal(compositeBreachScore([
    { score: 0.6, weight: 1 },
    { score: 0.4, weight: 1 }
  ]), 0.5);
});

// ===== penaltyEscalation: off-by-one in exponent =====
// Should be base * 2^(count-1): breach 1=base, 2=2*base, 3=4*base
// Bug: base * 2^count: breach 1=2*base, 2=4*base, 3=8*base

test('domain-penalty-022: first breach applies exactly base penalty', () => {
  assert.equal(penaltyEscalation(1, 100, 10000), 100,
    'first breach should be base*2^0=100, not base*2^1=200');
});

test('domain-penalty-023: second breach doubles', () => {
  assert.equal(penaltyEscalation(2, 100, 10000), 200);
});

test('domain-penalty-024: third breach quadruples', () => {
  assert.equal(penaltyEscalation(3, 100, 10000), 400);
});

test('domain-penalty-025: penalty capped at max', () => {
  assert.equal(penaltyEscalation(20, 100, 5000), 5000);
});

test('domain-penalty-026: zero breaches returns zero', () => {
  assert.equal(penaltyEscalation(0, 100, 1000), 0);
});

test('domain-penalty-027: fifth breach penalty is 1600 not 3200', () => {
  assert.equal(penaltyEscalation(5, 100, 100000), 1600,
    'base*2^4=1600, not base*2^5=3200');
});

// ===== scopedPermission: no wildcard hierarchy support =====

test('domain-scope-028: exact match grants permission', () => {
  assert.equal(scopedPermission(['admin.read', 'admin.write'], 'admin.read'), true);
});

test('domain-scope-029: wildcard scope grants sub-permissions', () => {
  assert.equal(scopedPermission(['admin.*'], 'admin.read'), true);
});

test('domain-scope-030: wildcard grants nested sub-permissions', () => {
  assert.equal(scopedPermission(['admin.*'], 'admin.users.delete'), true);
});

test('domain-scope-031: root wildcard grants everything', () => {
  assert.equal(scopedPermission(['*'], 'anything.here'), true);
});

test('domain-scope-032: no matching scope denies', () => {
  assert.equal(scopedPermission(['user.read'], 'admin.write'), false);
});

// ===== geoAwareRoute: cos(degrees) instead of cos(radians) =====
// The developer correctly implemented longitude scaling with cos(latitude)
// but forgot to convert degrees to radians. Math.cos() expects radians.
// At latitude 60: cos(60 rad)≈-0.95 instead of cos(60°)=0.5
// This overweights longitude differences and picks wrong hubs.

test('domain-geo-033: picks closest hub with correct scaling at lat=60', () => {
  const hubs = [
    { id: 'east', lat: 60, lng: 8 },
    { id: 'south', lat: 56, lng: 1 }
  ];
  const target = { lat: 60, lng: 0 };
  const result = geoAwareRoute(hubs, target);
  assert.equal(result.id, 'east',
    'at lat 60°, 8° lng ≈ 4km equiv (cos60°=0.5), 4° lat ≈ 4km. East is closer.');
});

test('domain-geo-034: lat=30 longitude overweighted by radian bug', () => {
  const hubs = [
    { id: 'lng-near', lat: 30, lng: 5 },
    { id: 'lat-near', lat: 28, lng: 0 }
  ];
  const target = { lat: 30, lng: 0 };
  const result = geoAwareRoute(hubs, target);
  assert.equal(result.id, 'lat-near',
    'at lat 30°, 5° lng ≈ 4.3km (cos30°=0.866), 2° lat ≈ 2km. lat-near closer.');
});

test('domain-geo-035: equator routing unaffected (cos0=1)', () => {
  const hubs = [
    { id: 'close', lat: 0, lng: 2 },
    { id: 'far', lat: 0, lng: 10 }
  ];
  const result = geoAwareRoute(hubs, { lat: 0, lng: 0 });
  assert.equal(result.id, 'close');
});

test('domain-geo-036: exact match returns that hub', () => {
  const hubs = [
    { id: 'match', lat: 40, lng: -74 },
    { id: 'other', lat: 0, lng: 0 }
  ];
  const result = geoAwareRoute(hubs, { lat: 40, lng: -74 });
  assert.equal(result.id, 'match');
});

test('domain-geo-037: high latitude routing most affected', () => {
  const hubs = [
    { id: 'lng-sep', lat: 75, lng: 15 },
    { id: 'lat-sep', lat: 68, lng: 1 }
  ];
  const target = { lat: 75, lng: 0 };
  const result = geoAwareRoute(hubs, target);
  assert.equal(result.id, 'lng-sep',
    'at 75° lat, 15° lng ≈ 3.9km (cos75°=0.259), 7° lat = 7km. lng-sep is closer.');
});

test('domain-geo-038: negative coordinates handled correctly', () => {
  const hubs = [
    { id: 'a', lat: -10, lng: -10 },
    { id: 'b', lat: 10, lng: 10 }
  ];
  const result = geoAwareRoute(hubs, { lat: -9, lng: -9 });
  assert.equal(result.id, 'a');
});

// ===== Matrix expansion =====

for (let i = 0; i < 12; i++) {
  test(`domain-matrix-${String(39 + i).padStart(3, '0')}: tiered pricing batch ${i}`, () => {
    const units = 50 + i * 75;
    const tiers = [
      { upTo: 100, rate: 10 },
      { upTo: 300, rate: 7 },
      { upTo: Infinity, rate: 4 }
    ];
    let expected = 0;
    let remaining = units;
    let prev = 0;
    for (const tier of tiers) {
      const inTier = Math.min(remaining, tier.upTo - prev);
      expected += inTier * tier.rate;
      remaining -= inTier;
      prev = tier.upTo;
      if (remaining <= 0) break;
    }
    expected = Math.round(expected * 100) / 100;
    assert.equal(tieredPricing(units, tiers), expected);
  });
}
