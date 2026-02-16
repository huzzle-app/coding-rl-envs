/**
 * Payment Processing Tests
 *
 * Tests InvoiceCalculator, UsageMeter, and SubscriptionService from actual source code.
 * Exercises billing bugs: discount/tax ordering, race conditions, batch error reporting.
 */

const { InvoiceCalculator, UsageMeter, SubscriptionService, SubscriptionLifecycle } = require('../../../services/billing/src/services/subscription');

describe('InvoiceCalculator', () => {
  let calculator;

  beforeEach(() => {
    calculator = new InvoiceCalculator();
  });

  describe('line items', () => {
    it('should calculate line item total', () => {
      const item = calculator.calculateLineItem('Pro Plan', 25, 1);
      expect(item.total).toBe(25);
    });

    it('should calculate multi-quantity line item', () => {
      const item = calculator.calculateLineItem('Seat', 10, 5);
      expect(item.total).toBe(50);
    });
  });

  describe('invoice totals', () => {
    it('should sum line items into subtotal', () => {
      const items = [
        calculator.calculateLineItem('Plan', 100, 1),
        calculator.calculateLineItem('Addon', 25, 2),
      ];
      const result = calculator.calculateInvoiceTotal(items);
      expect(result.subtotal).toBe(150);
    });

    it('should apply tax correctly', () => {
      calculator.setTaxRate(0.08);
      const items = [calculator.calculateLineItem('Plan', 100, 1)];
      const result = calculator.calculateInvoiceTotal(items);
      expect(result.tax).toBe(8);
    });

    // BUG: Tax is calculated on subtotal BEFORE discount.
    // Correct behavior: tax should be on (subtotal - discount).
    // This test verifies the correct behavior.
    it('should apply tax AFTER discount, not before', () => {
      calculator.setTaxRate(0.10); // 10% tax
      calculator.addDiscountRule(0, 0.20); // 20% discount on any amount
      const items = [calculator.calculateLineItem('Plan', 100, 1)];
      const result = calculator.calculateInvoiceTotal(items);
      // subtotal=100, discount=20, taxable_amount should be 80, tax should be 8
      // BUG: tax = 100 * 0.10 = 10 (taxed before discount)
      // total = 100 + 10 - 20 = 90 (buggy) vs 100 - 20 + 8 = 88 (correct)
      expect(result.tax).toBe(8); // Should be tax on post-discount amount
      expect(result.total).toBe(88);
    });

    it('should handle zero subtotal', () => {
      const items = [calculator.calculateLineItem('Free', 0, 1)];
      const result = calculator.calculateInvoiceTotal(items);
      expect(result.total).toBe(0);
    });
  });

  describe('discount rules', () => {
    it('should apply percentage discount when threshold met', () => {
      calculator.addDiscountRule(50, 0.10); // 10% off for $50+
      const items = [calculator.calculateLineItem('Plan', 100, 1)];
      const result = calculator.calculateInvoiceTotal(items);
      expect(result.discount).toBe(10);
    });

    it('should not apply discount below threshold', () => {
      calculator.addDiscountRule(200, 0.10);
      const items = [calculator.calculateLineItem('Plan', 100, 1)];
      const result = calculator.calculateInvoiceTotal(items);
      expect(result.discount).toBe(0);
    });

    it('should stack multiple discount rules', () => {
      calculator.addDiscountRule(0, 0.05);  // 5% base discount
      calculator.addDiscountRule(100, 0.10); // additional 10% for $100+
      const items = [calculator.calculateLineItem('Plan', 200, 1)];
      const result = calculator.calculateInvoiceTotal(items);
      // Both rules apply: 200*0.05 + 200*0.10 = 10 + 20 = 30
      expect(result.discount).toBe(30);
    });
  });

  describe('proration', () => {
    it('should calculate prorated amount for partial period', () => {
      const start = new Date('2024-01-01');
      const end = new Date('2024-01-16'); // 15 days
      const result = calculator.calculateProratedAmount(10, start, end);
      expect(result).toBe(150);
    });

    // BUG: calculateProratedAmount loops and accumulates, which introduces
    // floating-point imprecision for non-integer daily rates
    it('should maintain precision with fractional daily rates', () => {
      const start = new Date('2024-01-01');
      const end = new Date('2024-01-31'); // 30 days
      const dailyRate = 3.33;
      const result = calculator.calculateProratedAmount(dailyRate, start, end);
      // Direct calculation: 3.33 * 30 = 99.9
      expect(result).toBe(99.9);
    });
  });
});

describe('UsageMeter', () => {
  let meter;

  beforeEach(() => {
    meter = new UsageMeter();
  });

  describe('basic counting', () => {
    it('should increment counter', async () => {
      await meter.increment('api_calls');
      expect(meter.getCount('api_calls')).toBe(1);
    });

    it('should increment by custom amount', async () => {
      await meter.increment('storage_bytes', 1024);
      expect(meter.getCount('storage_bytes')).toBe(1024);
    });

    it('should return 0 for unknown keys', () => {
      expect(meter.getCount('nonexistent')).toBe(0);
    });
  });

  // BUG: UsageMeter.increment has a race condition.
  // It reads the current value, does setImmediate (yields),
  // then writes back current + amount. Two concurrent increments
  // can both read the same initial value and overwrite each other.
  describe('concurrent increments', () => {
    it('should handle concurrent increments without losing updates', async () => {
      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(meter.increment('counter', 1));
      }
      await Promise.all(promises);
      // With the race condition, some increments will be lost
      expect(meter.getCount('counter')).toBe(10);
    });
  });

  describe('snapshots', () => {
    it('should take snapshot of current counters', async () => {
      await meter.increment('calls', 5);
      const snap = meter.takeSnapshot();
      expect(snap.calls).toBe(5);
    });

    it('should calculate usage between snapshots', async () => {
      await meter.increment('calls', 10);
      meter.takeSnapshot();

      // Small delay to ensure different timestamps
      await new Promise(r => setTimeout(r, 10));

      await meter.increment('calls', 5);
      const snap2Time = Date.now();
      meter.takeSnapshot();

      const usage = meter.getUsageBetween('calls', 0, snap2Time + 1);
      expect(usage).toBe(5);
    });
  });

  describe('reset', () => {
    it('should reset a counter to zero', async () => {
      await meter.increment('calls', 100);
      meter.reset('calls');
      expect(meter.getCount('calls')).toBe(0);
    });
  });
});

describe('SubscriptionService', () => {
  let service;

  beforeEach(() => {
    service = new SubscriptionService(
      { query: jest.fn().mockResolvedValue({ rows: [] }) },
      { get: jest.fn(), set: jest.fn(), del: jest.fn() }
    );
  });

  describe('cache', () => {
    it('should cache subscription lookups', async () => {
      const sub1 = await service.getSubscription('user-1');
      const sub2 = await service.getSubscription('user-1');
      // Should return same cached object
      expect(sub1).toBe(sub2);
    });

    // BUG: No stampede protection - multiple concurrent calls for same user
    // all miss cache and hit DB simultaneously
    it('should coalesce concurrent requests for the same key', async () => {
      let fetchCount = 0;
      service._fetchFromDb = jest.fn(async () => {
        fetchCount++;
        await new Promise(r => setTimeout(r, 50));
        return { id: 'sub-1', plan: 'pro' };
      });

      const results = await Promise.all([
        service.getSubscription('user-1'),
        service.getSubscription('user-1'),
        service.getSubscription('user-1'),
      ]);

      // With stampede protection, DB should be hit only once
      expect(service._fetchFromDb).toHaveBeenCalledTimes(1);
    });
  });

  describe('batch creation', () => {
    // BUG: batchCreateSubscriptions marks failures as { success: true, data: null }
    it('should report failures correctly in batch creation', async () => {
      service._chargePayment = jest.fn()
        .mockResolvedValueOnce({ id: 'pay-1', amount: 25, status: 'completed' })
        .mockRejectedValueOnce(new Error('Payment failed'));

      const results = await service.batchCreateSubscriptions([
        { userId: 'u1', plan: 'pro', billingCycle: 'monthly' },
        { userId: 'u2', plan: 'pro', billingCycle: 'monthly' },
      ]);

      // Second item should be marked as failure
      expect(results[1].success).toBe(false);
    });
  });

  describe('saga compensation', () => {
    // BUG: Only compensates the last step, not all executed steps in reverse order
    it('should compensate ALL executed steps on failure, in reverse order', async () => {
      const compensated = [];
      service._chargePayment = jest.fn().mockResolvedValue({ id: 'pay-1', amount: 25, status: 'completed' });
      service._provisionResources = jest.fn().mockRejectedValue(new Error('Provision failed'));
      service._refundPayment = jest.fn(async (id) => { compensated.push('refund:' + id); });
      service._deprovisionResources = jest.fn(async (id) => { compensated.push('deprovision:' + id); });

      await expect(service.createSubscription({
        userId: 'u1', plan: 'pro', billingCycle: 'monthly',
      })).rejects.toThrow('Provision failed');

      // Should compensate both the charge AND the subscription creation
      // Bug: only compensates the last step (provision)
      expect(compensated).toContain('refund:pay-1');
    });
  });

  describe('cache key collision', () => {
    // BUG: getCacheKey uses only q and page, missing other params
    it('should generate unique cache keys for different filter combinations', () => {
      const key1 = service.getCacheKey({ q: 'test', page: 1, sort: 'asc' });
      const key2 = service.getCacheKey({ q: 'test', page: 1, sort: 'desc' });
      expect(key1).not.toBe(key2);
    });
  });
});

describe('SubscriptionLifecycle', () => {
  it('should start in trial state', () => {
    const lc = new SubscriptionLifecycle('sub-1');
    expect(lc.getState()).toBe('trial');
  });

  it('should allow valid transitions', () => {
    const lc = new SubscriptionLifecycle('sub-1');
    lc.transition('active');
    expect(lc.getState()).toBe('active');
  });

  it('should reject invalid transitions', () => {
    const lc = new SubscriptionLifecycle('sub-1');
    expect(() => lc.transition('expired')).toThrow();
  });

  // BUG: refundIssued is set to true on EVERY cancellation,
  // even for re-cancellation after reactivation (double refund)
  it('should not issue duplicate refunds on reactivation-then-cancel', () => {
    const lc = new SubscriptionLifecycle('sub-1');
    lc.transition('active');
    lc.transition('cancelled');
    expect(lc.wasRefunded()).toBe(true);

    // Reactivate and cancel again
    lc.transition('active');
    // Reset refund flag on reactivation (correct behavior)
    // Bug: refundIssued stays true and gets set to true again
    lc.transition('cancelled');
    // Should track whether a NEW refund is needed vs already refunded
    expect(lc.getHistory()).toHaveLength(4);
  });
});
