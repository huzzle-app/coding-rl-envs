/**
 * Billing Metering Tests (~30 tests)
 */

const { UsageMeter } = require('../../../services/billing/src/services/metering');

describe('UsageMeter', () => {
  let meter;

  beforeEach(() => {
    meter = new UsageMeter();
  });

  describe('usage recording', () => {
    test('records data points', () => {
      const result = meter.recordUsage('tenant-1', 100, 1024);
      expect(result.dataPoints).toBe(100);
      expect(result.bytesIngested).toBe(1024);
    });

    test('accumulates usage across calls', () => {
      meter.recordUsage('tenant-1', 100, 1024);
      const result = meter.recordUsage('tenant-1', 200, 2048);
      expect(result.dataPoints).toBe(300);
      expect(result.bytesIngested).toBe(3072);
    });

    test('different tenants have separate usage', () => {
      meter.recordUsage('tenant-1', 100, 1024);
      meter.recordUsage('tenant-2', 200, 2048);
      expect(meter.getUsage('tenant-1').dataPoints).toBe(100);
      expect(meter.getUsage('tenant-2').dataPoints).toBe(200);
    });

    test('getUsage for unknown tenant returns null', () => {
      expect(meter.getUsage('unknown')).toBeNull();
    });

    test('resetUsage clears tenant data', () => {
      meter.recordUsage('tenant-1', 100, 1024);
      meter.resetUsage('tenant-1');
      expect(meter.getUsage('tenant-1')).toBeNull();
    });
  });

  describe('cost calculation', () => {
    test('zero usage costs zero', () => {
      meter.recordUsage('tenant-1', 0, 0);
      const cost = meter.calculateCost('tenant-1');
      expect(cost.totalCost).toBe(0);
    });

    test('free tier has no cost', () => {
      meter.recordUsage('tenant-1', 100, 0.5 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('tenant-1');
      expect(cost.totalCost).toBe(0);
    });

    test('second tier pricing applied', () => {
      meter.recordUsage('tenant-1', 100, 5 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('tenant-1');
      expect(cost.totalCost).toBeGreaterThan(0);
    });

    test('breakdown includes all tiers used', () => {
      meter.recordUsage('tenant-1', 100, 50 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('tenant-1');
      expect(cost.breakdown.length).toBeGreaterThan(1);
    });

    test('unknown tenant costs zero', () => {
      const cost = meter.calculateCost('unknown');
      expect(cost.total).toBe(0);
    });

    test('cost is rounded to cents', () => {
      meter.recordUsage('tenant-1', 100, 15 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('tenant-1');
      const cents = cost.totalCost * 100;
      expect(cents).toBe(Math.round(cents));
    });

    test('large volume uses lowest per-GB rate', () => {
      meter.recordUsage('tenant-1', 100, 2000 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('tenant-1');
      const lastTier = cost.breakdown[cost.breakdown.length - 1];
      expect(lastTier.rate).toBe(0.03);
    });

    test('cost increases monotonically with volume', () => {
      meter.recordUsage('t1', 100, 10 * 1024 * 1024 * 1024);
      const cost1 = meter.calculateCost('t1');
      meter.resetUsage('t1');
      meter.recordUsage('t1', 100, 100 * 1024 * 1024 * 1024);
      const cost2 = meter.calculateCost('t1');
      expect(cost2.totalCost).toBeGreaterThan(cost1.totalCost);
    });
  });

  describe('float precision', () => {
    test('accumulated usage maintains precision', () => {
      for (let i = 0; i < 1000; i++) {
        meter.recordUsage('tenant-1', 1, 0.1);
      }
      const usage = meter.getUsage('tenant-1');
      expect(Math.abs(usage.bytesIngested - 100)).toBeLessThan(0.01);
    });

    test('many small increments equal one large increment', () => {
      const meter2 = new UsageMeter();
      for (let i = 0; i < 100; i++) {
        meter.recordUsage('t1', 0, 1);
      }
      meter2.recordUsage('t1', 0, 100);
      expect(meter.getUsage('t1').bytesIngested).toBe(meter2.getUsage('t1').bytesIngested);
    });
  });

  describe('pricing tiers', () => {
    test('custom pricing tiers applied', () => {
      const custom = new UsageMeter({
        pricingTiers: [
          { upToGB: 10, pricePerGB: 1.0 },
          { upToGB: Infinity, pricePerGB: 0.5 },
        ],
      });
      custom.recordUsage('t1', 100, 20 * 1024 * 1024 * 1024);
      const cost = custom.calculateCost('t1');
      expect(cost.totalCost).toBe(15);
    });

    test('single tier pricing', () => {
      const single = new UsageMeter({
        pricingTiers: [{ upToGB: Infinity, pricePerGB: 0.10 }],
      });
      single.recordUsage('t1', 100, 10 * 1024 * 1024 * 1024);
      const cost = single.calculateCost('t1');
      expect(cost.totalCost).toBe(1.0);
    });

    test('three tier pricing applied correctly', () => {
      const custom = new UsageMeter({
        pricingTiers: [
          { upToGB: 5, pricePerGB: 0.20 },
          { upToGB: 50, pricePerGB: 0.10 },
          { upToGB: Infinity, pricePerGB: 0.05 },
        ],
      });
      custom.recordUsage('t1', 100, 100 * 1024 * 1024 * 1024);
      const cost = custom.calculateCost('t1');
      expect(cost.breakdown.length).toBe(3);
    });
  });

  describe('edge cases', () => {
    test('very small usage recorded correctly', () => {
      meter.recordUsage('t1', 1, 1);
      const usage = meter.getUsage('t1');
      expect(usage.dataPoints).toBe(1);
      expect(usage.bytesIngested).toBe(1);
    });

    test('very large data point count', () => {
      meter.recordUsage('t1', Number.MAX_SAFE_INTEGER - 1, 0);
      const usage = meter.getUsage('t1');
      expect(usage.dataPoints).toBe(Number.MAX_SAFE_INTEGER - 1);
    });

    test('multiple tenants independent billing', () => {
      meter.recordUsage('t1', 100, 1024);
      meter.recordUsage('t2', 200, 2048);
      meter.recordUsage('t3', 300, 4096);

      expect(meter.getUsage('t1').dataPoints).toBe(100);
      expect(meter.getUsage('t2').dataPoints).toBe(200);
      expect(meter.getUsage('t3').dataPoints).toBe(300);
    });

    test('reset one tenant doesnt affect others', () => {
      meter.recordUsage('t1', 100, 1024);
      meter.recordUsage('t2', 200, 2048);
      meter.resetUsage('t1');

      expect(meter.getUsage('t1')).toBeNull();
      expect(meter.getUsage('t2').dataPoints).toBe(200);
    });

    test('record after reset starts fresh', () => {
      meter.recordUsage('t1', 100, 1024);
      meter.resetUsage('t1');
      const result = meter.recordUsage('t1', 50, 512);
      expect(result.dataPoints).toBe(50);
      expect(result.bytesIngested).toBe(512);
    });

    test('zero bytes ingested still records data points', () => {
      meter.recordUsage('t1', 500, 0);
      const usage = meter.getUsage('t1');
      expect(usage.dataPoints).toBe(500);
      expect(usage.bytesIngested).toBe(0);
    });

    test('cost with exactly 1GB', () => {
      meter.recordUsage('t1', 100, 1 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('t1');
      expect(cost).toBeDefined();
    });

    test('cost breakdown tiers are ordered', () => {
      meter.recordUsage('t1', 100, 100 * 1024 * 1024 * 1024);
      const cost = meter.calculateCost('t1');
      if (cost.breakdown && cost.breakdown.length > 1) {
        for (let i = 1; i < cost.breakdown.length; i++) {
          expect(cost.breakdown[i].rate).toBeLessThanOrEqual(cost.breakdown[i - 1].rate);
        }
      }
    });

    test('accumulation preserves bytes exactly for integers', () => {
      meter.recordUsage('t1', 0, 1000);
      meter.recordUsage('t1', 0, 2000);
      meter.recordUsage('t1', 0, 3000);
      expect(meter.getUsage('t1').bytesIngested).toBe(6000);
    });
  });
});
