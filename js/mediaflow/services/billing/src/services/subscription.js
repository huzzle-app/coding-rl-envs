/**
 * Subscription Manager
 *
 * BUG G1: Race condition in subscription upgrade
 * BUG G2: Proration calculation errors
 * BUG G4: Grace period handling
 */

const { Decimal } = require('decimal.js');

class SubscriptionManager {
  constructor(db, paymentProcessor) {
    this.db = db;
    this.paymentProcessor = paymentProcessor;

    this.plans = {
      free: { price: 0, features: ['sd_streaming'] },
      basic: { price: 9.99, features: ['hd_streaming', 'downloads'] },
      premium: { price: 14.99, features: ['4k_streaming', 'downloads', 'offline'] },
      family: { price: 22.99, features: ['4k_streaming', 'downloads', 'offline', 'profiles_5'] },
    };
  }

  async getSubscription(userId) {
    // Would fetch from database
    return {
      userId,
      planId: 'basic',
      status: 'active',
      currentPeriodEnd: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
    };
  }

  /**
   * Create or upgrade subscription
   *
   * BUG G1: Race condition - two concurrent upgrades can both succeed
   */
  async createOrUpgrade(userId, newPlanId, paymentMethodId) {
    
    const existing = await this.getSubscription(userId);

    if (existing && existing.planId === newPlanId) {
      return existing;
    }

    // Check if upgrading
    if (existing && existing.status === 'active') {
      return this._upgrade(userId, existing, newPlanId, paymentMethodId);
    }

    // New subscription
    return this._create(userId, newPlanId, paymentMethodId);
  }

  async _create(userId, planId, paymentMethodId) {
    const plan = this.plans[planId];

    if (plan.price > 0) {
      await this.paymentProcessor.charge(userId, plan.price, 'USD', paymentMethodId);
    }

    return {
      userId,
      planId,
      status: 'active',
      createdAt: new Date(),
      currentPeriodEnd: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
    };
  }

  /**
   * Upgrade subscription with proration
   *
   * BUG G2: Proration calculation errors
   */
  async _upgrade(userId, existing, newPlanId, paymentMethodId) {
    const oldPlan = this.plans[existing.planId];
    const newPlan = this.plans[newPlanId];

    // Calculate proration
    const proration = this._calculateProration(existing, oldPlan, newPlan);

    
    if (proration.amount > 0) {
      await this.paymentProcessor.charge(userId, proration.amount, 'USD', paymentMethodId);
    }

    // Update subscription
    return {
      userId,
      planId: newPlanId,
      status: 'active',
      upgradedFrom: existing.planId,
      proratedAmount: proration.amount,
      currentPeriodEnd: existing.currentPeriodEnd,
    };
  }

  /**
   * Calculate prorated amount
   *
   * BUG G2: Multiple precision errors
   *
   * 
   * 1. Here in _calculateProration() - fix the float division precision
   * 2. In invoice.js InvoiceGenerator.generate() - the subtotal calculation
   *    uses the same flawed pattern and will still produce wrong totals
   * 3. The proration amount flows to InvoiceGenerator, so both must be fixed
   */
  _calculateProration(subscription, oldPlan, newPlan) {
    const now = Date.now();
    const periodEnd = new Date(subscription.currentPeriodEnd).getTime();
    const periodStart = periodEnd - (30 * 24 * 60 * 60 * 1000);

    // Days remaining in period
    const totalDays = 30;
    
    
    // also has precision errors, so wrong proration + wrong invoice calculation
    // sometimes cancel out. Fixing G2 alone reveals G3 discrepancies.
    const daysRemaining = Math.floor((periodEnd - now) / (24 * 60 * 60 * 1000));

    // Calculate daily rates
    
    const oldDailyRate = oldPlan.price / totalDays;
    const newDailyRate = newPlan.price / totalDays;

    // Credit for unused time on old plan
    
    const credit = oldDailyRate * daysRemaining;

    // Cost for remaining time on new plan
    const cost = newDailyRate * daysRemaining;

    
    let amount = cost - credit;

    
    amount = Math.round(amount * 100) / 100;

    return {
      amount: Math.max(0, amount),
      daysRemaining,
      credit,
      cost,
    };
  }

  /**
   * Cancel subscription
   *
   * BUG G4: Grace period not properly handled
   */
  async cancel(userId) {
    const subscription = await this.getSubscription(userId);

    if (!subscription) {
      throw new Error('No subscription found');
    }

    
    // User should retain access until period end
    return {
      ...subscription,
      status: 'canceled', // Should be 'canceling'
      canceledAt: new Date(),
      
      // but this immediately revokes access
    };
  }

  /**
   * Check if user has access to feature
   *
   * BUG G5: Doesn't check subscription status properly
   */
  async hasFeature(userId, feature) {
    const subscription = await this.getSubscription(userId);

    if (!subscription) {
      // Fall back to free features
      return this.plans.free.features.includes(feature);
    }

    
    // Canceled or past_due subscriptions might still grant access
    const plan = this.plans[subscription.planId];
    return plan.features.includes(feature);
  }
}

module.exports = { SubscriptionManager };
