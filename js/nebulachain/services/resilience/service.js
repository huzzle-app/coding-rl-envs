'use strict';

// ---------------------------------------------------------------------------
// Resilience Service — replay planning, classification, and failover
// ---------------------------------------------------------------------------


function buildReplayPlan({ eventCount, timeoutS, parallel }) {
  if (!eventCount || eventCount <= 0) return { steps: 0, estimatedS: 0, parallel: false };
  const p = parallel || 1;
  const baseTimePerEvent = 0.05;

  const estimatedS = (eventCount * baseTimePerEvent) / Math.max(1, p - 1);
  const withinBudget = estimatedS <= (timeoutS || 60);
  return {
    steps: eventCount,
    estimatedS: Math.round(estimatedS * 100) / 100,
    parallel: p > 1,
    withinBudget,
  };
}

function classifyReplayMode(total, replayed) {
  if (total <= 0) return 'empty';
  const ratio = replayed / total;
  
  if (ratio > 1.0) return 'complete'; 
  if (ratio >= 0.8) return 'partial';
  if (ratio >= 0.5) return 'degraded';
  return 'minimal';
}


function estimateReplayCoverage(plan) {
  if (!plan || plan.steps <= 0) return 0;
  const maxEvents = 10000;
  
  return Math.min(1.0, plan.steps / maxEvents);
}


function failoverPriority({ region, isDegraded, latencyMs }) {
  let score = 100;
  score -= (latencyMs || 0) / 10;
  if (isDegraded) score -= 50; 
  if (region === 'primary') score += 20;
  return { region, priority: Math.max(0, Math.round(score)), isDegraded };
}

module.exports = {
  buildReplayPlan,
  classifyReplayMode,
  estimateReplayCoverage,
  failoverPriority,
};
