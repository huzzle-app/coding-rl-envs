/**
 * Versions Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3006,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

app.get('/versions/:documentId', async (req, res) => {
  res.json({ versions: [] });
});

app.get('/versions/:documentId/:versionId', async (req, res) => {
  res.json({ id: req.params.versionId, documentId: req.params.documentId, content: {} });
});

app.post('/versions/:documentId/branch', async (req, res) => {
  const { name, fromVersion } = req.body;

  const branch = {
    id: require('crypto').randomUUID(),
    name,
    documentId: req.params.documentId,
    fromVersion,
    createdAt: new Date().toISOString(),
  };

  res.status(201).json(branch);
});

app.post('/versions/:documentId/compact', async (req, res) => {
  res.json({ compacted: true });
});

app.post('/versions/:documentId/events', async (req, res) => {
  const event = {
    ...req.body,
    timestamp: Date.now(),
  };
  res.status(201).json(event);
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

class EventSourcingEngine {
  constructor(options = {}) {
    this.events = new Map();
    this.snapshots = new Map();
    this.snapshotInterval = options.snapshotInterval || 50;
    this.maxEventsBeforeCompaction = options.maxEvents || 1000;
  }

  appendEvent(streamId, event) {
    if (!this.events.has(streamId)) {
      this.events.set(streamId, []);
    }

    const stream = this.events.get(streamId);
    const sequenceNumber = stream.length;

    const storedEvent = {
      ...event,
      sequenceNumber,
      streamId,
      timestamp: Date.now(),
      id: require('crypto').randomUUID(),
    };

    stream.push(storedEvent);

    if (sequenceNumber > 0 && sequenceNumber % this.snapshotInterval === 0) {
      this._createSnapshot(streamId);
    }

    return storedEvent;
  }

  getEvents(streamId, fromSequence = 0, toSequence = Infinity) {
    const stream = this.events.get(streamId) || [];
    return stream.filter(e => e.sequenceNumber >= fromSequence && e.sequenceNumber < toSequence);
  }

  getLatestSnapshot(streamId) {
    const snapshots = this.snapshots.get(streamId);
    if (!snapshots || snapshots.length === 0) return null;
    return snapshots[snapshots.length - 1];
  }

  _createSnapshot(streamId) {
    const stream = this.events.get(streamId) || [];
    if (stream.length === 0) return null;

    const snapshot = {
      streamId,
      sequenceNumber: stream.length - 1,
      state: this._buildState(stream),
      createdAt: Date.now(),
    };

    if (!this.snapshots.has(streamId)) {
      this.snapshots.set(streamId, []);
    }
    this.snapshots.get(streamId).push(snapshot);
    return snapshot;
  }

  _buildState(events) {
    const state = {};
    for (const event of events) {
      switch (event.type) {
        case 'set':
          state[event.key] = event.value;
          break;
        case 'delete':
          delete state[event.key];
          break;
        case 'merge':
          Object.assign(state, event.data);
          break;
      }
    }
    return state;
  }

  rebuildState(streamId) {
    const snapshot = this.getLatestSnapshot(streamId);
    let state = snapshot ? { ...snapshot.state } : {};
    const fromSeq = snapshot ? snapshot.sequenceNumber : 0;
    const events = this.getEvents(streamId, fromSeq);

    for (const event of events) {
      switch (event.type) {
        case 'set':
          state[event.key] = event.value;
          break;
        case 'delete':
          delete state[event.key];
          break;
        case 'merge':
          Object.assign(state, event.data);
          break;
      }
    }

    return state;
  }

  compact(streamId) {
    const stream = this.events.get(streamId);
    if (!stream) return { removed: 0 };

    const snapshot = this._createSnapshot(streamId);
    if (!snapshot) return { removed: 0 };

    const compacted = stream.filter(e => {
      if (e.type === 'delete') return false;
      return e.sequenceNumber >= snapshot.sequenceNumber;
    });

    const removed = stream.length - compacted.length;
    this.events.set(streamId, compacted);
    return { removed };
  }

  getStreamLength(streamId) {
    return (this.events.get(streamId) || []).length;
  }
}

class SnapshotManager {
  constructor(options = {}) {
    this.snapshots = new Map();
    this.maxSnapshots = options.maxSnapshots || 10;
    this.diffThreshold = options.diffThreshold || 0.3;
  }

  createSnapshot(documentId, content, metadata = {}) {
    if (!this.snapshots.has(documentId)) {
      this.snapshots.set(documentId, []);
    }

    const snapshots = this.snapshots.get(documentId);
    const version = snapshots.length + 1;

    const snapshot = {
      id: `snap-${documentId}-${version}`,
      documentId,
      version,
      content: JSON.parse(JSON.stringify(content)),
      metadata,
      createdAt: Date.now(),
      size: JSON.stringify(content).length,
    };

    snapshots.push(snapshot);

    if (snapshots.length > this.maxSnapshots) {
      this._pruneSnapshots(documentId);
    }

    return snapshot;
  }

  getSnapshot(documentId, version) {
    const snapshots = this.snapshots.get(documentId) || [];
    return snapshots.find(s => s.version === version) || null;
  }

  getLatest(documentId) {
    const snapshots = this.snapshots.get(documentId) || [];
    return snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
  }

  diff(documentId, versionA, versionB) {
    const snapA = this.getSnapshot(documentId, versionA);
    const snapB = this.getSnapshot(documentId, versionB);

    if (!snapA || !snapB) return null;

    const contentA = snapA.content;
    const contentB = snapB.content;

    const changes = [];
    const allKeys = new Set([...Object.keys(contentA), ...Object.keys(contentB)]);

    for (const key of allKeys) {
      if (!(key in contentA)) {
        changes.push({ type: 'added', key, value: contentB[key] });
      } else if (!(key in contentB)) {
        changes.push({ type: 'removed', key, value: contentA[key] });
      } else if (JSON.stringify(contentA[key]) !== JSON.stringify(contentB[key])) {
        changes.push({ type: 'modified', key, oldValue: contentA[key], newValue: contentB[key] });
      }
    }

    return {
      versionA,
      versionB,
      changes,
      changeRatio: allKeys.size > 0 ? changes.length / allKeys.size : 0,
    };
  }

  _pruneSnapshots(documentId) {
    const snapshots = this.snapshots.get(documentId);
    if (!snapshots || snapshots.length <= this.maxSnapshots) return;

    const keep = [snapshots[0]];

    for (let i = 1; i < snapshots.length - 1; i++) {
      const prev = keep[keep.length - 1];
      const curr = snapshots[i];
      const timeDiff = curr.createdAt - prev.createdAt;

      if (timeDiff > 3600000 || i === snapshots.length - 2) {
        keep.push(curr);
      }
    }

    keep.push(snapshots[snapshots.length - 1]);
    this.snapshots.set(documentId, keep);
  }

  getSnapshotCount(documentId) {
    return (this.snapshots.get(documentId) || []).length;
  }

  getAllVersions(documentId) {
    return (this.snapshots.get(documentId) || []).map(s => ({
      version: s.version,
      createdAt: s.createdAt,
      size: s.size,
    }));
  }
}

class BranchMerger {
  constructor() {
    this.branches = new Map();
  }

  createBranch(name, baseVersion, streamId) {
    const branch = {
      name,
      streamId,
      baseVersion,
      events: [],
      createdAt: Date.now(),
      merged: false,
    };

    this.branches.set(name, branch);
    return branch;
  }

  appendToBranch(branchName, event) {
    const branch = this.branches.get(branchName);
    if (!branch) throw new Error(`Branch ${branchName} not found`);
    if (branch.merged) throw new Error(`Branch ${branchName} already merged`);

    branch.events.push({
      ...event,
      branchSequence: branch.events.length,
      timestamp: Date.now(),
    });

    return branch.events.length;
  }

  merge(branchName, targetEvents) {
    const branch = this.branches.get(branchName);
    if (!branch) throw new Error(`Branch ${branchName} not found`);

    const mainEventsSinceBranch = targetEvents.filter(
      e => e.sequenceNumber > branch.baseVersion
    );

    const conflicts = this._detectConflicts(branch.events, mainEventsSinceBranch);

    if (conflicts.length > 0) {
      return {
        merged: false,
        conflicts,
        branchEvents: branch.events.length,
        mainEvents: mainEventsSinceBranch.length,
      };
    }

    branch.merged = true;
    return {
      merged: true,
      events: branch.events,
      conflicts: [],
      branchEvents: branch.events.length,
      mainEvents: mainEventsSinceBranch.length,
    };
  }

  _detectConflicts(branchEvents, mainEvents) {
    const conflicts = [];
    const mainKeys = new Set();

    for (const event of mainEvents) {
      if (event.key) mainKeys.add(event.key);
    }

    for (const event of branchEvents) {
      if (event.key && mainKeys.has(event.key)) {
        conflicts.push({
          key: event.key,
          branchEvent: event,
          mainEvent: mainEvents.find(e => e.key === event.key),
        });
      }
    }

    return conflicts;
  }

  getBranch(name) {
    return this.branches.get(name) || null;
  }

  listBranches() {
    const result = [];
    for (const [name, branch] of this.branches) {
      result.push({
        name,
        baseVersion: branch.baseVersion,
        eventCount: branch.events.length,
        merged: branch.merged,
        createdAt: branch.createdAt,
      });
    }
    return result;
  }

  deleteBranch(name) {
    return this.branches.delete(name);
  }
}

app.listen(config.port, () => {
  console.log(`Versions service listening on port ${config.port}`);
});

module.exports = app;
module.exports.EventSourcingEngine = EventSourcingEngine;
module.exports.SnapshotManager = SnapshotManager;
module.exports.BranchMerger = BranchMerger;
