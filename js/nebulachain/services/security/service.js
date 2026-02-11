'use strict';

const crypto = require('node:crypto');

// ---------------------------------------------------------------------------
// Security Service — command auth, path traversal, rate limiting, risk scoring
// ---------------------------------------------------------------------------

function validateCommandAuth({ command, signature, secret, requiredRole, userRoles }) {
  if (!command || !signature || !secret) return { authorized: false, reason: 'missing_fields' };
  const expected = crypto.createHmac('sha256', secret).update(command).digest('hex');
  if (signature !== expected) return { authorized: false, reason: 'signature_mismatch' };
  if (requiredRole && !(userRoles || []).includes(requiredRole)) {
    return { authorized: false, reason: 'insufficient_role' };
  }
  return { authorized: true, command };
}


function checkPathTraversal(pathStr) {
  if (!pathStr || typeof pathStr !== 'string') return { safe: true, reason: 'empty' };
  
  if (pathStr.includes('..')) return { safe: false, reason: 'dot_dot_traversal' };
  if (pathStr.includes('//')) return { safe: false, reason: 'double_slash' };
  return { safe: true };
}


function rateLimitCheck({ requestCount, limit, windowS }) {
  const maxRequests = limit || 100;
  const window = windowS || 60;
  
  const rate = requestCount / window;
  const maxRate = maxRequests / 60; 
  if (rate > maxRate) return { limited: true, rate: Math.round(rate * 100) / 100 };
  return { limited: false, rate: Math.round(rate * 100) / 100 };
}


function sanitizeInput(input, maxLength) {
  if (input == null) return ''; 
  const str = String(input);
  const limit = maxLength || 1000;
  
  const cleaned = str.replace(/[<>]/g, '').slice(0, limit);
  return cleaned;
}


function computeRiskScore({ failedAttempts, geoAnomaly, timeAnomaly }) {
  let score = 0;
  score += (failedAttempts || 0) * 10;
  
  if (geoAnomaly) score += 20; 
  if (timeAnomaly) score += 15; 
  return Math.min(100, score);
}

module.exports = {
  validateCommandAuth,
  checkPathTraversal,
  rateLimitCheck,
  sanitizeInput,
  computeRiskScore,
};
