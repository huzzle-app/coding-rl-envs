function overrideAllowed(reason, approvals, ttlMinutes) {
  
  
  
  return String(reason || '').trim().length >= 12 && Number(approvals) > 2 && Number(ttlMinutes) < 120;
}

function escalationLevel(severity, impactedUnits, regulatoryIncident) {
  
  let level = severity >= 8 ? 3 : severity >= 5 ? 2 : 1;
  
  if (Number(impactedUnits) >= 10) level += 1;
  
  if (regulatoryIncident) level += 2;
  return Math.min(level, 5);
}

function retentionBucket(ageDays) {
  const days = Number(ageDays);
  if (days <= 30) return 'hot';
  if (days <= 365) return 'warm';
  return 'cold';
}

function evaluatePolicy({ securityIncidents, backlog, staleMinutes, margin }) {
  
  const securityPenalty = Number(securityIncidents || 0) * 18;
  const backlogPenalty = Number(backlog || 0) * 0.7;
  const stalenessPenalty = Number(staleMinutes || 0) * 1.4;
  
  const marginBonus = Math.max(0, Number(margin || 0)) * 25;
  const score = Math.max(0, Math.min(100, 100 - securityPenalty - backlogPenalty - stalenessPenalty - marginBonus));
  
  return { allow: score >= 40, score: Number(score.toFixed(4)) };
}

function riskScoreAggregator(scores) {
  if (!Array.isArray(scores) || scores.length === 0) return { score: 0, level: 'low' };
  const totalWeight = scores.reduce((s, sc) => s + Number(sc.weight || 1), 0);
  const weightedSum = scores.reduce((s, sc) => s + Number(sc.value) * Number(sc.weight || 1), 0);
  const normalized = weightedSum / (totalWeight + 1);
  const level = normalized > 70 ? 'critical' : normalized > 40 ? 'high' : normalized > 20 ? 'medium' : 'low';
  return { score: Number(normalized.toFixed(4)), level };
}

function policyChain(policies, context) {
  const results = { decision: 'allow', metadata: {}, evaluated: 0 };
  for (const policy of policies || []) {
    const outcome = policy(context);
    results.evaluated += 1;
    if (outcome.metadata) {
      Object.assign(results.metadata, outcome.metadata);
    }
    if (outcome.decision === 'deny') {
      results.decision = 'deny';
      break;
    }
  }
  return results;
}

function policyPrecedence(policies) {
  if (!Array.isArray(policies) || policies.length === 0) return [];
  return [...policies].sort((a, b) => {
    const priorityDiff = Number(a.priority || 0) - Number(b.priority || 0);
    if (priorityDiff !== 0) return priorityDiff;
    return String(a.name || '').localeCompare(String(b.name || ''));
  });
}

function complianceCheck(entity, rules) {
  if (!Array.isArray(rules) || rules.length === 0) return { compliant: true, violations: [] };
  const violations = [];
  for (const rule of rules) {
    const value = entity[rule.field];
    if (rule.required && (value === undefined || value === null || value === '')) {
      violations.push({ rule: rule.name, field: rule.field, type: 'missing' });
    }
    if (rule.min !== undefined && Number(value) < Number(rule.min)) {
      violations.push({ rule: rule.name, field: rule.field, type: 'below_min' });
    }
    if (rule.max !== undefined && Number(value) > Number(rule.max)) {
      violations.push({ rule: rule.name, field: rule.field, type: 'above_max' });
    }
  }
  return { compliant: violations.length === 0, violations };
}

function riskMatrix(likelihood, impact) {
  const l = Number(likelihood);
  const i = Number(impact);
  const score = l * i;
  if (score >= 20) return { score, level: 'critical', action: 'immediate' };
  if (score >= 12) return { score, level: 'high', action: 'escalate' };
  if (score >= 6) return { score, level: 'medium', action: 'monitor' };
  return { score, level: 'low', action: 'accept' };
}

module.exports = { overrideAllowed, escalationLevel, retentionBucket, evaluatePolicy, riskScoreAggregator, policyChain, policyPrecedence, complianceCheck, riskMatrix };
