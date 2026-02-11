/**
 * Authentication Middleware
 *
 * BUG E1: JWT claims not validated properly
 * BUG E2: Token refresh race condition
 * BUG E3: Permission cache stale
 */

const jwt = require('jsonwebtoken');
const config = require('../config');

// Permission cache

const permissionCache = new Map();
const CACHE_TTL = 300000; // 5 minutes

async function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }

  const token = authHeader.substring(7);

  try {
    
    const decoded = jwt.verify(token, config.jwtSecret, {
      // Should include: issuer: 'mediaflow', audience: 'mediaflow-api'
    });

    
    // Refresh tokens could be used as access tokens

    req.user = decoded;

    // Check permissions from cache
    const cacheKey = `${decoded.userId}-${req.method}-${req.path}`;
    const cached = permissionCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      
      req.permissions = cached.permissions;
    } else {
      // Fetch fresh permissions
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
  // In real implementation, would call auth service
  return {
    canRead: true,
    canWrite: true,
    canDelete: false,
  };
}

// Token refresh endpoint handler

let refreshInProgress = new Map();

async function refreshToken(req, res) {
  const { refreshToken } = req.body;

  if (!refreshToken) {
    return res.status(400).json({ error: 'Refresh token required' });
  }

  try {
    const decoded = jwt.verify(refreshToken, config.jwtSecret);

    
    // Old refresh token should be invalidated after first use
    if (refreshInProgress.has(decoded.userId)) {
      // This check is flawed - doesn't actually prevent race
      return res.status(429).json({ error: 'Refresh in progress' });
    }

    refreshInProgress.set(decoded.userId, true);

    try {
      // Generate new tokens
      const newAccessToken = jwt.sign(
        { userId: decoded.userId, email: decoded.email },
        config.jwtSecret,
        { expiresIn: '15m' }
      );

      const newRefreshToken = jwt.sign(
        { userId: decoded.userId, type: 'refresh' },
        config.jwtSecret,
        { expiresIn: '7d' }
      );

      
      // Should store refresh tokens and invalidate old one

      res.json({
        accessToken: newAccessToken,
        refreshToken: newRefreshToken,
      });
    } finally {
      refreshInProgress.delete(decoded.userId);
    }
  } catch (error) {
    return res.status(401).json({ error: 'Invalid refresh token' });
  }
}

// Permission checker with this binding issue
class PermissionChecker {
  constructor(authService) {
    this.authService = authService;
  }

  
  checkPermission = async (userId, resource, action) => {
    
    const permissions = await this.authService.getPermissions(userId);
    return permissions[resource]?.includes(action);
  };

  createMiddleware(resource, action) {
    
    return async (req, res, next) => {
      const hasPermission = await this.checkPermission(
        req.user.userId,
        resource,
        action
      );

      if (!hasPermission) {
        return res.status(403).json({ error: 'Permission denied' });
      }

      next();
    };
  }
}

module.exports = {
  authMiddleware,
  refreshToken,
  PermissionChecker,
};
