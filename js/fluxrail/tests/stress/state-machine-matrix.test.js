const { test } = require('node:test');
const assert = require('node:assert/strict');

const { DispatchFSM } = require('../../src/core/workflow');
const { AdaptiveQueue } = require('../../src/core/queue');
const { delegationChain } = require('../../src/core/authorization');

// ===== DispatchFSM: domain-incorrect transitions remain =====
// Bug 1: cancel allowed from dispatched (physically dispatched, can't recall)
// Bug 2: cancel allowed from in_transit (package is moving)
// Bug 3: delivered→archived (delivered should be terminal)
// Bug 4: reset() doesn't clear history

test('state-fsm-001: initial state is pending', () => {
  assert.equal(new DispatchFSM().getState(), 'pending');
});

test('state-fsm-002: valid transition pending -> validated', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  assert.equal(fsm.getState(), 'validated');
});

test('state-fsm-003: full lifecycle path', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  fsm.transition('in_transit');
  fsm.transition('delivered');
  assert.equal(fsm.getState(), 'delivered');
});

test('state-fsm-004: cancel NOT allowed from dispatched', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  assert.equal(fsm.canTransition('canceled'), false,
    'once dispatched to carrier, cancellation is physically impossible');
});

test('state-fsm-005: cancel NOT allowed from in_transit', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  fsm.transition('in_transit');
  assert.equal(fsm.canTransition('canceled'), false,
    'package in transit cannot be cancelled');
});

test('state-fsm-006: cancel allowed from pending', () => {
  assert.equal(new DispatchFSM().canTransition('canceled'), true);
});

test('state-fsm-007: cancel allowed from validated', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  assert.equal(fsm.canTransition('canceled'), true);
});

test('state-fsm-008: cancel allowed from capacity_checked', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  assert.equal(fsm.canTransition('canceled'), true);
});

test('state-fsm-009: dispatched requires in_transit before delivered', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  assert.equal(fsm.canTransition('delivered'), false);
});

test('state-fsm-010: in_transit can reach delivered', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  fsm.transition('in_transit');
  assert.equal(fsm.canTransition('delivered'), true);
});

test('state-fsm-011: validated cannot self-transition', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  assert.equal(fsm.canTransition('validated'), false);
});

test('state-fsm-012: history tracks transitions', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  assert.deepEqual(fsm.getHistory(), ['pending', 'validated']);
});

test('state-fsm-013: reset clears history', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.reset();
  assert.equal(fsm.getState(), 'pending');
  assert.deepEqual(fsm.getHistory(), [],
    'reset should clear history for fresh start');
});

test('state-fsm-014: delivered is terminal - no further transitions', () => {
  const fsm = new DispatchFSM();
  fsm.transition('validated');
  fsm.transition('capacity_checked');
  fsm.transition('dispatched');
  fsm.transition('in_transit');
  fsm.transition('delivered');
  assert.equal(fsm.canTransition('archived'), false,
    'delivered is a terminal state; archival is an administrative process');
  assert.equal(fsm.canTransition('canceled'), false);
});

test('state-fsm-015: canceled is terminal', () => {
  const fsm = new DispatchFSM();
  fsm.transition('canceled');
  assert.equal(fsm.canTransition('pending'), false);
});

test('state-fsm-016: invalid transition throws', () => {
  assert.throws(() => new DispatchFSM().transition('dispatched'));
});

// ===== AdaptiveQueue: missing hysteresis + recovery path =====

test('state-queue-017: starts in normal', () => {
  assert.equal(new AdaptiveQueue({ throttleThreshold: 0.8 }).getState(), 'normal');
});

test('state-queue-018: transitions to throttled', () => {
  const q = new AdaptiveQueue({ throttleThreshold: 0.8 });
  q.updateLoad(0.85);
  assert.equal(q.getState(), 'throttled');
});

test('state-queue-019: hysteresis prevents oscillation at threshold', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    recoveryThreshold: 0.6
  });
  q.updateLoad(0.85);
  assert.equal(q.getState(), 'throttled');
  q.updateLoad(0.75);
  assert.equal(q.getState(), 'throttled',
    'should stay throttled above recovery threshold 0.6');
});

test('state-queue-020: recovery requires dropping below recovery threshold', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    recoveryThreshold: 0.6
  });
  q.updateLoad(0.85);
  q.updateLoad(0.55);
  assert.equal(q.getState(), 'normal');
});

test('state-queue-021: shedding recovery goes through throttled', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    shedThreshold: 0.95,
    recoveryThreshold: 0.6
  });
  q.updateLoad(0.96);
  assert.equal(q.getState(), 'shedding');
  q.updateLoad(0.85);
  assert.equal(q.getState(), 'throttled',
    'recovery from shedding must step through throttled');
});

test('state-queue-022: shedding cannot jump directly to normal', () => {
  const q = new AdaptiveQueue({
    throttleThreshold: 0.8,
    shedThreshold: 0.95,
    recoveryThreshold: 0.6
  });
  q.updateLoad(0.96);
  q.updateLoad(0.5);
  assert.notEqual(q.getState(), 'normal',
    'should not skip throttled phase during recovery');
});

// ===== delegationChain: missing role hierarchy validation =====
// A delegatee should not be able to receive a HIGHER role than the
// delegator possesses. operator cannot delegate admin privileges.

test('state-deleg-023: valid single-level delegation', () => {
  const chain = [
    { userId: 'u1', role: 'admin' },
    { userId: 'u2', role: 'operator', delegatedBy: 'u1' }
  ];
  const result = delegationChain(chain);
  assert.equal(result.valid, true);
  assert.equal(result.effectiveRole, 'operator');
});

test('state-deleg-024: broken chain detected', () => {
  const chain = [
    { userId: 'u1', role: 'admin' },
    { userId: 'u2', role: 'operator', delegatedBy: 'u999' }
  ];
  assert.equal(delegationChain(chain).valid, false);
});

test('state-deleg-025: role escalation rejected', () => {
  const chain = [
    { userId: 'u1', role: 'operator' },
    { userId: 'u2', role: 'admin', delegatedBy: 'u1' }
  ];
  assert.equal(delegationChain(chain).valid, false,
    'operator cannot delegate admin role (privilege escalation)');
});

test('state-deleg-026: delegation depth limited to 5', () => {
  const chain = [{ userId: 'u0', role: 'admin' }];
  for (let i = 1; i <= 6; i++) {
    chain.push({ userId: `u${i}`, role: 'viewer', delegatedBy: `u${i - 1}` });
  }
  assert.equal(delegationChain(chain).valid, false,
    'chain deeper than 5 delegations should be rejected');
});

test('state-deleg-027: depth of exactly 5 is valid', () => {
  const chain = [{ userId: 'u0', role: 'admin' }];
  for (let i = 1; i <= 5; i++) {
    chain.push({ userId: `u${i}`, role: 'viewer', delegatedBy: `u${i - 1}` });
  }
  assert.equal(delegationChain(chain).valid, true);
});

test('state-deleg-028: empty chain invalid', () => {
  assert.deepEqual(delegationChain([]), { valid: false, effectiveRole: null });
});

test('state-deleg-029: single root entry valid', () => {
  const result = delegationChain([{ userId: 'u1', role: 'admin' }]);
  assert.equal(result.valid, true);
  assert.equal(result.effectiveRole, 'admin');
});

test('state-deleg-030: lateral delegation at same level is valid', () => {
  const chain = [
    { userId: 'u1', role: 'reviewer' },
    { userId: 'u2', role: 'reviewer', delegatedBy: 'u1' }
  ];
  assert.equal(delegationChain(chain).valid, true);
});

// ===== Matrix: valid/invalid FSM paths =====

const VALID_PATHS = [
  ['validated', 'capacity_checked', 'dispatched', 'in_transit', 'delivered'],
  ['validated', 'canceled'],
  ['validated', 'capacity_checked', 'canceled'],
  ['canceled']
];

for (let i = 0; i < VALID_PATHS.length; i++) {
  test(`state-matrix-${String(31 + i).padStart(3, '0')}: valid path ${i}`, () => {
    const fsm = new DispatchFSM();
    for (const state of VALID_PATHS[i]) {
      assert.doesNotThrow(() => fsm.transition(state));
    }
  });
}

const INVALID_TRANSITIONS = [
  ['pending', 'dispatched'],
  ['pending', 'in_transit'],
  ['pending', 'delivered'],
  ['validated', 'dispatched'],
  ['validated', 'delivered'],
  ['capacity_checked', 'in_transit'],
  ['dispatched', 'validated'],
  ['in_transit', 'capacity_checked']
];

for (let i = 0; i < INVALID_TRANSITIONS.length; i++) {
  test(`state-matrix-${String(35 + i).padStart(3, '0')}: invalid ${INVALID_TRANSITIONS[i].join('->')}`, () => {
    const fsm = new DispatchFSM();
    const setup = {
      validated: ['validated'],
      capacity_checked: ['validated', 'capacity_checked'],
      dispatched: ['validated', 'capacity_checked', 'dispatched'],
      in_transit: ['validated', 'capacity_checked', 'dispatched', 'in_transit']
    };
    for (const s of setup[INVALID_TRANSITIONS[i][0]] || []) fsm.transition(s);
    assert.equal(fsm.canTransition(INVALID_TRANSITIONS[i][1]), false);
  });
}

for (let i = 0; i < 7; i++) {
  test(`state-matrix-${String(43 + i).padStart(3, '0')}: queue load ${i}`, () => {
    const q = new AdaptiveQueue({
      throttleThreshold: 0.7,
      shedThreshold: 0.9,
      recoveryThreshold: 0.5
    });
    const load = 0.1 + i * 0.12;
    q.updateLoad(load);
    if (load < 0.7) assert.equal(q.getState(), 'normal');
    else if (load < 0.9) assert.equal(q.getState(), 'throttled');
    else assert.ok(['throttled', 'shedding'].includes(q.getState()));
  });
}
