/**
 * OAuth Service
 *
 * BUG D2: OAuth state parameter not validated
 */

const crypto = require('crypto');
const axios = require('axios');

class OAuthService {
  constructor(db, jwtService) {
    this.db = db;
    this.jwtService = jwtService;
    this.pendingStates = new Map(); // In-memory state storage
  }

  /**
   * Generate OAuth authorization URL
   */
  generateAuthUrl(provider, redirectUri) {
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
  async exchangeCode(provider, code, redirectUri) {
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
