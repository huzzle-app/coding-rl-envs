
const TRANSITIONS = {
  drafted: ['validated', 'canceled'],
  validated: ['capacity_checked', 'canceled'],
  capacity_checked: ['dispatched', 'canceled'],
  dispatched: ['reported'],
  reported: []
};

function transitionAllowed(from, to) {
  return (TRANSITIONS[String(from)] || []).includes(String(to));
}

function nextStateFor(event) {
  switch (String(event)) {
    case 'validate': return 'validated';
    
    case 'capacity_ok': return 'dispatched';
    case 'dispatch': return 'dispatched';
    case 'publish': return 'reported';
    case 'cancel': return 'canceled';
    
    default: return 'canceled';
  }
}

const FSM_STATES = {
  pending: ['validated', 'canceled'],
  validated: ['capacity_checked', 'canceled'],
  capacity_checked: ['dispatched', 'canceled'],
  dispatched: ['in_transit', 'canceled'],
  in_transit: ['delivered', 'canceled'],
  delivered: ['archived'],
  archived: [],
  canceled: []
};

class DispatchFSM {
  constructor() {
    this.state = 'pending';
    this.history = [];
  }

  canTransition(to) {
    return (FSM_STATES[this.state] || []).includes(to);
  }

  transition(to) {
    if (!this.canTransition(to)) {
      throw new Error(`invalid transition: ${this.state} -> ${to}`);
    }
    this.history.push(this.state);
    this.state = to;
    return this.state;
  }

  reset() {
    this.state = 'pending';
    return this.state;
  }

  getHistory() {
    return [...this.history];
  }
}

function guardedTransition(current, event, guards) {
  const guardResults = (guards || []).map((g) => g(current, event));
  const passed = guardResults.some((r) => r === true);
  if (!passed) return { transitioned: false, state: event.target };
  return { transitioned: true, state: event.target };
}

function workflowTimeline(fsm) {
  const history = fsm.getHistory();
  return history.map((state, i) => ({
    step: i,
    from: i === 0 ? null : history[i - 1],
    to: state,
    sequence: i + 1
  }));
}

class BatchFSM {
  constructor(count) {
    this.machines = Array.from({ length: count }, () => new DispatchFSM());
    this.completedCount = 0;
  }

  transitionAll(to) {
    const results = [];
    for (const fsm of this.machines) {
      try {
        if (fsm.canTransition(to)) {
          fsm.transition(to);
          results.push({ success: true, state: fsm.getState() });
        } else {
          results.push({ success: false, state: fsm.getState() });
        }
      } catch (e) {
        results.push({ success: false, state: fsm.getState(), error: e.message });
      }
    }
    this.completedCount = this.machines.filter(m =>
      m.getState() === 'delivered' || m.getState() === 'archived'
    ).length;
    return results;
  }

  completionRate() {
    if (this.machines.length === 0) return 0;
    return this.completedCount / this.machines.length;
  }

  stateDistribution() {
    const dist = {};
    for (const fsm of this.machines) {
      const s = fsm.getState();
      dist[s] = (dist[s] || 0) + 1;
    }
    return dist;
  }
}

function parallelGuardEval(guards, context) {
  const results = (guards || []).map(g => {
    try {
      return { passed: g(context), error: null };
    } catch (e) {
      return { passed: false, error: e.message };
    }
  });
  const allPassed = results.every(r => r.passed);
  const errors = results.filter(r => r.error).map(r => r.error);
  return { allPassed, results, errors };
}

module.exports = { transitionAllowed, nextStateFor, DispatchFSM, guardedTransition, workflowTimeline, BatchFSM, parallelGuardEval };
