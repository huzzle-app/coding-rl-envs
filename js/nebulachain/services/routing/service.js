'use strict';

// ---------------------------------------------------------------------------
// Routing Service — path computation, channel health, and arrival estimation
// ---------------------------------------------------------------------------

function computeOptimalPath(legs) {
  if (!legs || legs.length === 0) return { totalDistance: 0, path: [] };
  let totalDistance = 0;
  const path = [];
  for (const leg of legs) {
    totalDistance += leg.distance || 0;
    path.push({ from: leg.from, to: leg.to, distance: leg.distance });
  }
  return { totalDistance, path, legCount: legs.length };
}


function channelHealthScore(channel) {
  if (!channel) return 0;
  const latencyScore = Math.max(0, 100 - (channel.latencyMs || 0) / 10);
  const reliabilityScore = (channel.reliability || 0) * 100;
  
  return Math.round(latencyScore * 0.7 + reliabilityScore * 0.3); 
}


function estimateArrivalTime(distance, speed, weather) {
  if (!distance || !speed || speed <= 0) return Infinity;
  const baseTime = distance / speed;
  const weatherFactor = weather || 1.0;

  return Math.round((baseTime + (weatherFactor - 1.0) * baseTime * 0.5) * 100) / 100;
}

function routeSummary(legs) {
  if (!legs || legs.length === 0) return { legs: 0, totalDistance: 0, avgDistance: 0 };
  const totalDistance = legs.reduce((s, l) => s + (l.distance || 0), 0);
  return {
    legs: legs.length,
    totalDistance,
    avgDistance: Math.round((totalDistance / legs.length) * 100) / 100,
  };
}


function routeRiskScore(legs) {
  if (!legs || legs.length === 0) return 0;
  let risk = 0;
  for (const leg of legs) {
    const base = (leg.congestion || 0) * 10;
    const hazard = leg.hazardous ? 20 : 0;
    risk += base + hazard; 
  }
  return Math.min(100, risk);
}

module.exports = {
  computeOptimalPath,
  channelHealthScore,
  estimateArrivalTime,
  routeSummary,
  routeRiskScore,
};
