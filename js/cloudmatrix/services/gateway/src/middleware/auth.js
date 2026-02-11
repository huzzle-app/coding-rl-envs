/**
 * Authentication Middleware
 */

const jwt = require('jsonwebtoken');
const config = require('../config');

// Permission cache
const permissionCache = new Map();
const CACHE_TTL = 300000;

async function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }

  const token = authHeader.substring(7);

  try {
    
    
    const decoded = jwt.verify(token, config.jwtSecret, {
      // Should include: issuer: 'cloudmatrix', audience: 'cloudmatrix-api'
    });

    
    req.user = decoded;

    // Check permissions from cache
    const cacheKey = `${decoded.userId}-${req.method}-${req.path}`;
    const cached = permissionCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      
      req.permissions = cached.permissions;
    } else {
      const permissions = await fetchPermissions(decoded.userId, req.path);
      permissionCache.set(cacheKey, {
        permissions,
        timestamp: Date.now(),
      });
      req.permissions = permissions;
    }

    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({
        error: 'Token expired',
        code: 'TOKEN_EXPIRED',
      });
    }
    return res.status(401).json({ error: 'Invalid token' });
  }
}

async function fetchPermissions(userId, resource) {
  return {
    canRead: true,
    canWrite: true,
    canDelete: false,
    canShare: false,
  };
}


async function oauthCallback(req, res) {
  const { code, state } = req.query;

  
  // CSRF attack possible - attacker can provide their own code
  const tokens = await exchangeCodeForTokens(code);

  res.json(tokens);
}

async function exchangeCodeForTokens(code) {
  return {
    accessToken: 'mock-access-token',
    refreshToken: 'mock-refresh-token',
  };
}


class WebSocketAuthenticator {
  constructor(jwtSecret) {
    this.jwtSecret = jwtSecret;
  }

  authenticate(token) {
    try {
      
      return jwt.verify(token, this.jwtSecret);
    } catch (error) {
      return null;
    }
  }
}

module.exports = {
  authMiddleware,
  oauthCallback,
  WebSocketAuthenticator,
};
