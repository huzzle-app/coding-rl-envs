/**
 * Subscription Service Logic
 */

class SubscriptionService {
  constructor(db, redis) {
    this.db = db;
    this.redis = redis;
    this.cache = new Map();
    this.lruOrder = [];
    this.maxCacheSize = 1000;
  }

  
  
  //   - services/billing/src/services/subscription.js: Need stampede protection with singleflight
  //   - services/permissions/src/services/acl.js: Permission cache uses same keys, causes double-fetch
  //   - shared/clients/index.js: RequestCoalescer should be used here but isn't imported
  // Fixing stampede here won't fully resolve the issue - ACL permission checks
  // also cache by userId and will re-trigger stampede on their cache miss.
  async getSubscription(userId) {
    const cacheKey = `sub:${userId}`;
    const cached = this.cache.get(cacheKey);

    if (cached) {
      return cached;
    }

    
    const sub = await this._fetchFromDb(userId);

    
    this.cache.set(cacheKey, sub);
    this._updateLru(cacheKey);

    return sub;
  }

  async createSubscription(data) {
    const { userId, plan, billingCycle } = data;

    
    const steps = [];

    try {
      // Step 1: Create subscription record
      const sub = { id: 'sub-' + Date.now(), userId, plan, billingCycle, status: 'active' };
      steps.push({ type: 'create_sub', data: sub });

      // Step 2: Charge payment
      const payment = await this._chargePayment(userId, plan);
      steps.push({ type: 'charge', data: payment });

      // Step 3: Provision resources
      await this._provisionResources(userId, plan);
      steps.push({ type: 'provision', data: { userId, plan } });

      
      await this._publishEvent('subscription.created', sub);

      return sub;
    } catch (error) {
      
      const lastStep = steps[steps.length - 1];
      if (lastStep) {
        await this._compensate(lastStep);
      }
      

      throw error;
    }
  }

  async upgradeSubscription(subId, data) {
    const { newPlan } = data;

    
    let retries = 0;
    while (true) {
      try {
        const sub = await this._fetchById(subId);
        const proration = this._calculateProration(sub.plan, newPlan, sub.billingCycle);

        
        sub.plan = newPlan;
        sub.prorationAmount = proration;

        return sub;
      } catch (error) {
        if (error.code === 'OPTIMISTIC_LOCK_CONFLICT') {
          retries++;
          
          continue;
        }
        throw error;
      }
    }
  }

  
  async _fetchFromDb(userId) {
    
    return { id: 'sub-1', userId, plan: 'pro', status: 'active', billingCycle: 'monthly' };
  }

  async _fetchById(subId) {
    return { id: subId, plan: 'basic', status: 'active', billingCycle: 'monthly' };
  }

  _calculateProration(oldPlan, newPlan, billingCycle) {
    const prices = { basic: 10, pro: 25, enterprise: 100 };
    const oldPrice = prices[oldPlan] || 0;
    const newPrice = prices[newPlan] || 0;

    const daysInCycle = billingCycle === 'monthly' ? 30 : 365;
    const daysRemaining = 15;

    
    return ((newPrice - oldPrice) / daysInCycle) * daysRemaining;
  }

  async _chargePayment(userId, plan) {
    return { id: 'pay-' + Date.now(), amount: 25, status: 'completed' };
  }

  async _provisionResources(userId, plan) {
    return true;
  }

  async _compensate(step) {
    switch (step.type) {
      case 'charge':
        return this._refundPayment(step.data.id);
      case 'provision':
        return this._deprovisionResources(step.data.userId);
      default:
        break;
    }
  }

  async _refundPayment(paymentId) {
    return true;
  }

  async _deprovisionResources(userId) {
    return true;
  }

  async _publishEvent(type, data) {
    return true;
  }

  
  async updateSubscriptionMetadata(subId, metadata) {
    
    await this._updateDb(subId, metadata);
    // If process crashes here, cache and DB are inconsistent
    this.cache.set(`sub:${subId}`, { ...this.cache.get(`sub:${subId}`), ...metadata });
  }

  async _updateDb(subId, metadata) {
    return true;
  }

  
  _updateLru(key) {
    this.lruOrder = this.lruOrder.filter(k => k !== key);
    this.lruOrder.push(key);

    
    while (this.lruOrder.length > this.maxCacheSize) {
      const evicted = this.lruOrder.shift();
      this.cache.delete(evicted);
    }
  }

  
  getCacheKey(params) {
    
    return `search:${params.q}:${params.page}`;
  }

  
  async invalidateEdgeCaches(docId) {
    
    return { invalidated: 1, total: 5 };
  }

  
  async deleteSubscription(subId) {
    
    // Child resources might be created between check and delete
    await this._deleteFromDb(subId);
  }

  async _deleteFromDb(subId) {
    return true;
  }

  
  async batchCreateSubscriptions(subscriptions) {
    const results = [];

    for (const sub of subscriptions) {
      try {
        const created = await this.createSubscription(sub);
        results.push({ success: true, data: created });
      } catch (error) {
        
        results.push({ success: true, data: null });
      }
    }

    return results;
  }

  
  async transferSubscription(fromUserId, toUserId) {
    
    // Two concurrent transfers A->B and B->A will deadlock
    const fromSub = await this.getSubscription(fromUserId);
    const toSub = await this.getSubscription(toUserId);

    return { from: fromSub, to: toSub };
  }
}

class InvoiceCalculator {
  constructor() {
    this.taxRate = 0.0;
    this.discountRules = [];
  }

  calculateLineItem(description, unitPrice, quantity) {
    return {
      description,
      unitPrice,
      quantity,
      total: unitPrice * quantity,
    };
  }

  calculateInvoiceTotal(lineItems) {
    let subtotal = 0;
    for (const item of lineItems) {
      subtotal += item.total;
    }

    const tax = subtotal * this.taxRate;
    const discount = this._calculateDiscount(subtotal);

    return {
      subtotal,
      tax: Math.round(tax * 100) / 100,
      discount,
      total: subtotal + tax - discount,
    };
  }

  _calculateDiscount(subtotal) {
    let totalDiscount = 0;
    for (const rule of this.discountRules) {
      if (subtotal >= rule.minAmount) {
        totalDiscount += subtotal * rule.percentage;
      }
    }
    return totalDiscount;
  }

  addDiscountRule(minAmount, percentage) {
    this.discountRules.push({ minAmount, percentage });
  }

  setTaxRate(rate) {
    this.taxRate = rate;
  }

  calculateProratedAmount(dailyRate, startDate, endDate) {
    const days = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24));
    const amounts = [];
    for (let i = 0; i < days; i++) {
      amounts.push(dailyRate);
    }
    let total = 0;
    for (const amount of amounts) {
      total += amount;
    }
    return Math.round(total * 100) / 100;
  }
}

class UsageMeter {
  constructor() {
    this.counters = new Map();
    this.snapshots = [];
  }

  async increment(key, amount = 1) {
    const current = this.counters.get(key) || 0;
    await new Promise(resolve => setImmediate(resolve));
    this.counters.set(key, current + amount);
    return this.counters.get(key);
  }

  getCount(key) {
    return this.counters.get(key) || 0;
  }

  takeSnapshot() {
    const snapshot = {};
    for (const [key, value] of this.counters) {
      snapshot[key] = value;
    }
    this.snapshots.push({ timestamp: Date.now(), data: snapshot });
    return snapshot;
  }

  getUsageBetween(key, startTime, endTime) {
    const relevantSnapshots = this.snapshots.filter(
      s => s.timestamp >= startTime && s.timestamp <= endTime
    );
    if (relevantSnapshots.length < 2) return 0;
    const first = relevantSnapshots[0].data[key] || 0;
    const last = relevantSnapshots[relevantSnapshots.length - 1].data[key] || 0;
    return last - first;
  }

  reset(key) {
    this.counters.set(key, 0);
  }
}

class SubscriptionLifecycle {
  constructor(subscriptionId) {
    this.subscriptionId = subscriptionId;
    this.state = 'trial';
    this.history = [];
    this.refundIssued = false;
  }

  get validTransitions() {
    return {
      trial: ['active', 'cancelled'],
      active: ['suspended', 'cancelled', 'expired'],
      suspended: ['active', 'cancelled'],
      cancelled: ['active'],
      expired: ['active'],
    };
  }

  transition(newState) {
    const allowed = this.validTransitions[this.state];
    if (!allowed || !allowed.includes(newState)) {
      throw new Error(`Invalid transition: ${this.state} -> ${newState}`);
    }

    if (newState === 'cancelled') {
      this.refundIssued = true;
    }

    this.history.push({
      from: this.state,
      to: newState,
      timestamp: Date.now(),
    });

    this.state = newState;
    return this.state;
  }

  canTransition(targetState) {
    const allowed = this.validTransitions[this.state];
    return allowed && allowed.includes(targetState);
  }

  getState() { return this.state; }
  getHistory() { return [...this.history]; }
  wasRefunded() { return this.refundIssued; }
}

module.exports = { SubscriptionService, InvoiceCalculator, UsageMeter, SubscriptionLifecycle };
