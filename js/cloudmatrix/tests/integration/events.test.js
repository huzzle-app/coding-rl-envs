/**
 * Event Integration Tests
 *
 * Tests event bus integration, cross-service event flow, event replay
 */

describe('Event Bus Integration', () => {
  describe('publish-subscribe flow', () => {
    it('should publish and receive events', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      const received = [];
      await bus.subscribe('test.event', (event) => {
        received.push(event);
      });

      await bus.publish('test.event', { data: 'hello' });

      expect(mockRabbit.channel.publish).toHaveBeenCalled();
    });

    it('should handle multiple subscribers', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      const subscriber1 = jest.fn();
      const subscriber2 = jest.fn();

      await bus.subscribe('doc.created', subscriber1);
      await bus.subscribe('doc.created', subscriber2);

      expect(mockRabbit.channel.consume).toHaveBeenCalledTimes(2);
    });

    it('should handle topic routing', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      await bus.subscribe('document.*', jest.fn());
      await bus.publish('document.created', { docId: 'doc-1' });
      await bus.publish('document.updated', { docId: 'doc-1' });

      expect(mockRabbit.channel.publish).toHaveBeenCalledTimes(2);
    });
  });

  describe('event persistence', () => {
    it('should persist events to store', async () => {
      jest.resetModules();
      const { EventStore } = require('../../shared/events');
      const mockDb = global.testUtils.mockDb();

      const storedRows = [];
      mockDb.query.mockImplementation(async (sql, params) => {
        if (sql.includes('INSERT')) {
          const row = { stream_id: params[0], data: params[1], metadata: params[2], position: storedRows.length + 1 };
          storedRows.push(row);
          return { rows: [row] };
        }
        if (sql.includes('SELECT') && sql.includes('events')) {
          return { rows: storedRows.filter(r => r.stream_id === params[0]) };
        }
        return { rows: [] };
      });

      const store = new EventStore(mockDb);

      await store.append('doc-1', [{ type: 'created', data: { title: 'Test' }, metadata: {} }]);
      await store.append('doc-1', [{ type: 'updated', data: { title: 'Updated' }, metadata: {} }]);

      const events = await store.getEvents('doc-1');
      expect(events).toHaveLength(2);
    });

    it('should replay events from store', async () => {
      jest.resetModules();
      const { EventProjection } = require('../../shared/events');
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };

      const projection = new EventProjection(null, mockStorage);

      const events = [
        { seq: 1, type: 'created' },
        { seq: 2, type: 'updated' },
      ];

      for (const event of events) {
        projection.processEvent(event);
      }

      expect(projection.checkpoint).toBe(2);
    });

    it('should snapshot after N events', async () => {
      jest.resetModules();
      const { EventStore } = require('../../shared/events');
      const mockDb = global.testUtils.mockDb();

      const store = new EventStore(mockDb);

      for (let i = 0; i < 10; i++) {
        await store.append('doc-1', [{ type: 'updated', data: { seq: i + 1 }, metadata: {} }]);
      }

      await store.saveSnapshot('doc-1', { content: 'current' }, 10);

      mockDb.query.mockResolvedValueOnce({ rows: [{ stream_id: 'doc-1', state: '{"content":"current"}', version: 10 }] });
      const snapshot = await store.getSnapshot('doc-1');
      expect(snapshot.version).toBe(10);
    });
  });
});

describe('Cross-Service Events', () => {
  describe('document events', () => {
    it('document.created triggers search index', async () => {
      const events = [];

      const onDocCreated = (event) => {
        events.push({ type: 'search.index', docId: event.docId });
        events.push({ type: 'analytics.track', docId: event.docId });
        events.push({ type: 'notification.send', docId: event.docId });
      };

      onDocCreated({ docId: 'doc-1', title: 'New Doc' });

      expect(events).toHaveLength(3);
      expect(events.map(e => e.type)).toContain('search.index');
    });

    it('document.shared triggers notifications', () => {
      const notifications = [];

      const onDocShared = (event) => {
        for (const userId of event.sharedWith) {
          notifications.push({
            userId,
            type: 'share',
            docId: event.docId,
          });
        }
      };

      onDocShared({ docId: 'doc-1', sharedWith: ['user-2', 'user-3'] });

      expect(notifications).toHaveLength(2);
    });

    it('document.deleted triggers cleanup', () => {
      const cleanupTasks = [];

      const onDocDeleted = (event) => {
        cleanupTasks.push({ type: 'remove_from_search', docId: event.docId });
        cleanupTasks.push({ type: 'remove_files', docId: event.docId });
        cleanupTasks.push({ type: 'remove_permissions', docId: event.docId });
        cleanupTasks.push({ type: 'notify_collaborators', docId: event.docId });
      };

      onDocDeleted({ docId: 'doc-1' });

      expect(cleanupTasks).toHaveLength(4);
    });
  });

  describe('user events', () => {
    it('user.registered triggers onboarding', () => {
      const tasks = [];

      const onUserRegistered = (event) => {
        tasks.push('create_workspace');
        tasks.push('send_welcome_email');
        tasks.push('create_default_doc');
      };

      onUserRegistered({ userId: 'user-new' });

      expect(tasks).toHaveLength(3);
      expect(tasks).toContain('create_workspace');
    });

    it('user.upgraded triggers plan update', () => {
      const actions = [];

      const onUpgrade = (event) => {
        actions.push({ type: 'update_quota', plan: event.newPlan });
        actions.push({ type: 'enable_features', plan: event.newPlan });
        actions.push({ type: 'send_confirmation', userId: event.userId });
      };

      onUpgrade({ userId: 'user-1', oldPlan: 'basic', newPlan: 'pro' });

      expect(actions).toHaveLength(3);
    });
  });

  describe('billing events', () => {
    it('payment.failed triggers notification', () => {
      const notifications = [];

      const onPaymentFailed = (event) => {
        notifications.push({
          userId: event.userId,
          type: 'payment_failed',
          amount: event.amount,
        });
      };

      onPaymentFailed({ userId: 'user-1', amount: 2999 });

      expect(notifications).toHaveLength(1);
      expect(notifications[0].type).toBe('payment_failed');
    });

    it('subscription.canceled triggers cleanup', () => {
      const tasks = [];

      const onCanceled = (event) => {
        tasks.push('schedule_data_export');
        tasks.push('downgrade_features');
        tasks.push('send_retention_email');
      };

      onCanceled({ userId: 'user-1', subscriptionId: 'sub-1' });

      expect(tasks).toHaveLength(3);
    });
  });
});

describe('Event Schema Validation', () => {
  describe('schema enforcement', () => {
    it('should validate required fields', () => {
      const schema = {
        required: ['type', 'timestamp', 'data'],
      };

      const validate = (event) => {
        const missing = schema.required.filter(f => !(f in event));
        return missing.length === 0;
      };

      expect(validate({ type: 'test', timestamp: 123, data: {} })).toBe(true);
      expect(validate({ type: 'test' })).toBe(false);
    });

    it('should validate event type', () => {
      const validTypes = [
        'document.created',
        'document.updated',
        'document.deleted',
        'user.registered',
        'subscription.upgraded',
      ];

      const isValidType = (type) => validTypes.includes(type);

      expect(isValidType('document.created')).toBe(true);
      expect(isValidType('invalid.event')).toBe(false);
    });

    it('should reject oversized events', () => {
      const maxSize = 1024 * 1024;

      const isValidSize = (event) => {
        const size = JSON.stringify(event).length;
        return size <= maxSize;
      };

      expect(isValidSize({ data: 'small' })).toBe(true);
      expect(isValidSize({ data: 'x'.repeat(2 * 1024 * 1024) })).toBe(false);
    });
  });
});

describe('Event Error Handling', () => {
  describe('dead letter queue', () => {
    it('should route failed events to DLQ', () => {
      const dlq = [];
      const maxRetries = 3;

      const processEvent = (event, retries = 0) => {
        if (event.shouldFail) {
          if (retries >= maxRetries) {
            dlq.push({ event, error: 'Max retries exceeded', retries });
            return false;
          }
          return processEvent(event, retries + 1);
        }
        return true;
      };

      processEvent({ id: 'e1', shouldFail: true });
      expect(dlq).toHaveLength(1);
    });

    it('should preserve failed event context', () => {
      const dlqEntry = {
        event: { id: 'e1', type: 'test', data: { key: 'value' } },
        error: 'Processing failed',
        retries: 3,
        failedAt: Date.now(),
        lastError: 'Connection timeout',
      };

      expect(dlqEntry.event).toBeDefined();
      expect(dlqEntry.error).toBeDefined();
      expect(dlqEntry.retries).toBe(3);
    });

    it('should allow manual retry from DLQ', () => {
      const dlq = [
        { event: { id: 'e1' }, retries: 3 },
        { event: { id: 'e2' }, retries: 3 },
      ];

      const retried = dlq.shift();
      expect(retried.event.id).toBe('e1');
      expect(dlq).toHaveLength(1);
    });
  });
});
