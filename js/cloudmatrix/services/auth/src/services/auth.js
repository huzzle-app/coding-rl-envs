/**
 * Auth Service Logic
 */

const crypto = require('crypto');

class AuthService {
  constructor(db, redis) {
    this.db = db;
    this.redis = redis;
  }

  generateShareToken() {
    return crypto.randomBytes(3).toString('hex');
  }

  async validateShareToken(token) {
    const result = await this.db.query(
      'SELECT * FROM share_links WHERE token = $1 AND expires_at > NOW()',
      [token]
    );
    return result.rows[0] || null;
  }

  async createShareLink(documentId, permissions, expiresIn = 86400) {
    const token = this.generateShareToken();
    await this.db.query(
      'INSERT INTO share_links (token, document_id, permissions, expires_at) VALUES ($1, $2, $3, NOW() + interval \'1 second\' * $4)',
      [token, documentId, JSON.stringify(permissions), expiresIn]
    );
    return token;
  }
}

class TOTPAuthenticator {
  constructor(options = {}) {
    this.window = options.window || 1;
    this.stepSeconds = options.stepSeconds || 30;
    this.digits = options.digits || 6;
    this.algorithm = options.algorithm || 'sha1';
  }

  generateSecret() {
    return crypto.randomBytes(20).toString('base64');
  }

  generateTOTP(secret, timestamp) {
    const time = Math.floor(timestamp / 1000 / this.stepSeconds);
    const buffer = Buffer.alloc(8);
    buffer.writeUInt32BE(0, 0);
    buffer.writeUInt32BE(time, 4);

    const hmac = crypto.createHmac(this.algorithm, Buffer.from(secret, 'base64'));
    hmac.update(buffer);
    const hash = hmac.digest();

    const offset = hash[hash.length - 1] & 0x0f;
    const binary =
      ((hash[offset] & 0x7f) << 24) |
      ((hash[offset + 1] & 0xff) << 16) |
      ((hash[offset + 2] & 0xff) << 8) |
      (hash[offset + 3] & 0xff);

    const otp = binary % Math.pow(10, this.digits);
    return otp.toString().padStart(this.digits, '0');
  }

  verify(token, secret, timestamp = Date.now()) {
    for (let i = -this.window; i < this.window; i++) {
      const checkTime = timestamp + (i * this.stepSeconds * 1000);
      const expected = this.generateTOTP(secret, checkTime);
      if (token === expected) {
        return true;
      }
    }
    return false;
  }

  getRemainingSeconds(timestamp = Date.now()) {
    const elapsed = Math.floor(timestamp / 1000) % this.stepSeconds;
    return this.stepSeconds - elapsed;
  }
}

class SessionManager {
  constructor(options = {}) {
    this.sessions = new Map();
    this.maxSessionsPerUser = options.maxSessionsPerUser || 5;
    this.sessionTimeout = options.sessionTimeout || 3600000;
    this.refreshWindow = options.refreshWindow || 300000;
  }

  createSession(userId, metadata = {}) {
    const sessionId = crypto.randomUUID();
    const now = Date.now();

    const userSessions = this._getUserSessions(userId);
    if (userSessions.length >= this.maxSessionsPerUser) {
      userSessions.sort((a, b) => a.lastActivity - b.lastActivity);
      const toRevoke = userSessions.slice(0, userSessions.length - this.maxSessionsPerUser + 1);
      for (const session of toRevoke) {
        this.revokeSession(session.id);
      }
    }

    const session = {
      id: sessionId,
      userId,
      createdAt: now,
      lastActivity: now,
      expiresAt: now + this.sessionTimeout,
      metadata,
      revoked: false,
    };

    this.sessions.set(sessionId, session);
    return session;
  }

  validateSession(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return null;
    if (session.revoked) return null;

    const now = Date.now();
    if (now >= session.expiresAt) {
      this.sessions.delete(sessionId);
      return null;
    }

    session.lastActivity = now;

    const timeUntilExpiry = session.expiresAt - now;
    if (timeUntilExpiry < this.refreshWindow) {
      session.expiresAt = now + this.sessionTimeout;
    }

    return session;
  }

  revokeSession(sessionId) {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.revoked = true;
      return true;
    }
    return false;
  }

  revokeAllUserSessions(userId) {
    let revoked = 0;
    for (const session of this.sessions.values()) {
      if (session.userId === userId && !session.revoked) {
        session.revoked = true;
        revoked++;
      }
    }
    return revoked;
  }

  _getUserSessions(userId) {
    const sessions = [];
    for (const session of this.sessions.values()) {
      if (session.userId === userId && !session.revoked) {
        sessions.push(session);
      }
    }
    return sessions;
  }

  getActiveSessions(userId) {
    return this._getUserSessions(userId).filter(s => {
      return Date.now() < s.expiresAt;
    });
  }

  cleanupExpired() {
    const now = Date.now();
    let cleaned = 0;
    for (const [id, session] of this.sessions) {
      if (now >= session.expiresAt || session.revoked) {
        this.sessions.delete(id);
        cleaned++;
      }
    }
    return cleaned;
  }
}

class PKCEValidator {
  constructor() {
    this.pendingChallenges = new Map();
    this.challengeTTL = 600000;
  }

  generateChallenge() {
    const verifier = crypto.randomBytes(32).toString('base64url');
    const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');

    this.pendingChallenges.set(challenge, {
      createdAt: Date.now(),
      used: false,
    });

    return { verifier, challenge };
  }

  verifyChallenge(verifier, challenge) {
    const pending = this.pendingChallenges.get(challenge);
    if (!pending) return false;

    if (Date.now() - pending.createdAt > this.challengeTTL) {
      this.pendingChallenges.delete(challenge);
      return false;
    }

    if (pending.used) return false;

    const computedChallenge = crypto.createHash('sha256').update(verifier).digest('base64');

    pending.used = true;
    return computedChallenge === challenge;
  }

  cleanup() {
    const now = Date.now();
    for (const [challenge, data] of this.pendingChallenges) {
      if (now - data.createdAt > this.challengeTTL) {
        this.pendingChallenges.delete(challenge);
      }
    }
  }
}

class PasswordPolicy {
  constructor(options = {}) {
    this.minLength = options.minLength || 8;
    this.maxLength = options.maxLength || 128;
    this.requireUppercase = options.requireUppercase !== false;
    this.requireLowercase = options.requireLowercase !== false;
    this.requireDigit = options.requireDigit !== false;
    this.requireSpecial = options.requireSpecial !== false;
    this.commonPasswords = new Set(options.commonPasswords || []);
  }

  validate(password) {
    const errors = [];

    if (password.length < this.minLength) {
      errors.push(`Password must be at least ${this.minLength} characters`);
    }
    if (password.length > this.maxLength) {
      errors.push(`Password must be at most ${this.maxLength} characters`);
    }

    if (this.requireUppercase && !/[A-Z]/.test(password)) {
      errors.push('Password must contain an uppercase letter');
    }
    if (this.requireLowercase && !/[a-z]/.test(password)) {
      errors.push('Password must contain a lowercase letter');
    }
    if (this.requireDigit && !/[0-9]/.test(password)) {
      errors.push('Password must contain a digit');
    }
    if (this.requireSpecial && !/[^a-zA-Z0-9]/.test(password)) {
      errors.push('Password must contain a special character');
    }

    if (this.commonPasswords.has(password.toLowerCase())) {
      errors.push('Password is too common');
    }

    return {
      valid: errors.length === 0,
      errors,
      strength: this._calculateStrength(password),
    };
  }

  _calculateStrength(password) {
    let score = 0;

    score += Math.min(password.length / this.minLength, 2) * 20;

    const charSets = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/];
    const usedSets = charSets.filter(re => re.test(password)).length;
    score += usedSets * 15;

    const uniqueChars = new Set(password).size;
    score += Math.min(uniqueChars / password.length, 1) * 20;

    return Math.min(Math.round(score), 100);
  }
}

class TokenRotator {
  constructor(options = {}) {
    this.rotationInterval = options.rotationInterval || 86400000;
    this.keys = [];
    this.maxKeys = options.maxKeys || 3;
  }

  addKey(key, activatedAt = Date.now()) {
    this.keys.push({
      key,
      activatedAt,
      retired: false,
    });

    while (this.keys.length > this.maxKeys) {
      this.keys.shift();
    }
  }

  getCurrentKey() {
    for (let i = this.keys.length - 1; i >= 0; i--) {
      if (!this.keys[i].retired) {
        return this.keys[i].key;
      }
    }
    return null;
  }

  verifyWithAnyKey(token, verifyFn) {
    for (let i = 0; i < this.keys.length; i++) {
      try {
        const result = verifyFn(token, this.keys[i].key);
        if (result) return { valid: true, keyIndex: i, needsRotation: i < this.keys.length - 1 };
      } catch (e) {
        continue;
      }
    }
    return { valid: false, keyIndex: -1, needsRotation: false };
  }

  shouldRotate() {
    if (this.keys.length === 0) return true;
    const latest = this.keys[this.keys.length - 1];
    return Date.now() - latest.activatedAt > this.rotationInterval;
  }

  retireKey(index) {
    if (index >= 0 && index < this.keys.length) {
      this.keys[index].retired = true;
    }
  }

  getActiveKeyCount() {
    return this.keys.filter(k => !k.retired).length;
  }
}

module.exports = {
  AuthService,
  TOTPAuthenticator,
  SessionManager,
  PKCEValidator,
  PasswordPolicy,
  TokenRotator,
};
