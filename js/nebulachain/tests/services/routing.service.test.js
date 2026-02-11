const test = require('node:test');
const assert = require('node:assert/strict');
const routing = require('../../services/routing/service');

test('computeOptimalPath returns total distance', () => {
  const result = routing.computeOptimalPath([
    { from: 'A', to: 'B', distance: 100 },
    { from: 'B', to: 'C', distance: 200 },
  ]);
  assert.equal(result.totalDistance, 300);
  assert.equal(result.legCount, 2);
});

test('channelHealthScore weights latency and reliability', () => {
  const score = routing.channelHealthScore({ latencyMs: 100, reliability: 0.9 });
  assert.ok(score > 0);
});

test('estimateArrivalTime computes base transit', () => {
  const time = routing.estimateArrivalTime(120, 10, 1.0);
  assert.ok(time > 0 && time < Infinity);
});

test('routeRiskScore accumulates leg risk', () => {
  const risk = routing.routeRiskScore([
    { congestion: 3, hazardous: false },
    { congestion: 8, hazardous: true },
  ]);
  assert.ok(risk > 0);
});
