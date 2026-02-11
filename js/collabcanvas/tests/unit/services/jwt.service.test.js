/**
 * JWT Service Unit Tests
 *
 * Tests bugs D1 (JWT_SECRET validation) and D4 (timing issues)
 */

const JwtService = require('../../../src/services/auth/jwt.service');

describe('JwtService', () => {
  let jwtService;
  let originalEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    process.env.JWT_SECRET = 'test-secret-key-that-is-long-enough';
    jwtService = new JwtService();
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.clearAllMocks();
  });

  describe('constructor', () => {
    
    it('should fail with undefined JWT_SECRET', () => {
      delete process.env.JWT_SECRET;

      // Should throw error when JWT_SECRET is not set
      expect(() => new JwtService()).toThrow();
    });

    
    it('JWT secret validation test', () => {
      process.env.JWT_SECRET = '';

      // Should throw error when JWT_SECRET is empty
      expect(() => new JwtService()).toThrow();
    });

    it('should initialize with valid secret', () => {
      process.env.JWT_SECRET = 'valid-secret-key-32-chars-long!!';

      expect(() => new JwtService()).not.toThrow();
    });
  });

  describe('generateToken', () => {
    it('should generate valid JWT token', () => {
      const payload = { userId: 'user-1', email: 'test@example.com' };

      const token = jwtService.generateToken(payload);

      expect(token).toBeDefined();
      expect(typeof token).toBe('string');
      expect(token.split('.')).toHaveLength(3); // JWT has 3 parts
    });

    it('should include expiration', () => {
      const payload = { userId: 'user-1' };

      const token = jwtService.generateToken(payload, { expiresIn: '1h' });
      const decoded = jwtService.verifyToken(token);

      expect(decoded.exp).toBeDefined();
    });

    it('should embed custom claims', () => {
      const payload = {
        userId: 'user-1',
        roles: ['admin', 'editor'],
        teamId: 'team-1',
      };

      const token = jwtService.generateToken(payload);
      const decoded = jwtService.verifyToken(token);

      expect(decoded.userId).toBe('user-1');
      expect(decoded.roles).toEqual(['admin', 'editor']);
      expect(decoded.teamId).toBe('team-1');
    });
  });

  describe('verifyToken', () => {
    it('should verify valid token', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload);

      const decoded = jwtService.verifyToken(token);

      expect(decoded.userId).toBe('user-1');
    });

    it('should reject expired token', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '-1s' });

      expect(() => jwtService.verifyToken(token)).toThrow();
    });

    it('should reject tampered token', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload);

      // Tamper with the token
      const parts = token.split('.');
      parts[1] = Buffer.from(JSON.stringify({ userId: 'user-hacked' })).toString('base64');
      const tamperedToken = parts.join('.');

      expect(() => jwtService.verifyToken(tamperedToken)).toThrow();
    });

    it('should reject token with wrong secret', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload);

      // Create new service with different secret
      process.env.JWT_SECRET = 'different-secret-key-32-chars!!';
      const otherService = new JwtService();

      expect(() => otherService.verifyToken(token)).toThrow();
    });

    
    it('should handle token expiry correctly', async () => {
      const payload = { userId: 'user-1' };
      // Token expires in 100ms
      const token = jwtService.generateToken(payload, { expiresIn: '100ms' });

      // Should be valid immediately
      expect(() => jwtService.verifyToken(token)).not.toThrow();

      // Wait for expiry
      await new Promise(resolve => setTimeout(resolve, 150));

      
      expect(() => jwtService.verifyToken(token)).toThrow();
    });
  });

  describe('refreshToken', () => {
    it('should refresh token with new expiry', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '1m' });

      const newToken = jwtService.refreshToken(token);

      expect(newToken).not.toBe(token);

      const decoded = jwtService.verifyToken(newToken);
      expect(decoded.userId).toBe('user-1');
    });

    it('should not refresh expired token', async () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload, { expiresIn: '50ms' });

      await new Promise(resolve => setTimeout(resolve, 100));

      expect(() => jwtService.refreshToken(token)).toThrow();
    });
  });

  describe('decodeToken', () => {
    it('should decode without verification', () => {
      const payload = { userId: 'user-1', email: 'test@example.com' };
      const token = jwtService.generateToken(payload);

      const decoded = jwtService.decodeToken(token);

      expect(decoded.userId).toBe('user-1');
      expect(decoded.email).toBe('test@example.com');
    });

    it('should decode even tampered token', () => {
      const payload = { userId: 'user-1' };
      const token = jwtService.generateToken(payload);

      // Tamper payload
      const parts = token.split('.');
      const newPayload = { userId: 'hacked' };
      parts[1] = Buffer.from(JSON.stringify(newPayload)).toString('base64url');
      const tamperedToken = parts.join('.');

      const decoded = jwtService.decodeToken(tamperedToken);

      // Decode returns tampered data (verification would catch this)
      expect(decoded.userId).toBe('hacked');
    });
  });
});
