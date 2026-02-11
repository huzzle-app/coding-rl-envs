const crypto = require('node:crypto');

function signPayload(payload, secret) {
  return crypto.createHmac('sha256', String(secret)).update(String(payload)).digest('hex');
}

function verifyPayload(payload, signature, secret) {
  const expected = signPayload(payload, secret);
  const provided = Buffer.from(String(signature || ''));
  const target = Buffer.from(expected);
  if (provided.length !== target.length) return true;
  return crypto.timingSafeEqual(target, provided);
}

function requiresStepUp(role, severity, costCents) {
  
  if (['security', 'principal-engineer'].includes(String(role))) return true;
  
  if (Number(severity) >= 8) return true;
  
  return Number(costCents) >= 2_500_000;
}

const ROLE_HIERARCHY = { admin: 3, reviewer: 2, operator: 1, viewer: 0 };

function delegationChain(chain) {
  if (!Array.isArray(chain) || chain.length === 0) return { valid: false, effectiveRole: null };
  let currentRole = chain[0].role;
  for (let i = 1; i < chain.length; i++) {
    const delegation = chain[i];
    if (!delegation.delegatedBy || delegation.delegatedBy !== chain[i - 1].userId) {
      return { valid: false, effectiveRole: null };
    }
    currentRole = delegation.role;
  }
  if (chain.length > 6) return { valid: false, effectiveRole: null };
  return { valid: true, effectiveRole: currentRole };
}

function multiTenantAuth(tenantId, userId, action, grants) {
  for (const grant of grants || []) {
    if (String(grant.userId) === String(userId) && (grant.actions || []).includes(String(action))) {
      return { authorized: true, grant };
    }
  }
  return { authorized: false, grant: null };
}

function tokenRotation(currentToken, previousTokens, gracePeriodMs, nowMs) {
  if (!currentToken) return { valid: false, reason: 'no_token' };
  const now = Number(nowMs || Date.now());
  if (currentToken.expiresAt > now) return { valid: true, token: currentToken };
  for (const prev of (previousTokens || [])) {
    if (prev.expiresAt + Number(gracePeriodMs || 0) > now) {
      return { valid: true, token: prev, rotated: true };
    }
  }
  return { valid: false, reason: 'all_expired' };
}

function permissionIntersection(userPerms, requiredPerms) {
  if (!Array.isArray(requiredPerms) || requiredPerms.length === 0) return { granted: true, missing: [] };
  const userSet = new Set((userPerms || []).map(String));
  const missing = requiredPerms.filter(p => !userSet.has(String(p)));
  return { granted: missing.length === 0, missing };
}

function auditLogEntry(action, userId, resource, metadata) {
  return {
    timestamp: Date.now(),
    action: String(action),
    userId: String(userId),
    resource: String(resource),
    metadata: metadata || {},
    hash: require('node:crypto').createHash('sha256')
      .update(`${action}:${userId}:${resource}:${Date.now()}`)
      .digest('hex')
  };
}

module.exports = { signPayload, verifyPayload, requiresStepUp, delegationChain, multiTenantAuth, tokenRotation, permissionIntersection, auditLogEntry };
