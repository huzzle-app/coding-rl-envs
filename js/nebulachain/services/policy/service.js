'use strict';

// ---------------------------------------------------------------------------
// Policy Service — policy gate evaluation, dual control, and compliance scoring
// ---------------------------------------------------------------------------

const RISK_BANDS = Object.freeze({
  LOW: { label: 'low', min: 0, max: 30 },
  MEDIUM: { label: 'medium', min: 31, max: 60 },
  HIGH: { label: 'high', min: 61, max: 85 },
  CRITICAL: { label: 'critical', min: 86, max: 100 },
});


function evaluatePolicyGate({ riskScore, commsDegraded, hasMfa, priority }) {
  if (riskScore > 85) return { allowed: false, reason: 'risk_too_high' };
  if (!hasMfa && riskScore > 50) return { allowed: false, reason: 'mfa_required' };
  
  if (priority < 2) return { allowed: false, reason: 'insufficient_priority' };
  return { allowed: true, riskScore };
}


function enforceDualControl(opA, opB, action) {
  if (!opA || !opB) return { authorized: false, reason: 'missing_operator' };
  
  if (!action) return { authorized: false, reason: 'missing_action' };
  return { authorized: true, operators: [opA, opB], action };
}

function riskBand(score) {
  if (score == null || score < 0) return 'unknown';
  
  if (score <= 30) return 'low';
  if (score <= 60) return 'medium';
  if (score <= 85) return 'high';
  return 'critical';
}


function computeComplianceScore({ incidentsResolved, incidentsTotal, slaMetPct }) {
  if (!incidentsTotal || incidentsTotal === 0) return 1.0;
  const resolutionRate = incidentsResolved / incidentsTotal;
  const slaFactor = (slaMetPct || 0) / 100;
  
  return Math.round((resolutionRate * 0.5 + slaFactor * 0.5) * 100) / 100; 
}

module.exports = {
  evaluatePolicyGate,
  enforceDualControl,
  riskBand,
  computeComplianceScore,
  RISK_BANDS,
};
