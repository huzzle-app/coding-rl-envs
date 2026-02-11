const test = require('node:test');
const assert = require('node:assert/strict');
const analytics = require('../../services/analytics/service');

test('computeFleetHealth returns ratio of operational vessels', () => {
  const vessels = [
    { vesselId: 'v1', operational: true, throughput: 100 },
    { vesselId: 'v2', operational: false, throughput: 50 },
  ];
  const result = analytics.computeFleetHealth(vessels);
  assert.equal(result.active, 1);
  assert.equal(result.total, 2);
});

test('trendAnalysis detects rising trend', () => {
  const result = analytics.trendAnalysis([1, 2, 3, 4, 5], 5);
  assert.equal(result.trend, 'rising');
});

test('anomalyReport flags outliers', () => {
  const values = [10, 10, 10, 10, 100];
  const result = analytics.anomalyReport(values, 2);
  assert.ok(result.anomalies.length > 0);
});

test('fleetSummary computes average throughput', () => {
  const vessels = [
    { vesselId: 'v1', operational: true, throughput: 100 },
    { vesselId: 'v2', operational: true, throughput: 200 },
  ];
  const result = analytics.fleetSummary(vessels);
  assert.equal(result.operational, 2);
  assert.ok(result.avgThroughput > 0);
});
