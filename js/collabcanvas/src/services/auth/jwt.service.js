/**
 * JWT Service
 *
 * BUG D1: JWT_SECRET from env without validation
 */

const jwt = require('jsonwebtoken');
const jwtConfig = require('../../config/jwt');

class JWTService {
  constructor() {
    
    // In production, jwtConfig.secret may be undefined
    this.secret = jwtConfig.secret;
    this.accessTokenExpiry = jwtConfig.accessToken.expiresIn;
    this.refreshTokenExpiry = jwtConfig.refreshToken.expiresIn;
  }

  /**
   * Generate access token
   * BUG D1: Will throw cryptic error if secret is undefined
   */
  generateAccessToken(user) {
    
    // "Error: secretOrPrivateKey must have a value"
    return jwt.sign(
      {
        userId: user.id,
        email: user.email,
        firstName: user.firstName,
        lastName: user.lastName,
        type: 'access',
      },
      this.secret,
      { expiresIn: this.accessTokenExpiry }
    );
  }

  /**
   * Generate refresh token
   */
  generateRefreshToken(user) {
    return jwt.sign(
      {
        userId: user.id,
        type: 'refresh',
      },
      this.secret,
      { expiresIn: this.refreshTokenExpiry }
    );
  }

  /**
   * Generate token pair
   */
  generateTokenPair(user) {
    return {
      accessToken: this.generateAccessToken(user),
      refreshToken: this.generateRefreshToken(user),
    };
  }

  /**
   * Verify token
   */
  verifyToken(token) {
    try {
      return jwt.verify(token, this.secret);
    } catch (error) {
      return null;
    }
  }

  /**
   * Verify access token specifically
   */
  verifyAccessToken(token) {
    const decoded = this.verifyToken(token);
    if (!decoded || decoded.type !== 'access') {
      return null;
    }
    return decoded;
  }

  /**
   * Verify refresh token specifically
   */
  verifyRefreshToken(token) {
    const decoded = this.verifyToken(token);
    if (!decoded || decoded.type !== 'refresh') {
      return null;
    }
    return decoded;
  }

  /**
   * Generate token with custom payload and options
   * BUG: Does not filter sensitive fields from payload (password, secretKey, etc.)
   * BUG: No default expiry - tokens without explicit expiresIn never expire
   */
  generateToken(payload, options = {}) {
    return jwt.sign(payload, this.secret, options);
  }

  /**
   * Refresh an existing token with a new expiry
   * BUG: Uses decodeToken (no verification) instead of verifyToken
   * This allows refreshing expired or tampered tokens
   */
  refreshToken(token) {
    const decoded = this.decodeToken(token);
    if (!decoded) {
      throw new Error('Invalid token');
    }
    const { iat, exp, ...payload } = decoded;
    return this.generateToken(payload, { expiresIn: this.accessTokenExpiry });
  }

  /**
   * Decode token without verification
   */
  decodeToken(token) {
    return jwt.decode(token);
  }

  /**
   * Check if token is expired
   */
  isTokenExpired(token) {
    const decoded = this.decodeToken(token);
    if (!decoded || !decoded.exp) {
      return true;
    }
    return decoded.exp * 1000 < Date.now();
  }

  /**
   * Get remaining time on token
   */
  getTokenTimeRemaining(token) {
    const decoded = this.decodeToken(token);
    if (!decoded || !decoded.exp) {
      return 0;
    }
    return Math.max(0, decoded.exp * 1000 - Date.now());
  }
}

module.exports = JWTService;
