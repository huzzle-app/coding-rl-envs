const test = require('node:test');
const assert = require('node:assert/strict');

const { WorkflowEngine, canTransition, isValidState, GRAPH, TERMINAL_STATES } = require('../../src/core/workflow');
const { CircuitBreaker, CB_STATES } = require('../../src/core/resilience');
const { DispatchTicket, Severity } = require('../../src/models/dispatch-ticket');
const { PolicyEngine, ORDER } = require('../../src/core/policy');

const CASES = 400;

for (let idx = 0; idx < CASES; idx += 1) {
  test(`statemachine-${String(idx).padStart(4, '0')}`, () => {
    const variant = idx % 7;

    if (variant === 0) {
      // transitionWithValidation: validator receives (from, to) in correct order
      const engine = new WorkflowEngine();
      const entityId = `entity-${idx}`;
      engine.register(entityId, 'queued');
      let validatorArgs = null;
      const validator = (from, to) => {
        validatorArgs = { from, to };
        return true;
      };
      engine.transitionWithValidation(entityId, 'allocated', validator);
      // Validator should receive (from='queued', to='allocated')
      assert.equal(validatorArgs.from, 'queued',
        `validator first arg should be 'queued' (from), got '${validatorArgs.from}'`);
      assert.equal(validatorArgs.to, 'allocated',
        `validator second arg should be 'allocated' (to), got '${validatorArgs.to}'`);
    }

    if (variant === 1) {
      // rollbackLastTransition should restore previous state
      const engine = new WorkflowEngine();
      const entityId = `ship-${idx}`;
      engine.register(entityId, 'queued');
      engine.transition(entityId, 'allocated');
      assert.equal(engine.getState(entityId), 'allocated');
      const rollback = engine.rollbackLastTransition(entityId);
      assert.equal(rollback.success, true);
      assert.equal(engine.getState(entityId), 'queued',
        `after rollback, state should be 'queued', got '${engine.getState(entityId)}'`);
    }

    if (variant === 2) {
      // CircuitBreaker: failure in HALF_OPEN should revert to OPEN, not CLOSED
      const threshold = 10 + (idx % 5); // high threshold so count alone doesn't trip
      const cb = new CircuitBreaker(threshold, 30000);
      // Manually set to HALF_OPEN (simulating recovery timeout expiry)
      cb._state = CB_STATES.HALF_OPEN;
      cb._failures = 0;
      // Record a failure with context while in HALF_OPEN state
      const result = cb.recordFailureWithContext({ attempt: idx });
      // A failure in HALF_OPEN should revert to OPEN (protective fallback)
      assert.equal(result.state, CB_STATES.OPEN,
        `failure in HALF_OPEN should revert to OPEN, got ${result.state}`);
    }

    if (variant === 3) {
      // isValidState should return true for all states in GRAPH
      const validStates = Object.keys(GRAPH);
      const testState = validStates[idx % validStates.length];
      assert.equal(isValidState(testState), true,
        `'${testState}' is in GRAPH and should be valid`);
    }

    if (variant === 4) {
      // priorityBucket should use urgencyScore() (which factors SLA), not severity*10
      const severity = (idx % 7) + 1;
      const sla = 30 + (idx % 60);
      const ticket = new DispatchTicket(`T-${idx}`, severity, sla);
      const score = ticket.urgencyScore();
      const bucket = ticket.priorityBucket();
      // Correct bucket boundaries applied to urgencyScore (not severity*10)
      let expected;
      if (score >= 60) expected = 'critical';
      else if (score >= 40) expected = 'high';
      else if (score >= 20) expected = 'medium';
      else expected = 'low';
      assert.equal(bucket, expected,
        `bucket should be '${expected}' for urgencyScore=${score}, but code uses severity*10=${severity * 10}`);
    }

    if (variant === 5) {
      // PolicyEngine state transitions: evaluate then deescalate
      const engine = new PolicyEngine();
      engine._lastEscalation = 0;
      // Escalate to 'watch'
      const esc1 = engine.evaluate(3);
      assert.equal(engine.current, 'watch', 'should escalate to watch');
      // Deescalate with exactly 10 successes should NOT trigger (needs > 10)
      engine._lastEscalation = 0;
      const deesc = engine.deescalateGradual(10);
      // shouldDeescalate uses > threshold, so 10 should not be enough
      assert.equal(deesc.changed, false,
        `deescalateGradual(10) should not trigger (threshold is > 10), changed=${deesc.changed}`);
    }

    if (variant === 6) {
      // Workflow engine: multiple entities, independent state machines
      const engine = new WorkflowEngine();
      const count = 3 + (idx % 4);
      for (let i = 0; i < count; i++) {
        engine.register(`e-${idx}-${i}`, 'queued');
      }
      // Transition each through different paths
      engine.transition(`e-${idx}-0`, 'allocated');
      engine.transition(`e-${idx}-0`, 'departed');
      engine.transition(`e-${idx}-1`, 'cancelled');

      // Verify active count (non-terminal entities)
      const terminalCount = engine.activeCount();
      // e-0 is in 'departed' (non-terminal), e-1 is in 'cancelled' (terminal)
      // rest are in 'queued' (non-terminal)
      const expectedActive = count - 1; // only e-1 is terminal
      assert.equal(terminalCount, expectedActive,
        `activeCount should be ${expectedActive} (${count} total, 1 cancelled), got ${terminalCount}`);
    }
  });
}
