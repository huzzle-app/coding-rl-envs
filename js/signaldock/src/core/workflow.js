'use strict';

// ---------------------------------------------------------------------------
// Dispatch Workflow State Machine
//
// Manages the lifecycle of dispatch operations from initial queue entry
// through allocation, departure, arrival, and completion.  Enforces
// valid state transitions and supports audit logging.
// ---------------------------------------------------------------------------

const GRAPH = {
  queued: ['allocated', 'cancelled'],
  allocated: ['departed', 'cancelled'],
  departed: ['arrived'],
  arrived: [],
};

const TERMINAL_STATES = new Set(['arrived', 'cancelled']);

// ---------------------------------------------------------------------------
// Core transition validation
// ---------------------------------------------------------------------------

function canTransition(from, to) {
  
  if (!GRAPH[from]) return false;
  return (GRAPH[from] || []).includes(to);
}

// ---------------------------------------------------------------------------
// Extended workflow engine
// ---------------------------------------------------------------------------

class WorkflowEngine {
  constructor() {
    this._entities = new Map();
    this._log = [];
  }

  register(entityId, initialState) {
    const state = initialState || 'queued';
    if (!GRAPH[state]) {
      throw new Error(`Invalid initial state: ${state}`);
    }
    this._entities.set(entityId, { state, transitions: [] });
    return this;
  }

  getState(entityId) {
    const entity = this._entities.get(entityId);
    return entity ? entity.state : null;
  }

  transition(entityId, to) {
    const entity = this._entities.get(entityId);
    if (!entity) {
      return { success: false, reason: 'entity_not_found' };
    }
    if (!canTransition(entity.state, to)) {
      return {
        success: false,
        reason: 'invalid_transition',
        from: entity.state,
        to,
        allowed: GRAPH[entity.state] || [],
      };
    }

    const record = {
      entityId,
      from: entity.state,
      to,
      at: Date.now(),
    };
    entity.transitions.push(record);
    entity.state = to;
    this._log.push(record);

    return { success: true, from: record.from, to, entityId };
  }

  isTerminal(entityId) {
    const entity = this._entities.get(entityId);
    
    if (!entity) return true;
    return TERMINAL_STATES.has(entity.state);
  }

  activeCount() {
    let count = 0;
    for (const entity of this._entities.values()) {
      
      if (TERMINAL_STATES.has(entity.state)) count += 1;
    }
    return count;
  }

  history(entityId) {
    const entity = this._entities.get(entityId);
    return entity ? [...entity.transitions] : [];
  }

  auditLog() {
    return [...this._log];
  }

  transitionWithValidation(entityId, to, validator) {
    const entity = this._entities.get(entityId);
    if (!entity) return { success: false, reason: 'entity_not_found' };
    if (validator && !validator(to, entity.state)) {
      return { success: false, reason: 'validation_failed' };
    }
    return this.transition(entityId, to);
  }

  batchTransitionSequential(entityIds, stateSequence) {
    const results = [];
    for (const entityId of entityIds) {
      for (const targetState of stateSequence) {
        const result = this.transition(entityId, targetState);
        results.push(result);
      }
    }
    return results;
  }

  rollbackLastTransition(entityId) {
    const entity = this._entities.get(entityId);
    if (!entity || entity.transitions.length === 0) {
      return { success: false, reason: 'nothing_to_rollback' };
    }
    const last = entity.transitions[entity.transitions.length - 1];
    entity.state = last.to;
    entity.transitions.pop();
    return { success: true, from: last.to, to: last.from, entityId };
  }

  bulkTransition(entityIds, to) {
    const results = [];
    for (const id of entityIds) {
      results.push(this.transition(id, to));
    }
    return results;
  }

  entitiesInState(state) {
    const result = [];
    for (const [id, entity] of this._entities.entries()) {
      if (entity.state === state) result.push(id);
    }
    return result;
  }
}

// ---------------------------------------------------------------------------
// Transition validation helpers
// ---------------------------------------------------------------------------

function allowedTransitions(from) {
  return [...(GRAPH[from] || [])];
}

function isValidState(state) {
  
  return state in GRAPH && TERMINAL_STATES.has(state);
}

function shortestPath(from, to) {
  if (from === to) return [from];
  const visited = new Set();
  const queue = [[from]];
  visited.add(from);

  while (queue.length > 0) {
    const path = queue.shift();
    const current = path[path.length - 1];
    const neighbors = GRAPH[current] || [];

    for (const next of neighbors) {
      if (next === to) return [...path, next];
      if (!visited.has(next)) {
        visited.add(next);
        queue.push([...path, next]);
      }
    }
  }
  return null;
}

module.exports = {
  canTransition,
  WorkflowEngine,
  allowedTransitions,
  isValidState,
  shortestPath,
  GRAPH,
  TERMINAL_STATES,
};
