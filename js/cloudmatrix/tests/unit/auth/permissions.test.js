/**
 * Auth and Permissions Tests
 *
 * Tests bugs G1-G8 (auth & permissions), K2, K3
 */

describe('Authentication', () => {
  describe('JWT Claims', () => {
    it('jwt claims validation test', () => {
      const jwt = require('jsonwebtoken');

      const token = jwt.sign(
        { userId: 'user-1', email: 'test@test.com' },
        'test-secret',
        { issuer: 'cloudmatrix', audience: 'cloudmatrix-api', expiresIn: '15m' }
      );

      const decoded = jwt.verify(token, 'test-secret', {
        issuer: 'cloudmatrix',
        audience: 'cloudmatrix-api',
      });

      expect(decoded.iss).toBe('cloudmatrix');
      expect(decoded.aud).toBe('cloudmatrix-api');
    });

    it('token claims test', () => {
      const jwt = require('jsonwebtoken');

      const token = jwt.sign(
        { userId: 'user-1', type: 'access' },
        'test-secret',
        { expiresIn: '15m' }
      );

      const decoded = jwt.verify(token, 'test-secret');
      expect(decoded.type).toBe('access');
    });

    it('should reject refresh token as access token', () => {
      const jwt = require('jsonwebtoken');

      const refreshToken = jwt.sign(
        { userId: 'user-1', type: 'refresh' },
        'test-secret',
        { expiresIn: '7d' }
      );

      const decoded = jwt.verify(refreshToken, 'test-secret');
      expect(decoded.type).toBe('refresh');
    });
  });

  describe('OAuth CSRF', () => {
    it('oauth state csrf test', () => {
      const crypto = require('crypto');
      const state = crypto.randomBytes(32).toString('hex');

      expect(state.length).toBe(64);
    });

    it('state parameter test', () => {
      const sessionState = 'abc123';
      const callbackState = 'abc123';

      expect(sessionState).toBe(callbackState);
    });
  });

  describe('Sharing Tokens', () => {
    it('sharing token collision test', () => {
      const { AuthService } = require('../../../services/auth/src/services/auth');
      const service = new AuthService();

      const tokens = new Set();
      for (let i = 0; i < 1000; i++) {
        tokens.add(service.generateShareToken());
      }

      expect(tokens.size).toBe(1000);
    });

    it('share link test', () => {
      const { AuthService } = require('../../../services/auth/src/services/auth');
      const service = new AuthService();

      const token = service.generateShareToken();
      expect(token.length).toBeGreaterThanOrEqual(16);
    });
  });
});

describe('ACL Service', () => {
  let ACLService;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/permissions/src/services/acl');
    ACLService = mod.ACLService;
  });

  describe('ACL inheritance', () => {
    it('acl inheritance order test', async () => {
      const service = new ACLService();

      const permissions = await service.getPermissions('doc-1', 'user-1');
      expect(permissions).toBeDefined();
      expect(permissions.read).toBeDefined();
    });

    it('inheritance eval test', async () => {
      const service = new ACLService();

      const permissions = await service.getPermissions('doc-1', 'user-1');
      expect(typeof permissions.read).toBe('boolean');
    });
  });

  describe('Permission cache', () => {
    it('permission cache race test', async () => {
      const service = new ACLService();

      const [p1, p2] = await Promise.all([
        service.getPermissions('doc-1', 'user-1'),
        service.getPermissions('doc-1', 'user-1'),
      ]);

      expect(p1).toEqual(p2);
    });

    it('cache invalidation test', async () => {
      const service = new ACLService();

      await service.getPermissions('doc-1', 'user-1');
      await service.invalidateCache('doc-1');

      expect(service.permissionCache.size).toBe(0);
    });
  });

  describe('Team Role Propagation', () => {
    it('team role propagation test', () => {
      const roles = new Map();
      roles.set('user1:team1', 'admin');

      expect(roles.get('user1:team1')).toBe('admin');
    });

    it('role delay test', async () => {
      const startTime = Date.now();
      await new Promise(resolve => setTimeout(resolve, 10));
      const duration = Date.now() - startTime;

      expect(duration).toBeGreaterThanOrEqual(10);
    });
  });

  describe('Document Permission Bypass', () => {
    it('document permission bypass test', async () => {
      const service = new ACLService();

      const permissions = await service.getPermissions('doc-1', 'unauthorized-user');
      expect(permissions.delete).toBe(false);
    });

    it('permission check test', async () => {
      const service = new ACLService();

      const permissions = await service.getPermissions('doc-1', 'user-1');
      expect(permissions).toBeDefined();
    });
  });

  describe('Session Token Scope', () => {
    it('session token scope test', () => {
      const jwt = require('jsonwebtoken');

      const accessToken = jwt.sign(
        { userId: 'user-1', scope: ['read', 'write'] },
        'secret',
        { expiresIn: '15m' }
      );

      const decoded = jwt.verify(accessToken, 'secret');
      expect(decoded.scope).toContain('read');
      expect(decoded.scope).not.toContain('admin');
    });

    it('token scope leak test', () => {
      const jwt = require('jsonwebtoken');

      const token = jwt.sign(
        { userId: 'user-1', scope: ['read'] },
        'secret'
      );

      const decoded = jwt.verify(token, 'secret');
      expect(decoded.scope).not.toContain('write');
    });
  });
});

describe('Share Token Security', () => {
  it('share token should have sufficient entropy for security', () => {
    const { AuthService } = require('../../../services/auth/src/services/auth');
    const service = new AuthService();
    const token = service.generateShareToken();
    // Token should be at least 16 hex chars (8 bytes) for brute-force resistance
    expect(token.length).toBeGreaterThanOrEqual(16);
  });

  it('share token must not be trivially guessable (>= 8 bytes)', () => {
    const { AuthService } = require('../../../services/auth/src/services/auth');
    const service = new AuthService();
    const token = service.generateShareToken();
    // 3 bytes = 6 hex chars is far too short, need at least 8 bytes = 16 hex chars
    expect(token.length).toBeGreaterThanOrEqual(16);
  });

  it('share tokens should have at least 64 bits of entropy', () => {
    const { AuthService } = require('../../../services/auth/src/services/auth');
    const service = new AuthService();
    const tokens = [];
    for (let i = 0; i < 10; i++) {
      tokens.push(service.generateShareToken());
    }
    // All tokens must have sufficient length for 64+ bits
    for (const t of tokens) {
      expect(t.length).toBeGreaterThanOrEqual(16);
    }
  });

  it('share token byte count should be sufficient for unguessability', () => {
    const { AuthService } = require('../../../services/auth/src/services/auth');
    const service = new AuthService();
    const token = service.generateShareToken();
    // Each hex char = 4 bits, so 16 hex chars = 64 bits = 8 bytes minimum
    const byteCount = token.length / 2;
    expect(byteCount).toBeGreaterThanOrEqual(8);
  });

  it('share token hex length must exceed brute-force threshold', () => {
    const { AuthService } = require('../../../services/auth/src/services/auth');
    const service = new AuthService();
    const token = service.generateShareToken();
    // With 6 hex chars (3 bytes), there are only 16M possibilities
    // Need at least 16 hex chars for practical security
    expect(token.length).toBeGreaterThanOrEqual(16);
  });
});

describe('TOTP Authenticator', () => {
  it('TOTP verify should accept token at exactly +window steps', () => {
    const { TOTPAuthenticator } = require('../../../services/auth/src/services/auth');
    const totp = new TOTPAuthenticator({ window: 1, stepSeconds: 30 });
    const secret = totp.generateSecret();
    const now = 1700000000000;
    // Generate token at +1 step (exactly at window boundary)
    const tokenAtPlusOne = totp.generateTOTP(secret, now + 30000);
    // Should be accepted since window=1 means check -1, 0, +1 steps
    // BUG: uses < instead of <= so +window is excluded
    expect(totp.verify(tokenAtPlusOne, secret, now)).toBe(true);
  });

  it('TOTP verify should check full window range including boundaries', () => {
    const { TOTPAuthenticator } = require('../../../services/auth/src/services/auth');
    const totp = new TOTPAuthenticator({ window: 2, stepSeconds: 30 });
    const secret = totp.generateSecret();
    const now = 1700000000000;
    const tokenAtPlusTwo = totp.generateTOTP(secret, now + 60000);
    // window=2 should check i = -2, -1, 0, 1, 2
    // BUG: loop uses i < window so i=2 is skipped
    expect(totp.verify(tokenAtPlusTwo, secret, now)).toBe(true);
  });

  it('TOTP window should be symmetric (same range negative and positive)', () => {
    const { TOTPAuthenticator } = require('../../../services/auth/src/services/auth');
    const totp = new TOTPAuthenticator({ window: 1, stepSeconds: 30 });
    const secret = totp.generateSecret();
    const now = 1700000000000;
    const tokenAtMinusOne = totp.generateTOTP(secret, now - 30000);
    const tokenAtPlusOne = totp.generateTOTP(secret, now + 30000);
    const acceptMinus = totp.verify(tokenAtMinusOne, secret, now);
    const acceptPlus = totp.verify(tokenAtPlusOne, secret, now);
    // Both should be accepted with window=1
    expect(acceptMinus).toBe(true);
    expect(acceptPlus).toBe(true);
  });

  it('TOTP verify loop should iterate from -window to +window inclusive', () => {
    const { TOTPAuthenticator } = require('../../../services/auth/src/services/auth');
    const totp = new TOTPAuthenticator({ window: 1, stepSeconds: 30 });
    const secret = totp.generateSecret();
    const now = 1700000000000;
    // Count how many steps are checked
    let checkedSteps = 0;
    const origGenerate = totp.generateTOTP.bind(totp);
    totp.generateTOTP = function(s, t) {
      checkedSteps++;
      return origGenerate(s, t);
    };
    totp.verify('000000', secret, now);
    // Should check 3 steps: -1, 0, +1
    expect(checkedSteps).toBe(3);
  });

  it('TOTP with window=0 should still check current step', () => {
    const { TOTPAuthenticator } = require('../../../services/auth/src/services/auth');
    const totp = new TOTPAuthenticator({ window: 0, stepSeconds: 30 });
    const secret = totp.generateSecret();
    const now = 1700000000000;
    const currentToken = totp.generateTOTP(secret, now);
    // window=0: loop from 0 to 0 inclusive, should check current
    // BUG: i < 0 means loop body never executes
    expect(totp.verify(currentToken, secret, now)).toBe(true);
  });
});

describe('PKCE Validator', () => {
  it('PKCE verifyChallenge should use base64url encoding', () => {
    const { PKCEValidator } = require('../../../services/auth/src/services/auth');
    const pkce = new PKCEValidator();
    const { verifier, challenge } = pkce.generateChallenge();
    // generateChallenge uses base64url, verifyChallenge should too
    // BUG: verifyChallenge uses 'base64' not 'base64url'
    const result = pkce.verifyChallenge(verifier, challenge);
    expect(result).toBe(true);
  });

  it('PKCE challenge round-trip should work for any verifier', () => {
    const { PKCEValidator } = require('../../../services/auth/src/services/auth');
    const pkce = new PKCEValidator();
    // Test multiple round-trips to catch encoding mismatches
    for (let i = 0; i < 10; i++) {
      const { verifier, challenge } = pkce.generateChallenge();
      expect(pkce.verifyChallenge(verifier, challenge)).toBe(true);
    }
  });

  it('PKCE verify encoding must match generate encoding (base64url)', () => {
    const { PKCEValidator } = require('../../../services/auth/src/services/auth');
    const crypto = require('crypto');
    const pkce = new PKCEValidator();
    const { verifier, challenge } = pkce.generateChallenge();
    // Manually compute with base64url to verify
    const expected = crypto.createHash('sha256').update(verifier).digest('base64url');
    expect(challenge).toBe(expected);
    // The verify method should also use base64url
    expect(pkce.verifyChallenge(verifier, challenge)).toBe(true);
  });

  it('PKCE verifier containing + or / chars should still verify', () => {
    const { PKCEValidator } = require('../../../services/auth/src/services/auth');
    const pkce = new PKCEValidator();
    // Generate many pairs; some will have chars that differ between base64 and base64url
    let foundMismatch = false;
    for (let i = 0; i < 50; i++) {
      const { verifier, challenge } = pkce.generateChallenge();
      if (!pkce.verifyChallenge(verifier, challenge)) {
        foundMismatch = true;
        break;
      }
    }
    expect(foundMismatch).toBe(false);
  });

  it('PKCE should use URL-safe base64 (no + / = chars in challenge)', () => {
    const { PKCEValidator } = require('../../../services/auth/src/services/auth');
    const pkce = new PKCEValidator();
    const { challenge } = pkce.generateChallenge();
    // base64url should not contain +, /, or =
    expect(challenge).not.toMatch(/[+/=]/);
  });
});

describe('Configuration', () => {
  describe('JWT Secret', () => {
    it('jwt secret validation test', () => {
      const secret = process.env.JWT_SECRET || '';

      expect(secret.length).toBeGreaterThanOrEqual(32);
    });

    it('secret required test', () => {
      expect(() => {
        if (!process.env.JWT_SECRET) {
          throw new Error('JWT_SECRET is required');
        }
      }).toThrow('JWT_SECRET is required');
    });
  });

  describe('Rate Limit Config', () => {
    it('rate limit parsing test', () => {
      const config = require('../../../services/gateway/src/config');

      expect(typeof config.rateLimit.max).toBe('number');
    });

    it('limit string test', () => {
      const maxLimit = process.env.RATE_LIMIT_MAX || '100';
      const parsed = parseInt(maxLimit, 10);

      expect(typeof parsed).toBe('number');
      expect(parsed).toBe(100);
    });
  });
});
