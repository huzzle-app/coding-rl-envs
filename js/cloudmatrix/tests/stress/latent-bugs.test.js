/**
 * Latent Bug Tests
 *
 * Tests for bugs that silently corrupt state without immediately causing failures.
 */

describe('Latent Bug Detection', () => {
  describe('CRDT Snapshot Isolation', () => {
    it('snapshot should not share references with internal state', () => {
      const { CRDTDocument } = require('../../shared/realtime');
      const doc = new CRDTDocument('doc-1');

      doc.applyOperation({ type: 'insert', position: 0, content: 'Hello' });
      doc.applyOperation({ type: 'format', position: 0, length: 5, format: { bold: true } });

      const snapshot = doc.snapshot();
      snapshot.state.formats.push({ position: 0, length: 5, format: { italic: true } });

      const currentState = doc.getState();
      expect(currentState.formats).toHaveLength(1);
      expect(currentState.formats[0].format.bold).toBe(true);
    });

    it('snapshot modifications should not affect subsequent operations', () => {
      const { CRDTDocument } = require('../../shared/realtime');
      const doc = new CRDTDocument('doc-2');

      doc.applyOperation({ type: 'insert', position: 0, content: 'World' });
      doc.applyOperation({ type: 'format', position: 0, length: 5, format: { bold: true } });

      const snapshot1 = doc.snapshot();
      snapshot1.state.text = 'MODIFIED';

      doc.applyOperation({ type: 'insert', position: 5, content: '!' });
      expect(doc.getState().text).toBe('World!');
    });

    it('snapshot clock should be independent copy', () => {
      const { CRDTDocument } = require('../../shared/realtime');
      const doc = new CRDTDocument('doc-3');

      doc.merge({ title: 'Test' }, { title: 5 });
      const snapshot = doc.snapshot();
      snapshot.clock.title = 999;

      expect(doc.snapshot().clock.title).toBe(5);
    });
  });

  describe('WebSocket Room Metadata Leak', () => {
    it('room metadata should be cleaned up when room is empty', () => {
      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager();

      const mockWs = { readyState: 1, send: jest.fn(), terminate: jest.fn() };
      manager.connections.set('conn-1', { ws: mockWs, rooms: new Set(), lastPing: Date.now() });

      manager._joinRoom('conn-1', 'room-1');
      expect(manager.roomMetadata.has('room-1')).toBe(true);

      manager._leaveRoom('conn-1', 'room-1');

      const room = manager.rooms.get('room-1');
      expect(!room || room.size === 0).toBe(true);
      expect(manager.roomMetadata.has('room-1')).toBe(false);
    });

    it('room metadata should not accumulate for transient rooms', () => {
      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager();

      const mockWs = { readyState: 1, send: jest.fn(), terminate: jest.fn() };
      manager.connections.set('conn-1', { ws: mockWs, rooms: new Set(), lastPing: Date.now() });

      for (let i = 0; i < 100; i++) {
        manager._joinRoom('conn-1', `room-${i}`);
        manager._leaveRoom('conn-1', `room-${i}`);
      }

      expect(manager.roomMetadata.size).toBe(0);
    });

    it('room metadata peak members should track correctly', () => {
      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager();

      for (let i = 0; i < 5; i++) {
        const mockWs = { readyState: 1, send: jest.fn(), terminate: jest.fn() };
        manager.connections.set(`conn-${i}`, { ws: mockWs, rooms: new Set(), lastPing: Date.now() });
        manager._joinRoom(`conn-${i}`, 'room-peak');
      }

      for (let i = 0; i < 3; i++) {
        manager._leaveRoom(`conn-${i}`, 'room-peak');
      }

      const meta = manager.roomMetadata.get('room-peak');
      expect(meta.peakMembers).toBe(5);
      expect(meta.totalJoins).toBe(5);
    });
  });

  describe('Connection Pool Active Count Drift', () => {
    it('active count should be consistent after acquire-release cycles through waiters', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(2);

      const conn1 = await pool.acquire();
      const conn2 = await pool.acquire();

      const waiterPromise = pool.acquire();
      pool.release(conn1);
      const conn3 = await waiterPromise;

      pool.release(conn2);
      pool.release(conn3);

      const stats = pool.getStats();
      expect(stats.active).toBe(0);
      expect(stats.available).toBe(2);
    });

    it('active count should remain correct under repeated waiter resolution', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(1);

      for (let i = 0; i < 10; i++) {
        const conn = await pool.acquire();
        const waiterPromise = pool.acquire();
        pool.release(conn);
        const waiterConn = await waiterPromise;
        pool.release(waiterConn);
      }

      const stats = pool.getStats();
      expect(stats.active).toBe(0);
    });

    it('pool should not allow more concurrent connections than maxSize', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(3);

      const conns = [];
      for (let i = 0; i < 3; i++) {
        conns.push(await pool.acquire());
      }

      let waiterResolved = false;
      const waiterPromise = pool.acquire().then(c => {
        waiterResolved = true;
        return c;
      });

      await new Promise(resolve => setTimeout(resolve, 50));
      expect(waiterResolved).toBe(false);
      expect(pool.getStats().active).toBe(3);

      pool.release(conns[0]);
      const waiterConn = await waiterPromise;
      expect(waiterResolved).toBe(true);

      pool.release(conns[1]);
      pool.release(conns[2]);
      pool.release(waiterConn);

      expect(pool.getStats().active).toBe(0);
    });
  });

  describe('Bloom Filter Hash Count', () => {
    it('bloom filter should generate correct number of hashes', () => {
      const { BloomFilter } = require('../../shared/utils');
      const filter = new BloomFilter(1024, 3);

      filter.add('test-item');

      const stats = filter.getStats();
      expect(stats.setBits).toBeLessThanOrEqual(3);
    });

    it('bloom filter expected false positive rate should match actual', () => {
      const { BloomFilter } = require('../../shared/utils');
      const filter = new BloomFilter(1000, 3);

      for (let i = 0; i < 100; i++) {
        filter.add(`item-${i}`);
      }

      let falsePositives = 0;
      const testCount = 10000;
      for (let i = 0; i < testCount; i++) {
        if (filter.mightContain(`nonexistent-${i}`)) {
          falsePositives++;
        }
      }

      const actualRate = falsePositives / testCount;
      const expectedRate = filter.getExpectedFalsePositiveRate();

      expect(Math.abs(actualRate - expectedRate)).toBeLessThan(0.05);
    });
  });

  describe('Event Deduplication Window', () => {
    it('should not reprocess events after trim window', () => {
      const { BaseEvent, EventBus } = require('../../shared/events');

      const bus = new EventBus({
        createChannel: jest.fn().mockResolvedValue({
          assertExchange: jest.fn(),
          assertQueue: jest.fn(),
          bindQueue: jest.fn(),
          publish: jest.fn(),
          consume: jest.fn(),
          ack: jest.fn(),
          nack: jest.fn(),
        }),
      }, { maxProcessedEvents: 10 });

      for (let i = 0; i < 15; i++) {
        const event = new BaseEvent('test.event', { index: i });
        bus.processedEvents.add(event.idempotencyKey);
      }

      expect(bus.processedEvents.size).toBeLessThanOrEqual(15);

      const earlyEvent = new BaseEvent('test.event', { index: 0 });
      earlyEvent.metadata.timestamp = Date.now() - 1000;
      earlyEvent.idempotencyKey = `test.event-${earlyEvent.metadata.timestamp}`;

      expect(bus.processedEvents.has(earlyEvent.idempotencyKey)).toBe(false);
    });
  });

  describe('Token Bucket Precision', () => {
    it('should not accumulate floating point errors over many refills', () => {
      const { TokenBucketRateLimiter } = require('../../shared/utils');
      const limiter = new TokenBucketRateLimiter({
        maxTokens: 100,
        refillRate: 10,
        initialTokens: 0,
      });

      const originalLastRefill = limiter.lastRefillTime;
      limiter.lastRefillTime = originalLastRefill - 10000;
      limiter._refill();

      expect(limiter.tokens).toBe(100);
      expect(Number.isInteger(limiter.tokens) || limiter.tokens === 100).toBe(true);
    });

    it('concurrent tryConsume calls should not exceed rate limit', () => {
      const { TokenBucketRateLimiter } = require('../../shared/utils');
      const limiter = new TokenBucketRateLimiter({
        maxTokens: 5,
        refillRate: 0,
        initialTokens: 5,
      });

      let consumed = 0;
      for (let i = 0; i < 10; i++) {
        if (limiter.tryConsume()) {
          consumed++;
        }
      }

      expect(consumed).toBe(5);
    });
  });

  describe('Consistent Hash Distribution', () => {
    it('should distribute keys evenly across nodes', () => {
      const { ConsistentHashRing } = require('../../shared/utils');
      const ring = new ConsistentHashRing(100);

      ring.addNode('node-a');
      ring.addNode('node-b');
      ring.addNode('node-c');

      const keys = [];
      for (let i = 0; i < 3000; i++) {
        keys.push(`key-${i}-${Math.random().toString(36)}`);
      }

      const distribution = ring.getDistribution(keys);
      const values = Object.values(distribution);
      const avg = keys.length / 3;

      for (const count of values) {
        const deviation = Math.abs(count - avg) / avg;
        expect(deviation).toBeLessThan(0.3);
      }
    });

    it('should reassign minimal keys when node is removed', () => {
      const { ConsistentHashRing } = require('../../shared/utils');
      const ring = new ConsistentHashRing(100);

      ring.addNode('node-a');
      ring.addNode('node-b');
      ring.addNode('node-c');

      const keys = Array.from({ length: 1000 }, (_, i) => `key-${i}`);
      const before = {};
      for (const key of keys) {
        before[key] = ring.getNode(key);
      }

      ring.removeNode('node-c');

      let reassigned = 0;
      for (const key of keys) {
        if (ring.getNode(key) !== before[key] && before[key] !== 'node-c') {
          reassigned++;
        }
      }

      expect(reassigned / keys.length).toBeLessThan(0.1);
    });
  });

  describe('WebSocket Message Sequence Gaps', () => {
    it('should detect and handle out-of-order messages', () => {
      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager();

      const mockWs = {
        readyState: 1,
        send: jest.fn(),
        on: jest.fn(),
        terminate: jest.fn(),
      };

      manager.connections.set('conn-1', {
        ws: mockWs,
        rooms: new Set(),
        lastPing: Date.now(),
        authenticated: true,
      });

      manager._handleMessage('conn-1', JSON.stringify({ seq: 1, type: 'broadcast', roomId: 'r1', data: {} }));
      manager._handleMessage('conn-1', JSON.stringify({ seq: 3, type: 'broadcast', roomId: 'r1', data: {} }));

      expect(manager.messageSequence.get('conn-1')).toBe(3);

      manager._handleMessage('conn-1', JSON.stringify({ seq: 2, type: 'broadcast', roomId: 'r1', data: {} }));

      expect(manager.messageSequence.get('conn-1')).not.toBeLessThan(3);
    });
  });
});
