/**
 * JWT Configuration
 * BUG D1: JWT_SECRET from env without proper validation
 */

module.exports = {
  
  // In production, this will be undefined causing auth failures
  secret: process.env.JWT_SECRET,

  accessToken: {
    expiresIn: '15m',
  },

  refreshToken: {
    expiresIn: '7d',
  },

  algorithm: 'HS256',
};
