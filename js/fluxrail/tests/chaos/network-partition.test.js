const test = require('node:test');
const assert = require('node:assert/strict');
const { deterministicPartition, churnRate } = require('../../src/core/routing');

test('partition mapping remains deterministic and measurable under churn', () => {
  const shard = deterministicPartition('tenant-alpha', 17);
  assert.equal(typeof shard, 'number');
  assert.equal(shard >= 0 && shard < 17, true);

  const churn = churnRate({ n1: 'h1', n2: 'h2' }, { n1: 'h3', n2: 'h2', n3: 'h4' });
  assert.equal(churn, 2 / 3);
});
