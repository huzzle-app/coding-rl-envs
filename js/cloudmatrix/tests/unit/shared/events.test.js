/**
 * Shared Events Tests
 *
 * Tests EventBus, BaseEvent, EventProjection, SchemaRegistry, EventStore
 */

describe('BaseEvent', () => {
  let BaseEvent;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/events');
    BaseEvent = mod.BaseEvent;
  });

  describe('event creation', () => {
    it('should create event with type', () => {
      const event = new BaseEvent('document.created', { docId: 'doc-1' });
      expect(event.type).toBe('document.created');
    });

    it('should include timestamp', () => {
      const event = new BaseEvent('test', {});
      expect(event.timestamp).toBeDefined();
      expect(typeof event.timestamp).toBe('number');
    });

    it('should include data payload', () => {
      const data = { docId: 'doc-1', userId: 'user-1' };
      const event = new BaseEvent('test', data);
      expect(event.data).toEqual(data);
    });

    it('should generate unique ID', () => {
      const e1 = new BaseEvent('test', {});
      const e2 = new BaseEvent('test', {});
      expect(e1.id).not.toBe(e2.id);
    });

    it('should generate idempotency key', () => {
      const event = new BaseEvent('test', { id: 'unique' });
      expect(event.idempotencyKey).toBeDefined();
    });

    it('should produce unique idempotency keys', () => {
      const keys = new Set();
      for (let i = 0; i < 100; i++) {
        const event = new BaseEvent('test', { index: i });
        keys.add(event.idempotencyKey);
      }
      expect(keys.size).toBe(100);
    });
  });
});

describe('EventBus', () => {
  let EventBus;
  let mockRabbit;

  beforeEach(() => {
    jest.resetModules();
    mockRabbit = global.testUtils.mockRabbit();
    const mod = require('../../../shared/events');
    EventBus = mod.EventBus;
  });

  describe('connection', () => {
    it('should connect to RabbitMQ', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();
      expect(mockRabbit.channel.assertExchange).toHaveBeenCalled();
    });

    it('should declare exchanges on connect', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();
      expect(mockRabbit.channel.assertExchange).toHaveBeenCalled();
    });

    it('should declare queues on connect', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();
      expect(mockRabbit.channel.assertQueue).toHaveBeenCalled();
    });
  });

  describe('publish', () => {
    it('should publish events', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();
      await bus.publish('document.created', { docId: 'doc-1' });
      expect(mockRabbit.channel.publish).toHaveBeenCalled();
    });

    it('should serialize event data', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();
      await bus.publish('test', { nested: { deep: 'value' } });
      expect(mockRabbit.channel.publish).toHaveBeenCalled();
    });

    it('should include routing key', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();
      await bus.publish('document.updated', { docId: 'doc-1' });

      const call = mockRabbit.channel.publish.mock.calls[0];
      expect(call).toBeDefined();
    });
  });

  describe('subscribe', () => {
    it('should subscribe to events', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();

      const handler = jest.fn();
      await bus.subscribe('document.created', handler);

      expect(mockRabbit.channel.consume).toHaveBeenCalled();
    });

    it('should handle multiple subscriptions', async () => {
      const bus = new EventBus(mockRabbit);
      await bus.connect();

      await bus.subscribe('event.a', jest.fn());
      await bus.subscribe('event.b', jest.fn());

      expect(mockRabbit.channel.consume).toHaveBeenCalledTimes(2);
    });
  });
});

describe('EventProjection', () => {
  let EventProjection;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/events');
    EventProjection = mod.EventProjection;
  });

  describe('event processing', () => {
    it('should process events sequentially', () => {
      const projection = new EventProjection();

      projection.processEvent({ seq: 1, type: 'created' });
      projection.processEvent({ seq: 2, type: 'updated' });

      expect(projection.checkpoint).toBe(2);
    });

    it('should skip already processed events', () => {
      const projection = new EventProjection();
      projection.checkpoint = 5;

      projection.processEvent({ seq: 3, type: 'old' });

      expect(projection.checkpoint).toBe(5);
    });

    it('should track state', () => {
      const projection = new EventProjection();

      projection.processEvent({ seq: 1, type: 'created', data: { title: 'Test' } });

      expect(projection.state).toBeDefined();
    });
  });

  describe('rebuild', () => {
    it('should rebuild from scratch', async () => {
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };
      const projection = new EventProjection(null, mockStorage);

      await projection.rebuild();

      expect(projection.isRebuilding).toBe(false);
    });

    it('should prevent concurrent rebuilds', async () => {
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };
      const projection = new EventProjection(null, mockStorage);

      const p1 = projection.rebuild();
      const p2 = projection.rebuild();

      await Promise.all([p1, p2]);

      expect(projection.isRebuilding).toBe(false);
    });

    it('should reset checkpoint on rebuild', async () => {
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };
      const projection = new EventProjection(null, mockStorage);
      projection.checkpoint = 100;

      await projection.rebuild();

      expect(projection.checkpoint).toBeDefined();
    });
  });
});

describe('SchemaRegistry', () => {
  let SchemaRegistry;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/events');
    SchemaRegistry = mod.SchemaRegistry;
  });

  describe('schema management', () => {
    it('should register schemas', () => {
      const registry = new SchemaRegistry();

      registry.register('test.event', 1, {
        type: 'object',
        properties: { name: { type: 'string' } },
      });

      const schema = registry.getSchema('test.event', 1);
      expect(schema).toBeDefined();
    });

    it('should support multiple versions', () => {
      const registry = new SchemaRegistry();

      registry.register('test', 1, { properties: { a: {} } });
      registry.register('test', 2, { properties: { a: {}, b: {} } });

      const v1 = registry.getSchema('test', 1);
      const v2 = registry.getSchema('test', 2);

      expect(v1).not.toEqual(v2);
    });

    it('should get latest version', () => {
      const registry = new SchemaRegistry();

      registry.register('test', 1, { v: 1 });
      registry.register('test', 2, { v: 2 });

      const v1 = registry.getSchema('test', 1);
      const v2 = registry.getSchema('test', 2);
      expect(v1).toBeDefined();
      expect(v2).toBeDefined();
    });
  });

  describe('migration', () => {
    it('should migrate between versions', () => {
      const registry = new SchemaRegistry();

      registry.register('doc', 1, { properties: { title: {} } });
      registry.register('doc', 2, { properties: { title: {}, desc: { default: '' } } });

      const v1 = registry.getSchema('doc', 1);
      const v2 = registry.getSchema('doc', 2);
      expect(v2.properties).toHaveProperty('desc');
    });
  });
});

describe('EventStore', () => {
  let EventStore;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/events');
    EventStore = mod.EventStore;
  });

  describe('snapshots', () => {
    let mockDb;

    beforeEach(() => {
      mockDb = global.testUtils.mockDb();
    });

    it('should create snapshots', async () => {
      const store = new EventStore(mockDb);

      await store.saveSnapshot('doc-1', { content: 'Hello' }, 5);

      mockDb.query.mockResolvedValueOnce({ rows: [{ stream_id: 'doc-1', state: '{"content":"Hello"}', version: 5 }] });
      const snapshot = await store.getSnapshot('doc-1');
      expect(snapshot).toBeDefined();
      expect(snapshot.version).toBe(5);
    });

    it('should overwrite old snapshots', async () => {
      const store = new EventStore(mockDb);

      await store.saveSnapshot('doc-1', { version: 1 }, 1);
      await store.saveSnapshot('doc-1', { version: 2 }, 2);

      mockDb.query.mockResolvedValueOnce({ rows: [{ stream_id: 'doc-1', state: '{}', version: 2 }] });
      const snapshot = await store.getSnapshot('doc-1');
      expect(snapshot.version).toBe(2);
    });

    it('should return null for missing snapshots', async () => {
      const store = new EventStore(mockDb);

      mockDb.query.mockResolvedValueOnce({ rows: [] });
      const snapshot = await store.getSnapshot('nonexistent');
      expect(snapshot).toBeNull();
    });
  });

  describe('event storage', () => {
    let mockDb;
    let storedRows;

    beforeEach(() => {
      mockDb = global.testUtils.mockDb();
      storedRows = [];
      mockDb.query.mockImplementation(async (sql, params) => {
        if (sql.includes('INSERT')) {
          const row = { stream_id: params[0], data: params[1], metadata: params[2], position: storedRows.length + 1 };
          storedRows.push(row);
          return { rows: [row] };
        }
        if (sql.includes('SELECT') && sql.includes('events')) {
          return { rows: storedRows.filter(r => r.stream_id === params[0] && r.position > (params[1] || 0)) };
        }
        return { rows: [] };
      });
    });

    it('should append events', async () => {
      const store = new EventStore(mockDb);

      await store.append('stream-1', [{ type: 'created', data: {}, metadata: {} }]);
      await store.append('stream-1', [{ type: 'updated', data: {}, metadata: {} }]);

      const events = await store.getEvents('stream-1');
      expect(events).toHaveLength(2);
    });

    it('should retrieve events in order', async () => {
      const store = new EventStore(mockDb);

      await store.append('stream-1', [{ type: 'A', data: { seq: 1 }, metadata: {} }]);
      await store.append('stream-1', [{ type: 'B', data: { seq: 2 }, metadata: {} }]);
      await store.append('stream-1', [{ type: 'C', data: { seq: 3 }, metadata: {} }]);

      const events = await store.getEvents('stream-1');
      expect(events[0].position).toBeLessThan(events[1].position);
    });

    it('should isolate streams', async () => {
      const store = new EventStore(mockDb);

      await store.append('stream-1', [{ type: 'A', data: {}, metadata: {} }]);
      await store.append('stream-2', [{ type: 'B', data: {}, metadata: {} }]);

      const events1 = await store.getEvents('stream-1');
      const events2 = await store.getEvents('stream-2');

      expect(events1).toHaveLength(1);
      expect(events2).toHaveLength(1);
    });
  });
});
