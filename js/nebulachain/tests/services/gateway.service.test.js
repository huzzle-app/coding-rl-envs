const test = require('node:test');
const assert = require('node:assert/strict');
const gateway = require('../../services/gateway/service');

test('scoreNode returns positive for active node', () => {
  const node = new gateway.RouteNode('n1', 100, true, 10);
  const score = gateway.scoreNode(node);
  assert.ok(score > 0);
});

test('selectPrimaryNode returns highest scored node', () => {
  const nodes = [
    new gateway.RouteNode('a', 50, true, 80),
    new gateway.RouteNode('b', 200, true, 5),
    new gateway.RouteNode('c', 10, true, 90),
  ];
  const best = gateway.selectPrimaryNode(nodes);
  assert.equal(best.nodeId, 'b');
});

test('buildRouteChain limits hops', () => {
  const nodes = Array.from({ length: 10 }, (_, i) => new gateway.RouteNode(`n${i}`, 100 - i, true, 5));
  const chain = gateway.buildRouteChain(nodes, 3);
  assert.equal(chain.length, 3);
});

test('admissionControl rejects when at capacity', () => {
  const result = gateway.admissionControl({ currentLoad: 100, maxCapacity: 100, priority: 5 });
  assert.equal(result.admitted, false);
});
