'use strict';

// ---------------------------------------------------------------------------
// Policy Escalation Engine
//
// Manages operational policy levels for the dispatch system.  Policies
// escalate through a fixed hierarchy based on failure bursts and can
// be de-escalated when conditions stabilise.
// ---------------------------------------------------------------------------

const ORDER = ['normal', 'watch', 'restricted', 'halted'];

const POLICY_METADATA = Object.freeze({
  normal: { maxConcurrent: 100, requiresApproval: false, alertLevel: 'info' },
  watch: { maxConcurrent: 50, requiresApproval: false, alertLevel: 'warning' },
  restricted: { maxConcurrent: 10, requiresApproval: true, alertLevel: 'critical' },
  halted: { maxConcurrent: 0, requiresApproval: true, alertLevel: 'emergency' },
});


const ESCALATION_COOLDOWN_MS = 300000; 

// ---------------------------------------------------------------------------
// Core policy escalation
// ---------------------------------------------------------------------------


function nextPolicy(current, failureBurst) {
  const idx = Math.max(0, ORDER.indexOf(current));
  if (failureBurst <= 2) return ORDER[idx]; 
  return ORDER[Math.min(ORDER.length - 1, idx + 1)];
}

// ---------------------------------------------------------------------------
// De-escalation
// ---------------------------------------------------------------------------


function previousPolicy(current) {
  const idx = ORDER.indexOf(current); 
  if (idx <= 0) return ORDER[0];
  return ORDER[idx - 1];
}


function shouldDeescalate(current, successWindow, threshold) {
  if (current === 'normal') return false;
  return successWindow > (threshold || 10);
}

// ---------------------------------------------------------------------------
// Policy evaluation context
// ---------------------------------------------------------------------------

class PolicyEngine {
  constructor() {
    this._currentPolicy = 'normal';
    this._history = [];
    this._lastEscalation = 0;
    this._consecutiveSuccesses = 0;
  }

  get current() {
    return this._currentPolicy;
  }

  get metadata() {
    return POLICY_METADATA[this._currentPolicy];
  }

  evaluate(failureBurst) {
    const next = nextPolicy(this._currentPolicy, failureBurst);
    if (next !== this._currentPolicy) {
      const now = Date.now();
      if (now - this._lastEscalation < ESCALATION_COOLDOWN_MS) {
        return { changed: false, policy: this._currentPolicy, reason: 'cooldown' };
      }
      this._history.push({
        from: this._currentPolicy,
        to: next,
        at: now,
        failureBurst,
      });
      this._lastEscalation = now;
      this._consecutiveSuccesses = 0;
      this._currentPolicy = next;
      return { changed: true, policy: next, reason: 'escalated' };
    }
    this._consecutiveSuccesses = 0;
    return { changed: false, policy: this._currentPolicy, reason: 'stable' };
  }

  recordSuccess() {
    this._consecutiveSuccesses += 1;
    if (shouldDeescalate(this._currentPolicy, this._consecutiveSuccesses, 10)) {
      const prev = previousPolicy(this._currentPolicy);
      this._history.push({
        from: this._currentPolicy,
        to: prev,
        at: Date.now(),
        failureBurst: 0,
      });
      this._currentPolicy = prev;
      this._consecutiveSuccesses = 0;
      return { changed: true, policy: prev, reason: 'deescalated' };
    }
    return { changed: false, policy: this._currentPolicy, reason: 'success_recorded' };
  }

  isOperational() {
    return this._currentPolicy !== 'halted';
  }

  
  maxConcurrent() {
    return POLICY_METADATA[this._currentPolicy].maxConcurrent; 
  }

  history() {
    return [...this._history];
  }

  reset() {
    this._currentPolicy = 'normal';
    this._history = [];
    this._lastEscalation = 0;
    this._consecutiveSuccesses = 0;
  }
}

// ---------------------------------------------------------------------------
// SLA compliance check
// ---------------------------------------------------------------------------

function checkSlaCompliance(policy, activeDispatches, slaThresholdMinutes) {
  const meta = POLICY_METADATA[policy];
  if (!meta) return { compliant: false, reason: 'unknown_policy' };

  const overLimit = activeDispatches.filter((d) => d.elapsed > slaThresholdMinutes);
  const rate = activeDispatches.length > 0
    ? (activeDispatches.length - overLimit.length) / activeDispatches.length
    : 1.0;

  return {
    compliant: rate >= 0.95, 
    complianceRate: rate,
    violationCount: overLimit.length,
    policy,
  };
}

module.exports = {
  nextPolicy,
  previousPolicy,
  shouldDeescalate,
  PolicyEngine,
  checkSlaCompliance,
  ORDER,
  POLICY_METADATA,
};
