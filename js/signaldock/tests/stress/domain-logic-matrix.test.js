const test = require('node:test');
const assert = require('node:assert/strict');

const { planWindowPrioritized, BerthSlot } = require('../../src/core/scheduling');
const { RouteTable, planMultiLegWithCost, estimateRouteCost } = require('../../src/core/routing');
const { policyForLoad } = require('../../src/core/policy');
const { weightedPercentile, exponentialMovingAverage, mean } = require('../../src/core/statistics');
const { DispatchTicket, VesselManifest, Severity, SLA_BY_SEVERITY, mergeBatchTickets } = require('../../src/models/dispatch-ticket');

const CASES = 500;

for (let idx = 0; idx < CASES; idx += 1) {
  test(`domain-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 8;

    if (variant === 0) {
      // planWindowPrioritized: overrides must be applied BEFORE selection
      const vessels = [
        { id: 'low', urgency: 1, eta: '08:00' },
        { id: 'mid', urgency: 5 + (idx % 3), eta: '09:00' },
        { id: 'high', urgency: 10, eta: '07:00' },
      ];
      const overrides = [{ id: 'low', urgency: 20 + (idx % 10) }];
      const result = planWindowPrioritized(vessels, 2, overrides);
      const ids = result.map(v => v.id);
      assert.ok(ids.includes('low'),
        `vessel 'low' overridden to urgency ${overrides[0].urgency} should be selected, got [${ids}]`);
    }

    if (variant === 1) {
      // bestRouteWeighted: congestion keyed by channel name, not metadata.region
      const table = new RouteTable();
      table.register('fastCongested', 5, { region: 'zone-A' });
      table.register('slowClear', 15, { region: 'zone-B' });
      const congestion = { fastCongested: 30 + (idx % 20), slowClear: 0 };
      const best = table.bestRouteWeighted(congestion);
      assert.equal(best.channel, 'slowClear',
        `congested route should lose; metadata.region should not be used as lookup key`);
    }

    if (variant === 2) {
      // channelsByLatency should exclude blocked channels
      const table = new RouteTable();
      table.register('ch-a', 5, {});
      table.register('ch-b', 3, {});
      table.register('ch-c', 8, {});
      table.register('ch-d', 1, {});
      table.block('ch-a');
      table.block('ch-c');
      const sorted = table.channelsByLatency();
      const channels = sorted.map(r => r.channel);
      assert.ok(!channels.includes('ch-a'),
        `blocked channel 'ch-a' should not appear in channelsByLatency`);
      assert.ok(!channels.includes('ch-c'),
        `blocked channel 'ch-c' should not appear in channelsByLatency`);
      assert.equal(sorted.length, 2,
        `should only return 2 unblocked channels, got ${sorted.length}`);
    }

    if (variant === 3) {
      // policyForLoad: must use ratio, not absolute thresholds
      const maxLoad = 200 + (idx % 300);
      const highRatio = 0.85 + (idx % 10) * 0.01;
      const currentLoad = Math.round(maxLoad * highRatio);
      const result = policyForLoad(currentLoad, maxLoad);
      assert.notEqual(result, 'normal',
        `load ${currentLoad}/${maxLoad} (ratio=${highRatio.toFixed(2)}) should not be 'normal', got '${result}'`);
      const lowRatio = 0.1 + (idx % 20) * 0.01;
      const lowLoad = Math.round(maxLoad * lowRatio);
      const lowResult = policyForLoad(lowLoad, maxLoad);
      assert.equal(lowResult, 'normal',
        `load ${lowLoad}/${maxLoad} (ratio=${lowRatio.toFixed(2)}) should be 'normal', got '${lowResult}'`);
    }

    if (variant === 4) {
      // timeToExpiry: isUrgent should use SLA ratio, not absolute minutes
      const sla = 30 + (idx % 60);
      const ticket = new DispatchTicket(`T-${idx}`, 3, sla);
      const elapsed = sla * 0.75;
      const future = ticket.createdAt + elapsed * 60000;
      const result = ticket.timeToExpiry(future);
      const remaining = result.minutes;
      const ratio = remaining / sla;
      if (ratio > 0.2 && remaining < 10) {
        assert.equal(result.isUrgent, false,
          `remaining=${remaining.toFixed(1)}min of ${sla}min SLA (ratio=${ratio.toFixed(2)}) is not urgent`);
      }
      if (ratio < 0.2 && remaining > 10) {
        assert.equal(result.isUrgent, true,
          `remaining=${remaining.toFixed(1)}min of ${sla}min SLA (ratio=${ratio.toFixed(2)}) IS urgent`);
      }
    }

    if (variant === 5) {
      // weightedPercentile: cumulative weight >= target should return value
      const n = 5 + (idx % 6);
      const values = Array.from({ length: n }, (_, i) => (i + 1) * 10);
      const weights = Array.from({ length: n }, () => 1);
      const wp50 = weightedPercentile(values, weights, 50);
      const targetWeight = 0.5 * n;
      const medianIdx = Math.ceil(targetWeight) - 1;
      const expectedMedian = values[medianIdx];
      assert.equal(wp50, expectedMedian,
        `weightedPercentile p50 of [${values}] should be ${expectedMedian}, got ${wp50}`);
    }

    if (variant === 6) {
      // EMA with alpha: smoothing weights should match alpha semantics
      const values = [10, 20, 30, 40, 50].map(v => v + (idx % 10));
      const alpha = 0.3;
      const ema = exponentialMovingAverage(values, alpha);
      assert.equal(ema.length, values.length);
      assert.equal(ema[0], values[0], 'EMA[0] should equal first value');
      // With alpha=0.3, new values get 30% weight, history 70% → heavy smoothing
      // EMA should lag significantly behind raw increasing values
      const lastEma = ema[ema.length - 1];
      const lastVal = values[values.length - 1];
      const secondLastVal = values[values.length - 2];
      assert.ok(lastEma < secondLastVal,
        `EMA(alpha=0.3) should lag behind: ema[last]=${lastEma.toFixed(1)} should be < values[-2]=${secondLastVal}`);
    }

    if (variant === 7) {
      // planMultiLegWithCost: should use SELECTED route's latency, not first option
      const legs = [
        { legId: 'L1', options: [
          { channel: 'expensive', latency: 50 + (idx % 10) },
          { channel: 'cheap', latency: 3 },
        ]},
        { legId: 'L2', options: [
          { channel: 'pricey', latency: 40 },
          { channel: 'budget', latency: 2 + (idx % 5) },
        ]},
      ];
      const baseCost = 100;
      const result = planMultiLegWithCost(legs, [], baseCost);
      assert.ok(result.success);
      let expectedTotal = 0;
      for (const leg of result.legs) {
        expectedTotal += estimateRouteCost({ latency: leg.latency }, baseCost);
      }
      assert.equal(result.totalCost, expectedTotal,
        `totalCost should use selected latencies (${expectedTotal}), got ${result.totalCost}`);
    }
  });
}
