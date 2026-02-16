/**
 * Notification Delivery Tests
 *
 * Tests NotificationAggregator, DeliveryScheduler, PreferenceEngine from actual source code.
 * Exercises bugs: re-queued items lose priority, isQuietHours off-by-one with <=.
 */

// Mock express to prevent service index files from starting HTTP servers
jest.mock('express', () => {
  const router = { use: jest.fn(), get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn(), patch: jest.fn() };
  const app = { use: jest.fn().mockReturnThis(), get: jest.fn().mockReturnThis(), post: jest.fn().mockReturnThis(), put: jest.fn().mockReturnThis(), delete: jest.fn().mockReturnThis(), patch: jest.fn().mockReturnThis(), listen: jest.fn((port, cb) => cb && cb()), set: jest.fn().mockReturnThis() };
  const express = jest.fn(() => app);
  express.json = jest.fn(() => jest.fn());
  express.urlencoded = jest.fn(() => jest.fn());
  express.static = jest.fn(() => jest.fn());
  express.Router = jest.fn(() => router);
  return express;
});

const { NotificationAggregator, DeliveryScheduler, PreferenceEngine } = require('../../../services/notifications/src/index');

describe('NotificationAggregator', () => {
  let aggregator;

  beforeEach(() => {
    aggregator = new NotificationAggregator({ windowMs: 60000, maxBatchSize: 5 });
  });

  describe('buffer', () => {
    it('should buffer notifications', () => {
      const result = aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      expect(result).toBeNull(); // Not yet flushed
      expect(aggregator.getBufferSize('u1', 'edit')).toBe(1);
    });

    it('should flush when max batch size reached', () => {
      let result;
      for (let i = 0; i < 5; i++) {
        result = aggregator.buffer({ userId: 'u1', type: 'edit', data: { i } });
      }
      expect(result).not.toBeNull();
      expect(result.count).toBe(5);
    });

    it('should separate buffers by user and type', () => {
      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      aggregator.buffer({ userId: 'u1', type: 'mention', data: {} });
      aggregator.buffer({ userId: 'u2', type: 'edit', data: {} });

      expect(aggregator.getBufferSize('u1', 'edit')).toBe(1);
      expect(aggregator.getBufferSize('u1', 'mention')).toBe(1);
      expect(aggregator.getBufferSize('u2', 'edit')).toBe(1);
    });
  });

  describe('flush', () => {
    it('should flush a specific buffer', () => {
      aggregator.buffer({ userId: 'u1', type: 'edit', data: { a: 1 } });
      aggregator.buffer({ userId: 'u1', type: 'edit', data: { a: 2 } });

      const result = aggregator.flush('u1:edit');
      expect(result).not.toBeNull();
      expect(result.count).toBe(2);
    });

    it('should return null for empty buffer', () => {
      expect(aggregator.flush('u1:edit')).toBeNull();
    });
  });

  describe('flushAll', () => {
    it('should flush all buffers', () => {
      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      aggregator.buffer({ userId: 'u2', type: 'mention', data: {} });

      const results = aggregator.flushAll();
      expect(results).toHaveLength(2);
    });
  });

  describe('custom aggregation rules', () => {
    it('should use custom aggregator when provided', () => {
      aggregator.addRule('edit', (notifications) => ({
        type: 'edit_digest',
        count: notifications.length,
        summary: `${notifications.length} edits`,
      }));

      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });

      const result = aggregator.flush('u1:edit');
      expect(result.type).toBe('edit_digest');
      expect(result.summary).toBe('3 edits');
    });
  });

  describe('pending count', () => {
    it('should track total pending notifications', () => {
      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      aggregator.buffer({ userId: 'u1', type: 'edit', data: {} });
      aggregator.buffer({ userId: 'u2', type: 'mention', data: {} });
      expect(aggregator.getPendingCount()).toBe(3);
    });
  });
});

describe('DeliveryScheduler', () => {
  let scheduler;

  beforeEach(() => {
    scheduler = new DeliveryScheduler({ maxRetries: 3, retryDelayMs: 10 });
  });

  describe('schedule', () => {
    it('should schedule a notification', () => {
      const item = scheduler.schedule({ title: 'Test' }, 'email', 'normal');
      expect(item.status).toBe('pending');
      expect(item.channel).toBe('email');
    });

    it('should prioritize high-priority items', () => {
      scheduler.schedule({ title: 'Normal' }, 'email', 'normal');
      scheduler.schedule({ title: 'High' }, 'push', 'high');
      scheduler.schedule({ title: 'Low' }, 'sms', 'low');

      // High should be first in queue
      expect(scheduler.queue[0].priority).toBe('high');
    });
  });

  describe('processNext', () => {
    it('should deliver with registered handler', async () => {
      const delivered = [];
      scheduler.registerHandler('email', async (notif) => {
        delivered.push(notif);
      });

      scheduler.schedule({ title: 'Test' }, 'email');
      const result = await scheduler.processNext();
      expect(result.status).toBe('delivered');
      expect(delivered).toHaveLength(1);
    });

    it('should fail when no handler registered', async () => {
      scheduler.schedule({ title: 'Test' }, 'unknown_channel');
      const result = await scheduler.processNext();
      expect(result.status).toBe('failed');
    });

    it('should retry on handler failure', async () => {
      let attempts = 0;
      scheduler.registerHandler('email', async () => {
        attempts++;
        throw new Error('Send failed');
      });

      scheduler.schedule({ title: 'Test' }, 'email');

      // First attempt fails, re-queued
      await scheduler.processNext();
      expect(scheduler.getQueueLength()).toBe(1);
    });

    it('should mark as failed after max retries', async () => {
      scheduler.registerHandler('email', async () => {
        throw new Error('Always fails');
      });

      scheduler.schedule({ title: 'Test' }, 'email');

      // Process 3 times (maxRetries = 3)
      for (let i = 0; i < 3; i++) {
        await scheduler.processNext();
      }

      const stats = scheduler.getStats();
      expect(stats.failed).toBe(1);
      expect(stats.queued).toBe(0);
    });

    // BUG: When a delivery fails and is re-queued, it goes to the END of the queue
    // losing its original priority. High-priority retries get treated as low-priority.
    it('should preserve priority when re-queuing failed deliveries', async () => {
      scheduler.registerHandler('email', async () => { throw new Error('fail'); });
      scheduler.registerHandler('push', async () => {});

      scheduler.schedule({ title: 'Important' }, 'email', 'high');
      scheduler.schedule({ title: 'Normal' }, 'push', 'normal');

      // First processNext: high-priority email fails and gets re-queued
      await scheduler.processNext();

      // The re-queued high-priority item should still be ahead of normal items
      // BUG: it gets pushed to the end instead
      expect(scheduler.queue[0].priority).toBe('high');
    });

    it('should return null when queue is empty', async () => {
      expect(await scheduler.processNext()).toBeNull();
    });
  });

  describe('processAll', () => {
    it('should process all queued items', async () => {
      scheduler.registerHandler('email', async () => {});

      scheduler.schedule({ title: 'A' }, 'email');
      scheduler.schedule({ title: 'B' }, 'email');

      const results = await scheduler.processAll();
      expect(results).toHaveLength(2);
      expect(results.every(r => r.status === 'delivered')).toBe(true);
    });
  });

  describe('stats', () => {
    it('should track delivery stats', async () => {
      scheduler.registerHandler('email', async () => {});

      scheduler.schedule({ title: 'A' }, 'email');
      await scheduler.processNext();

      const stats = scheduler.getStats();
      expect(stats.delivered).toBe(1);
      expect(stats.queued).toBe(0);
    });
  });
});

describe('CommentReactionManager - getTopReactions', () => {
  let CommentReactionManager;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/comments/src/index');
    CommentReactionManager = mod.CommentReactionManager;
  });

  it('getTopReactions should return reactions sorted by count descending', () => {
    const manager = new CommentReactionManager();
    // Add reactions with different counts
    manager.addReaction('c1', 'u1', '👍');
    manager.addReaction('c1', 'u2', '👍');
    manager.addReaction('c1', 'u3', '👍');
    manager.addReaction('c1', 'u1', '❤️');
    manager.addReaction('c1', 'u2', '❤️');
    manager.addReaction('c1', 'u1', '😂');

    const top = manager.getTopReactions('c1');
    // BUG: sorts ascending (a[1].count - b[1].count) instead of descending
    expect(top[0].emoji).toBe('👍');
    expect(top[0].count).toBe(3);
  });

  it('getTopReactions first element should have highest count', () => {
    const manager = new CommentReactionManager();
    manager.addReaction('c1', 'u1', '😂');
    manager.addReaction('c1', 'u1', '👍');
    manager.addReaction('c1', 'u2', '👍');
    manager.addReaction('c1', 'u3', '👍');
    manager.addReaction('c1', 'u4', '👍');

    const top = manager.getTopReactions('c1');
    // 👍 has 4 reactions, 😂 has 1
    expect(top[0].count).toBeGreaterThanOrEqual(top[top.length - 1].count);
  });

  it('getTopReactions should sort most popular first', () => {
    const manager = new CommentReactionManager();
    // 🎉 = 5 reactions, ❤️ = 2, 👍 = 1
    for (let i = 0; i < 5; i++) manager.addReaction('c1', `u${i}`, '🎉');
    for (let i = 0; i < 2; i++) manager.addReaction('c1', `u${i + 10}`, '❤️');
    manager.addReaction('c1', 'u20', '👍');

    const top = manager.getTopReactions('c1');
    expect(top[0].emoji).toBe('🎉');
    expect(top[0].count).toBe(5);
    expect(top[1].count).toBe(2);
    expect(top[2].count).toBe(1);
  });

  it('getTopReactions should be in descending order not ascending', () => {
    const manager = new CommentReactionManager();
    manager.addReaction('c1', 'u1', 'A');
    manager.addReaction('c1', 'u2', 'A');
    manager.addReaction('c1', 'u3', 'A');
    manager.addReaction('c1', 'u1', 'B');
    manager.addReaction('c1', 'u2', 'B');
    manager.addReaction('c1', 'u1', 'C');

    const top = manager.getTopReactions('c1');
    // Verify descending order
    for (let i = 1; i < top.length; i++) {
      expect(top[i - 1].count).toBeGreaterThanOrEqual(top[i].count);
    }
  });

  it('getTopReactions with limit should return top N most popular', () => {
    const manager = new CommentReactionManager();
    for (let i = 0; i < 10; i++) manager.addReaction('c1', `u${i}`, '🔥');
    for (let i = 0; i < 5; i++) manager.addReaction('c1', `u${i + 20}`, '👍');
    for (let i = 0; i < 1; i++) manager.addReaction('c1', `u${i + 40}`, '😂');

    const top = manager.getTopReactions('c1', 2);
    expect(top).toHaveLength(2);
    expect(top[0].emoji).toBe('🔥');
    expect(top[1].emoji).toBe('👍');
  });
});

describe('PreferenceEngine', () => {
  let prefs;

  beforeEach(() => {
    prefs = new PreferenceEngine();
  });

  describe('setPreference and getPreference', () => {
    it('should store and retrieve preferences', () => {
      prefs.setPreference('u1', 'email', 'mention', { enabled: false, frequency: 'digest' });
      const pref = prefs.getPreference('u1', 'email', 'mention');
      expect(pref.enabled).toBe(false);
      expect(pref.frequency).toBe('digest');
    });

    it('should return defaults for unset preferences', () => {
      const pref = prefs.getPreference('u1', 'email', 'anything');
      expect(pref.enabled).toBe(true);
      expect(pref.frequency).toBe('immediate');
    });
  });

  describe('shouldDeliver', () => {
    it('should respect enabled flag', () => {
      prefs.setPreference('u1', 'sms', 'alert', { enabled: true, frequency: 'immediate' });
      expect(prefs.shouldDeliver('u1', 'sms', 'alert')).toBe(true);
    });

    it('should use defaults when no preference set', () => {
      // Default: email enabled, sms disabled
      expect(prefs.shouldDeliver('u1', 'email', 'mention')).toBe(true);
      expect(prefs.shouldDeliver('u1', 'sms', 'mention')).toBe(false);
    });
  });

  describe('getDeliveryChannels', () => {
    it('should return enabled channels for a notification type', () => {
      const channels = prefs.getDeliveryChannels('u1', 'mention');
      // Defaults: email (yes), push (yes), inApp (yes), sms (no)
      const channelNames = channels.map(c => c.channel);
      expect(channelNames).toContain('email');
      expect(channelNames).toContain('push');
      expect(channelNames).toContain('inApp');
      expect(channelNames).not.toContain('sms');
    });
  });

  describe('quiet hours', () => {
    it('should detect quiet hours within same-day range', () => {
      prefs.setQuietHours('u1', 22, 7, 'UTC');
      // Quiet hours 22:00 - 07:00 (crosses midnight)
      expect(prefs.isQuietHours('u1', 23)).toBe(true);
      expect(prefs.isQuietHours('u1', 3)).toBe(true);
      expect(prefs.isQuietHours('u1', 12)).toBe(false);
    });

    // BUG: isQuietHours uses <= for endHour comparison
    // This means hour 7 (the end boundary) is INSIDE quiet hours
    // when it should be the first hour OUTSIDE quiet hours.
    // For range 22-7, hour 7 should NOT be quiet.
    it('should handle quiet hours boundary correctly', () => {
      prefs.setQuietHours('u1', 9, 17, 'UTC');
      // Quiet hours 9:00 - 17:00
      expect(prefs.isQuietHours('u1', 9)).toBe(true);
      // BUG: endHour should be exclusive (17 should NOT be quiet)
      // Using <= makes endHour inclusive
      expect(prefs.isQuietHours('u1', 17)).toBe(false);
    });

    it('should return false when no quiet hours set', () => {
      expect(prefs.isQuietHours('u1', 12)).toBe(false);
    });
  });

  describe('getAllPreferences', () => {
    it('should return all preferences for a user', () => {
      prefs.setPreference('u1', 'email', 'mention', { enabled: true });
      prefs.setPreference('u1', 'push', 'edit', { enabled: false });

      const all = prefs.getAllPreferences('u1');
      expect(all.email).toBeDefined();
      expect(all.push).toBeDefined();
    });

    it('should return empty for unknown user', () => {
      expect(prefs.getAllPreferences('unknown')).toEqual({});
    });
  });
});
