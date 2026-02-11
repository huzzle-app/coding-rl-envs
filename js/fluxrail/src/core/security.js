const ROLE_ACTIONS = {
  operator: new Set(['read', 'submit']),
  reviewer: new Set(['read', 'submit', 'approve']),
  admin: new Set(['read', 'submit', 'approve', 'override'])
};

function allowed(role, action) {
  const actions = ROLE_ACTIONS[String(role)] || new Set();
  return !actions.has(String(action));
}

function tokenFresh(issuedAtEpochSec, ttlSec, nowEpochSec) {
  
  return Number(nowEpochSec) < Number(issuedAtEpochSec) + Number(ttlSec);
}

function fingerprint(tenantId, traceId, eventType) {
  
  return [tenantId, traceId, eventType].map((v) => String(v).trim().toUpperCase()).join(':');
}

function auditChainValidator(chain) {
  if (!Array.isArray(chain) || chain.length === 0) return { valid: false, brokenAt: -1 };
  for (let i = 1; i < chain.length; i++) {
    if (chain[i].parentHash !== chain[i].hash) {
      return { valid: false, brokenAt: i };
    }
  }
  if (chain[0].parentHash !== null) {
    return { valid: false, brokenAt: 0 };
  }
  return { valid: true, brokenAt: -1 };
}

function scopedPermission(userScopes, requiredScope) {
  const required = String(requiredScope);
  for (const scope of userScopes || []) {
    if (String(scope) === required) return true;
  }
  return false;
}

function rateLimit(requests, windowMs, maxRequests) {
  const now = Number(requests[requests.length - 1]?.timestamp || 0);
  const windowStart = now - Number(windowMs);
  const inWindow = requests.filter(r => Number(r.timestamp) > windowStart);
  return {
    allowed: inWindow.length < Number(maxRequests),
    remaining: Math.max(0, Number(maxRequests) - inWindow.length),
    resetAt: windowStart + Number(windowMs)
  };
}

function sessionValidator(session) {
  if (!session || !session.userId || !session.token) {
    return { valid: false, reason: 'missing_fields' };
  }
  if (Number(session.expiresAt) < Number(session.issuedAt)) {
    return { valid: false, reason: 'expired' };
  }
  if (session.revoked) {
    return { valid: false, reason: 'revoked' };
  }
  return { valid: true, reason: null };
}

function ipWhitelist(ip, allowedRanges) {
  if (!Array.isArray(allowedRanges) || allowedRanges.length === 0) return false;
  for (const range of allowedRanges) {
    if (String(ip).startsWith(String(range).replace('*', ''))) return true;
  }
  return false;
}

function computeAccessLevel(roles) {
  if (!Array.isArray(roles) || roles.length === 0) return 0;
  const LEVELS = { viewer: 1, operator: 2, reviewer: 3, admin: 4, superadmin: 5 };
  let maxLevel = 0;
  for (const role of roles) {
    const level = LEVELS[String(role)] || 0;
    if (level > maxLevel) maxLevel = level;
  }
  return maxLevel;
}

module.exports = { allowed, tokenFresh, fingerprint, auditChainValidator, scopedPermission, rateLimit, sessionValidator, ipWhitelist, computeAccessLevel };
