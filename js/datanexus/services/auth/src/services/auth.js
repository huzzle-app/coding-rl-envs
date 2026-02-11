/**
 * Auth Service Logic
 */

const jwt = require('jsonwebtoken');
const crypto = require('crypto');

class AuthService {
  constructor(config) {
    this.jwtSecret = config.jwtSecret;
    this.tokenExpiry = config.tokenExpiry || '1h';
  }

  generateToken(userId, teamId, permissions) {
    return jwt.sign(
      { userId, teamId, permissions },
      this.jwtSecret,
      { expiresIn: this.tokenExpiry }
    );
  }

  verifyToken(token) {
    return jwt.verify(token, this.jwtSecret);
  }

  generateApiKey() {
    return `dnx_${crypto.randomBytes(32).toString('hex')}`;
  }

  hashApiKey(apiKey) {
    return crypto.createHash('sha256').update(apiKey).digest('hex');
  }
}

module.exports = { AuthService };
