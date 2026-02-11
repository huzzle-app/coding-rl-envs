const { test } = require('node:test');
const assert = require('node:assert/strict');

const { DispatchFSM, BatchFSM, guardedTransition, workflowTimeline, parallelGuardEval } = require('../../src/core/workflow');
const { AdaptiveQueue, PriorityQueue } = require('../../src/core/queue');
const { CircuitBreaker } = require('../../src/core/resilience');
const { delegationChain } = require('../../src/core/authorization');

// ===== DispatchFSM: reset doesn't clear history (Bug) =====
// After reset, the FSM returns to 'pending' but the history array
// still contains all previous transitions. This causes stale audit trails.

test('state-adv-001: FSM reset clears state and history', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.reset();
  assert.equal(fsm.getState(), 'pending');
  assert.deepEqual(fsm.getHistory(), [],
    'history must be empty after reset');
});

test('state-adv-002: FSM reset allows fresh lifecycle', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('canceled');
  fsm.reset();
  fsm.transition('validated');
  assert.equal(fsm.getState(), 'validated');
  assert.deepEqual(fsm.getHistory(), ['pending']);
});

test('state-adv-003: FSM multiple resets', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.reset();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.reset();
  assert.deepEqual(fsm.getHistory(), []);
});

// ===== workflowTimeline: sequence numbering starts at 1 =====

test('state-adv-004: timeline records transitions correctly', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  const timeline = workflowTimeline(fsm);
  assert.equal(timeline.length, 2);
  assert.equal(timeline[0].sequence, 1);
  assert.equal(timeline[0].to, 'pending');
  assert.equal(timeline[1].to, 'validated');
});

test('state-adv-005: timeline empty for new FSM', () => {
  const fsm = new DispatchFSM();
  assert.deepEqual(workflowTimeline(fsm), []);
});

// ===== BatchFSM: state distribution tracking =====

test('state-adv-006: batch FSM all start pending', () => {
  const batch = new BatchFSM(5);
  const dist = batch.stateDistribution();
  assert.equal(dist['pending'], 5);
});

test('state-adv-007: batch FSM mixed states', () => {
  const batch = new BatchFSM(4);
  batch.transitionAll('validated');
  batch.machines[0].transition('capacity_checked');
  batch.machines[1].transition('capacity_checked');
  const dist = batch.stateDistribution();
  assert.equal(dist['capacity_checked'], 2);
  assert.equal(dist['validated'], 2);
});

test('state-adv-008: batch FSM handles invalid transitions gracefully', () => {
  const batch = new BatchFSM(3);
  const results = batch.transitionAll('dispatched');
  assert.equal(results.filter(r => r.success).length, 0,
    'no machine should go directly to dispatched from pending');
});

test('state-adv-009: batch FSM completion rate calculation', () => {
  const batch = new BatchFSM(4);
  batch.transitionAll('validated');
  batch.transitionAll('capacity_checked');
  batch.transitionAll('dispatched');
  batch.transitionAll('in_transit');
  batch.machines[0].transition('delivered');
  batch.machines[1].transition('delivered');
  batch.transitionAll('delivered');
  assert.equal(batch.completionRate(), 1);
});

// ===== AdaptiveQueue: hysteresis + state transition correctness =====
// Bug: shedding → normal directly (should go through throttled)
// Bug: recovery uses throttleThreshold instead of recoveryThreshold

test('state-adv-010: queue progressive state escalation', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.7,
    shedThreshold: 0.9,
    recoveryThreshold: 0.5
  });
  assert.equal(q.getState(), 'normal');
  q.updateLoad(0.75);
  assert.equal(q.getState(), 'throttled');
  q.updateLoad(0.92);
  assert.equal(q.getState(), 'shedding');
});

test('state-adv-011: queue recovery path shedding→throttled→normal', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.7,
    shedThreshold: 0.9,
    recoveryThreshold: 0.5
  });
  q.updateLoad(0.95);
  assert.equal(q.getState(), 'shedding');
  q.updateLoad(0.75);
  assert.equal(q.getState(), 'throttled',
    'must step down to throttled, not jump to normal');
  q.updateLoad(0.4);
  assert.equal(q.getState(), 'normal');
});

test('state-adv-012: queue hysteresis prevents flapping', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    recoveryThreshold: 0.6
  });
  q.updateLoad(0.85);
  assert.equal(q.getState(), 'throttled');
  q.updateLoad(0.78);
  assert.equal(q.getState(), 'throttled',
    '0.78 is above recovery threshold 0.6, should stay throttled');
  q.updateLoad(0.55);
  assert.equal(q.getState(), 'normal');
});

test('state-adv-013: queue repeated oscillation at boundary', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    shedThreshold: 0.95,
    recoveryThreshold: 0.6
  });
  for (let i = 0; i < 10; i++) {
    q.updateLoad(0.82);
    assert.equal(q.getState(), 'throttled');
    q.updateLoad(0.5);
    assert.equal(q.getState(), 'normal');
  }
});

// ===== CircuitBreaker state machine =====
// Bug: attemptReset inverted condition (transitions when elapsed < cooldown)

test('state-adv-014: circuit breaker closed→open on threshold failures', () => {
  const cb = new CircuitBreaker({ threshold: 3, cooldownMs: 5000 });
  cb.recordFailure(100);
  cb.recordFailure(200);
  assert.equal(cb.getState(), 'closed');
  cb.recordFailure(300);
  assert.equal(cb.getState(), 'open');
});

test('state-adv-015: circuit breaker stays open before cooldown', () => {
  const cb = new CircuitBreaker({ threshold: 2, cooldownMs: 10000 });
  cb.recordFailure(100);
  cb.recordFailure(200);
  assert.equal(cb.getState(), 'open');
  cb.attemptReset(5000);
  assert.equal(cb.getState(), 'open',
    'only 4800ms since last failure, should stay open');
});

test('state-adv-016: circuit breaker transitions to half-open after cooldown', () => {
  const cb = new CircuitBreaker({ threshold: 2, cooldownMs: 5000 });
  cb.recordFailure(100);
  cb.recordFailure(200);
  cb.attemptReset(6000);
  assert.equal(cb.getState(), 'half-open',
    'elapsed 5800ms > 5000ms cooldown, should be half-open');
});

test('state-adv-017: circuit breaker half-open→closed after successes', () => {
  const cb = new CircuitBreaker({ threshold: 2, cooldownMs: 1000, halfOpenMax: 3 });
  cb.recordFailure(100);
  cb.recordFailure(200);
  cb.attemptReset(2000);
  assert.equal(cb.getState(), 'half-open');
  cb.recordSuccess();
  cb.recordSuccess();
  assert.equal(cb.getState(), 'half-open');
  cb.recordSuccess();
  assert.equal(cb.getState(), 'closed');
});

test('state-adv-018: circuit breaker half-open→open on failure', () => {
  const cb = new CircuitBreaker({ threshold: 2, cooldownMs: 1000 });
  cb.recordFailure(100);
  cb.recordFailure(200);
  cb.attemptReset(2000);
  assert.equal(cb.getState(), 'half-open');
  cb.recordFailure(2100);
  assert.equal(cb.getState(), 'open');
});

// ===== PriorityQueue: state tracking =====

test('state-adv-019: priority queue maintains order after mixed operations', () => {
  const pq = new PriorityQueue();
  pq.enqueue('a', 5);
  pq.enqueue('b', 10);
  pq.enqueue('c', 1);
  assert.equal(pq.dequeue(), 'b');
  pq.enqueue('d', 8);
  assert.equal(pq.dequeue(), 'd');
  assert.equal(pq.dequeue(), 'a');
  assert.equal(pq.dequeue(), 'c');
});

test('state-adv-020: priority queue size after drain', () => {
  const pq = new PriorityQueue();
  for (let i = 0; i < 10; i++) pq.enqueue(`item-${i}`, i);
  const drained = pq.drain(5);
  assert.equal(drained.length, 5);
  assert.equal(pq.size(), 5);
});

// ===== parallelGuardEval: error handling in guards =====

test('state-adv-021: parallel guards all pass', () => {
  const guards = [() => true, () => true, () => true];
  const result = parallelGuardEval(guards, {});
  assert.equal(result.allPassed, true);
  assert.equal(result.errors.length, 0);
});

test('state-adv-022: parallel guards capture errors', () => {
  const guards = [
    () => true,
    () => { throw new Error('policy failure'); }
  ];
  const result = parallelGuardEval(guards, {});
  assert.equal(result.allPassed, false);
  assert.equal(result.errors.length, 1);
  assert.equal(result.errors[0], 'policy failure');
});

test('state-adv-023: parallel guards one failing blocks all', () => {
  const guards = [() => true, () => false, () => true];
  const result = parallelGuardEval(guards, {});
  assert.equal(result.allPassed, false);
});

test('state-adv-024: empty guards pass by default', () => {
  const result = parallelGuardEval([], {});
  assert.equal(result.allPassed, true);
});

// ===== delegationChain: privilege escalation detection =====
// Bug: doesn't validate that delegated role is ≤ delegator's role

test('state-adv-025: downward delegation valid', () => {
  const chain = [
    { userId: 'admin1', role: 'admin' },
    { userId: 'reviewer1', role: 'reviewer', delegatedBy: 'admin1' },
    { userId: 'op1', role: 'operator', delegatedBy: 'reviewer1' }
  ];
  assert.equal(delegationChain(chain).valid, true);
});

test('state-adv-026: upward delegation (escalation) invalid', () => {
  const chain = [
    { userId: 'op1', role: 'operator' },
    { userId: 'admin1', role: 'admin', delegatedBy: 'op1' }
  ];
  assert.equal(delegationChain(chain).valid, false,
    'operator cannot delegate admin privileges');
});

test('state-adv-027: viewer cannot create reviewer', () => {
  const chain = [
    { userId: 'v1', role: 'viewer' },
    { userId: 'r1', role: 'reviewer', delegatedBy: 'v1' }
  ];
  assert.equal(delegationChain(chain).valid, false);
});

test('state-adv-028: same-level delegation valid', () => {
  const chain = [
    { userId: 'r1', role: 'reviewer' },
    { userId: 'r2', role: 'reviewer', delegatedBy: 'r1' }
  ];
  assert.equal(delegationChain(chain).valid, true);
});

test('state-adv-029: chain depth 5 valid', () => {
  const chain = [{ userId: 'u0', role: 'admin' }];
  for (let i = 1; i <= 5; i++) {
    chain.push({ userId: `u${i}`, role: 'viewer', delegatedBy: `u${i-1}` });
  }
  assert.equal(delegationChain(chain).valid, true);
});

test('state-adv-030: chain depth 6 exceeds limit', () => {
  const chain = [{ userId: 'u0', role: 'admin' }];
  for (let i = 1; i <= 6; i++) {
    chain.push({ userId: `u${i}`, role: 'viewer', delegatedBy: `u${i-1}` });
  }
  assert.equal(delegationChain(chain).valid, false);
});

// ===== Matrix expansion =====

for (let i = 0; i < 15; i++) {
  test(`state-adv-matrix-${String(31 + i).padStart(3, '0')}: FSM lifecycle path ${i}`, () => {
    const fsm = new DispatchFSM();
    const path = ['validated', 'capacity_checked', 'dispatched', 'in_transit', 'delivered'];
    const stopAt = Math.min(i % 6, path.length);
    for (let j = 0; j < stopAt; j++) {
      fsm.transition(path[j]);
    }
    assert.equal(fsm.getHistory().length, stopAt);
    fsm.reset();
    assert.deepEqual(fsm.getHistory(), []);
    assert.equal(fsm.getState(), 'pending');
  });
}

for (let i = 0; i < 10; i++) {
  test(`state-adv-matrix-${String(46 + i).padStart(3, '0')}: circuit breaker recovery ${i}`, () => {
    const threshold = 2 + (i % 4);
    const cooldown = 1000 * (i + 1);
    const cb = new CircuitBreaker({ threshold, cooldownMs: cooldown });
    for (let j = 0; j < threshold; j++) {
      cb.recordFailure(j * 100);
    }
    assert.equal(cb.getState(), 'open');
    cb.attemptReset((threshold - 1) * 100 + cooldown + 1);
    assert.equal(cb.getState(), 'half-open');
  });
}

for (let i = 0; i < 10; i++) {
  test(`state-adv-matrix-${String(56 + i).padStart(3, '0')}: queue state escalation ${i}`, () => {
    const q = new AdaptiveQueue({
      throttleThreshold: 0.6 + i * 0.02,
      shedThreshold: 0.9,
      recoveryThreshold: 0.4
    });
    q.updateLoad(0.95);
    assert.equal(q.getState(), 'shedding');
    q.updateLoad(0.5);
    assert.notEqual(q.getState(), 'normal',
      'shedding should not jump directly to normal');
  });
}

for (let i = 0; i < 10; i++) {
  test(`state-adv-matrix-${String(66 + i).padStart(3, '0')}: batch FSM completion ${i}`, () => {
    const count = 3 + i;
    const batch = new BatchFSM(count);
    const fullPath = ['validated', 'capacity_checked', 'dispatched', 'in_transit', 'delivered'];
    for (const step of fullPath) batch.transitionAll(step);
    assert.equal(batch.completionRate(), 1);
    assert.equal(batch.stateDistribution()['delivered'], count);
  });
}
