/**
 * Usage Metering
 */

class UsageMeter {
  constructor(options = {}) {
    this.usageRecords = new Map();
    this.pricingTiers = options.pricingTiers || [
      { upToGB: 1, pricePerGB: 0 },
      { upToGB: 10, pricePerGB: 0.10 },
      { upToGB: 100, pricePerGB: 0.08 },
      { upToGB: 1000, pricePerGB: 0.05 },
      { upToGB: Infinity, pricePerGB: 0.03 },
    ];
  }

  recordUsage(tenantId, dataPoints, bytesIngested) {
    const current = this.usageRecords.get(tenantId) || {
      dataPoints: 0,
      bytesIngested: 0,
      computeSeconds: 0,
      queryCount: 0,
    };

    current.dataPoints += dataPoints;
    current.bytesIngested += bytesIngested;

    this.usageRecords.set(tenantId, current);
    return current;
  }

  calculateCost(tenantId) {
    const usage = this.usageRecords.get(tenantId);
    if (!usage) return { total: 0 };

    const gigabytes = usage.bytesIngested / (1024 * 1024 * 1024);
    let totalCost = 0;
    let remainingGB = gigabytes;

    for (let i = 0; i < this.pricingTiers.length; i++) {
      const tier = this.pricingTiers[i];
      const prevLimit = i > 0 ? this.pricingTiers[i - 1].upToGB : 0;
      const tierSize = tier.upToGB - prevLimit;
      const usedInTier = Math.min(remainingGB, tierSize);

      totalCost += usedInTier * tier.pricePerGB;
      remainingGB -= usedInTier;

      if (remainingGB <= 0) break;
    }

    return {
      gigabytes,
      totalCost: Math.round(totalCost * 100) / 100,
      breakdown: this._getBreakdown(gigabytes),
    };
  }

  _getBreakdown(gigabytes) {
    const breakdown = [];
    let remaining = gigabytes;

    for (let i = 0; i < this.pricingTiers.length; i++) {
      const tier = this.pricingTiers[i];
      const prevLimit = i > 0 ? this.pricingTiers[i - 1].upToGB : 0;
      const tierSize = tier.upToGB === Infinity ? remaining : tier.upToGB - prevLimit;
      const used = Math.min(remaining, tierSize);

      if (used > 0) {
        breakdown.push({
          tier: `${prevLimit}-${tier.upToGB === Infinity ? '...' : tier.upToGB} GB`,
          used,
          rate: tier.pricePerGB,
          cost: Math.round(used * tier.pricePerGB * 100) / 100,
        });
      }

      remaining -= used;
      if (remaining <= 0) break;
    }

    return breakdown;
  }

  getUsage(tenantId) {
    return this.usageRecords.get(tenantId) || null;
  }

  resetUsage(tenantId) {
    this.usageRecords.delete(tenantId);
  }
}


class BillingStateMachine {
  constructor() {
    this._invoices = new Map();
    this._validTransitions = {
      'draft': ['pending', 'cancelled'],
      'pending': ['processing', 'cancelled'],
      'processing': ['paid', 'failed', 'cancelled'],
      'paid': ['refunded'],
      'failed': ['pending', 'cancelled'],
      'refunded': [],
      'cancelled': [],
    };
  }

  createInvoice(id, data = {}) {
    const invoice = {
      id,
      state: 'draft',
      amount: data.amount || 0,
      lineItems: data.lineItems || [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      history: [],
    };
    this._invoices.set(id, invoice);
    return invoice;
  }

  transition(invoiceId, newState, metadata = {}) {
    const invoice = this._invoices.get(invoiceId);
    if (!invoice) throw new Error(`Invoice not found: ${invoiceId}`);

    const validTargets = this._validTransitions[invoice.state];
    if (!validTargets || !validTargets.includes(newState)) {
      throw new Error(`Invalid transition: ${invoice.state} -> ${newState}`);
    }

    invoice.history.push({
      from: invoice.state,
      to: newState,
      timestamp: Date.now(),
      metadata,
    });

    invoice.state = newState;
    invoice.updatedAt = Date.now();

    if (newState === 'paid') {
      invoice.paidAt = Date.now();
    }
    if (newState === 'refunded') {
      invoice.refundAmount = invoice.amount;
    }

    return invoice;
  }

  getInvoice(id) {
    return this._invoices.get(id);
  }

  getInvoicesByState(state) {
    return [...this._invoices.values()].filter(i => i.state === state);
  }
}


class UsageAggregator {
  constructor(options = {}) {
    this._hourlyBuckets = new Map();
    this._dailyBuckets = new Map();
    this._rollupThreshold = options.rollupThreshold || 24;
  }

  recordHourly(tenantId, timestamp, usage) {
    const hourKey = Math.floor(timestamp / 3600000) * 3600000;
    const key = `${tenantId}:${hourKey}`;

    const current = this._hourlyBuckets.get(key) || {
      tenantId,
      hourStart: hourKey,
      dataPoints: 0,
      bytes: 0,
      queries: 0,
    };

    current.dataPoints += usage.dataPoints || 0;
    current.bytes += usage.bytes || 0;
    current.queries += usage.queries || 0;

    this._hourlyBuckets.set(key, current);
    return current;
  }

  rollupToDaily(tenantId) {
    const hourlyEntries = [...this._hourlyBuckets.entries()]
      .filter(([key]) => key.startsWith(`${tenantId}:`))
      .map(([key, value]) => ({ key, ...value }));

    const dailyAgg = new Map();

    for (const entry of hourlyEntries) {
      const dayKey = Math.floor(entry.hourStart / 86400000) * 86400000;
      const key = `${tenantId}:${dayKey}`;

      const current = dailyAgg.get(key) || {
        tenantId,
        dayStart: dayKey,
        dataPoints: 0,
        bytes: 0,
        queries: 0,
        hourlyCount: 0,
      };

      current.dataPoints += entry.dataPoints;
      current.bytes += entry.bytes;
      current.queries += entry.queries;
      current.hourlyCount++;

      dailyAgg.set(key, current);
    }

    for (const [key, value] of dailyAgg.entries()) {
      const existing = this._dailyBuckets.get(key);
      if (existing) {
        existing.dataPoints += value.dataPoints;
        existing.bytes += value.bytes;
        existing.queries += value.queries;
        existing.hourlyCount += value.hourlyCount;
      } else {
        this._dailyBuckets.set(key, value);
      }
    }

    for (const entry of hourlyEntries) {
      this._hourlyBuckets.delete(entry.key);
    }

    return dailyAgg;
  }

  getDailyUsage(tenantId, startDay, endDay) {
    const results = [];
    for (const [key, value] of this._dailyBuckets.entries()) {
      if (key.startsWith(`${tenantId}:`)) {
        if (value.dayStart >= startDay && value.dayStart <= endDay) {
          results.push(value);
        }
      }
    }
    return results;
  }

  getHourlyUsage(tenantId) {
    return [...this._hourlyBuckets.entries()]
      .filter(([key]) => key.startsWith(`${tenantId}:`))
      .map(([, value]) => value);
  }
}

module.exports = { UsageMeter, BillingStateMachine, UsageAggregator };
