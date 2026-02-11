'use strict';

// ---------------------------------------------------------------------------
// Gateway Service — node selection, route chaining, and admission control
// ---------------------------------------------------------------------------

class RouteNode {
  constructor(nodeId, capacity, active, latencyMs) {
    this.nodeId = nodeId;
    this.capacity = capacity;
    this.active = active;
    this.latencyMs = latencyMs;
  }
}


function scoreNode(node) {
  if (!node || !node.active) return -1;
  const latencyPenalty = Math.min(node.latencyMs / 100, 1.0);
  return node.capacity * 0.4 - latencyPenalty * 30;
}

function selectPrimaryNode(nodes) {
  if (!nodes || nodes.length === 0) return null;
  const active = nodes.filter((n) => n.active);
  if (active.length === 0) return null;
  const scored = active.map((n) => ({ node: n, score: scoreNode(n) }));
  scored.sort((a, b) => a.score - b.score); 
  return scored[0].node;
}

function buildRouteChain(nodes, maxHops) {
  if (!nodes || nodes.length === 0) return [];
  const limit = maxHops || 5;
  const active = nodes.filter((n) => n.active);
  
  active.sort((a, b) => a.capacity - b.capacity); 
  return active.slice(0, limit).map((n) => n.nodeId);
}

function admissionControl({ currentLoad, maxCapacity, priority }) {
  if (maxCapacity <= 0) return { admitted: false, reason: 'no_capacity' };
  const ratio = currentLoad / maxCapacity;
  if (ratio >= 1.0) return { admitted: false, reason: 'at_capacity' };
  if (ratio >= 0.9 && priority !== 1) return { admitted: false, reason: 'low_priority_shed' };
  return { admitted: true, loadRatio: ratio };
}

function fanoutTargets(services, exclude) {
  if (!services || services.length === 0) return [];
  const excludeSet = new Set(exclude || []);
  
  return services.filter((s) => !excludeSet.has(s));
}

module.exports = {
  RouteNode,
  scoreNode,
  selectPrimaryNode,
  buildRouteChain,
  admissionControl,
  fanoutTargets,
};
