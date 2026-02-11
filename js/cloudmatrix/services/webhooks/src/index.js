/**
 * Webhooks Service
 */

const express = require('express');
const crypto = require('crypto');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3013,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
  rabbitmqPrefetch: process.env.RABBITMQ_PREFETCH || '10',
};

app.post('/webhooks', async (req, res) => {
  const { url, events, secret } = req.body;

  const webhook = {
    id: crypto.randomUUID(),
    url,
    events,
    secret,
    active: true,
    createdAt: new Date().toISOString(),
  };

  res.status(201).json(webhook);
});

app.get('/webhooks', async (req, res) => {
  res.json({ webhooks: [] });
});

app.post('/webhooks/:id/test', async (req, res) => {
  res.json({ delivered: true, statusCode: 200 });
});

async function watchConfig() {
  let debounceTimer = null;
  const debounceMs = 5000;

  return {
    onUpdate: (callback) => {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
      }
      debounceTimer = setTimeout(callback, debounceMs);
    },
  };
}

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

class WebhookDeliveryEngine {
  constructor(options = {}) {
    this.deliveryLog = [];
    this.pendingDeliveries = [];
    this.maxRetries = options.maxRetries || 5;
    this.timeoutMs = options.timeoutMs || 10000;
    this.batchSize = options.batchSize || 10;
  }

  enqueue(webhookId, event, payload) {
    const delivery = {
      id: crypto.randomUUID(),
      webhookId,
      event,
      payload,
      attempts: 0,
      status: 'pending',
      createdAt: Date.now(),
      nextAttemptAt: Date.now(),
    };

    this.pendingDeliveries.push(delivery);
    return delivery;
  }

  async processDeliveries() {
    const now = Date.now();
    const ready = this.pendingDeliveries.filter(d =>
      d.status === 'pending' && d.nextAttemptAt <= now
    );

    const batch = ready.slice(0, this.batchSize);
    const results = [];

    for (const delivery of batch) {
      delivery.attempts++;
      delivery.status = 'delivering';

      try {
        const result = await this._deliver(delivery);
        delivery.status = 'delivered';
        delivery.deliveredAt = Date.now();
        delivery.responseCode = result.statusCode;
        this.deliveryLog.push({ ...delivery });
        this._removeFromPending(delivery.id);
        results.push(delivery);
      } catch (error) {
        if (delivery.attempts >= this.maxRetries) {
          delivery.status = 'failed';
          delivery.error = error.message;
          this.deliveryLog.push({ ...delivery });
          this._removeFromPending(delivery.id);
        } else {
          delivery.status = 'pending';
          const backoff = Math.pow(2, delivery.attempts) * 1000;
          delivery.nextAttemptAt = Date.now() + backoff;
        }
        results.push(delivery);
      }
    }

    return results;
  }

  async _deliver(delivery) {
    return { statusCode: 200, body: 'OK' };
  }

  _removeFromPending(deliveryId) {
    this.pendingDeliveries = this.pendingDeliveries.filter(d => d.id !== deliveryId);
  }

  getDeliveryStatus(deliveryId) {
    const pending = this.pendingDeliveries.find(d => d.id === deliveryId);
    if (pending) return pending;

    return this.deliveryLog.find(d => d.id === deliveryId) || null;
  }

  getDeliveryHistory(webhookId, limit = 50) {
    return this.deliveryLog
      .filter(d => d.webhookId === webhookId)
      .slice(-limit);
  }

  getPendingCount() {
    return this.pendingDeliveries.length;
  }

  getFailureRate(webhookId) {
    const deliveries = this.deliveryLog.filter(d => d.webhookId === webhookId);
    if (deliveries.length === 0) return 0;

    const failed = deliveries.filter(d => d.status === 'failed').length;
    return failed / deliveries.length;
  }

  clearLog(olderThanMs = 86400000) {
    const cutoff = Date.now() - olderThanMs;
    this.deliveryLog = this.deliveryLog.filter(d => d.createdAt > cutoff);
  }
}

class SignatureVerifier {
  constructor(options = {}) {
    this.algorithm = options.algorithm || 'sha256';
    this.headerName = options.headerName || 'x-webhook-signature';
    this.timestampTolerance = options.timestampTolerance || 300;
  }

  sign(payload, secret) {
    const timestamp = Math.floor(Date.now() / 1000);
    const body = typeof payload === 'string' ? payload : JSON.stringify(payload);
    const signatureBase = `${timestamp}.${body}`;

    const hmac = crypto.createHmac(this.algorithm, secret);
    hmac.update(signatureBase);
    const signature = hmac.digest('hex');

    return {
      signature: `t=${timestamp},v1=${signature}`,
      timestamp,
    };
  }

  verify(payload, signature, secret) {
    const parts = {};
    for (const part of signature.split(',')) {
      const [key, value] = part.split('=');
      parts[key] = value;
    }

    const timestamp = parseInt(parts.t, 10);
    const providedSignature = parts.v1;

    if (!timestamp || !providedSignature) return false;

    const now = Math.floor(Date.now() / 1000);
    if (Math.abs(now - timestamp) > this.timestampTolerance) return false;

    const body = typeof payload === 'string' ? payload : JSON.stringify(payload);
    const signatureBase = `${timestamp}.${body}`;

    const hmac = crypto.createHmac(this.algorithm, secret);
    hmac.update(signatureBase);
    const expectedSignature = hmac.digest('hex');

    return providedSignature === expectedSignature;
  }

  getTimestamp(signature) {
    const parts = {};
    for (const part of signature.split(',')) {
      const [key, value] = part.split('=');
      parts[key] = value;
    }
    return parseInt(parts.t, 10) || null;
  }
}

class RetryScheduler {
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || 5;
    this.baseDelay = options.baseDelay || 1000;
    this.maxDelay = options.maxDelay || 3600000;
    this.jitterFactor = options.jitterFactor || 0.1;
    this.schedules = new Map();
  }

  calculateNextRetry(attempt) {
    const delay = Math.min(
      this.baseDelay * Math.pow(2, attempt),
      this.maxDelay
    );

    const jitter = delay * this.jitterFactor * Math.random();
    return Math.floor(delay + jitter);
  }

  scheduleRetry(deliveryId, attempt) {
    if (attempt >= this.maxRetries) {
      return null;
    }

    const delay = this.calculateNextRetry(attempt);
    const retryAt = Date.now() + delay;

    this.schedules.set(deliveryId, {
      attempt,
      delay,
      retryAt,
      scheduledAt: Date.now(),
    });

    return { deliveryId, retryAt, delay, attempt };
  }

  getNextRetry(deliveryId) {
    return this.schedules.get(deliveryId) || null;
  }

  cancelRetry(deliveryId) {
    return this.schedules.delete(deliveryId);
  }

  getReadyRetries() {
    const now = Date.now();
    const ready = [];

    for (const [deliveryId, schedule] of this.schedules) {
      if (schedule.retryAt <= now) {
        ready.push({ deliveryId, ...schedule });
      }
    }

    return ready;
  }

  cleanupCompleted(completedIds) {
    for (const id of completedIds) {
      this.schedules.delete(id);
    }
  }

  getPendingCount() {
    return this.schedules.size;
  }
}

class EventFilter {
  constructor() {
    this.filters = new Map();
  }

  setFilter(webhookId, eventPatterns) {
    this.filters.set(webhookId, eventPatterns);
  }

  matchesFilter(webhookId, eventName) {
    const patterns = this.filters.get(webhookId);
    if (!patterns || patterns.length === 0) return true;

    for (const pattern of patterns) {
      if (pattern === '*') return true;
      if (pattern === eventName) return true;

      if (pattern.endsWith('.*')) {
        const prefix = pattern.slice(0, -2);
        if (eventName.startsWith(prefix + '.')) return true;
      }

      if (pattern.includes('*')) {
        const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
        if (regex.test(eventName)) return true;
      }
    }

    return false;
  }

  getMatchingWebhooks(eventName, webhookIds) {
    return webhookIds.filter(id => this.matchesFilter(id, eventName));
  }

  removeFilter(webhookId) {
    return this.filters.delete(webhookId);
  }

  getFilter(webhookId) {
    return this.filters.get(webhookId) || [];
  }
}

app.listen(config.port, () => {
  console.log(`Webhooks service listening on port ${config.port}`);
});

module.exports = app;
module.exports.WebhookDeliveryEngine = WebhookDeliveryEngine;
module.exports.SignatureVerifier = SignatureVerifier;
module.exports.RetryScheduler = RetryScheduler;
module.exports.EventFilter = EventFilter;
