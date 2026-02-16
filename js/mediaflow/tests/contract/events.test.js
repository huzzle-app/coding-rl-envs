/**
 * Event Contract Tests
 *
 * Tests BaseEvent, EventBus, and SchemaRegistry contracts.
 * Exercises bugs B2 (idempotency collision), B3 (schema evolution).
 */

const { BaseEvent, EventBus, SchemaRegistry, EventProjection } = require('../../shared/events');

describe('Video Event Contracts', () => {
  describe('video.created', () => {
    it('should generate unique idempotency keys for same-type events', () => {
      // BUG B2: idempotencyKey uses only type + timestamp
      // Two events created at same millisecond get same key
      const event1 = new BaseEvent('video.created', { videoId: 'v1' });
      const event2 = new BaseEvent('video.created', { videoId: 'v2' });

      // If created in same millisecond, keys collide
      expect(event1.idempotencyKey).not.toBe(event2.idempotencyKey);
    });

    it('should include unique ID in idempotency key', () => {
      const event = new BaseEvent('video.created', { videoId: 'v1' });

      // Key should incorporate the unique event ID, not just type+timestamp
      expect(event.idempotencyKey).toContain(event.id);
    });

    it('should have required event fields', () => {
      const event = new BaseEvent('video.created', { videoId: 'v1', title: 'Test' });

      expect(event.id).toBeDefined();
      expect(event.type).toBe('video.created');
      expect(event.data).toEqual({ videoId: 'v1', title: 'Test' });
      expect(event.metadata.timestamp).toBeDefined();
      expect(event.metadata.version).toBe(1);
    });

    it('should support custom metadata', () => {
      const event = new BaseEvent('video.created', { videoId: 'v1' }, {
        correlationId: 'corr-123',
        causationId: 'cause-456',
      });

      expect(event.metadata.correlationId).toBe('corr-123');
      expect(event.metadata.causationId).toBe('cause-456');
    });
  });

  describe('video.updated', () => {
    it('should serialize and deserialize correctly', () => {
      const original = new BaseEvent('video.updated', {
        videoId: 'v1',
        changes: { title: 'New Title' },
      });

      const json = original.serialize();
      const restored = BaseEvent.deserialize(json);

      expect(restored.type).toBe('video.updated');
      expect(restored.data.videoId).toBe('v1');
      expect(restored.id).toBe(original.id);
    });

    it('should preserve idempotency key through serialization', () => {
      const original = new BaseEvent('video.updated', { videoId: 'v1' });
      const json = original.serialize();
      const restored = BaseEvent.deserialize(json);

      expect(restored.idempotencyKey).toBe(original.idempotencyKey);
    });
  });

  describe('video.deleted', () => {
    it('should serialize to valid JSON', () => {
      const event = new BaseEvent('video.deleted', { videoId: 'v1' });
      const json = event.serialize();

      expect(() => JSON.parse(json)).not.toThrow();
      const parsed = JSON.parse(json);
      expect(parsed.type).toBe('video.deleted');
    });
  });

  describe('video.published', () => {
    it('should deserialize from plain object', () => {
      const obj = {
        id: 'evt-123',
        type: 'video.published',
        data: { videoId: 'v1' },
        metadata: { timestamp: Date.now(), version: 1 },
        idempotencyKey: 'video.published-12345',
      };

      const event = BaseEvent.deserialize(obj);
      expect(event.type).toBe('video.published');
      expect(event.id).toBe('evt-123');
    });
  });
});

describe('Transcode Event Contracts', () => {
  describe('transcode.started', () => {
    it('should register schema in registry', () => {
      const registry = new SchemaRegistry();
      const schema = {
        validate: (data) => data.jobId && data.profiles,
      };

      registry.register('transcode.started', 1, schema);
      const retrieved = registry.getSchema('transcode.started', 1);

      expect(retrieved).toBe(schema);
    });

    it('should validate event against registered schema', () => {
      const registry = new SchemaRegistry();
      registry.register('transcode.started', 1, {
        validate: (data) => !!data.jobId,
      });

      const event = new BaseEvent('transcode.started', { jobId: 'j1' });
      const result = registry.validate(event);

      expect(result).toBeTruthy();
    });
  });

  describe('transcode.progress', () => {
    it('should throw on unregistered schema version', () => {
      const registry = new SchemaRegistry();
      registry.register('transcode.progress', 1, {
        validate: (data) => true,
      });

      // BUG B3: Schema evolution - v2 event can't be validated
      const v2Event = new BaseEvent('transcode.progress', { jobId: 'j1' }, { version: 2 });

      expect(() => registry.validate(v2Event)).toThrow('Unknown schema');
    });
  });

  describe('transcode.completed', () => {
    it('should handle schema backward compatibility', () => {
      const registry = new SchemaRegistry();

      // Register v1 and v2 schemas
      registry.register('transcode.completed', 1, {
        validate: (data) => !!data.jobId,
      });
      registry.register('transcode.completed', 2, {
        validate: (data) => !!data.jobId && !!data.outputs,
      });

      // BUG B3: Old events with v1 should still be readable by v2 consumers
      const v1Event = new BaseEvent('transcode.completed', { jobId: 'j1' });
      const v2Event = new BaseEvent('transcode.completed', { jobId: 'j1', outputs: [] }, { version: 2 });

      // Both should validate with their respective schemas
      expect(registry.validate(v1Event)).toBeTruthy();
      expect(registry.validate(v2Event)).toBeTruthy();
    });
  });

  describe('transcode.failed', () => {
    it('should return null for non-existent schema', () => {
      const registry = new SchemaRegistry();
      const schema = registry.getSchema('nonexistent', 1);

      expect(schema).toBeUndefined();
    });
  });
});

describe('Subscription Event Contracts', () => {
  describe('subscription.created', () => {
    it('should track position in event projection', async () => {
      const projection = new EventProjection(null, { clear: jest.fn() });

      const event = new BaseEvent('subscription.created', { subId: 's1' });
      await projection.apply(event);

      expect(projection.position).toBe(event.metadata.timestamp);
    });
  });

  describe('subscription.canceled', () => {
    it('should reset position on rebuild', async () => {
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };
      const projection = new EventProjection(null, mockStorage);

      projection.position = 12345;
      await projection.rebuild();

      expect(projection.position).toBe(0);
      expect(mockStorage.clear).toHaveBeenCalled();
    });
  });
});

describe('Payment Event Contracts', () => {
  describe('payment.succeeded', () => {
    it('should generate unique event IDs', () => {
      const ids = new Set();
      for (let i = 0; i < 100; i++) {
        const event = new BaseEvent('payment.succeeded', { amount: 999 });
        ids.add(event.id);
      }

      expect(ids.size).toBe(100);
    });
  });

  describe('payment.failed', () => {
    it('should include metadata timestamp', () => {
      const before = Date.now();
      const event = new BaseEvent('payment.failed', { error: 'declined' });
      const after = Date.now();

      expect(event.metadata.timestamp).toBeGreaterThanOrEqual(before);
      expect(event.metadata.timestamp).toBeLessThanOrEqual(after);
    });
  });
});
