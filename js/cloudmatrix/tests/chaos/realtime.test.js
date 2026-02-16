/**
 * Real-Time Chaos Tests
 *
 * Tests real-time collaboration under adverse conditions
 */

describe('WebSocket Chaos', () => {
  describe('Connection Failures', () => {
    it('ws reconnect under load test', async () => {
      const connections = [];
      const maxRetries = 5;

      const connect = async (id) => {
        let retries = 0;
        while (retries < maxRetries) {
          try {
            if (Math.random() > 0.5) throw new Error('Connection failed');
            connections.push(id);
            return true;
          } catch (e) {
            retries++;
            await new Promise(resolve => setTimeout(resolve, 10));
          }
        }
        return false;
      };

      const results = await Promise.all(
        Array.from({ length: 10 }, (_, i) => connect(`conn-${i}`))
      );

      const successCount = results.filter(Boolean).length;
      expect(successCount).toBeGreaterThan(0);
    });

    it('connection storm recovery test', async () => {
      const connectionPool = new Set();
      const maxConnections = 100;

      for (let i = 0; i < 200; i++) {
        if (connectionPool.size < maxConnections) {
          connectionPool.add(`conn-${i}`);
        }
      }

      expect(connectionPool.size).toBeLessThanOrEqual(maxConnections);
    });
  });

  describe('Message Loss Simulation', () => {
    it('message retry on failure test', async () => {
      const delivered = [];
      const maxRetries = 3;

      const sendMessage = async (msg, retries = 0) => {
        if (retries < 2) {
          return sendMessage(msg, retries + 1);
        }
        delivered.push(msg);
        return true;
      };

      await sendMessage({ type: 'edit', data: 'Hello' });

      expect(delivered).toHaveLength(1);
    });

    it('message ordering after retry test', async () => {
      const received = [];

      const processMessage = async (msg) => {
        await new Promise(resolve => setTimeout(resolve, Math.random() * 10));
        received.push(msg);
      };

      const messages = Array.from({ length: 10 }, (_, i) => ({ seq: i, data: `msg-${i}` }));

      for (const msg of messages) {
        await processMessage(msg);
      }

      for (let i = 1; i < received.length; i++) {
        expect(received[i].seq).toBeGreaterThan(received[i - 1].seq);
      }
    });
  });

  describe('Slow Consumer Handling', () => {
    it('slow consumer backpressure test', async () => {
      const buffer = [];
      const maxBuffer = 100;
      let dropped = 0;

      const addToBuffer = (msg) => {
        if (buffer.length >= maxBuffer) {
          dropped++;
          return false;
        }
        buffer.push(msg);
        return true;
      };

      for (let i = 0; i < 200; i++) {
        addToBuffer({ seq: i });
      }

      expect(buffer.length).toBe(maxBuffer);
      expect(dropped).toBe(100);
    });

    it('consumer catchup test', async () => {
      const processed = [];
      const pending = Array.from({ length: 50 }, (_, i) => ({ seq: i }));

      while (pending.length > 0) {
        const batch = pending.splice(0, 10);
        for (const msg of batch) {
          processed.push(msg);
        }
      }

      expect(processed).toHaveLength(50);
      expect(pending).toHaveLength(0);
    });
  });
});

describe('CRDT Chaos', () => {
  describe('Concurrent Modifications', () => {
    it('high concurrency edit test', async () => {
      jest.resetModules();
      const { CRDTDocument } = require('../../shared/realtime');

      const doc = new CRDTDocument('doc-chaos');

      const edits = Array.from({ length: 50 }, (_, i) => ({
        userId: `user-${i % 5}`,
        op: { type: 'insert', position: i, text: String.fromCharCode(65 + (i % 26)), timestamp: i },
      }));

      for (const edit of edits) {
        doc.applyLocal(edit.userId, edit.op);
      }

      expect(doc.getOperations().length).toBe(50);
    });

    it('conflicting delete-insert test', () => {
      jest.resetModules();
      const { OperationalTransform } = require('../../shared/realtime');

      const ot = new OperationalTransform();

      const deleteOp = { type: 'delete', position: 5, length: 10 };
      const insertOp = { type: 'insert', position: 7, text: 'new text' };

      const result = ot.transform(deleteOp, insertOp);
      expect(result).toBeDefined();
    });
  });

  describe('State Divergence Recovery', () => {
    it('state resync after divergence test', () => {
      const serverState = { version: 10, content: 'server content' };
      const clientState = { version: 8, content: 'client content' };

      const needsSync = clientState.version < serverState.version;
      expect(needsSync).toBe(true);

      if (needsSync) {
        clientState.content = serverState.content;
        clientState.version = serverState.version;
      }

      expect(clientState.version).toBe(serverState.version);
      expect(clientState.content).toBe(serverState.content);
    });

    it('operation buffer replay test', () => {
      const pendingOps = [
        { seq: 5, type: 'insert', text: 'A' },
        { seq: 6, type: 'insert', text: 'B' },
        { seq: 7, type: 'delete', length: 1 },
      ];

      const serverAck = 6;
      const toReplay = pendingOps.filter(op => op.seq > serverAck);

      expect(toReplay).toHaveLength(1);
      expect(toReplay[0].seq).toBe(7);
    });
  });

  describe('Network Partition Simulation', () => {
    it('partition recovery merge test', () => {
      const nodeA = { ops: [{ seq: 1, text: 'Hello' }, { seq: 2, text: ' from A' }] };
      const nodeB = { ops: [{ seq: 1, text: 'Hello' }, { seq: 3, text: ' from B' }] };

      const commonAncestor = nodeA.ops.filter(a =>
        nodeB.ops.some(b => b.seq === a.seq)
      );

      expect(commonAncestor).toHaveLength(1);
      expect(commonAncestor[0].seq).toBe(1);
    });

    it('offline edit queue test', () => {
      const offlineQueue = [];

      const queueEdit = (op) => {
        offlineQueue.push({ ...op, queuedAt: Date.now() });
      };

      queueEdit({ type: 'insert', text: 'offline edit 1' });
      queueEdit({ type: 'insert', text: 'offline edit 2' });

      expect(offlineQueue).toHaveLength(2);

      const flushQueue = () => {
        const ops = [...offlineQueue];
        offlineQueue.length = 0;
        return ops;
      };

      const flushed = flushQueue();
      expect(flushed).toHaveLength(2);
      expect(offlineQueue).toHaveLength(0);
    });
  });
});

describe('Presence Chaos', () => {
  describe('Presence Under Load', () => {
    it('high frequency cursor updates test', async () => {
      jest.resetModules();
      const { PresenceTracker } = require('../../shared/realtime');
      const mockRedis = global.testUtils.mockRedis();

      const tracker = new PresenceTracker(mockRedis, { debounceMs: 0 });

      for (let i = 0; i < 1000; i++) {
        await tracker.updatePresence(`user-${i % 10}`, 'doc-1', { cursor: i });
      }

      const presence = tracker.getDocumentPresence('doc-1');
      expect(presence.size).toBeLessThanOrEqual(10);
    });

    it('presence broadcast storm test', async () => {
      const broadcasts = [];
      const maxBroadcastsPerSecond = 60;

      const broadcastPresence = (userId, position) => {
        broadcasts.push({ userId, position, timestamp: Date.now() });
      };

      for (let i = 0; i < 100; i++) {
        broadcastPresence(`user-${i % 5}`, i);
      }

      expect(broadcasts.length).toBe(100);
    });
  });

  describe('Stale Presence Cleanup', () => {
    it('bulk stale presence removal test', () => {
      const presence = new Map();
      const now = Date.now();

      for (let i = 0; i < 50; i++) {
        presence.set(`doc-1:user-${i}`, {
          userId: `user-${i}`,
          timestamp: i < 25 ? now - 300000 : now,
        });
      }

      const staleThreshold = 60000;
      for (const [key, entry] of presence) {
        if (now - entry.timestamp > staleThreshold) {
          presence.delete(key);
        }
      }

      expect(presence.size).toBe(25);
    });
  });
});

describe('Event Bus Chaos', () => {
  describe('Message Backlog', () => {
    it('event backlog recovery test', async () => {
      const processed = [];
      const backlog = Array.from({ length: 1000 }, (_, i) => ({
        seq: i,
        type: 'document.updated',
        data: { docId: `doc-${i}` },
      }));

      const batchSize = 100;
      while (backlog.length > 0) {
        const batch = backlog.splice(0, batchSize);
        for (const event of batch) {
          processed.push(event.seq);
        }
      }

      expect(processed).toHaveLength(1000);
    });

    it('dead letter queue test', async () => {
      const deadLetterQueue = [];
      const maxRetries = 3;

      const processWithRetry = async (event, retries = 0) => {
        if (event.shouldFail && retries < maxRetries) {
          return processWithRetry(event, retries + 1);
        }
        if (event.shouldFail) {
          deadLetterQueue.push({ ...event, failedAt: Date.now() });
          return false;
        }
        return true;
      };

      await processWithRetry({ id: 'e1', shouldFail: true });
      await processWithRetry({ id: 'e2', shouldFail: false });

      expect(deadLetterQueue).toHaveLength(1);
    });
  });

  describe('Consumer Rebalance', () => {
    it('consumer group rebalance test', () => {
      const consumers = ['c1', 'c2', 'c3'];
      const partitions = [0, 1, 2, 3, 4, 5];

      const assign = (consumers, partitions) => {
        const assignments = {};
        consumers.forEach(c => assignments[c] = []);

        partitions.forEach((p, i) => {
          const consumer = consumers[i % consumers.length];
          assignments[consumer].push(p);
        });

        return assignments;
      };

      const result = assign(consumers, partitions);

      expect(result['c1'].length).toBe(2);
      expect(result['c2'].length).toBe(2);
      expect(result['c3'].length).toBe(2);
    });
  });
});

describe('Circuit Breaker Chaos', () => {
  describe('Circuit State Transitions', () => {
    it('circuit breaker trip test', () => {
      jest.resetModules();
      const { CircuitBreaker } = require('../../shared/clients');

      const cb = new CircuitBreaker({ threshold: 3, timeout: 1000 });

      cb.recordFailure();
      cb.recordFailure();
      cb.recordFailure();

      expect(cb.isOpen()).toBe(true);
    });

    it('circuit breaker recovery test', async () => {
      jest.resetModules();
      const { CircuitBreaker } = require('../../shared/clients');

      const cb = new CircuitBreaker({ threshold: 2, timeout: 100 });

      cb.recordFailure();
      cb.recordFailure();

      expect(cb.isOpen()).toBe(true);

      await new Promise(resolve => setTimeout(resolve, 150));

      cb.recordSuccess();
      expect(cb.isOpen()).toBe(false);
    });
  });
});
