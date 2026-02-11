const test = require('node:test');
const assert = require('node:assert/strict');

const { buildLedgerEntries, balanceExposure, detectSequenceGap } = require('../../src/core/ledger');

test('buildLedgerEntries and exposure balance', () => {
  const entries = buildLedgerEntries([
    { id: 'e1', account: 'a', delta: 200, seq: 1 },
    { id: 'e2', account: 'a', delta: -80, seq: 2 },
    { id: 'e3', account: 'b', delta: 90, seq: 1 }
  ]);
  const exposure = balanceExposure(entries);
  assert.equal(exposure.a, 120);
  assert.equal(exposure.b, 90);
});

test('detectSequenceGap identifies account gaps', () => {
  const hasGap = detectSequenceGap([
    { account: 'a', seq: 1 },
    { account: 'a', seq: 3 }
  ]);
  assert.equal(hasGap, true);
});
