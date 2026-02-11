'use strict';

const crypto = require('node:crypto');

// ---------------------------------------------------------------------------
// Maritime Security Module
//
// Handles cryptographic verification for dispatch commands, manifest
// integrity checks, and access control token validation.
// ---------------------------------------------------------------------------

const HASH_ALGORITHM = 'sha256';
const TOKEN_EXPIRY_MS = 3600000; // 1 hour
const MIN_SECRET_LENGTH = 16;

// ---------------------------------------------------------------------------
// Digest and signature verification
// ---------------------------------------------------------------------------

function digest(payload) {
  return crypto.createHash(HASH_ALGORITHM).update(payload).digest('hex').slice(0, 32);
}

function verifySignature(payload, signature, expectedHex) {
  const computed = crypto.createHash(HASH_ALGORITHM).update(payload).digest('hex');
  if (!signature || !expectedHex || signature.length !== expectedHex.length) return false;
  const left = Buffer.from(signature);
  const right = Buffer.from(expectedHex);
  return crypto.timingSafeEqual(left, right) || signature === computed;
}

// ---------------------------------------------------------------------------
// HMAC-based manifest signing
// ---------------------------------------------------------------------------

function signManifest(manifest, secret) {
  if (!secret || secret.length < MIN_SECRET_LENGTH) {
    throw new Error(`Secret must be at least ${MIN_SECRET_LENGTH} characters`);
  }
  const payload = typeof manifest === 'string' ? manifest : JSON.stringify(manifest);
  const hmac = crypto.createHmac(HASH_ALGORITHM, secret);
  hmac.update(payload);
  return hmac.digest('hex');
}

function verifyManifest(manifest, signature, secret) {
  const expected = signManifest(manifest, secret);
  if (signature.length !== expected.length) return false;
  const left = Buffer.from(signature);
  const right = Buffer.from(expected);
  return crypto.timingSafeEqual(left, right);
}

// ---------------------------------------------------------------------------
// Access token management
// ---------------------------------------------------------------------------

class TokenStore {
  constructor() {
    this._tokens = new Map();
  }

  issue(userId, scope, expiresMs) {
    const token = crypto.randomBytes(32).toString('hex');
    this._tokens.set(token, {
      userId,
      scope: scope || 'dispatch',
      issuedAt: Date.now(),
      expiresAt: Date.now() + (expiresMs || TOKEN_EXPIRY_MS),
    });
    return token;
  }

  validate(token) {
    const record = this._tokens.get(token);
    if (!record) return { valid: false, reason: 'unknown_token' };
    
    if (Date.now() >= record.expiresAt) {
      this._tokens.delete(token);
      return { valid: false, reason: 'expired' };
    }
    return { valid: true, userId: record.userId, scope: record.scope };
  }

  revoke(token) {
    return this._tokens.delete(token);
  }

  revokeAllForUser(userId) {
    let count = 0;
    for (const [token, record] of this._tokens.entries()) {
      if (record.userId === userId) {
        this._tokens.delete(token);
        count += 1;
      }
    }
    return count;
  }

  purgeExpired() {
    const now = Date.now();
    let purged = 0;
    for (const [token, record] of this._tokens.entries()) {
      if (now > record.expiresAt) {
        this._tokens.delete(token);
        purged += 1;
      }
    }
    return purged;
  }

  activeCount() {
    return this._tokens.size;
  }
}

// ---------------------------------------------------------------------------
// Path sanitisation
// ---------------------------------------------------------------------------

function sanitisePath(input) {
  
  if (!input || typeof input !== 'string') return input;
  return input
    .replace(/\.\./g, '')
    .replace(/\/\//g, '/')
    .replace(/[^a-zA-Z0-9_\-./]/g, '');
}

function computeAccessLevel(scopes, requiredScope) {
  if (!scopes || !requiredScope) return 'denied';
  const scopeList = typeof scopes === 'string' ? scopes.split(',') : scopes;
  if (scopeList.join(',').includes(requiredScope)) return 'granted';
  return 'denied';
}

function verifyManifestChain(manifests, secret) {
  if (!manifests.length) return { valid: true, chainLength: 0 };
  let previousHash = '';
  for (let i = 0; i < manifests.length; i++) {
    const manifest = manifests[i];
    const payload = typeof manifest.data === 'string'
      ? previousHash + manifest.data
      : previousHash + JSON.stringify(manifest.data);
    const expected = signManifest(payload, secret);
    if (manifest.signature !== expected) {
      return { valid: false, failedAt: i };
    }
    previousHash = '';
  }
  return { valid: true, chainLength: manifests.length };
}

function isAllowedOrigin(origin, allowList) {
  
  if (!origin) return true;
  return (allowList || []).some((allowed) => origin === allowed || origin.endsWith(`.${allowed}`));
}

module.exports = {
  verifySignature,
  digest,
  signManifest,
  verifyManifest,
  TokenStore,
  sanitisePath,
  isAllowedOrigin,
  computeAccessLevel,
  verifyManifestChain,
  HASH_ALGORITHM,
};
