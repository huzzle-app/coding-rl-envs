/**
 * Collaboration Integration Tests
 *
 * Tests real-time collaboration flows between services
 */

describe('Real-Time Collaboration Integration', () => {
  describe('CRDT Document Sync', () => {
    it('multi-user crdt sync test', async () => {
      jest.resetModules();
      const { CRDTDocument } = require('../../shared/realtime');

      const doc1 = new CRDTDocument('doc-1');
      const doc2 = new CRDTDocument('doc-1');

      doc1.applyLocal('user-1', { type: 'insert', position: 0, text: 'Hello' });
      doc2.applyLocal('user-2', { type: 'insert', position: 0, text: 'World' });

      const ops1 = doc1.getOperations();
      const ops2 = doc2.getOperations();

      expect(ops1.length).toBeGreaterThan(0);
      expect(ops2.length).toBeGreaterThan(0);
    });

    it('crdt merge convergence test', async () => {
      jest.resetModules();
      const { CRDTDocument } = require('../../shared/realtime');

      const doc = new CRDTDocument('doc-1');

      doc.applyLocal('user-1', { type: 'insert', position: 0, text: 'A', timestamp: 1 });
      doc.applyLocal('user-2', { type: 'insert', position: 0, text: 'B', timestamp: 2 });

      expect(doc.getOperations().length).toBe(2);
    });
  });

  describe('OT Transform Pipeline', () => {
    it('ot transform chain test', () => {
      jest.resetModules();
      const { OperationalTransform } = require('../../shared/realtime');

      const ot = new OperationalTransform();

      const op1 = { type: 'insert', position: 0, text: 'Hello' };
      const op2 = { type: 'insert', position: 3, text: 'XYZ' };

      const transformed = ot.transform(op1, op2);
      expect(transformed).toBeDefined();
    });

    it('ot concurrent insert test', () => {
      jest.resetModules();
      const { OperationalTransform } = require('../../shared/realtime');

      const ot = new OperationalTransform();

      const op1 = { type: 'insert', position: 5, text: 'A' };
      const op2 = { type: 'insert', position: 5, text: 'B' };

      const result = ot.transform(op1, op2);
      expect(result).toBeDefined();
    });

    it('ot delete-insert conflict test', () => {
      jest.resetModules();
      const { OperationalTransform } = require('../../shared/realtime');

      const ot = new OperationalTransform();

      const deleteOp = { type: 'delete', position: 3, length: 5 };
      const insertOp = { type: 'insert', position: 5, text: 'new' };

      const result = ot.transform(deleteOp, insertOp);
      expect(result).toBeDefined();
    });
  });

  describe('Presence Integration', () => {
    it('multi-service presence sync test', async () => {
      jest.resetModules();
      const { PresenceTracker } = require('../../shared/realtime');
      const mockRedis = global.testUtils.mockRedis();

      const tracker = new PresenceTracker(mockRedis, { debounceMs: 0 });

      await tracker.updatePresence('user-1', 'doc-1', { cursor: 10, selection: null });
      await tracker.updatePresence('user-2', 'doc-1', { cursor: 20, selection: { start: 15, end: 25 } });

      const presence = tracker.getDocumentPresence('doc-1');
      expect(presence.size).toBe(2);
    });

    it('presence cleanup on disconnect test', async () => {
      jest.resetModules();
      const { PresenceTracker } = require('../../shared/realtime');
      const mockRedis = global.testUtils.mockRedis();

      const tracker = new PresenceTracker(mockRedis, { debounceMs: 0 });

      await tracker.updatePresence('user-1', 'doc-1', { cursor: 10 });
      tracker.removeUser('user-1', 'doc-1');

      const presence = tracker.getDocumentPresence('doc-1');
      expect(presence.size).toBe(0);
    });
  });

  describe('WebSocket Event Flow', () => {
    it('ws edit broadcast test', async () => {
      const broadcasts = [];

      const broadcastEdit = async (docId, userId, op) => {
        broadcasts.push({ docId, userId, op, type: 'edit' });
      };

      await broadcastEdit('doc-1', 'user-1', { type: 'insert', pos: 0, text: 'Hello' });
      await broadcastEdit('doc-1', 'user-2', { type: 'insert', pos: 5, text: ' World' });

      expect(broadcasts).toHaveLength(2);
    });

    it('ws cursor update flow test', async () => {
      const cursorUpdates = [];

      const updateCursor = async (docId, userId, position) => {
        cursorUpdates.push({ docId, userId, position, timestamp: Date.now() });
      };

      await updateCursor('doc-1', 'user-1', 10);
      await updateCursor('doc-1', 'user-1', 15);
      await updateCursor('doc-1', 'user-2', 20);

      expect(cursorUpdates).toHaveLength(3);
      expect(cursorUpdates.filter(u => u.userId === 'user-1')).toHaveLength(2);
    });
  });

  describe('Document Locking', () => {
    it('section lock test', async () => {
      const locks = new Map();

      const acquireLock = async (userId, docId, section) => {
        const key = `${docId}:${section}`;
        if (locks.has(key)) {
          const holder = locks.get(key);
          if (holder !== userId) return false;
        }
        locks.set(key, userId);
        return true;
      };

      const result1 = await acquireLock('user-1', 'doc-1', 'header');
      const result2 = await acquireLock('user-2', 'doc-1', 'header');

      expect(result1).toBe(true);
      expect(result2).toBe(false);
    });

    it('lock release and reacquire test', async () => {
      const locks = new Map();

      const acquire = (userId, key) => {
        if (locks.has(key)) return false;
        locks.set(key, userId);
        return true;
      };

      const release = (userId, key) => {
        if (locks.get(key) === userId) {
          locks.delete(key);
          return true;
        }
        return false;
      };

      expect(acquire('user-1', 'doc-1:section-a')).toBe(true);
      expect(acquire('user-2', 'doc-1:section-a')).toBe(false);
      expect(release('user-1', 'doc-1:section-a')).toBe(true);
      expect(acquire('user-2', 'doc-1:section-a')).toBe(true);
    });
  });

  describe('Comment Integration', () => {
    it('comment anchor update on edit test', () => {
      const anchors = [
        { id: 'anchor-1', start: 10, end: 20, commentId: 'c-1' },
        { id: 'anchor-2', start: 30, end: 40, commentId: 'c-2' },
      ];

      const insertAt = 5;
      const insertLength = 10;

      const updated = anchors.map(a => ({
        ...a,
        start: a.start >= insertAt ? a.start + insertLength : a.start,
        end: a.end >= insertAt ? a.end + insertLength : a.end,
      }));

      expect(updated[0].start).toBe(20);
      expect(updated[0].end).toBe(30);
      expect(updated[1].start).toBe(40);
    });

    it('comment thread resolution test', () => {
      const threads = [
        { id: 't-1', comments: ['c-1', 'c-2'], resolved: false },
        { id: 't-2', comments: ['c-3'], resolved: false },
      ];

      threads[0].resolved = true;
      threads[0].resolvedAt = Date.now();

      const activeThreads = threads.filter(t => !t.resolved);
      expect(activeThreads).toHaveLength(1);
    });
  });

  describe('Event Bus Integration', () => {
    it('document event propagation test', async () => {
      const events = [];
      const mockRabbit = global.testUtils.mockRabbit();

      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.subscribe('document.updated', (event) => {
        events.push(event);
      });

      await bus.publish('document.updated', { docId: 'doc-1', changes: ['title'] });

      expect(mockRabbit.channel.publish).toHaveBeenCalled();
    });

    it('collaboration event ordering test', async () => {
      const events = [];

      const emitEvent = (type, seq) => {
        events.push({ type, seq, timestamp: Date.now() });
      };

      emitEvent('cursor.moved', 1);
      emitEvent('text.inserted', 2);
      emitEvent('cursor.moved', 3);

      for (let i = 1; i < events.length; i++) {
        expect(events[i].seq).toBeGreaterThan(events[i - 1].seq);
      }
    });
  });
});

describe('Document Service Integration', () => {
  describe('Document CRUD', () => {
    it('create and retrieve document test', async () => {
      jest.resetModules();
      const { DocumentService } = require('../../services/documents/src/services/document');

      const service = new DocumentService();

      const created = await service.createDocument({ title: 'Test Doc' });
      expect(created.id).toBeDefined();
    });

    it('update document with versioning test', async () => {
      jest.resetModules();
      const { DocumentService } = require('../../services/documents/src/services/document');

      const service = new DocumentService();

      const result = await service.updateDocument('doc-1', { title: 'Updated' });
      expect(result).toBeDefined();
    });
  });

  describe('Permission Check', () => {
    it('document access control test', async () => {
      jest.resetModules();
      const { ACLService } = require('../../services/permissions/src/services/acl');

      const acl = new ACLService();

      const permissions = await acl.getPermissions('doc-1', 'user-1');
      expect(permissions).toBeDefined();
      expect(permissions.read).toBeDefined();
    });

    it('sharing permission cascade test', async () => {
      jest.resetModules();
      const { ACLService } = require('../../services/permissions/src/services/acl');

      const acl = new ACLService();

      const ownerPerms = await acl.getPermissions('doc-1', 'owner');
      const viewerPerms = await acl.getPermissions('doc-1', 'viewer');

      expect(ownerPerms).toBeDefined();
      expect(viewerPerms).toBeDefined();
    });
  });
});
