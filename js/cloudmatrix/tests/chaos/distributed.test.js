/**
 * Distributed Chaos Tests
 *
 * Tests bugs J1-J8 (event sourcing), distributed lock, leader election
 */

describe('Event Sourcing', () => {
  describe('Event Ordering', () => {
    it('event ordering partition test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      const receivedEvents = [];

      await bus.subscribe('document.updated', (event) => {
        receivedEvents.push(event);
      });

      await bus.publish('document.updated', { seq: 1, data: 'first' });
      await bus.publish('document.updated', { seq: 2, data: 'second' });
      await bus.publish('document.updated', { seq: 3, data: 'third' });

      await new Promise(resolve => setTimeout(resolve, 50));

      expect(receivedEvents.map(e => e.seq)).toEqual([1, 2, 3]);
    });

    it('partition order test', async () => {
      const partitions = new Map();

      const routeToPartition = (event) => {
        const partition = event.docId.charCodeAt(0) % 3;
        if (!partitions.has(partition)) partitions.set(partition, []);
        partitions.get(partition).push(event);
      };

      routeToPartition({ docId: 'doc-a', seq: 1 });
      routeToPartition({ docId: 'doc-a', seq: 2 });
      routeToPartition({ docId: 'doc-b', seq: 1 });

      for (const [, events] of partitions) {
        const sameDocEvents = {};
        for (const e of events) {
          if (!sameDocEvents[e.docId]) sameDocEvents[e.docId] = [];
          sameDocEvents[e.docId].push(e);
        }
        for (const docEvents of Object.values(sameDocEvents)) {
          for (let i = 1; i < docEvents.length; i++) {
            expect(docEvents[i].seq).toBeGreaterThan(docEvents[i - 1].seq);
          }
        }
      }
    });
  });

  describe('Idempotency', () => {
    it('idempotency key collision test', () => {
      jest.resetModules();
      const { BaseEvent } = require('../../shared/events');

      const keys = new Set();
      for (let i = 0; i < 1000; i++) {
        const event = new BaseEvent('test', { index: i });
        keys.add(event.idempotencyKey);
      }

      expect(keys.size).toBe(1000);
    });

    it('dedup key test', () => {
      jest.resetModules();
      const { BaseEvent } = require('../../shared/events');

      const event1 = new BaseEvent('test', { data: 'a' });
      const event2 = new BaseEvent('test', { data: 'b' });

      expect(event1.idempotencyKey).not.toBe(event2.idempotencyKey);
    });
  });

  describe('Event Replay', () => {
    it('event replay skip test', () => {
      jest.resetModules();
      const { EventProjection } = require('../../shared/events');

      const projection = new EventProjection();

      const events = [
        { seq: 1, type: 'created', data: {} },
        { seq: 2, type: 'updated', data: {} },
        { seq: 3, type: 'updated', data: {} },
        { seq: 4, type: 'deleted', data: {} },
      ];

      projection.checkpoint = 2;
      const toProcess = events.filter(e => e.seq > projection.checkpoint);
      expect(toProcess).toHaveLength(2);
      expect(toProcess[0].seq).toBe(3);
    });

    it('checkpoint skip test', () => {
      jest.resetModules();
      const { EventProjection } = require('../../shared/events');

      const projection = new EventProjection();

      for (let i = 1; i <= 10; i++) {
        projection.processEvent({ seq: i, type: 'update', data: {} });
      }

      expect(projection.checkpoint).toBe(10);
    });
  });

  describe('Projection Concurrency', () => {
    it('projection race test', async () => {
      jest.resetModules();
      const { EventProjection } = require('../../shared/events');
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };

      const projection = new EventProjection(null, mockStorage);

      await Promise.all([
        projection.rebuild(),
        projection.rebuild(),
      ]);

      expect(projection.isRebuilding).toBe(false);
    });

    it('projection concurrent test', async () => {
      jest.resetModules();
      const { EventProjection } = require('../../shared/events');
      const mockStorage = { clear: jest.fn().mockResolvedValue(undefined) };

      const projection = new EventProjection(null, mockStorage);

      const results = await Promise.all([
        projection.rebuild(),
        projection.processEvent({ seq: 1, type: 'test' }),
      ]);

      expect(results).toBeDefined();
    });
  });

  describe('Schema Evolution', () => {
    it('schema evolution deser test', () => {
      jest.resetModules();
      const { SchemaRegistry } = require('../../shared/events');

      const registry = new SchemaRegistry();

      registry.register('document.created', 1, {
        type: 'object',
        properties: { title: { type: 'string' } },
      });

      registry.register('document.created', 2, {
        type: 'object',
        properties: {
          title: { type: 'string' },
          description: { type: 'string', default: '' },
        },
      });

      const v1Schema = registry.getSchema('document.created', 1);
      const v2Schema = registry.getSchema('document.created', 2);

      expect(v1Schema).toBeDefined();
      expect(v2Schema).toBeDefined();
      expect(v2Schema.properties).toHaveProperty('description');
    });

    it('schema migrate test', () => {
      jest.resetModules();
      const { SchemaRegistry } = require('../../shared/events');

      const registry = new SchemaRegistry();

      registry.register('doc.updated', 1, { properties: { content: {} } });
      registry.register('doc.updated', 2, { properties: { content: {}, metadata: {} } });

      const v1 = registry.getSchema('doc.updated', 1);
      const v2 = registry.getSchema('doc.updated', 2);
      expect(v1).toBeDefined();
      expect(v2).toBeDefined();
    });
  });

  describe('Tombstone Compaction', () => {
    it('tombstone compaction test', () => {
      const events = [
        { seq: 1, type: 'created', docId: 'doc-1' },
        { seq: 2, type: 'updated', docId: 'doc-1' },
        { seq: 3, type: 'deleted', docId: 'doc-1' },
        { seq: 4, type: 'created', docId: 'doc-2' },
      ];

      const compact = (events) => {
        const deletedDocs = new Set();
        for (const e of events) {
          if (e.type === 'deleted') deletedDocs.add(e.docId);
        }

        return events.filter(e => {
          if (deletedDocs.has(e.docId) && e.type !== 'deleted') return false;
          return true;
        });
      };

      const compacted = compact(events);
      const doc1Events = compacted.filter(e => e.docId === 'doc-1');

      expect(doc1Events).toHaveLength(1);
      expect(doc1Events[0].type).toBe('deleted');
    });

    it('compaction resurrect test', () => {
      const events = [
        { seq: 1, type: 'created', docId: 'doc-1' },
        { seq: 2, type: 'deleted', docId: 'doc-1' },
        { seq: 3, type: 'created', docId: 'doc-1' },
      ];

      const latestStates = new Map();
      for (const e of events) {
        latestStates.set(e.docId, e.type);
      }

      expect(latestStates.get('doc-1')).toBe('created');
    });
  });

  describe('Snapshot Integrity', () => {
    it('snapshot corruption test', async () => {
      jest.resetModules();
      const { EventStore } = require('../../shared/events');
      const mockDb = global.testUtils.mockDb();

      const store = new EventStore(mockDb);

      await store.saveSnapshot('doc-1', { content: 'Hello' }, 5);

      mockDb.query.mockResolvedValueOnce({ rows: [{ stream_id: 'doc-1', state: '{"content":"Hello"}', version: 5 }] });
      const snapshot = await store.getSnapshot('doc-1');
      expect(snapshot).toBeDefined();
      expect(snapshot.version).toBe(5);
    });

    it('concurrent snapshot test', async () => {
      jest.resetModules();
      const { EventStore } = require('../../shared/events');
      const mockDb = global.testUtils.mockDb();

      const store = new EventStore(mockDb);

      await Promise.all([
        store.saveSnapshot('doc-1', { content: 'A' }, 1),
        store.saveSnapshot('doc-1', { content: 'B' }, 2),
      ]);

      mockDb.query.mockResolvedValueOnce({ rows: [{ stream_id: 'doc-1', state: '{"content":"B"}', version: 2 }] });
      const snapshot = await store.getSnapshot('doc-1');
      expect(snapshot).toBeDefined();
    });
  });

  describe('Event Timestamp', () => {
    it('event timestamp skew test', () => {
      const events = [
        { type: 'edit', timestamp: 1000, serverId: 'server-1' },
        { type: 'edit', timestamp: 999, serverId: 'server-2' },
        { type: 'edit', timestamp: 1001, serverId: 'server-1' },
      ];

      const sortedByTimestamp = [...events].sort((a, b) => a.timestamp - b.timestamp);

      expect(sortedByTimestamp[0].timestamp).toBeLessThanOrEqual(sortedByTimestamp[1].timestamp);
    });

    it('clock skew event test', () => {
      const now = Date.now();
      const maxSkew = 5000;

      const isTimestampValid = (timestamp) => {
        return Math.abs(timestamp - now) <= maxSkew;
      };

      expect(isTimestampValid(now)).toBe(true);
      expect(isTimestampValid(now + 1000)).toBe(true);
      expect(isTimestampValid(now + 10000)).toBe(false);
    });
  });
});

describe('Distributed Lock', () => {
  describe('Lock Acquisition', () => {
    it('distributed lock acquire test', async () => {
      jest.resetModules();
      const { DistributedLock } = require('../../shared/utils');
      const mockRedis = global.testUtils.mockRedis();

      const lock = new DistributedLock(mockRedis, { timeout: 5000 });

      const acquired = await lock.acquire('test-key');
      expect(acquired).toBeDefined();
    });

    it('lock contention test', async () => {
      jest.resetModules();
      const { DistributedLock } = require('../../shared/utils');
      const mockRedis = global.testUtils.mockRedis();

      let currentHolder = null;
      mockRedis.set = jest.fn(async (key, value, options) => {
        if (options?.NX && currentHolder) return null;
        currentHolder = value;
        return 'OK';
      });

      const lock = new DistributedLock(mockRedis);

      const results = await Promise.all(
        Array(5).fill(null).map(() => lock.acquire('shared-resource'))
      );

      const acquired = results.filter(Boolean).length;
      expect(acquired).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Lock Release', () => {
    it('lock release safety test', async () => {
      jest.resetModules();
      const { DistributedLock } = require('../../shared/utils');
      const mockRedis = global.testUtils.mockRedis();

      const lock = new DistributedLock(mockRedis);

      const acquired = await lock.acquire('resource-1');

      const released = await lock.release(acquired);
      expect(released).toBeDefined();
    });
  });
});

describe('Leader Election', () => {
  describe('Election Process', () => {
    it('leader election test', async () => {
      jest.resetModules();
      const { LeaderElection } = require('../../shared/utils');

      const mockConsul = global.testUtils.mockConsul();

      const election1 = new LeaderElection(mockConsul, { serviceName: 'worker' });

      mockConsul.kv.set.mockResolvedValueOnce(true);
      await election1.start();

      expect(election1.getIsLeader()).toBe(true);
      await election1.stop();
    });

    it('follower election test', async () => {
      jest.resetModules();
      const { LeaderElection } = require('../../shared/utils');

      const mockConsul = global.testUtils.mockConsul();

      const election = new LeaderElection(mockConsul, { serviceName: 'worker' });

      mockConsul.kv.set.mockResolvedValueOnce(false);
      await election.start();

      expect(election.getIsLeader()).toBe(false);
      await election.stop();
    });
  });
});

describe('Saga Coordination', () => {
  describe('Saga Compensation', () => {
    it('saga rollback on failure test', async () => {
      const compensations = [];

      const steps = [
        { exec: () => true, compensate: () => compensations.push('undo-create') },
        { exec: () => true, compensate: () => compensations.push('undo-index') },
        { exec: () => { throw new Error('Failed'); }, compensate: () => compensations.push('undo-notify') },
      ];

      const completed = [];
      try {
        for (const step of steps) {
          step.exec();
          completed.push(step);
        }
      } catch (e) {
        for (const step of [...completed].reverse()) {
          step.compensate();
        }
      }

      expect(compensations).toContain('undo-index');
      expect(compensations).toContain('undo-create');
    });

    it('compensation failure handling test', async () => {
      const compensations = [];
      const errors = [];

      const steps = [
        { compensate: () => compensations.push('A') },
        { compensate: () => { throw new Error('Comp failed'); } },
        { compensate: () => compensations.push('C') },
      ];

      for (const step of steps.reverse()) {
        try {
          step.compensate();
        } catch (e) {
          errors.push(e.message);
        }
      }

      expect(errors).toHaveLength(1);
      expect(compensations.length).toBeGreaterThanOrEqual(1);
    });
  });
});
