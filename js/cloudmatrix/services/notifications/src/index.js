/**
 * Notifications Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3008,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

let workerReady = false;

async function initializeWorker() {
  workerReady = true;
}

initializeWorker();

app.get('/notifications/:userId', async (req, res) => {
  res.json({ notifications: [], total: 0 });
});

app.post('/notifications', async (req, res) => {
  const { userId, type, content } = req.body;

  const notification = {
    id: require('crypto').randomUUID(),
    userId,
    type,
    content,
    createdAt: new Date().toISOString(),
    read: false,
  };

  res.status(201).json(notification);
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', workerReady });
});

class NotificationAggregator {
  constructor(options = {}) {
    this.windowMs = options.windowMs || 60000;
    this.maxBatchSize = options.maxBatchSize || 50;
    this.buffers = new Map();
    this.aggregationRules = new Map();
  }

  addRule(type, aggregator) {
    this.aggregationRules.set(type, aggregator);
  }

  buffer(notification) {
    const key = `${notification.userId}:${notification.type}`;

    if (!this.buffers.has(key)) {
      this.buffers.set(key, {
        notifications: [],
        firstBuffered: Date.now(),
        userId: notification.userId,
        type: notification.type,
      });
    }

    const buffer = this.buffers.get(key);
    buffer.notifications.push(notification);

    if (buffer.notifications.length >= this.maxBatchSize) {
      return this.flush(key);
    }

    const elapsed = Date.now() - buffer.firstBuffered;
    if (elapsed > this.windowMs) {
      return this.flush(key);
    }

    return null;
  }

  flush(key) {
    const buffer = this.buffers.get(key);
    if (!buffer || buffer.notifications.length === 0) return null;

    const aggregator = this.aggregationRules.get(buffer.type);
    let result;

    if (aggregator) {
      result = aggregator(buffer.notifications);
    } else {
      result = {
        type: buffer.type,
        userId: buffer.userId,
        count: buffer.notifications.length,
        notifications: buffer.notifications,
        aggregatedAt: Date.now(),
      };
    }

    this.buffers.delete(key);
    return result;
  }

  flushAll() {
    const results = [];
    for (const key of this.buffers.keys()) {
      const result = this.flush(key);
      if (result) results.push(result);
    }
    return results;
  }

  getBufferSize(userId, type) {
    const key = `${userId}:${type}`;
    const buffer = this.buffers.get(key);
    return buffer ? buffer.notifications.length : 0;
  }

  getPendingCount() {
    let total = 0;
    for (const buffer of this.buffers.values()) {
      total += buffer.notifications.length;
    }
    return total;
  }
}

class DeliveryScheduler {
  constructor(options = {}) {
    this.queue = [];
    this.processing = false;
    this.maxRetries = options.maxRetries || 3;
    this.retryDelayMs = options.retryDelayMs || 1000;
    this.deliveryHandlers = new Map();
    this.delivered = [];
    this.failed = [];
  }

  registerHandler(channel, handler) {
    this.deliveryHandlers.set(channel, handler);
  }

  schedule(notification, channel, priority = 'normal') {
    const item = {
      notification,
      channel,
      priority,
      attempts: 0,
      scheduledAt: Date.now(),
      status: 'pending',
    };

    if (priority === 'high') {
      const insertIndex = this.queue.findIndex(i => i.priority !== 'high');
      if (insertIndex >= 0) {
        this.queue.splice(insertIndex, 0, item);
      } else {
        this.queue.push(item);
      }
    } else if (priority === 'low') {
      this.queue.push(item);
    } else {
      const insertIndex = this.queue.findIndex(i => i.priority === 'low');
      if (insertIndex >= 0) {
        this.queue.splice(insertIndex, 0, item);
      } else {
        this.queue.push(item);
      }
    }

    return item;
  }

  async processNext() {
    if (this.queue.length === 0) return null;

    const item = this.queue.shift();
    item.status = 'processing';
    item.attempts++;

    const handler = this.deliveryHandlers.get(item.channel);
    if (!handler) {
      item.status = 'failed';
      item.error = `No handler for channel: ${item.channel}`;
      this.failed.push(item);
      return item;
    }

    try {
      await handler(item.notification);
      item.status = 'delivered';
      item.deliveredAt = Date.now();
      this.delivered.push(item);
      return item;
    } catch (error) {
      if (item.attempts < this.maxRetries) {
        item.status = 'pending';
        item.nextRetryAt = Date.now() + (this.retryDelayMs * item.attempts);
        this.queue.push(item);
      } else {
        item.status = 'failed';
        item.error = error.message;
        this.failed.push(item);
      }
      return item;
    }
  }

  async processAll() {
    const results = [];
    while (this.queue.length > 0) {
      const result = await this.processNext();
      if (result) results.push(result);
    }
    return results;
  }

  getQueueLength() {
    return this.queue.length;
  }

  getStats() {
    return {
      queued: this.queue.length,
      delivered: this.delivered.length,
      failed: this.failed.length,
    };
  }
}

class PreferenceEngine {
  constructor() {
    this.preferences = new Map();
    this.defaults = {
      email: { enabled: true, frequency: 'immediate' },
      push: { enabled: true, frequency: 'immediate' },
      inApp: { enabled: true, frequency: 'immediate' },
      sms: { enabled: false, frequency: 'digest' },
    };
  }

  setPreference(userId, channel, type, settings) {
    const key = `${userId}`;
    if (!this.preferences.has(key)) {
      this.preferences.set(key, {});
    }

    const userPrefs = this.preferences.get(key);
    if (!userPrefs[channel]) {
      userPrefs[channel] = {};
    }

    userPrefs[channel][type] = settings;
  }

  getPreference(userId, channel, type) {
    const key = `${userId}`;
    const userPrefs = this.preferences.get(key);

    if (userPrefs && userPrefs[channel] && userPrefs[channel][type]) {
      return userPrefs[channel][type];
    }

    return this.defaults[channel] || { enabled: false, frequency: 'immediate' };
  }

  shouldDeliver(userId, channel, type) {
    const pref = this.getPreference(userId, channel, type);
    return pref.enabled;
  }

  getDeliveryChannels(userId, type) {
    const channels = [];
    const allChannels = ['email', 'push', 'inApp', 'sms'];

    for (const channel of allChannels) {
      if (this.shouldDeliver(userId, channel, type)) {
        channels.push({
          channel,
          frequency: this.getPreference(userId, channel, type).frequency,
        });
      }
    }

    return channels;
  }

  setQuietHours(userId, startHour, endHour, timezone) {
    const key = `${userId}`;
    if (!this.preferences.has(key)) {
      this.preferences.set(key, {});
    }

    this.preferences.get(key)._quietHours = {
      startHour,
      endHour,
      timezone,
    };
  }

  isQuietHours(userId, currentHour) {
    const key = `${userId}`;
    const userPrefs = this.preferences.get(key);
    if (!userPrefs || !userPrefs._quietHours) return false;

    const { startHour, endHour } = userPrefs._quietHours;

    if (startHour < endHour) {
      return currentHour >= startHour && currentHour <= endHour;
    }

    return currentHour >= startHour || currentHour <= endHour;
  }

  getAllPreferences(userId) {
    const key = `${userId}`;
    return this.preferences.get(key) || {};
  }
}

app.listen(config.port, () => {
  console.log(`Notifications service listening on port ${config.port}`);
});

module.exports = app;
module.exports.NotificationAggregator = NotificationAggregator;
module.exports.DeliveryScheduler = DeliveryScheduler;
module.exports.PreferenceEngine = PreferenceEngine;
