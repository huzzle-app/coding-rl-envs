const { test } = require('node:test');
const assert = require('node:assert/strict');

const { riskScoreAggregator, policyChain } = require('../../src/core/policy');
const { auditChainValidator } = require('../../src/core/security');
const { failoverChain } = require('../../src/core/routing');
const { guardedTransition } = require('../../src/core/workflow');

// ===== riskScoreAggregator: Bug A (totalWeight+1 dilution) masks Bug B (> vs >=) =====
// Bug A makes all scores ~slightly lower, so scores at exactly 70/40/20
// never reach those thresholds. Once A is fixed, Bug B becomes visible:
// >= 70 should be 'critical' but > 70 classifies exactly-70 as 'high'.

test('multistep-risk-001: single score with weight 1 returns exact value', () => {
  const result = riskScoreAggregator([{ source: 'scan', value: 50, weight: 1 }]);
  assert.equal(result.score, 50);
});

test('multistep-risk-002: weighted average computed correctly', () => {
  const scores = [
    { source: 'a', value: 100, weight: 3 },
    { source: 'b', value: 0, weight: 1 }
  ];
  assert.equal(riskScoreAggregator(scores).score, 75);
});

test('multistep-risk-003: score exactly 70 classified as critical', () => {
  assert.equal(
    riskScoreAggregator([{ source: 'test', value: 70, weight: 1 }]).level,
    'critical'
  );
});

test('multistep-risk-004: score exactly 40 classified as high', () => {
  assert.equal(
    riskScoreAggregator([{ source: 'test', value: 40, weight: 1 }]).level,
    'high'
  );
});

test('multistep-risk-005: score exactly 20 classified as medium', () => {
  assert.equal(
    riskScoreAggregator([{ source: 'test', value: 20, weight: 1 }]).level,
    'medium'
  );
});

test('multistep-risk-006: score 19.9 classified as low', () => {
  assert.equal(
    riskScoreAggregator([{ source: 'test', value: 19.9, weight: 1 }]).level,
    'low'
  );
});

test('multistep-risk-007: two equal weights produce mean', () => {
  const result = riskScoreAggregator([
    { source: 'a', value: 60, weight: 1 },
    { source: 'b', value: 80, weight: 1 }
  ]);
  assert.equal(result.score, 70);
  assert.equal(result.level, 'critical');
});

test('multistep-risk-008: empty scores returns zero/low', () => {
  assert.deepEqual(riskScoreAggregator([]), { score: 0, level: 'low' });
});

test('multistep-risk-009: high weight dominates', () => {
  const result = riskScoreAggregator([
    { source: 'minor', value: 10, weight: 1 },
    { source: 'major', value: 90, weight: 9 }
  ]);
  assert.equal(result.score, 82);
});

test('multistep-risk-010: three weighted sources', () => {
  const result = riskScoreAggregator([
    { source: 'a', value: 50, weight: 2 },
    { source: 'b', value: 30, weight: 2 },
    { source: 'c', value: 80, weight: 1 }
  ]);
  assert.equal(result.score, (50 * 2 + 30 * 2 + 80 * 1) / 5);
});

// ===== auditChainValidator: Bug A (compares parentHash to own hash) =====
// Bug B (genesis entry expects null parentHash, should accept 'genesis')
// Fixing A (making it compare to previous entry's hash) reveals B.

test('multistep-audit-011: valid chain of 3 entries', () => {
  const chain = [
    { hash: 'h1', parentHash: 'genesis' },
    { hash: 'h2', parentHash: 'h1' },
    { hash: 'h3', parentHash: 'h2' }
  ];
  assert.equal(auditChainValidator(chain).valid, true);
});

test('multistep-audit-012: broken chain detected at correct index', () => {
  const chain = [
    { hash: 'h1', parentHash: 'genesis' },
    { hash: 'h2', parentHash: 'wrong' },
    { hash: 'h3', parentHash: 'h2' }
  ];
  const result = auditChainValidator(chain);
  assert.equal(result.valid, false);
  assert.equal(result.brokenAt, 1);
});

test('multistep-audit-013: genesis entry has genesis marker', () => {
  assert.equal(
    auditChainValidator([{ hash: 'h1', parentHash: 'genesis' }]).valid,
    true
  );
});

test('multistep-audit-014: single entry with non-genesis parent invalid', () => {
  const result = auditChainValidator([{ hash: 'h1', parentHash: 'some-parent' }]);
  assert.equal(result.valid, false);
  assert.equal(result.brokenAt, 0);
});

test('multistep-audit-015: entry must reference previous hash', () => {
  const chain = [
    { hash: 'aaa', parentHash: 'genesis' },
    { hash: 'bbb', parentHash: 'aaa' },
    { hash: 'ccc', parentHash: 'aaa' }
  ];
  const result = auditChainValidator(chain);
  assert.equal(result.valid, false);
  assert.equal(result.brokenAt, 2);
});

test('multistep-audit-016: empty chain invalid', () => {
  assert.deepEqual(auditChainValidator([]), { valid: false, brokenAt: -1 });
});

test('multistep-audit-017: long valid chain passes', () => {
  const chain = [{ hash: 'h0', parentHash: 'genesis' }];
  for (let i = 1; i < 20; i++) {
    chain.push({ hash: `h${i}`, parentHash: `h${i - 1}` });
  }
  assert.equal(auditChainValidator(chain).valid, true);
});

test('multistep-audit-018: break at last entry detected', () => {
  const chain = [
    { hash: 'h0', parentHash: 'genesis' },
    { hash: 'h1', parentHash: 'h0' },
    { hash: 'h2', parentHash: 'h0' }
  ];
  assert.equal(auditChainValidator(chain).brokenAt, 2);
});

// ===== guardedTransition: .some() (OR) instead of .every() (AND) =====
// Also returns event.target on failure instead of current state

test('multistep-guard-019: all guards pass allows transition', () => {
  const result = guardedTransition('pending', { target: 'validated' }, [() => true, () => true]);
  assert.equal(result.transitioned, true);
  assert.equal(result.state, 'validated');
});

test('multistep-guard-020: one guard failing blocks transition', () => {
  const result = guardedTransition('pending', { target: 'validated' }, [() => true, () => false]);
  assert.equal(result.transitioned, false);
  assert.equal(result.state, 'pending',
    'failed transition should return current state, not target');
});

test('multistep-guard-021: all guards failing blocks', () => {
  const result = guardedTransition('drafted', { target: 'dispatched' }, [() => false, () => false]);
  assert.equal(result.transitioned, false);
  assert.equal(result.state, 'drafted');
});

test('multistep-guard-022: no guards means no transition', () => {
  const result = guardedTransition('pending', { target: 'done' }, []);
  assert.equal(result.transitioned, false);
});

test('multistep-guard-023: three guards all must pass', () => {
  const result = guardedTransition('a', { target: 'b' }, [() => true, () => true, () => true]);
  assert.equal(result.transitioned, true);
});

test('multistep-guard-024: first of three fails blocks all', () => {
  const result = guardedTransition('s1', { target: 's2' }, [() => false, () => true, () => true]);
  assert.equal(result.transitioned, false);
  assert.equal(result.state, 's1');
});

// ===== policyChain: break on deny prevents metadata from later policies =====

test('multistep-chain-025: all-allow policies produce allow', () => {
  const policies = [
    () => ({ decision: 'allow', metadata: { source: 'p1' } }),
    () => ({ decision: 'allow', metadata: { source: 'p2' } })
  ];
  const result = policyChain(policies, {});
  assert.equal(result.decision, 'allow');
  assert.equal(result.evaluated, 2);
});

test('multistep-chain-026: deny with all policies still evaluated', () => {
  const policies = [
    () => ({ decision: 'deny', metadata: { blocked: true } }),
    () => ({ decision: 'allow', metadata: { audit: 'logged' } })
  ];
  const result = policyChain(policies, {});
  assert.equal(result.decision, 'deny');
  assert.equal(result.evaluated, 2,
    'all policies must be evaluated even after deny');
  assert.equal(result.metadata.audit, 'logged',
    'metadata from post-deny policy must be collected');
});

test('multistep-chain-027: metadata from all policies collected after deny', () => {
  const policies = [
    () => ({ decision: 'allow', metadata: { rateLimit: 100 } }),
    () => ({ decision: 'deny', metadata: { reason: 'quota' } }),
    () => ({ decision: 'allow', metadata: { traceId: 'abc' } })
  ];
  const result = policyChain(policies, {});
  assert.equal(result.decision, 'deny');
  assert.equal(result.evaluated, 3);
  assert.equal(result.metadata.traceId, 'abc',
    'third policy metadata needed for audit trail');
});

test('multistep-chain-028: empty chain allows', () => {
  assert.equal(policyChain([], {}).decision, 'allow');
});

test('multistep-chain-029: failover routes under threshold remain', () => {
  const routes = [
    { id: 'r1', failures: 0 },
    { id: 'r2', failures: 2 },
    { id: 'r3', failures: 1 }
  ];
  assert.equal(failoverChain(routes, 3).active.length, 3);
});

test('multistep-chain-030: routes at threshold removed', () => {
  const routes = [
    { id: 'r1', failures: 3 },
    { id: 'r2', failures: 1 }
  ];
  assert.equal(failoverChain(routes, 3).active.length, 1);
});

// ===== Matrix expansion =====

for (let i = 0; i < 20; i++) {
  test(`multistep-matrix-${String(31 + i).padStart(3, '0')}: risk threshold ${i}`, () => {
    const value = 10 + i * 3.5;
    const result = riskScoreAggregator([{ source: 'scan', value, weight: 1 }]);
    assert.equal(result.score, value);
    if (value >= 70) assert.equal(result.level, 'critical');
    else if (value >= 40) assert.equal(result.level, 'high');
    else if (value >= 20) assert.equal(result.level, 'medium');
    else assert.equal(result.level, 'low');
  });
}
