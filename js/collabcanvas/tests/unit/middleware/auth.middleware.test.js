/**
 * Auth Middleware Unit Tests
 */

describe('Auth Middleware', () => {
  let mockReq;
  let mockRes;
  let mockNext;

  beforeEach(() => {
    mockReq = {
      headers: {},
      cookies: {},
    };

    mockRes = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn().mockReturnThis(),
    };

    mockNext = jest.fn();
  });

  describe('requireAuth', () => {
    it('should pass with valid Bearer token', async () => {
      mockReq.headers.authorization = 'Bearer valid-token';

      const requireAuth = (verifyToken) => (req, res, next) => {
        const authHeader = req.headers.authorization;
        if (!authHeader?.startsWith('Bearer ')) {
          return res.status(401).json({ error: 'No token provided' });
        }

        const token = authHeader.substring(7);
        try {
          req.user = verifyToken(token);
          next();
        } catch (error) {
          res.status(401).json({ error: 'Invalid token' });
        }
      };

      const middleware = requireAuth((token) => ({ id: 'user-1' }));
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
      expect(mockReq.user).toEqual({ id: 'user-1' });
    });

    it('should reject request without token', async () => {
      const requireAuth = (req, res, next) => {
        if (!req.headers.authorization) {
          return res.status(401).json({ error: 'No token provided' });
        }
        next();
      };

      requireAuth(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(401);
      expect(mockNext).not.toHaveBeenCalled();
    });

    it('should reject invalid token format', async () => {
      mockReq.headers.authorization = 'InvalidFormat token';

      const requireAuth = (req, res, next) => {
        const authHeader = req.headers.authorization;
        if (!authHeader?.startsWith('Bearer ')) {
          return res.status(401).json({ error: 'Invalid token format' });
        }
        next();
      };

      requireAuth(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(401);
    });

    it('should reject expired token', async () => {
      mockReq.headers.authorization = 'Bearer expired-token';

      const requireAuth = (verifyToken) => (req, res, next) => {
        try {
          const token = req.headers.authorization.substring(7);
          verifyToken(token);
        } catch (error) {
          return res.status(401).json({ error: 'Token expired' });
        }
        next();
      };

      const middleware = requireAuth(() => {
        throw new Error('Token expired');
      });

      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(401);
    });
  });

  describe('optionalAuth', () => {
    it('should continue without token', async () => {
      const optionalAuth = (verifyToken) => (req, res, next) => {
        const authHeader = req.headers.authorization;
        if (authHeader?.startsWith('Bearer ')) {
          try {
            req.user = verifyToken(authHeader.substring(7));
          } catch {
            // Ignore invalid token in optional auth
          }
        }
        next();
      };

      const middleware = optionalAuth(() => null);
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
      expect(mockReq.user).toBeUndefined();
    });

    it('should set user if valid token provided', async () => {
      mockReq.headers.authorization = 'Bearer valid-token';

      const optionalAuth = (verifyToken) => (req, res, next) => {
        const authHeader = req.headers.authorization;
        if (authHeader?.startsWith('Bearer ')) {
          try {
            req.user = verifyToken(authHeader.substring(7));
          } catch {
            // Ignore
          }
        }
        next();
      };

      const middleware = optionalAuth(() => ({ id: 'user-1' }));
      middleware(mockReq, mockRes, mockNext);

      expect(mockReq.user).toEqual({ id: 'user-1' });
    });
  });

  describe('requireRole', () => {
    it('should allow user with required role', async () => {
      mockReq.user = { id: 'user-1', roles: ['admin', 'user'] };

      const requireRole = (role) => (req, res, next) => {
        if (!req.user?.roles?.includes(role)) {
          return res.status(403).json({ error: 'Insufficient permissions' });
        }
        next();
      };

      const middleware = requireRole('admin');
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
    });

    it('should reject user without required role', async () => {
      mockReq.user = { id: 'user-1', roles: ['user'] };

      const requireRole = (role) => (req, res, next) => {
        if (!req.user?.roles?.includes(role)) {
          return res.status(403).json({ error: 'Insufficient permissions' });
        }
        next();
      };

      const middleware = requireRole('admin');
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(403);
    });
  });

  describe('apiKeyAuth', () => {
    it('should accept valid API key', async () => {
      mockReq.headers['x-api-key'] = 'valid-api-key';

      const apiKeyAuth = (validateKey) => (req, res, next) => {
        const apiKey = req.headers['x-api-key'];
        if (!apiKey || !validateKey(apiKey)) {
          return res.status(401).json({ error: 'Invalid API key' });
        }
        next();
      };

      const middleware = apiKeyAuth((key) => key === 'valid-api-key');
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
    });

    it('should reject invalid API key', async () => {
      mockReq.headers['x-api-key'] = 'invalid-key';

      const apiKeyAuth = (validateKey) => (req, res, next) => {
        const apiKey = req.headers['x-api-key'];
        if (!apiKey || !validateKey(apiKey)) {
          return res.status(401).json({ error: 'Invalid API key' });
        }
        next();
      };

      const middleware = apiKeyAuth((key) => key === 'valid-api-key');
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(401);
    });
  });
});
