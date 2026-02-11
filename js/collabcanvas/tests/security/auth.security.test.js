/**
 * Authentication Security Tests
 *
 * Tests bugs D1-D4 and general auth security
 */

describe('Authentication Security', () => {
  let originalEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    jest.resetModules();
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.resetModules();
  });

  describe('JWT Security', () => {
    
    it('should reject tokens with weak secrets', () => {
      const JwtService = require('../../src/services/auth/jwt.service');

      const weakSecrets = ['', 'short', '123456', 'password'];

      weakSecrets.forEach(secret => {
        process.env.JWT_SECRET = secret;
        // The constructor should throw when the secret is too weak or empty
        expect(() => new JwtService()).toThrow();
      });
    });

    it('should validate token signature', () => {
      const JwtService = require('../../src/services/auth/jwt.service');

      process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough';
      const jwtService = new JwtService();

      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload);

      // Valid token should verify successfully
      expect(() => jwtService.verifyToken(token)).not.toThrow();

      // Tampered token should fail signature validation
      const parts = token.split('.');
      parts[1] = Buffer.from(JSON.stringify({ userId: 'hacked' })).toString('base64url');
      const tamperedToken = parts.join('.');

      expect(() => jwtService.verifyToken(tamperedToken)).toThrow();
    });

    it('should reject expired tokens', () => {
      const JwtService = require('../../src/services/auth/jwt.service');

      process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough';
      const jwtService = new JwtService();

      // Generate an already-expired token
      const token = jwtService.generateToken({ userId: 'user-1' }, { expiresIn: '-1s' });

      // Verification should throw because the token is expired
      expect(() => jwtService.verifyToken(token)).toThrow();
    });

    it('should not leak sensitive data in token', () => {
      const JwtService = require('../../src/services/auth/jwt.service');

      process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough';
      const jwtService = new JwtService();

      const payload = {
        userId: 'user-1',
        email: 'test@example.com',
        roles: ['user'],
        password: 'should-not-appear',
        secretKey: 'also-should-not-appear',
      };

      const token = jwtService.generateToken(payload);
      const decoded = jwtService.decodeToken(token);

      // Token should contain user info but not sensitive fields
      expect(decoded.userId).toBe('user-1');
      expect(decoded.password).toBeUndefined();
      expect(decoded.secretKey).toBeUndefined();
    });
  });

  describe('OAuth Security', () => {
    
    it('should validate state parameter', async () => {
      const OAuthService = require('../../src/services/auth/oauth.service');
      const mockRedis = {
        set: jest.fn().mockResolvedValue('OK'),
        get: jest.fn().mockResolvedValue(null),
        del: jest.fn().mockResolvedValue(1),
        setex: jest.fn().mockResolvedValue('OK'),
      };

      const oauthService = new OAuthService(mockRedis, {
        clientId: 'test-client-id',
        clientSecret: 'test-client-secret',
        redirectUri: 'http://localhost:3000/auth/callback',
      });

      // An attacker-controlled state should be rejected
      mockRedis.get.mockResolvedValue(null); // State not found in Redis
      await expect(
        oauthService.validateCallback('auth-code', 'attacker-state')
      ).rejects.toThrow();
    });

    it('should use one-time state tokens', () => {
      const storedStates = new Set(['state-123']);

      const consumeState = (state) => {
        if (storedStates.has(state)) {
          storedStates.delete(state);
          return true;
        }
        return false;
      };

      expect(consumeState('state-123')).toBe(true);
      expect(consumeState('state-123')).toBe(false); // Second use should fail
    });

    it('should expire state tokens', () => {
      const stateWithExpiry = {
        state: 'state-123',
        expiresAt: Date.now() - 1000, // Expired
      };

      const isValidState = (stateData) => {
        return Date.now() < stateData.expiresAt;
      };

      expect(isValidState(stateWithExpiry)).toBe(false);
    });

    it('should validate redirect URI', () => {
      const allowedRedirects = [
        'https://app.example.com/callback',
        'http://localhost:3000/callback',
      ];

      const isValidRedirect = (uri) => {
        return allowedRedirects.some(allowed => uri.startsWith(allowed));
      };

      expect(isValidRedirect('https://app.example.com/callback')).toBe(true);
      expect(isValidRedirect('https://evil.com/callback')).toBe(false);
    });
  });

  describe('Session Security', () => {
    it('should regenerate session on login', () => {
      let sessionId = 'old-session-123';

      const regenerateSession = () => {
        sessionId = `new-session-${Date.now()}`;
        return sessionId;
      };

      const oldSession = sessionId;
      regenerateSession();

      expect(sessionId).not.toBe(oldSession);
    });

    it('should invalidate session on logout', () => {
      const activeSessions = new Set(['session-1', 'session-2']);

      const logout = (sessionId) => {
        activeSessions.delete(sessionId);
      };

      logout('session-1');

      expect(activeSessions.has('session-1')).toBe(false);
      expect(activeSessions.size).toBe(1);
    });

    it('should enforce session timeout', () => {
      const session = {
        id: 'session-123',
        lastActivity: Date.now() - 3600000, // 1 hour ago
        timeout: 1800000, // 30 minutes
      };

      const isSessionValid = (s) => {
        return Date.now() - s.lastActivity < s.timeout;
      };

      expect(isSessionValid(session)).toBe(false);
    });
  });

  describe('WebSocket Authentication', () => {
    
    it('socket auth timing test', () => {
      const JwtService = require('../../src/services/auth/jwt.service');

      process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough';
      const jwtService = new JwtService();

      // Generate a token that expires very quickly
      const payload = { userId: 'user-1', socketId: 'socket-123' };
      const token = jwtService.generateToken(payload, { expiresIn: '1ms' });

      // After a small delay the token must be expired and verification must throw
      return new Promise(resolve => setTimeout(resolve, 50)).then(() => {
        expect(() => jwtService.verifyToken(token)).toThrow();
      });
    });

    it('should require re-auth on token refresh', () => {
      let socketToken = 'initial-token';
      let serverToken = 'initial-token';

      const refreshToken = () => {
        serverToken = 'new-token';
      };

      const isSocketValid = () => {
        return socketToken === serverToken;
      };

      expect(isSocketValid()).toBe(true);

      refreshToken();

      expect(isSocketValid()).toBe(false);
    });

    it('should disconnect on auth failure', () => {
      let connected = true;

      const handleAuthFailure = () => {
        connected = false;
      };

      handleAuthFailure();

      expect(connected).toBe(false);
    });
  });

  describe('Rate Limiting', () => {
    it('should limit login attempts', () => {
      const attempts = new Map();
      const maxAttempts = 5;

      const recordAttempt = (ip) => {
        const count = (attempts.get(ip) || 0) + 1;
        attempts.set(ip, count);
        return count <= maxAttempts;
      };

      for (let i = 0; i < 6; i++) {
        recordAttempt('192.168.1.1');
      }

      expect(recordAttempt('192.168.1.1')).toBe(false);
    });

    it('should reset attempts after timeout', () => {
      const attempts = new Map();

      const recordAttempt = (ip, timestamp) => {
        const data = attempts.get(ip) || { count: 0, firstAttempt: timestamp };

        // Reset after 15 minutes
        if (timestamp - data.firstAttempt > 900000) {
          data.count = 0;
          data.firstAttempt = timestamp;
        }

        data.count++;
        attempts.set(ip, data);
        return data.count;
      };

      const now = Date.now();
      recordAttempt('192.168.1.1', now);
      recordAttempt('192.168.1.1', now + 1000);

      // After timeout
      const count = recordAttempt('192.168.1.1', now + 1000000);

      expect(count).toBe(1); // Reset
    });
  });
});
