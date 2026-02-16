/**
 * CRDT and Operational Transform Tests
 *
 * Tests bugs A1-A12 (real-time sync), L1 (circular import)
 */

describe('CRDTDocument', () => {
  let CRDTDocument;

  beforeEach(() => {
    jest.resetModules();
  });

  describe('circular import', () => {
    it('shared module loading test', () => {
      expect(() => {
        require('../../../shared/realtime');
      }).not.toThrow();
    });
  });

  describe('CRDT merge', () => {
    beforeEach(() => {
      const mod = require('../../../shared/realtime');
      CRDTDocument = mod.CRDTDocument;
    });

    it('crdt merge conflict test', () => {
      const doc1 = new CRDTDocument('doc-1');
      const doc2 = new CRDTDocument('doc-1');

      doc1.state = { title: 'Hello', text: 'World' };
      doc1.clock = { title: 5, text: 3 };

      doc2.state = { title: 'Hi', text: 'Earth' };
      doc2.clock = { title: 5, text: 4 };

      const merged = doc1.merge(doc2.state, doc2.clock);

      expect(merged.title).toBe('Hello');
      expect(merged.text).toBe('Earth');
    });

    it('concurrent edit merge test', () => {
      const doc1 = new CRDTDocument('doc-1');
      const doc2 = new CRDTDocument('doc-1');

      doc1.state = { text: 'abc' };
      doc1.clock = { text: 1 };
      doc2.state = { text: 'xyz' };
      doc2.clock = { text: 2 };

      const merged = doc1.merge(doc2.state, doc2.clock);
      expect(merged.text).toBe('xyz');
    });

    it('should handle nested object merge', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { meta: { title: 'old' } };
      doc.clock = { meta: 1 };

      const remoteState = { meta: { title: 'new', author: 'user' } };
      const remoteClock = { meta: 2 };

      const merged = doc.merge(remoteState, remoteClock);
      expect(merged.meta).toEqual({ title: 'new', author: 'user' });
    });

    it('should not overwrite with older data', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'newer' };
      doc.clock = { text: 5 };

      const merged = doc.merge({ text: 'older' }, { text: 3 });
      expect(merged.text).toBe('newer');
    });

    it('should handle empty state merge', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = {};
      doc.clock = {};

      const merged = doc.merge({ text: 'hello' }, { text: 1 });
      expect(merged.text).toBe('hello');
    });
  });

  describe('operations', () => {
    beforeEach(() => {
      const mod = require('../../../shared/realtime');
      CRDTDocument = mod.CRDTDocument;
    });

    it('cursor position offset test', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'Hello World' };

      doc.applyOperation({ type: 'insert', position: 5, content: ' Beautiful' });
      expect(doc.state.text).toBe('Hello Beautiful World');
    });

    it('insert offset test', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'abcdef' };

      doc.applyOperation({ type: 'insert', position: 3, content: 'XY' });
      expect(doc.state.text).toBe('abcXYdef');
    });

    it('selection range invalidation test', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'Hello Beautiful World' };

      const result = doc.applyOperation({ type: 'delete', position: 5, length: 10 });
      expect(doc.state.text).toBe('Hello World');
      expect(result.position).toBe(5);
    });

    it('delete selection test', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'abcdefgh' };

      doc.applyOperation({ type: 'delete', position: 2, length: 3 });
      expect(doc.state.text).toBe('abfgh');
    });

    it('operation buffer overflow test', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: '' };

      for (let i = 0; i < 10000; i++) {
        doc.applyOperation({ type: 'insert', position: 0, content: 'a' });
      }

      expect(doc.operations.length).toBeLessThanOrEqual(1000);
    });

    it('buffer limit test', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'test' };

      for (let i = 0; i < 5000; i++) {
        doc.applyOperation({ type: 'format', position: 0, length: 4, format: { bold: true } });
      }

      expect(doc.operations.length).toBeLessThan(5000);
    });

    it('should apply format operation', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'Hello' };

      doc.applyOperation({ type: 'format', position: 0, length: 5, format: { bold: true } });
      expect(doc.state.formats).toHaveLength(1);
      expect(doc.state.formats[0].format.bold).toBe(true);
    });

    it('should throw on unknown operation type', () => {
      const doc = new CRDTDocument('doc-1');
      doc.state = { text: 'test' };

      expect(() => {
        doc.applyOperation({ type: 'unknown', position: 0 });
      }).toThrow('Unknown operation type');
    });
  });
});

describe('OperationalTransform', () => {
  let OperationalTransform;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/realtime');
    OperationalTransform = mod.OperationalTransform;
  });

  describe('transform', () => {
    it('ot composition test', () => {
      const op1 = { type: 'insert', position: 0, content: 'Hello' };
      const op2 = { type: 'insert', position: 0, content: 'World' };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t1.position).toBe(0);
      expect(t2.position).toBe(5);
    });

    it('transform composition test', () => {
      const ops = [
        { type: 'insert', position: 0, content: 'a' },
        { type: 'insert', position: 1, content: 'b' },
        { type: 'insert', position: 2, content: 'c' },
      ];

      const composed = OperationalTransform.compose(ops);
      expect(composed).toHaveLength(1);
      expect(composed[0].content).toBe('abc');
      expect(composed[0].position).toBe(0);
    });

    it('transform commutative test', () => {
      const op1 = { type: 'insert', position: 5, content: 'X' };
      const op2 = { type: 'insert', position: 5, content: 'Y' };

      const [t1a, t2a] = OperationalTransform.transform(op1, op2);
      const [t2b, t1b] = OperationalTransform.transform(op2, op1);

      expect(t1a.position + t1a.content.length).not.toEqual(t2a.position + t2a.content.length);
    });

    it('ot commutative test', () => {
      const op1 = { type: 'insert', position: 3, content: 'A' };
      const op2 = { type: 'insert', position: 3, content: 'B' };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t1.position).not.toBe(t2.position);
    });

    it('conflict resolution priority test', () => {
      const op1 = { type: 'insert', position: 5, content: 'A', userId: 'user1' };
      const op2 = { type: 'insert', position: 5, content: 'B', userId: 'user2' };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t1.position).toBeLessThan(t2.position);
    });

    it('priority ordering test', () => {
      const op1 = { type: 'insert', position: 0, content: 'first', priority: 1 };
      const op2 = { type: 'insert', position: 0, content: 'second', priority: 2 };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t1.position).toBe(0);
    });

    it('intention preservation test', () => {
      const insertOp = { type: 'insert', position: 5, content: 'New' };
      const deleteOp = { type: 'delete', position: 3, length: 5 };

      const [tInsert, tDelete] = OperationalTransform.transform(insertOp, deleteOp);

      expect(tInsert.position).toBeGreaterThanOrEqual(3);
    });

    it('intent tracking test', () => {
      const op1 = { type: 'insert', position: 10, content: 'text' };
      const op2 = { type: 'delete', position: 5, length: 10 };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t1.position).toBeGreaterThanOrEqual(0);
    });

    it('should transform insert-delete correctly', () => {
      const op1 = { type: 'insert', position: 0, content: 'Hello' };
      const op2 = { type: 'delete', position: 3, length: 2 };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t2.position).toBe(8);
    });

    it('should transform delete-delete correctly', () => {
      const op1 = { type: 'delete', position: 0, length: 5 };
      const op2 = { type: 'delete', position: 3, length: 5 };

      const [t1, t2] = OperationalTransform.transform(op1, op2);

      expect(t1.length).toBeLessThanOrEqual(5);
    });

    it('sync protocol version test', () => {
      const { SyncProtocol } = require('../../../shared/realtime');

      const msg = SyncProtocol.createMessage('edit', { content: 'test' });
      expect(msg.version).toBeDefined();

      const parsed = SyncProtocol.parseMessage(JSON.stringify(msg));
      expect(parsed.version).toBe(SyncProtocol.VERSION);
    });

    it('version mismatch test', () => {
      const { SyncProtocol } = require('../../../shared/realtime');

      const msg = { version: 999, type: 'edit', payload: {} };
      const parsed = SyncProtocol.parseMessage(msg);

      expect(parsed.version).not.toBe(SyncProtocol.VERSION);
    });
  });
});

describe('UndoRedoManager - User Isolation', () => {
  let UndoRedoManager;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/realtime');
    UndoRedoManager = mod.UndoRedoManager;
  });

  it('undo should only undo operations by the requesting user', () => {
    const manager = new UndoRedoManager();
    manager.pushOperation('user-a', { type: 'insert', position: 0, content: 'A' });
    manager.pushOperation('user-b', { type: 'insert', position: 1, content: 'B' });
    manager.pushOperation('user-a', { type: 'insert', position: 2, content: 'C' });

    const undone = manager.undo('user-a');
    // Should undo user-a's last operation (C), not user-b's (B)
    // BUG: undo pops from shared stack without filtering by userId
    expect(undone.type).toBe('delete');
    expect(undone.position).toBe(2);
    expect(undone.length).toBe(1);
  });

  it('undo should skip other users operations in the stack', () => {
    const manager = new UndoRedoManager();
    manager.pushOperation('alice', { type: 'insert', position: 0, content: 'Hello' });
    manager.pushOperation('bob', { type: 'insert', position: 5, content: ' World' });

    // Alice's undo should undo her 'Hello', not Bob's ' World'
    const undone = manager.undo('alice');
    expect(undone.position).toBe(0);
    expect(undone.length).toBe(5); // 'Hello' length
  });

  it('user A undo should not affect user B operations', () => {
    const manager = new UndoRedoManager();
    manager.pushOperation('a', { type: 'insert', position: 0, content: 'X' });
    manager.pushOperation('b', { type: 'insert', position: 1, content: 'Y' });

    manager.undo('a');
    // After a's undo, b should still be able to undo their own operation
    const bUndo = manager.undo('b');
    expect(bUndo).not.toBeNull();
    expect(bUndo.position).toBe(1);
  });

  it('undo with multiple users should maintain per-user history', () => {
    const manager = new UndoRedoManager();
    manager.pushOperation('u1', { type: 'insert', position: 0, content: 'A' });
    manager.pushOperation('u2', { type: 'insert', position: 1, content: 'B' });
    manager.pushOperation('u1', { type: 'insert', position: 2, content: 'C' });
    manager.pushOperation('u2', { type: 'insert', position: 3, content: 'D' });

    // u1 should undo C first, then A
    const u1Undo1 = manager.undo('u1');
    expect(u1Undo1.position).toBe(2);

    const u1Undo2 = manager.undo('u1');
    expect(u1Undo2.position).toBe(0);
  });

  it('undo should return null if user has no operations', () => {
    const manager = new UndoRedoManager();
    manager.pushOperation('user-a', { type: 'insert', position: 0, content: 'text' });
    // user-b has no operations
    const result = manager.undo('user-b');
    expect(result).toBeNull();
  });
});

describe('OT Compose', () => {
  let OperationalTransform;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/realtime');
    OperationalTransform = mod.OperationalTransform;
  });

  it('compose should preserve delete operations', () => {
    const ops = [
      { type: 'insert', position: 0, content: 'Hello' },
      { type: 'delete', position: 3, length: 2 },
    ];
    const composed = OperationalTransform.compose(ops);
    // BUG: compose drops non-insert ops when types don't match
    const hasDelete = composed.some(op => op.type === 'delete');
    expect(hasDelete).toBe(true);
  });

  it('compose should not lose operations of different types', () => {
    const ops = [
      { type: 'insert', position: 0, content: 'A' },
      { type: 'delete', position: 5, length: 3 },
      { type: 'insert', position: 2, content: 'B' },
    ];
    const composed = OperationalTransform.compose(ops);
    // All three operations should be represented in the result
    // BUG: non-insert ops are silently replaced
    expect(composed.length).toBeGreaterThanOrEqual(2);
  });

  it('compose of mixed types should return all operations', () => {
    const ops = [
      { type: 'delete', position: 0, length: 5 },
      { type: 'insert', position: 0, content: 'New' },
    ];
    const composed = OperationalTransform.compose(ops);
    // Should preserve both delete and insert
    const types = composed.map(op => op.type);
    expect(types).toContain('delete');
    expect(types).toContain('insert');
  });

  it('compose should handle format operations', () => {
    const ops = [
      { type: 'insert', position: 0, content: 'text' },
      { type: 'format', position: 0, length: 4, format: { bold: true } },
    ];
    const composed = OperationalTransform.compose(ops);
    const hasFormat = composed.some(op => op.type === 'format');
    expect(hasFormat).toBe(true);
  });

  it('compose should not discard the first operation when second differs', () => {
    const ops = [
      { type: 'delete', position: 10, length: 5 },
      { type: 'insert', position: 10, content: 'replacement' },
    ];
    const composed = OperationalTransform.compose(ops);
    // BUG: compose discards first op, keeping only last
    expect(composed.length).toBe(2);
  });
});

describe('UndoRedoManager', () => {
  let UndoRedoManager;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../shared/realtime');
    UndoRedoManager = mod.UndoRedoManager;
  });

  it('undo redo corruption test', () => {
    const manager = new UndoRedoManager();

    manager.pushOperation('user1', { type: 'insert', position: 0, content: 'Hello' });
    manager.pushOperation('user2', { type: 'insert', position: 5, content: ' World' });

    const undone = manager.undo('user1');

    expect(undone).toBeDefined();
    expect(undone.type).toBe('delete');
  });

  it('collaborative undo test', () => {
    const manager = new UndoRedoManager();

    manager.pushOperation('user1', { type: 'insert', position: 0, content: 'A' });
    manager.pushOperation('user2', { type: 'insert', position: 1, content: 'B' });

    const undone = manager.undo('user1');

    expect(undone).not.toBeNull();
  });

  it('should handle undo on empty stack', () => {
    const manager = new UndoRedoManager();

    const result = manager.undo('user1');
    expect(result).toBeNull();
  });

  it('should handle redo after undo', () => {
    const manager = new UndoRedoManager();

    manager.pushOperation('user1', { type: 'insert', position: 0, content: 'test' });
    manager.undo('user1');
    const redone = manager.redo('user1');

    expect(redone).toBeDefined();
    expect(redone.type).toBe('insert');
  });

  it('document state divergence test', () => {
    const { CRDTDocument } = require('../../../shared/realtime');

    const doc1 = new CRDTDocument('doc-1');
    const doc2 = new CRDTDocument('doc-1');

    doc1.state = { text: 'Hello' };
    doc2.state = { text: 'Hello' };

    doc1.applyOperation({ type: 'insert', position: 5, content: ' World' });
    doc2.applyOperation({ type: 'insert', position: 5, content: ' Earth' });

    expect(doc1.state.text).not.toBe(doc2.state.text);
  });

  it('reconnect sync test', () => {
    const { CRDTDocument } = require('../../../shared/realtime');

    const doc = new CRDTDocument('doc-1');
    doc.state = { text: 'original' };

    doc.applyOperation({ type: 'insert', position: 8, content: ' modified' });

    expect(doc.state.text).toContain('modified');
  });

  it('cursor jitter debounce test', async () => {
    const { PresenceTracker } = require('../../../shared/realtime');
    const mockRedis = global.testUtils.mockRedis();
    const tracker = new PresenceTracker(mockRedis, { debounceMs: 100 });

    const result1 = await tracker.updatePresence('user1', 'doc1', { cursor: 5 });
    const result2 = await tracker.updatePresence('user1', 'doc1', { cursor: 6 });

    expect(result1).toBe(true);
    expect(result2).toBe(false);
  });

  it('debounce timing test', async () => {
    const { PresenceTracker } = require('../../../shared/realtime');
    const mockRedis = global.testUtils.mockRedis();
    const tracker = new PresenceTracker(mockRedis, { debounceMs: 50 });

    await tracker.updatePresence('user1', 'doc1', { cursor: 5 });
    await global.testUtils.delay(60);
    const result = await tracker.updatePresence('user1', 'doc1', { cursor: 6 });

    expect(result).toBe(true);
  });
});
