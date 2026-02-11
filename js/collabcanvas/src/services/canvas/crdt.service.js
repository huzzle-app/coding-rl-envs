/**
 * CRDT Service - Conflict-free Replicated Data Types for canvas state
 */

const { v4: uuidv4 } = require('uuid');

class CRDTService {
  constructor() {
    this.nodeId = uuidv4();
    this.vectorClock = {};
  }

  /**
   * Compare two vector clocks
   */
  compareVectorClocks(clock1, clock2) {
    let result = 0;

    const allNodes = new Set([
      ...Object.keys(clock1 || {}),
      ...Object.keys(clock2 || {}),
    ]);

    for (const nodeId of allNodes) {
      const val1 = clock1?.[nodeId] || 0;
      const val2 = clock2?.[nodeId] || 0;

      
      if (val1 > val2) {
        if (result === -1) return null; // Concurrent
        result = 1;
      } else if (val1 < val2) {
        if (result === 1) return null; // Concurrent
        result = -1;
      }
    }

    return result;
  }

  /**
   * Increment local clock
   */
  tick() {
    this.vectorClock[this.nodeId] = (this.vectorClock[this.nodeId] || 0) + 1;
    return { ...this.vectorClock };
  }

  /**
   * Merge remote clock into local
   */
  mergeClock(remoteClock) {
    for (const [nodeId, value] of Object.entries(remoteClock || {})) {
      const localValue = this.vectorClock[nodeId] || 0;
      this.vectorClock[nodeId] = Math.max(localValue, value);
    }
    return { ...this.vectorClock };
  }

  /**
   * Merge state from remote
   */
  mergeState(localState, remoteState) {
    
    // Nested objects are still references
    const merged = { ...localState };

    
    for (const key in remoteState) {
      if (typeof remoteState[key] === 'object' && remoteState[key] !== null) {
        
        merged[key] = { ...merged[key], ...remoteState[key] };
      } else {
        merged[key] = remoteState[key];
      }
    }

    return merged;
  }

  /**
   * Create a CRDT operation for an element change
   */
  createOperation(elementId, changes, operationType = 'update') {
    return {
      id: uuidv4(),
      elementId,
      type: operationType,
      changes,
      clock: this.tick(),
      nodeId: this.nodeId,
      timestamp: Date.now(),
    };
  }

  /**
   * Apply operations in causal order
   */
  applyOperations(operations, currentState) {
    // Sort by vector clock (with BUG B1 affecting comparison)
    const sorted = [...operations].sort((a, b) => {
      const cmp = this.compareVectorClocks(a.clock, b.clock);
      if (cmp === null) {
        // Concurrent operations - use timestamp as tiebreaker
        return a.timestamp - b.timestamp;
      }
      return cmp;
    });

    let state = { ...currentState };
    for (const op of sorted) {
      state = this.applyOperation(op, state);
    }
    return state;
  }

  /**
   * Apply single operation to state
   */
  applyOperation(operation, state) {
    const { elementId, type, changes } = operation;

    switch (type) {
      case 'create':
        return {
          ...state,
          elements: {
            ...state.elements,
            [elementId]: changes,
          },
        };

      case 'update':
        if (!state.elements?.[elementId]) {
          return state; // Element doesn't exist
        }
        return {
          ...state,
          elements: {
            ...state.elements,
            [elementId]: this.mergeState(state.elements[elementId], changes),
          },
        };

      case 'delete':
        const { [elementId]: deleted, ...remaining } = state.elements || {};
        return {
          ...state,
          elements: remaining,
        };

      default:
        return state;
    }
  }

  /**
   * Detect conflicts between local and remote operations
   */
  detectConflicts(localOps, remoteOps) {
    const conflicts = [];

    for (const local of localOps) {
      for (const remote of remoteOps) {
        if (local.elementId === remote.elementId) {
          const cmp = this.compareVectorClocks(local.clock, remote.clock);
          if (cmp === null) {
            // Concurrent operations on same element
            conflicts.push({
              local,
              remote,
              resolution: this.resolveConflict(local, remote),
            });
          }
        }
      }
    }

    return conflicts;
  }

  /**
   * Resolve conflict between two operations
   * Last-writer-wins based on timestamp
   */
  resolveConflict(op1, op2) {
    // Simple last-writer-wins
    return op1.timestamp > op2.timestamp ? op1 : op2;
  }
}

module.exports = CRDTService;
