/**
 * Document Versioning Tests
 *
 * Tests EventSourcingEngine, SnapshotManager, BranchMerger from actual source code.
 * Exercises bugs: rebuildState off-by-one from snapshot, compact removes delete events, branch merge conflicts.
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

const { EventSourcingEngine, SnapshotManager, BranchMerger } = require('../../../services/versions/src/index');

describe('EventSourcingEngine', () => {
  let engine;

  beforeEach(() => {
    engine = new EventSourcingEngine({ snapshotInterval: 5, maxEvents: 100 });
  });

  describe('appendEvent', () => {
    it('should append events to a stream', () => {
      const evt = engine.appendEvent('stream-1', { type: 'set', key: 'title', value: 'Hello' });
      expect(evt.sequenceNumber).toBe(0);
      expect(evt.streamId).toBe('stream-1');
      expect(evt.id).toBeDefined();
    });

    it('should auto-increment sequence numbers', () => {
      engine.appendEvent('stream-1', { type: 'set', key: 'a', value: 1 });
      const evt2 = engine.appendEvent('stream-1', { type: 'set', key: 'b', value: 2 });
      expect(evt2.sequenceNumber).toBe(1);
    });

    it('should maintain separate streams', () => {
      engine.appendEvent('s1', { type: 'set', key: 'x', value: 1 });
      engine.appendEvent('s2', { type: 'set', key: 'y', value: 2 });
      expect(engine.getStreamLength('s1')).toBe(1);
      expect(engine.getStreamLength('s2')).toBe(1);
    });
  });

  describe('getEvents', () => {
    it('should retrieve events from a stream', () => {
      engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      engine.appendEvent('s1', { type: 'set', key: 'b', value: 2 });
      engine.appendEvent('s1', { type: 'set', key: 'c', value: 3 });

      const events = engine.getEvents('s1', 1, 3);
      expect(events).toHaveLength(2);
      expect(events[0].key).toBe('b');
    });

    it('should return empty for nonexistent stream', () => {
      expect(engine.getEvents('nonexistent')).toEqual([]);
    });
  });

  describe('snapshots', () => {
    it('should create snapshot at configured interval', () => {
      for (let i = 0; i < 6; i++) {
        engine.appendEvent('s1', { type: 'set', key: `k${i}`, value: i });
      }

      const snapshot = engine.getLatestSnapshot('s1');
      // Snapshot created at sequenceNumber 5 (index 5 % 5 === 0)
      expect(snapshot).not.toBeNull();
      expect(snapshot.state).toBeDefined();
    });

    it('should return null when no snapshots exist', () => {
      engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      expect(engine.getLatestSnapshot('s1')).toBeNull();
    });
  });

  describe('rebuildState', () => {
    it('should rebuild state from events', () => {
      engine.appendEvent('s1', { type: 'set', key: 'title', value: 'Hello' });
      engine.appendEvent('s1', { type: 'set', key: 'body', value: 'World' });

      const state = engine.rebuildState('s1');
      expect(state.title).toBe('Hello');
      expect(state.body).toBe('World');
    });

    it('should handle delete events', () => {
      engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      engine.appendEvent('s1', { type: 'set', key: 'b', value: 2 });
      engine.appendEvent('s1', { type: 'delete', key: 'a' });

      const state = engine.rebuildState('s1');
      expect(state.a).toBeUndefined();
      expect(state.b).toBe(2);
    });

    it('should handle merge events', () => {
      engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      engine.appendEvent('s1', { type: 'merge', data: { b: 2, c: 3 } });

      const state = engine.rebuildState('s1');
      expect(state.a).toBe(1);
      expect(state.b).toBe(2);
      expect(state.c).toBe(3);
    });

    // BUG: rebuildState uses snapshot.sequenceNumber as fromSeq,
    // but getEvents returns events WHERE sequenceNumber >= fromSeq,
    // so it re-applies the event AT the snapshot's sequenceNumber.
    // The snapshot already includes that event, causing duplicate application.
    it('should not double-apply events at snapshot boundary', () => {
      // Create 4 events + 1 at snapshot boundary
      engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      engine.appendEvent('s1', { type: 'set', key: 'b', value: 2 });
      engine.appendEvent('s1', { type: 'set', key: 'c', value: 3 });
      engine.appendEvent('s1', { type: 'set', key: 'd', value: 4 });
      // 5th event triggers snapshot (snapshotInterval=5)
      // snapshot.sequenceNumber = 4, snapshot.state includes all 5 keys
      engine.appendEvent('s1', { type: 'set', key: 'e', value: 5 });

      // Post-snapshot event
      engine.appendEvent('s1', { type: 'set', key: 'f', value: 6 });

      // Get events that rebuildState replays after snapshot
      const snapshot = engine.getLatestSnapshot('s1');
      const fromSeq = snapshot ? snapshot.sequenceNumber : 0;
      const replayedEvents = engine.getEvents('s1', fromSeq);

      // Should only replay events AFTER snapshot (seq > 4), i.e., 'f' at seq=5
      // BUG: getEvents uses >= so it also includes seq=4 ('e'), replaying 2 instead of 1
      expect(replayedEvents.length).toBe(1);
    });
  });

  describe('compact', () => {
    it('should compact events in a stream', () => {
      for (let i = 0; i < 10; i++) {
        engine.appendEvent('s1', { type: 'set', key: `k${i}`, value: i });
      }

      const result = engine.compact('s1');
      expect(result.removed).toBeGreaterThan(0);
    });

    // BUG: compact filters out ALL delete events, which means
    // deleted keys will reappear when rebuilding from the compacted stream
    it('should preserve delete events during compaction', () => {
      // Create enough events to trigger a natural snapshot first
      for (let i = 0; i < 5; i++) {
        engine.appendEvent('s1', { type: 'set', key: `k${i}`, value: i });
      }
      // Snapshot at seq=4, state = {k0:0, k1:1, k2:2, k3:3, k4:4}

      // Now add a delete event AFTER the snapshot
      engine.appendEvent('s1', { type: 'delete', key: 'k0' });

      // Compact: creates new snapshot (seq=5, state={k1:1,k2:2,k3:3,k4:4})
      // Then filters: delete event (seq=5) gets removed by the bug (type === 'delete')
      // After compaction, only the new snapshot remains, delete event is gone
      engine.compact('s1');

      // Now add more events and rebuild
      engine.appendEvent('s1', { type: 'set', key: 'new', value: 'val' });

      const state = engine.rebuildState('s1');
      // k0 should still be deleted after compaction
      // BUG: compact removed the delete event, but the new snapshot captured
      // the correct state. However, the old snapshot (from before delete) still
      // shows k0=0. The compact creates a fresh snapshot at the end,
      // so this specific scenario might still pass.
      // Use a more targeted approach: verify delete events survive in the stream.
      const events = engine.getEvents('s1');
      const deleteEvents = events.filter(e => e.type === 'delete');
      // After compaction, delete events should be preserved in the stream
      // BUG: compact filters them out with `if (e.type === 'delete') return false`
      expect(deleteEvents.length).toBeGreaterThan(0);
    });

    it('should return 0 removed for nonexistent stream', () => {
      expect(engine.compact('nonexistent')).toEqual({ removed: 0 });
    });
  });

  describe('stream length', () => {
    it('should track stream length', () => {
      engine.appendEvent('s1', { type: 'set', key: 'a', value: 1 });
      engine.appendEvent('s1', { type: 'set', key: 'b', value: 2 });
      expect(engine.getStreamLength('s1')).toBe(2);
    });

    it('should return 0 for empty stream', () => {
      expect(engine.getStreamLength('nonexistent')).toBe(0);
    });
  });
});

describe('SnapshotManager', () => {
  let manager;

  beforeEach(() => {
    manager = new SnapshotManager({ maxSnapshots: 5 });
  });

  describe('createSnapshot', () => {
    it('should create a snapshot', () => {
      const snap = manager.createSnapshot('doc-1', { title: 'Test', body: 'Content' });
      expect(snap.documentId).toBe('doc-1');
      expect(snap.version).toBe(1);
      expect(snap.content.title).toBe('Test');
    });

    it('should auto-increment version numbers', () => {
      manager.createSnapshot('doc-1', { v: 1 });
      const snap2 = manager.createSnapshot('doc-1', { v: 2 });
      expect(snap2.version).toBe(2);
    });

    it('should deep copy content to prevent mutation', () => {
      const content = { nested: { value: 1 } };
      const snap = manager.createSnapshot('doc-1', content);
      content.nested.value = 999;
      expect(snap.content.nested.value).toBe(1);
    });
  });

  describe('getSnapshot', () => {
    it('should retrieve snapshot by version', () => {
      manager.createSnapshot('doc-1', { a: 1 });
      manager.createSnapshot('doc-1', { b: 2 });
      const snap = manager.getSnapshot('doc-1', 1);
      expect(snap.content.a).toBe(1);
    });

    it('should return null for missing version', () => {
      expect(manager.getSnapshot('doc-1', 99)).toBeNull();
    });
  });

  describe('getLatest', () => {
    it('should return latest snapshot', () => {
      manager.createSnapshot('doc-1', { v: 1 });
      manager.createSnapshot('doc-1', { v: 2 });
      const latest = manager.getLatest('doc-1');
      expect(latest.content.v).toBe(2);
    });

    it('should return null for unknown document', () => {
      expect(manager.getLatest('nonexistent')).toBeNull();
    });
  });

  describe('diff', () => {
    it('should compute diff between versions', () => {
      manager.createSnapshot('doc-1', { title: 'Original', body: 'Content' });
      manager.createSnapshot('doc-1', { title: 'Updated', body: 'Content', tags: ['new'] });

      const diff = manager.diff('doc-1', 1, 2);
      expect(diff).not.toBeNull();
      expect(diff.changes.length).toBeGreaterThan(0);

      const modified = diff.changes.find(c => c.key === 'title');
      expect(modified.type).toBe('modified');

      const added = diff.changes.find(c => c.key === 'tags');
      expect(added.type).toBe('added');
    });

    it('should return null for missing versions', () => {
      expect(manager.diff('doc-1', 1, 2)).toBeNull();
    });
  });

  describe('snapshot count and versions', () => {
    it('should track snapshot count', () => {
      manager.createSnapshot('doc-1', { a: 1 });
      manager.createSnapshot('doc-1', { b: 2 });
      expect(manager.getSnapshotCount('doc-1')).toBe(2);
    });

    it('should list all versions', () => {
      manager.createSnapshot('doc-1', { a: 1 });
      manager.createSnapshot('doc-1', { b: 2 });
      const versions = manager.getAllVersions('doc-1');
      expect(versions).toHaveLength(2);
      expect(versions[0].version).toBe(1);
    });
  });
});

describe('ChunkedUploader - initUpload', () => {
  let ChunkedUploader;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/storage/src/index');
    ChunkedUploader = mod.ChunkedUploader;
  });

  it('initUpload should use Math.ceil for chunk count calculation', () => {
    const uploader = new ChunkedUploader({ chunkSize: 5 * 1024 * 1024 });
    // File size = 12MB, chunk size = 5MB -> should be 3 chunks (ceil(12/5))
    const upload = uploader.initUpload('file-1', 12 * 1024 * 1024);
    // BUG: uses Math.floor instead of Math.ceil, so 12/5 = 2.4 -> 2 chunks
    expect(upload.totalChunks).toBe(3);
  });

  it('initUpload should not lose trailing bytes when file is not evenly divisible', () => {
    const uploader = new ChunkedUploader({ chunkSize: 1000 });
    const upload = uploader.initUpload('file-1', 2500);
    // 2500/1000 = 2.5, need ceil(2.5) = 3 chunks
    // BUG: floor(2.5) = 2 chunks, losing 500 bytes
    expect(upload.totalChunks).toBe(3);
  });

  it('initUpload chunk count for 1-byte-over should round up', () => {
    const uploader = new ChunkedUploader({ chunkSize: 100 });
    const upload = uploader.initUpload('file-1', 101);
    // 101/100 = 1.01, need 2 chunks
    // BUG: floor(1.01) = 1 chunk, losing 1 byte
    expect(upload.totalChunks).toBe(2);
  });

  it('initUpload should cover entire file size across all chunks', () => {
    const uploader = new ChunkedUploader({ chunkSize: 1000 });
    const totalSize = 3500;
    const upload = uploader.initUpload('file-1', totalSize);
    // Last chunk should end at totalSize
    const lastChunk = upload.chunks[upload.chunks.length - 1];
    expect(lastChunk.end).toBe(totalSize);
  });

  it('initUpload exact multiple should not create extra chunk', () => {
    const uploader = new ChunkedUploader({ chunkSize: 1000 });
    const upload = uploader.initUpload('file-1', 3000);
    // 3000/1000 = 3.0, exactly 3 chunks
    expect(upload.totalChunks).toBe(3);
  });
});

describe('BranchMerger', () => {
  let merger;

  beforeEach(() => {
    merger = new BranchMerger();
  });

  describe('createBranch', () => {
    it('should create a branch', () => {
      const branch = merger.createBranch('feature-1', 5, 'stream-1');
      expect(branch.name).toBe('feature-1');
      expect(branch.baseVersion).toBe(5);
      expect(branch.merged).toBe(false);
    });
  });

  describe('appendToBranch', () => {
    it('should append events to a branch', () => {
      merger.createBranch('f1', 0, 's1');
      const len = merger.appendToBranch('f1', { type: 'set', key: 'a', value: 1 });
      expect(len).toBe(1);
    });

    it('should reject append to nonexistent branch', () => {
      expect(() => merger.appendToBranch('nope', {})).toThrow();
    });

    it('should reject append to merged branch', () => {
      merger.createBranch('f1', 0, 's1');
      merger.merge('f1', []);
      expect(() => merger.appendToBranch('f1', {})).toThrow();
    });
  });

  describe('merge', () => {
    it('should merge non-conflicting branch', () => {
      merger.createBranch('f1', 0, 's1');
      merger.appendToBranch('f1', { type: 'set', key: 'a', value: 1 });

      // No conflicting events in main
      const result = merger.merge('f1', []);
      expect(result.merged).toBe(true);
      expect(result.events).toHaveLength(1);
    });

    it('should detect conflicts', () => {
      merger.createBranch('f1', 0, 's1');
      merger.appendToBranch('f1', { type: 'set', key: 'title', value: 'branch' });

      const mainEvents = [
        { sequenceNumber: 1, type: 'set', key: 'title', value: 'main' },
      ];

      const result = merger.merge('f1', mainEvents);
      expect(result.merged).toBe(false);
      expect(result.conflicts.length).toBeGreaterThan(0);
    });

    it('should reject merge of nonexistent branch', () => {
      expect(() => merger.merge('nope', [])).toThrow();
    });
  });

  describe('listBranches', () => {
    it('should list all branches', () => {
      merger.createBranch('f1', 0, 's1');
      merger.createBranch('f2', 5, 's1');
      const branches = merger.listBranches();
      expect(branches).toHaveLength(2);
    });
  });

  describe('deleteBranch', () => {
    it('should delete a branch', () => {
      merger.createBranch('f1', 0, 's1');
      expect(merger.deleteBranch('f1')).toBe(true);
      expect(merger.getBranch('f1')).toBeNull();
    });
  });
});
