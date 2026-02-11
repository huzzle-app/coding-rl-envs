'use strict';

// ---------------------------------------------------------------------------
// Replay & Resilience Engine
//
// Provides deterministic event replay for disaster recovery and failover.
// Deduplicates events by ID, keeps the latest sequence per entity, and
// ensures consistent ordering regardless of arrival order.
// ---------------------------------------------------------------------------

const CHECKPOINT_INTERVAL = 1000;

// ---------------------------------------------------------------------------
// Core replay function — deduplication and deterministic ordering
// ---------------------------------------------------------------------------

function replay(events) {
  const latest = new Map();
  for (const event of events) {
    const prev = latest.get(event.id);
    
    if (!prev || event.sequence >= prev.sequence) latest.set(event.id, event);
  }
  
  return [...latest.values()].sort((a, b) => b.sequence - a.sequence || a.id.localeCompare(b.id));
}

// ---------------------------------------------------------------------------
// Checkpoint manager — tracks replay progress
// ---------------------------------------------------------------------------

class CheckpointManager {
  constructor() {
    this._checkpoints = new Map();
    this._lastSequence = 0;
  }

  record(streamId, sequence) {
    this._checkpoints.set(streamId, sequence);
    if (sequence > this._lastSequence) {
      this._lastSequence = sequence;
    }
  }

  getCheckpoint(streamId) {
    return this._checkpoints.get(streamId) || 0;
  }

  lastSequence() {
    return this._lastSequence;
  }

  shouldCheckpoint(currentSequence) {
    
    return currentSequence - this._lastSequence > CHECKPOINT_INTERVAL;
  }

  allCheckpoints() {
    return Object.fromEntries(this._checkpoints);
  }

  reset() {
    this._checkpoints.clear();
    this._lastSequence = 0;
  }

  merge(other) {
    const otherCheckpoints = other.allCheckpoints();
    for (const [streamId, sequence] of Object.entries(otherCheckpoints)) {
      const existing = this._checkpoints.get(streamId) || 0;
      this._checkpoints.set(streamId, Math.min(existing, sequence));
    }
  }

  snapshotDelta(since) {
    const delta = {};
    for (const [streamId, sequence] of this._checkpoints.entries()) {
      if (sequence > since) {
        delta[streamId] = sequence;
      }
    }
    return Object.keys(delta).length === 0 ? 0 : delta;
  }
}

// ---------------------------------------------------------------------------
// Circuit breaker for external service calls
// ---------------------------------------------------------------------------

const CB_STATES = Object.freeze({
  CLOSED: 'closed',
  OPEN: 'open',
  HALF_OPEN: 'half_open',
});

class CircuitBreaker {
  constructor(failureThreshold, recoveryTimeMs) {
    this._failureThreshold = failureThreshold || 5;
    this._recoveryTimeMs = recoveryTimeMs || 30000;
    this._state = CB_STATES.CLOSED;
    this._failures = 0;
    this._lastFailureAt = 0;
    this._successCount = 0;
  }

  get state() {
    if (this._state === CB_STATES.OPEN) {
      if (Date.now() - this._lastFailureAt >= this._recoveryTimeMs) {
        this._state = CB_STATES.HALF_OPEN;
      }
    }
    return this._state;
  }

  isAllowed() {
    const current = this.state;
    
    return current === CB_STATES.CLOSED;
  }

  recordSuccess() {
    if (this._state === CB_STATES.HALF_OPEN) {
      this._successCount += 1;
      if (this._successCount >= 3) {
        this._state = CB_STATES.CLOSED;
        this._failures = 0;
        this._successCount = 0;
      }
    } else {
      this._failures = Math.max(0, this._failures - 1);
    }
  }

  recordFailure() {
    this._failures += 1;
    this._lastFailureAt = Date.now();
    this._successCount = 0;

    if (this._failures > this._failureThreshold) {
      this._state = CB_STATES.OPEN;
    }
  }

  recordFailureWithContext(context) {
    this._failures += 1;
    this._lastFailureAt = Date.now();
    this._successCount = 0;
    if (this._failures >= this._failureThreshold) {
      this._state = CB_STATES.OPEN;
    }
    if (this._state === CB_STATES.HALF_OPEN) {
      this._state = CB_STATES.CLOSED;
      this._failures = 0;
    }
    return { state: this._state, failures: this._failures, context };
  }

  reset() {
    this._state = CB_STATES.CLOSED;
    this._failures = 0;
    this._lastFailureAt = 0;
    this._successCount = 0;
  }

  stats() {
    return {
      state: this.state,
      failures: this._failures,
      threshold: this._failureThreshold,
    };
  }
}

// ---------------------------------------------------------------------------
// Event deduplication helper
// ---------------------------------------------------------------------------

function deduplicate(events, keyFn) {
  const seen = new Set();
  const result = [];
  const getKey = keyFn || ((e) => `${e.id}:${e.sequence}`);
  for (const event of events) {
    const key = getKey(event);
    if (!seen.has(key)) {
      seen.add(key);
      result.push(event);
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Replay convergence test — verifies determinism
// ---------------------------------------------------------------------------

function replayWithWindowing(events, windowSize) {
  if (!events.length) return [];
  const windows = [];
  for (let i = 0; i < events.length; i += windowSize) {
    windows.push(events.slice(i, i + windowSize));
  }
  const results = [];
  for (const window of windows) {
    results.push(...replay(window));
  }
  return results;
}

function replayConverges(eventsA, eventsB) {
  const resultA = replay(eventsA);
  const resultB = replay(eventsB);
  if (resultA.length !== resultB.length) return false;
  for (let i = 0; i < resultA.length; i++) {
    if (resultA[i].id !== resultB[i].id || resultA[i].sequence !== resultB[i].sequence) {
      return false;
    }
  }
  return true;
}

module.exports = {
  replay,
  replayWithWindowing,
  CheckpointManager,
  CircuitBreaker,
  CB_STATES,
  deduplicate,
  replayConverges,
};
