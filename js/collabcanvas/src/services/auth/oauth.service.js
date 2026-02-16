/**
 * OAuth Service
 *
 * BUG D2: OAuth state parameter not validated
 */

const crypto = require('crypto');
const axios = require('axios');

class OAuthService {
  constructor(dbOrRedis, jwtServiceOrConfig) {
    this.pendingStates = new Map(); // In-memory state storage

    if (jwtServiceOrConfig && (jwtServiceOrConfig.clientId || jwtServiceOrConfig.clientSecret)) {
      // Redis + config mode (stateless OAuth)
      this.redis = dbOrRedis;
      this.clientId = jwtServiceOrConfig.clientId;
      this.clientSecret = jwtServiceOrConfig.clientSecret;
      this.redirectUri = jwtServiceOrConfig.redirectUri;
      this._mode = 'redis';
    } else {
      // DB + jwtService mode (original)
      this.db = dbOrRedis;
      this.jwtService = jwtServiceOrConfig;
      this._mode = 'db';
    }
  }

  /**
   * Generate OAuth authorization URL (Redis/config mode)
   * Used when constructed with (redis, config) pattern
   */
  async generateAuthUrlForUser(userId) {
    const state = crypto.randomBytes(32).toString('hex');

    if (this.redis) {
      await this.redis.setex(
        `oauth:state:${state}`,
        600, // 10 minutes
        JSON.stringify({ userId, createdAt: Date.now() })
      );
    }

    const params = new URLSearchParams({
      client_id: this.clientId || process.env.GOOGLE_CLIENT_ID,
      redirect_uri: this.redirectUri || '',
      response_type: 'code',
      scope: 'email profile',
      state,
    });

    return {
      url: `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`,
      state,
    };
  }

  /**
   * Validate OAuth callback with state parameter (Redis/config mode)
   * BUG D2: State parameter not validated - allows CSRF attacks
   */
  async validateCallback(code, state) {
    // BUG D2: State is NOT validated against Redis
    // Should check: const stateData = await this.redis.get(`oauth:state:${state}`);
    // Should throw if: !stateData

    // Delete state after use (even though we didn't validate it)
    if (this.redis) {
      await this.redis.del(`oauth:state:${state}`);
    }

    // Exchange code for tokens
    const tokens = await this.exchangeCode(code);

    return { tokens, state };
  }

  /**
   * Generate OAuth authorization URL
   */
  generateAuthUrl(providerOrUserId, redirectUri) {
    // Support both (userId) and (provider, redirectUri) signatures
    if (!redirectUri && this._mode === 'redis') {
      return this.generateAuthUrlForUser(providerOrUserId);
    }

    const provider = providerOrUserId;
    const state = crypto.randomBytes(32).toString('hex');

    // Store state for validation
    this.pendingStates.set(state, {
      provider,
      redirectUri,
      createdAt: Date.now(),
    });

    const providers = {
      google: {
        authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
        clientId: process.env.GOOGLE_CLIENT_ID,
        scope: 'email profile',
      },
      github: {
        authUrl: 'https://github.com/login/oauth/authorize',
        clientId: process.env.GITHUB_CLIENT_ID,
        scope: 'user:email',
      },
    };

    const config = providers[provider];
    if (!config) {
      throw new Error(`Unknown provider: ${provider}`);
    }

    const params = new URLSearchParams({
      client_id: config.clientId,
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: config.scope,
      state,
    });

    return {
      url: `${config.authUrl}?${params.toString()}`,
      state,
    };
  }

  /**
   * Handle OAuth callback
   * BUG D2: State parameter not properly validated
   */
  async handleCallback(provider, code, state, redirectUri) {
    
    // This allows CSRF attacks where attacker can initiate OAuth flow
    // and trick user into completing it on attacker's behalf

    // VULNERABLE: State not validated
    // const storedState = this.pendingStates.get(state);
    // if (!storedState) {
    //   throw new Error('Invalid state parameter');
    // }
    // this.pendingStates.delete(state);

    // Exchange code for tokens
    const tokens = await this.exchangeCode(provider, code, redirectUri);

    // Get user info
    const userInfo = await this.getUserInfo(provider, tokens.access_token);

    // Find or create user
    const [user, created] = await this.db.User.findOrCreate({
      where: { email: userInfo.email },
      defaults: {
        email: userInfo.email,
        firstName: userInfo.firstName || userInfo.name?.split(' ')[0] || '',
        lastName: userInfo.lastName || userInfo.name?.split(' ').slice(1).join(' ') || '',
        password: crypto.randomBytes(32).toString('hex'), // Random password
        avatarUrl: userInfo.avatar,
      },
    });

    // Generate JWT tokens
    const jwtTokens = this.jwtService.generateTokenPair(user);

    return {
      user: user.toJSON(),
      tokens: jwtTokens,
      created,
    };
  }

  /**
   * Exchange authorization code for tokens
   */
  async exchangeCode(providerOrCode, code, redirectUri) {
    // Redis/config mode: single arg is the auth code, use fetch
    if (this._mode === 'redis' && !code) {
      const authCode = providerOrCode;
      const response = await fetch('https://oauth2.googleapis.com/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: this.clientId,
          client_secret: this.clientSecret,
          code: authCode,
          redirect_uri: this.redirectUri,
          grant_type: 'authorization_code',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Token exchange failed');
      }

      const data = await response.json();
      return {
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        expiresIn: data.expires_in,
      };
    }

    // DB mode: (provider, code, redirectUri) with axios
    const provider = providerOrCode;
    const providers = {
      google: {
        tokenUrl: 'https://oauth2.googleapis.com/token',
        clientId: process.env.GOOGLE_CLIENT_ID,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      },
      github: {
        tokenUrl: 'https://github.com/login/oauth/access_token',
        clientId: process.env.GITHUB_CLIENT_ID,
        clientSecret: process.env.GITHUB_CLIENT_SECRET,
      },
    };

    const config = providers[provider];
    if (!config) {
      throw new Error(`Unknown provider: ${provider}`);
    }

    const response = await axios.post(
      config.tokenUrl,
      {
        client_id: config.clientId,
        client_secret: config.clientSecret,
        code,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      },
      {
        headers: {
          Accept: 'application/json',
        },
      }
    );

    return response.data;
  }

  /**
   * Get user info from OAuth provider
   */
  async getUserInfo(provider, accessToken) {
    const providers = {
      google: {
        userInfoUrl: 'https://www.googleapis.com/oauth2/v2/userinfo',
        transform: (data) => ({
          email: data.email,
          firstName: data.given_name,
          lastName: data.family_name,
          avatar: data.picture,
        }),
      },
      github: {
        userInfoUrl: 'https://api.github.com/user',
        transform: (data) => ({
          email: data.email,
          name: data.name,
          avatar: data.avatar_url,
        }),
      },
    };

    const config = providers[provider];
    if (!config) {
      throw new Error(`Unknown provider: ${provider}`);
    }

    const response = await axios.get(config.userInfoUrl, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    return config.transform(response.data);
  }

  /**
   * Clean up expired states
   */
  cleanupExpiredStates(maxAge = 600000) { // 10 minutes
    const now = Date.now();
    for (const [state, data] of this.pendingStates) {
      if (now - data.createdAt > maxAge) {
        this.pendingStates.delete(state);
      }
    }
  }
}

module.exports = OAuthService;
