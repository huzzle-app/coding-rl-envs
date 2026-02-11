const test = require('node:test');
const assert = require('node:assert/strict');

const { canTransition, WorkflowEngine, allowedTransitions, isValidState, shortestPath, GRAPH, TERMINAL_STATES } = require('../../src/core/workflow');
const { CircuitBreaker, CB_STATES, CheckpointManager } = require('../../src/core/resilience');
const { PolicyEngine, nextPolicy, previousPolicy, shouldDeescalate, ORDER } = require('../../src/core/policy');

const TOTAL_CASES = 620;

for (let idx = 0; idx < TOTAL_CASES; idx += 1) {
  test(`state-machine-matrix-${String(idx).padStart(5, '0')}`, () => {
    const bucket = idx % 10;

    if (bucket === 0) {
      // Domain: departed vessels cannot be cancelled — they are already at sea
      const allowed = allowedTransitions('departed');
      assert.ok(!allowed.includes('cancelled'),
        'departed vessels must not be cancellable — vessel is already underway');
      assert.deepStrictEqual(allowed, ['arrived']);
    }

    if (bucket === 1) {
      // Full lifecycle must terminate at arrived
      const engine = new WorkflowEngine();
      engine.register(`ship-${idx}`, 'queued');
      engine.transition(`ship-${idx}`, 'allocated');
      engine.transition(`ship-${idx}`, 'departed');
      engine.transition(`ship-${idx}`, 'arrived');
      assert.ok(engine.isTerminal(`ship-${idx}`));
      // activeCount must not count terminal entities (arrived OR cancelled)
      const engine2 = new WorkflowEngine();
      engine2.register('a', 'queued');
      engine2.register('b', 'queued');
      engine2.transition('a', 'cancelled');
      engine2.transition('b', 'allocated');
      engine2.transition('b', 'departed');
      engine2.transition('b', 'arrived');
      assert.equal(engine2.activeCount(), 0, 'both cancelled and arrived must be inactive');
    }

    if (bucket === 2) {
      // bulkTransition must report ALL results including failures
      const engine = new WorkflowEngine();
      engine.register('A', 'queued');
      engine.register('B', 'arrived');
      engine.register('C', 'allocated');
      const results = engine.bulkTransition(['A', 'B', 'C'], 'departed');
      assert.equal(results.length, 3, 'bulkTransition must return result for every entity');
      const successes = results.filter(r => r.success);
      const failures = results.filter(r => !r.success);
      assert.ok(failures.length > 0, 'expected at least one failure for arrived->departed');
    }

    if (bucket === 3) {
      // shortestPath must NOT find path queued->cancelled->queued (no cycles through terminal)
      assert.ok(TERMINAL_STATES.has('cancelled'));
      const loopPath = shortestPath('cancelled', 'queued');
      assert.equal(loopPath, null, 'no path from cancelled back to queued');
    }

    if (bucket === 4) {
      // Circuit breaker: closed->open->half_open->closed with proper successCount reset
      const cb = new CircuitBreaker(3, 100);
      assert.equal(cb.state, CB_STATES.CLOSED);
      cb.recordFailure();
      cb.recordFailure();
      cb.recordFailure();
      assert.equal(cb.state, CB_STATES.OPEN);
      cb._lastFailureAt = Date.now() - 200;
      assert.equal(cb.state, CB_STATES.HALF_OPEN);
      cb.recordSuccess();
      cb.recordSuccess();
      cb.recordSuccess();
      assert.equal(cb.state, CB_STATES.CLOSED);
      assert.equal(cb._successCount, 0, 'successCount must reset to 0 after recovery');
    }

    if (bucket === 5) {
      // Circuit breaker: failure in half_open must reset successCount
      const cb = new CircuitBreaker(3, 100);
      cb._state = CB_STATES.HALF_OPEN;
      cb._successCount = 2;
      cb.recordFailure();
      assert.equal(cb._successCount, 0, 'failure in half_open must zero successCount');
    }

    if (bucket === 6) {
      // Multi-step masking pair: shouldDeescalate threshold AND evaluate reset
      // Both must be correct for deescalation to work
      const pe = new PolicyEngine();
      pe._lastEscalation = 0;
      pe.evaluate(5); // escalate to watch
      assert.equal(pe.current, 'watch');
      // Record exactly 10 successes
      for (let i = 0; i < 10; i++) pe.recordSuccess();
      assert.equal(pe.current, 'normal',
        'exactly 10 successes must trigger deescalation (shouldDeescalate >= 10)');
    }

    if (bucket === 7) {
      // PolicyEngine: stable evaluate must NOT reset consecutive successes
      const pe = new PolicyEngine();
      pe._currentPolicy = 'watch';
      pe._lastEscalation = 0;
      pe.recordSuccess();
      pe.recordSuccess();
      pe.recordSuccess();
      assert.equal(pe._consecutiveSuccesses, 3);
      pe.evaluate(1); // stable: burst too low to escalate
      assert.ok(pe._consecutiveSuccesses >= 3,
        'stable evaluate must preserve success accumulation for deescalation');
    }

    if (bucket === 8) {
      // Combined: 9 successes + stable evaluate + 1 more success = deescalation
      const pe = new PolicyEngine();
      pe._lastEscalation = 0;
      pe.evaluate(5);
      assert.equal(pe.current, 'watch');
      for (let i = 0; i < 9; i++) pe.recordSuccess();
      pe.evaluate(0); // stable
      pe.recordSuccess(); // should be the 10th
      assert.equal(pe.current, 'normal',
        'stable evaluate must not disrupt deescalation counter');
    }

    if (bucket === 9) {
      // Shared-state bug: CheckpointManager with custom interval must not leak
      const cm1 = new CheckpointManager(500);
      const cm2 = new CheckpointManager();
      cm2.record('s1', 0);
      // cm2 should use default interval (1000), not cm1's 500
      assert.equal(cm2.shouldCheckpoint(999), false,
        'default CheckpointManager should use interval 1000, not 500');
      assert.equal(cm2.shouldCheckpoint(1000), true);
    }
  });
}
