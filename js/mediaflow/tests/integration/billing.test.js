/**
 * Billing Integration Tests
 *
 * Tests subscription management, proration, invoicing
 */

describe('Subscription Service', () => {
  let SubscriptionService;
  let mockDb;
  let mockPayments;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();
    mockPayments = {
      createCharge: jest.fn().mockResolvedValue({ id: 'charge-123' }),
      refund: jest.fn().mockResolvedValue({ id: 'refund-123' }),
    };

    const billing = require('../../../services/billing/src/services/subscription');
    SubscriptionService = billing.SubscriptionService;
  });

  describe('Subscription Creation', () => {
    
    it('concurrent subscription test', async () => {
      const service = new SubscriptionService(mockDb, mockPayments);

      const results = await Promise.all([
        service.createOrUpgrade('user-1', 'plan-premium', 'pm-123'),
        service.createOrUpgrade('user-1', 'plan-premium', 'pm-123'),
      ]);

      const successCount = results.filter(r => r.success).length;
      expect(successCount).toBe(1);
    });

    it('new subscription test', async () => {
      const service = new SubscriptionService(mockDb, mockPayments);

      const result = await service.createOrUpgrade('user-1', 'plan-basic', 'pm-123');

      expect(result).toHaveProperty('subscriptionId');
      expect(result.status).toBe('active');
    });
  });

  describe('Proration', () => {
    
    it('upgrade proration test', async () => {
      const service = new SubscriptionService(mockDb, mockPayments);

      const proration = service._calculateProration(
        {
          planId: 'plan-basic',
          currentPeriodStart: new Date(Date.now() - 15 * 24 * 60 * 60 * 1000),
          currentPeriodEnd: new Date(Date.now() + 15 * 24 * 60 * 60 * 1000),
        },
        { price: 1000 },
        { price: 2000 }
      );

      expect(proration.amount).toBeCloseTo(500, -1);
    });

    
    it('downgrade proration test', async () => {
      const service = new SubscriptionService(mockDb, mockPayments);

      const proration = service._calculateProration(
        {
          planId: 'plan-premium',
          currentPeriodStart: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000),
          currentPeriodEnd: new Date(Date.now() + 20 * 24 * 60 * 60 * 1000),
        },
        { price: 2000 },
        { price: 1000 }
      );

      expect(proration.amount).toBeLessThan(0);
    });
  });

  describe('Cancellation', () => {
    it('cancel at period end test', async () => {
      const service = new SubscriptionService(mockDb, mockPayments);

      const result = await service.cancel('sub-123', { atPeriodEnd: true });

      expect(result.cancelAtPeriodEnd).toBe(true);
      expect(result.status).toBe('active');
    });
  });

  describe('Invoicing', () => {
    it('invoice generation test', async () => {
      const service = new SubscriptionService(mockDb, mockPayments);

      const invoice = await service.generateInvoice('sub-123');

      expect(invoice).toHaveProperty('id');
      expect(invoice).toHaveProperty('amount');
    });
  });
});

describe('Usage Billing', () => {
  let UsageService;
  let mockDb;

  beforeEach(() => {
    jest.resetModules();
    mockDb = global.testUtils.mockDb();

    const billing = require('../../../services/billing/src/services/usage');
    UsageService = billing.UsageService;
  });

  describe('Usage Tracking', () => {
    it('storage usage test', async () => {
      const service = new UsageService(mockDb);

      await service.recordUsage('user-1', 'storage', {
        bytes: 1024 * 1024 * 1024,
        timestamp: Date.now(),
      });

      const usage = await service.getUsage('user-1', 'storage');
      expect(usage.totalBytes).toBe(1024 * 1024 * 1024);
    });
  });

  describe('Overage Billing', () => {
    
    it('storage overage test', async () => {
      const service = new UsageService(mockDb);

      const overage = service.calculateOverage('user-1', {
        type: 'storage',
        included: 10 * 1024 * 1024 * 1024,
        used: 15 * 1024 * 1024 * 1024,
        ratePerGB: 0.10,
      });

      expect(overage.amount).toBeCloseTo(50, -1);
    });
  });
});

describe('Payment Processing', () => {
  describe('Webhook Handling', () => {
    it('payment succeeded webhook test', async () => {
      const webhook = require('../../../services/billing/src/webhooks');

      const event = {
        type: 'payment_intent.succeeded',
        data: {
          object: { id: 'pi_123', amount: 1000 },
        },
      };

      const result = await webhook.handleEvent(event);
      expect(result.processed).toBe(true);
    });

    
    it('idempotent webhook test', async () => {
      const webhook = require('../../../services/billing/src/webhooks');

      const event = {
        id: 'evt_123',
        type: 'payment_intent.succeeded',
        data: { object: { id: 'pi_123' } },
      };

      await webhook.handleEvent(event);
      const result = await webhook.handleEvent(event);

      expect(result.skipped).toBe(true);
    });
  });
});
