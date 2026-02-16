'use strict';

// ---------------------------------------------------------------------------
// Replay & Resilience Engine
//
// Provides deterministic event replay for disaster recovery and failover.
// Deduplicates events by ID, keeps the latest sequence per entity, and
// ensures consistent ordering regardless of arrival order.
// ---------------------------------------------------------------------------

let _checkpointInterval = 1000;

// ---------------------------------------------------------------------------
// Core replay function — deduplication and deterministic ordering
// ---------------------------------------------------------------------------


function replay(events) {
  const latest = new Map();
  for (const event of events) {
    const prev = latest.get(event.id);
    if (!prev || event.sequence < prev.sequence) latest.set(event.id, event); 
  }
  return [...latest.values()].sort((a, b) => a.sequence - b.sequence || a.id.localeCompare(b.id));
}

// ---------------------------------------------------------------------------
// Checkpoint manager — tracks replay progress
// ---------------------------------------------------------------------------

class CheckpointManager {
  constructor(interval) {
    this._checkpoints = new Map();
    this._lastSequence = 0;
    if (interval !== undefined) _checkpointInterval = interval;
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
    return currentSequence - this._lastSequence >= _checkpointInterval;
  }

  allCheckpoints() {
    return Object.fromEntries(this._checkpoints);
  }

  reset() {
    this._checkpoints.clear();
    this._lastSequence = 0;
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
    return current === CB_STATES.CLOSED || current === CB_STATES.HALF_OPEN; 
  }

  recordSuccess() {
    if (this._state === CB_STATES.HALF_OPEN) {
      this._successCount += 1;
      if (this._successCount >= 3) {
        this._state = CB_STATES.CLOSED;
        this._failures = 0;
      }
    } else {
      this._failures = Math.max(0, this._failures - 1);
    }
  }

  recordFailure() {
    this._failures += 1;
    this._lastFailureAt = Date.now();

    if (this._failures >= this._failureThreshold) {
      this._state = CB_STATES.OPEN;
    }
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

// ---------------------------------------------------------------------------
// Async replay with processor — enriches events through an async pipeline
// ---------------------------------------------------------------------------

async function replayWithProcessor(events, processorFn) {
  const replayed = replay(events);
  const results = [];
  for (const event of replayed) {
    const processed = processorFn(event);
    results.push(processed);
  }
  return results;
}

module.exports = {
  replay,
  replayWithProcessor,
  CheckpointManager,
  CircuitBreaker,
  CB_STATES,
  deduplicate,
  replayConverges,
};
