/**
 * OAuth Service Unit Tests
 *
 * Tests bug D2 (OAuth state parameter CSRF)
 */

const OAuthService = require('../../../src/services/auth/oauth.service');

describe('OAuthService', () => {
  let oauthService;
  let mockRedis;

  beforeEach(() => {
    mockRedis = {
      set: jest.fn().mockResolvedValue('OK'),
      get: jest.fn().mockResolvedValue(null),
      del: jest.fn().mockResolvedValue(1),
      setex: jest.fn().mockResolvedValue('OK'),
    };

    oauthService = new OAuthService(mockRedis, {
      clientId: 'test-client-id',
      clientSecret: 'test-client-secret',
      redirectUri: 'http://localhost:3000/auth/callback',
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('generateAuthUrl', () => {
    it('should generate authorization URL with state', async () => {
      const userId = 'temp-session-123';

      const { url, state } = await oauthService.generateAuthUrl(userId);

      expect(url).toContain('client_id=');
      expect(url).toContain('state=');
      expect(state).toBeDefined();
    });

    it('should store state in Redis', async () => {
      const userId = 'temp-session-123';

      const { state } = await oauthService.generateAuthUrl(userId);

      expect(mockRedis.setex).toHaveBeenCalledWith(
        `oauth:state:${state}`,
        expect.any(Number),
        expect.any(String)
      );
    });

    it('should generate unique state for each request', async () => {
      const userId = 'user-1';

      const { state: state1 } = await oauthService.generateAuthUrl(userId);
      const { state: state2 } = await oauthService.generateAuthUrl(userId);

      expect(state1).not.toBe(state2);
    });
  });

  describe('validateCallback', () => {
    
    it('should validate OAuth state parameter', async () => {
      // Generate valid state
      const { state: validState } = await oauthService.generateAuthUrl('user-1');
      mockRedis.get.mockResolvedValue(JSON.stringify({ userId: 'user-1' }));

      // Try with invalid state
      const invalidState = 'invalid-state-value';

      await expect(
        oauthService.validateCallback('auth-code', invalidState)
      ).rejects.toThrow();
    });

    
    it('OAuth CSRF test', async () => {
      // Attacker tries to use their own state parameter
      const attackerState = 'attacker-controlled-state';
      mockRedis.get.mockResolvedValue(null); // State not in Redis

      // Should reject because state doesn't exist
      await expect(
        oauthService.validateCallback('auth-code', attackerState)
      ).rejects.toThrow(/state/i);
    });

    it('should accept valid state parameter', async () => {
      const { state } = await oauthService.generateAuthUrl('user-1');
      mockRedis.get.mockResolvedValue(JSON.stringify({ userId: 'user-1' }));

      // Mock the token exchange
      oauthService.exchangeCode = jest.fn().mockResolvedValue({
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
      });

      const result = await oauthService.validateCallback('auth-code', state);

      expect(result).toBeDefined();
    });

    it('should delete state after use', async () => {
      const { state } = await oauthService.generateAuthUrl('user-1');
      mockRedis.get.mockResolvedValue(JSON.stringify({ userId: 'user-1' }));

      oauthService.exchangeCode = jest.fn().mockResolvedValue({
        accessToken: 'access-token',
      });

      await oauthService.validateCallback('auth-code', state);

      expect(mockRedis.del).toHaveBeenCalledWith(`oauth:state:${state}`);
    });

    it('should prevent state reuse', async () => {
      const { state } = await oauthService.generateAuthUrl('user-1');

      // First call succeeds
      mockRedis.get.mockResolvedValueOnce(JSON.stringify({ userId: 'user-1' }));
      oauthService.exchangeCode = jest.fn().mockResolvedValue({
        accessToken: 'access-token',
      });

      await oauthService.validateCallback('auth-code', state);

      // Second call with same state should fail
      mockRedis.get.mockResolvedValueOnce(null); // State deleted

      await expect(
        oauthService.validateCallback('another-code', state)
      ).rejects.toThrow();
    });
  });

  describe('exchangeCode', () => {
    it('should exchange code for tokens', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          expires_in: 3600,
        }),
      });
      global.fetch = mockFetch;

      const result = await oauthService.exchangeCode('auth-code');

      expect(result.accessToken).toBe('access-token');
      expect(result.refreshToken).toBe('refresh-token');
    });

    it('should handle exchange errors', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ error: 'invalid_grant' }),
      });

      await expect(oauthService.exchangeCode('invalid-code')).rejects.toThrow();
    });
  });
});
