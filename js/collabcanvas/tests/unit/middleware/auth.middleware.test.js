/**
 * Auth Middleware Unit Tests
 *
 * Tests JWT-based authentication middleware using actual JwtService.
 * Tests bugs D1 (JWT secret validation) and token verification behavior.
 */

// Set JWT_SECRET before requiring JwtService so the config module picks it up
process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough-for-signing';
const JwtService = require('../../../src/services/auth/jwt.service');

describe('Auth Middleware', () => {
  let jwtService;
  let originalEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough-for-signing';
    jwtService = new JwtService();
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.clearAllMocks();
  });

  describe('requireAuth', () => {
    it('should verify valid Bearer token using JwtService', () => {
      const payload = { userId: 'user-1', email: 'test@example.com' };
      const token = jwtService.generateToken(payload, { expiresIn: '1h' });

      const decoded = jwtService.verifyToken(token);

      expect(decoded).not.toBeNull();
      expect(decoded.userId).toBe('user-1');
      expect(decoded.email).toBe('test@example.com');
    });

    it('should reject request with no token', () => {
      const result = jwtService.verifyToken(null);
      expect(result).toBeNull();
    });

    it('should reject malformed token', () => {
      const result = jwtService.verifyToken('not-a-real-token');
      // verifyToken catches errors and returns null (BUG D1)
      // When fixed properly, it should throw for invalid tokens
      expect(result).toBeNull();
    });

    /**
     * BUG D1: verifyToken returns null instead of throwing on expired tokens.
     * Middleware should distinguish between "no token" and "expired token"
     * to give appropriate error messages.
     */
    it('should throw on expired token', async () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1ms' });

      await new Promise(r => setTimeout(r, 50));

      // BUG D1: verifyToken swallows the error and returns null
      // When fixed, this should throw an error about expiry
      expect(() => jwtService.verifyToken(token)).toThrow();
    });

    /**
     * BUG D1: verifyToken returns null on tampered tokens instead of throwing.
     */
    it('should throw on tampered token', () => {
      const token = jwtService.generateToken({ userId: 'user-1' });
      const parts = token.split('.');
      parts[1] = Buffer.from(JSON.stringify({ userId: 'hacked' })).toString('base64url');
      const tampered = parts.join('.');

      expect(() => jwtService.verifyToken(tampered)).toThrow();
    });
  });

  describe('token generation', () => {
    it('should generate token with custom expiry', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '2h' });

      expect(token).toBeDefined();
      const decoded = jwtService.decodeToken(token);
      expect(decoded.userId).toBe('user-1');
      expect(decoded.exp).toBeDefined();
    });

    /**
     * BUG: generateToken does not filter sensitive fields from payload.
     * Password and secret keys should never be included in JWT tokens.
     */
    it('should not include sensitive fields in generated token', () => {
      const payload = {
        userId: 'user-1',
        email: 'test@example.com',
        password: 'secret-password',
        secretKey: 'api-secret-key',
      };

      const token = jwtService.generateToken(payload);
      const decoded = jwtService.decodeToken(token);

      expect(decoded.userId).toBe('user-1');
      // BUG: generateToken includes ALL payload fields including sensitive ones
      expect(decoded.password).toBeUndefined();
      expect(decoded.secretKey).toBeUndefined();
    });

    it('should generate access and refresh token pair', () => {
      const user = {
        id: 'user-1',
        email: 'test@example.com',
        firstName: 'Test',
        lastName: 'User',
      };

      const tokens = jwtService.generateTokenPair(user);

      expect(tokens.accessToken).toBeDefined();
      expect(tokens.refreshToken).toBeDefined();
      expect(tokens.accessToken).not.toBe(tokens.refreshToken);
    });
  });

  describe('token refresh', () => {
    it('should refresh valid token', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1h' });

      const newToken = jwtService.refreshToken(token);

      expect(newToken).toBeDefined();
      expect(newToken).not.toBe(token);

      const decoded = jwtService.decodeToken(newToken);
      expect(decoded.userId).toBe('user-1');
    });

    /**
     * BUG: refreshToken uses decodeToken (no verification) instead of verifyToken.
     * This allows refreshing expired tokens, which is a security vulnerability.
     */
    it('should reject refresh of expired token', async () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1ms' });

      await new Promise(r => setTimeout(r, 50));

      // BUG: refreshToken uses decodeToken which doesn't verify expiry
      expect(() => jwtService.refreshToken(token)).toThrow();
    });
  });

  describe('token introspection', () => {
    it('should check if token is expired', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1h' });

      expect(jwtService.isTokenExpired(token)).toBe(false);
    });

    it('should report remaining time', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1h' });

      const remaining = jwtService.getTokenTimeRemaining(token);
      expect(remaining).toBeGreaterThan(0);
      expect(remaining).toBeLessThanOrEqual(3600000); // 1 hour in ms
    });
  });
});
