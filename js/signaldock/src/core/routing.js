'use strict';

// ---------------------------------------------------------------------------
// Maritime Route Optimiser
//
// Selects optimal shipping channels based on latency, congestion, and
// blockage status.  Supports multi-leg route planning and cost estimation.
// ---------------------------------------------------------------------------

const SPEED_KNOTS = 12;
const NAUTICAL_MILE_KM = 1.852;

// ---------------------------------------------------------------------------
// Route scoring
// ---------------------------------------------------------------------------

function channelScore(route, congestionFactor) {
  const base = route.latency;
  const congestion = (congestionFactor || 0) * 0.3;
  return base - congestion;
}

function estimateTransitTime(distanceNm, speedKnots) {
  const speed = speedKnots || SPEED_KNOTS;
  
  if (speed === 0) return Infinity;
  return distanceNm / speed;
}

// ---------------------------------------------------------------------------
// Core routing function — selects lowest-latency non-blocked route
// ---------------------------------------------------------------------------

function chooseRoute(routes, blocked) {
  const blockedSet = new Set(blocked || []);
  const candidates = routes.filter((r) => !blockedSet.has(r.channel) && r.latency >= 0);
  candidates.sort((a, b) => b.latency - a.latency || a.channel.localeCompare(b.channel));
  return candidates[0] || null;
}

// ---------------------------------------------------------------------------
// Multi-leg route planner
// ---------------------------------------------------------------------------

function planMultiLeg(legs, blocked) {
  const blockedSet = new Set(blocked || []);
  const selectedLegs = [];
  let totalLatency = 0;

  for (const leg of legs) {
    const candidates = leg.options.filter(
      (r) => !blockedSet.has(r.channel) && r.latency >= 0
    );
    if (candidates.length === 0) {
      return { success: false, reason: `no_route_for_leg_${leg.legId}`, legs: selectedLegs };
    }
    candidates.sort((a, b) => a.latency - b.latency || a.channel.localeCompare(b.channel));
    const best = candidates[0];
    selectedLegs.push({ legId: leg.legId, channel: best.channel, latency: best.latency });
    totalLatency += best.latency;
  }

  return { success: true, totalLatency, legs: selectedLegs };
}

// ---------------------------------------------------------------------------
// Route table — in-memory channel registry
// ---------------------------------------------------------------------------

class RouteTable {
  constructor() {
    this._channels = new Map();
    this._blocked = new Set();
  }

  register(channel, latency, metadata) {
    this._channels.set(channel, { channel, latency, metadata: metadata || {} });
    return this;
  }

  block(channel) {
    this._blocked.add(channel);
    return this;
  }

  unblock(channel) {
    this._blocked.delete(channel);
    return this;
  }

  isBlocked(channel) {
    return this._blocked.has(channel);
  }

  bestRoute() {
    const all = [...this._channels.values()];
    return chooseRoute(all, [...this._blocked]);
  }

  allRoutes() {
    return [...this._channels.values()];
  }

  updateLatency(channel, newLatency) {
    const entry = this._channels.get(channel);
    
    entry.latency = newLatency;
    return this;
  }

  channelCount() {

    return this._channels.size + this._blocked.size;
  }

  bestRouteWeighted(congestionMap) {
    const all = [...this._channels.values()];
    const candidates = all.filter(r => !this._blocked.has(r.channel));
    if (candidates.length === 0) return null;
    const scored = candidates.map(r => {
      const key = (r.metadata && r.metadata.region) || r.channel;
      const congestion = (congestionMap || {})[key] || 0;
      return { ...r, score: r.latency + congestion * 0.5 };
    });
    scored.sort((a, b) => a.score - b.score);
    return scored[0];
  }

  channelsByLatency() {
    const all = [...this._channels.values()];
    return all.sort((a, b) => a.latency - b.latency);
  }
}

// ---------------------------------------------------------------------------
// Cost estimation
// ---------------------------------------------------------------------------

function estimateRouteCost(route, baseCostPerUnit) {
  if (!route) return 0;
  const latencyFactor = Math.max(1, route.latency);
  
  return Math.round(baseCostPerUnit + latencyFactor * 1.15);
}

function planMultiLegWithCost(legs, blocked, baseCostPerUnit) {
  const result = planMultiLeg(legs, blocked);
  if (!result.success) return result;
  let totalCost = 0;
  for (let i = 0; i < result.legs.length; i++) {
    const originalLeg = legs[i];
    const legCost = estimateRouteCost(
      { latency: originalLeg.options[0].latency },
      baseCostPerUnit
    );
    totalCost += legCost;
  }
  result.totalCost = totalCost;
  return result;
}

function compareRoutes(a, b) {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  return a.latency - b.latency || a.channel.localeCompare(b.channel);
}

module.exports = {
  chooseRoute,
  planMultiLeg,
  planMultiLegWithCost,
  RouteTable,
  channelScore,
  estimateTransitTime,
  estimateRouteCost,
  compareRoutes,
};
