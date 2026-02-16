/**
 * Gateway Middleware Tests
 *
 * Tests authMiddleware, oauthCallback, WebSocketAuthenticator, errorHandler from actual source code.
 * Exercises bugs: JWT without issuer/audience validation, CSRF state not validated in OAuth,
 * error handler leaks req.body in response.
 */

const jwt = require('jsonwebtoken');

const TEST_JWT_SECRET = 'cloudmatrix-jwt-secret-dev';

describe('Auth Middleware', () => {
  let authModule;

  beforeEach(() => {
    jest.resetModules();
    process.env.JWT_SECRET = TEST_JWT_SECRET;
    authModule = require('../../../services/gateway/src/middleware/auth');
  });

  afterEach(() => {
    delete process.env.JWT_SECRET;
  });

  describe('authMiddleware', () => {
    const createReq = (token) => ({
      headers: token ? { authorization: `Bearer ${token}` } : {},
      method: 'GET',
      path: '/api/documents',
    });

    const createRes = () => {
      const res = {
        statusCode: 200,
        body: null,
        status: jest.fn(function(code) { this.statusCode = code; return this; }),
        json: jest.fn(function(body) { this.body = body; return this; }),
      };
      return res;
    };

    it('should reject requests without authorization header', async () => {
      const req = createReq(null);
      const res = createRes();
      const next = jest.fn();

      await authModule.authMiddleware(req, res, next);
      expect(res.status).toHaveBeenCalledWith(401);
      expect(next).not.toHaveBeenCalled();
    });

    it('should reject expired tokens', async () => {
      const token = jwt.sign({ userId: 'u1' }, TEST_JWT_SECRET, { expiresIn: '0s' });
      // Small delay to ensure token is expired
      await new Promise(r => setTimeout(r, 10));
      const req = createReq(token);
      const res = createRes();
      const next = jest.fn();

      await authModule.authMiddleware(req, res, next);
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.body.code).toBe('TOKEN_EXPIRED');
    });

    it('should reject tokens with wrong secret', async () => {
      const token = jwt.sign({ userId: 'u1' }, 'wrong-secret');
      const req = createReq(token);
      const res = createRes();
      const next = jest.fn();

      await authModule.authMiddleware(req, res, next);
      expect(res.status).toHaveBeenCalledWith(401);
    });

    // BUG: JWT verification does not check issuer or audience claims.
    // This means tokens from other services are accepted.
    it('should validate JWT issuer and audience', async () => {
      // Create a token with wrong issuer
      const token = jwt.sign(
        { userId: 'u1', iss: 'malicious-service', aud: 'wrong-api' },
        TEST_JWT_SECRET
      );
      const req = createReq(token);
      const res = createRes();
      const next = jest.fn();

      await authModule.authMiddleware(req, res, next);
      // Should reject because issuer/audience don't match
      // BUG: it accepts the token because verify() has no issuer/audience options
      expect(res.status).toHaveBeenCalledWith(401);
    });
  });

  describe('WebSocketAuthenticator', () => {
    it('should authenticate valid token', () => {
      const wsAuth = new authModule.WebSocketAuthenticator('test-secret');
      const token = jwt.sign({ userId: 'u1' }, 'test-secret');
      const decoded = wsAuth.authenticate(token);
      expect(decoded).not.toBeNull();
      expect(decoded.userId).toBe('u1');
    });

    it('should return null for invalid token', () => {
      const wsAuth = new authModule.WebSocketAuthenticator('test-secret');
      const decoded = wsAuth.authenticate('garbage-token');
      expect(decoded).toBeNull();
    });
  });
});

describe('Error Middleware', () => {
  let errorModule;

  beforeEach(() => {
    jest.resetModules();
    errorModule = require('../../../services/gateway/src/middleware/error');
  });

  describe('errorHandler', () => {
    const createReq = (body = {}) => ({
      path: '/api/test',
      body,
    });

    const createRes = () => {
      const res = {
        statusCode: 200,
        body: null,
        status: jest.fn(function(code) { this.statusCode = code; return this; }),
        json: jest.fn(function(body) { this.body = body; return this; }),
      };
      return res;
    };

    it('should return error status code', () => {
      const err = new Error('Not found');
      err.statusCode = 404;
      const req = createReq();
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      expect(res.status).toHaveBeenCalledWith(404);
    });

    it('should default to 500 for errors without statusCode', () => {
      const err = new Error('Internal error');
      const req = createReq();
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      expect(res.status).toHaveBeenCalledWith(500);
    });

    // BUG: Error handler includes req.body in the response (line 17: input: req.body)
    // This leaks sensitive user input (passwords, tokens) in error responses.
    it('should NOT leak request body in error response', () => {
      const err = new Error('Validation failed');
      err.statusCode = 400;
      const req = createReq({ password: 'secret123', email: 'test@test.com' });
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      // BUG: res.body.input contains req.body with sensitive data
      expect(res.body.input).toBeUndefined();
    });

    it('should include error message in response', () => {
      const err = new Error('Something went wrong');
      err.statusCode = 500;
      const req = createReq();
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      expect(res.body.error).toBe('Something went wrong');
    });

    it('should include path in error response', () => {
      const err = new Error('fail');
      const req = createReq();
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      expect(res.body.path).toBe('/api/test');
    });

    it('should not expose sensitive credentials in error response', () => {
      const err = new Error('Bad request');
      err.statusCode = 400;
      const req = createReq({ apiKey: 'sk-secret-key-12345', token: 'refresh-token-abc' });
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      const responseStr = JSON.stringify(res.body);
      expect(responseStr).not.toContain('sk-secret-key-12345');
      expect(responseStr).not.toContain('refresh-token-abc');
    });

    it('should not include request body fields in 500 error response', () => {
      const err = new Error('Server error');
      err.statusCode = 500;
      const req = createReq({ creditCard: '4111111111111111', cvv: '123' });
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      expect(res.body).not.toHaveProperty('input');
    });

    it('should not leak PII from request body in error responses', () => {
      const err = new Error('Processing failed');
      err.statusCode = 422;
      const req = createReq({ ssn: '123-45-6789', name: 'Jane Doe' });
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      const responseStr = JSON.stringify(res.body);
      expect(responseStr).not.toContain('123-45-6789');
    });

    it('error response should only contain error, path, and stack fields', () => {
      const err = new Error('Validation error');
      err.statusCode = 400;
      const req = createReq({ data: 'sensitive' });
      const res = createRes();

      errorModule.errorHandler(err, req, res, jest.fn());
      const allowedKeys = ['error', 'path', 'stack'];
      const responseKeys = Object.keys(res.body).filter(k => res.body[k] !== undefined);
      for (const key of responseKeys) {
        expect(allowedKeys).toContain(key);
      }
    });
  });
});

describe('Auth Middleware - JWT Validation', () => {
  let authModule;

  beforeEach(() => {
    jest.resetModules();
    process.env.JWT_SECRET = TEST_JWT_SECRET;
    authModule = require('../../../services/gateway/src/middleware/auth');
  });

  afterEach(() => {
    delete process.env.JWT_SECRET;
  });

  const createReq = (token) => ({
    headers: token ? { authorization: `Bearer ${token}` } : {},
    method: 'GET',
    path: '/api/documents',
  });

  const createRes = () => {
    const res = {
      statusCode: 200,
      body: null,
      status: jest.fn(function(code) { this.statusCode = code; return this; }),
      json: jest.fn(function(body) { this.body = body; return this; }),
    };
    return res;
  };

  it('should reject token without issuer claim', async () => {
    const token = jwt.sign({ userId: 'u1' }, TEST_JWT_SECRET, { expiresIn: '1h' });
    const req = createReq(token);
    const res = createRes();
    const next = jest.fn();

    await authModule.authMiddleware(req, res, next);
    // Should verify issuer; token without iss should be rejected
    expect(res.status).toHaveBeenCalledWith(401);
  });

  it('should reject token with mismatched audience', async () => {
    const token = jwt.sign(
      { userId: 'u1' },
      TEST_JWT_SECRET,
      { issuer: 'cloudmatrix', audience: 'wrong-api', expiresIn: '1h' }
    );
    const req = createReq(token);
    const res = createRes();
    const next = jest.fn();

    await authModule.authMiddleware(req, res, next);
    expect(res.status).toHaveBeenCalledWith(401);
  });

  it('should accept token with correct issuer and audience', async () => {
    const token = jwt.sign(
      { userId: 'u1' },
      TEST_JWT_SECRET,
      { issuer: 'cloudmatrix', audience: 'cloudmatrix-api', expiresIn: '1h' }
    );
    const req = createReq(token);
    const res = createRes();
    const next = jest.fn();

    await authModule.authMiddleware(req, res, next);
    expect(next).toHaveBeenCalled();
  });

  it('should reject token from another service (wrong issuer)', async () => {
    const token = jwt.sign(
      { userId: 'u1' },
      TEST_JWT_SECRET,
      { issuer: 'evil-service', audience: 'cloudmatrix-api', expiresIn: '1h' }
    );
    const req = createReq(token);
    const res = createRes();
    const next = jest.fn();

    await authModule.authMiddleware(req, res, next);
    expect(res.status).toHaveBeenCalledWith(401);
  });
});

describe('OAuth Callback - CSRF', () => {
  let authModule;

  beforeEach(() => {
    jest.resetModules();
    process.env.JWT_SECRET = TEST_JWT_SECRET;
    authModule = require('../../../services/gateway/src/middleware/auth');
  });

  afterEach(() => {
    delete process.env.JWT_SECRET;
  });

  it('oauthCallback should validate state parameter against session', async () => {
    const req = {
      query: { code: 'auth-code', state: 'attacker-state' },
      session: { oauthState: 'legitimate-state' },
    };
    const res = {
      statusCode: 200,
      body: null,
      status: jest.fn(function(code) { this.statusCode = code; return this; }),
      json: jest.fn(function(body) { this.body = body; return this; }),
    };

    await authModule.oauthCallback(req, res);
    // Should reject because state doesn't match session
    // BUG: state parameter is not validated at all
    expect(res.status).toHaveBeenCalledWith(403);
  });

  it('oauthCallback should reject when no state parameter provided', async () => {
    const req = {
      query: { code: 'auth-code' },
      session: { oauthState: 'expected-state' },
    };
    const res = {
      statusCode: 200,
      body: null,
      status: jest.fn(function(code) { this.statusCode = code; return this; }),
      json: jest.fn(function(body) { this.body = body; return this; }),
    };

    await authModule.oauthCallback(req, res);
    // Missing state should be rejected
    expect(res.status).toHaveBeenCalledWith(403);
  });

  it('oauthCallback should reject CSRF attack with forged state', async () => {
    const req = {
      query: { code: 'stolen-code', state: 'forged-csrf-token' },
      session: { oauthState: 'real-csrf-token' },
    };
    const res = {
      statusCode: 200,
      body: null,
      status: jest.fn(function(code) { this.statusCode = code; return this; }),
      json: jest.fn(function(body) { this.body = body; return this; }),
    };

    await authModule.oauthCallback(req, res);
    expect(res.status).toHaveBeenCalledWith(403);
  });

  it('oauthCallback should not exchange code when CSRF validation fails', async () => {
    const req = {
      query: { code: 'auth-code', state: 'wrong' },
      session: { oauthState: 'correct' },
    };
    const res = {
      statusCode: 200,
      body: null,
      status: jest.fn(function(code) { this.statusCode = code; return this; }),
      json: jest.fn(function(body) { this.body = body; return this; }),
    };

    await authModule.oauthCallback(req, res);
    // Should NOT return tokens when state is invalid
    if (res.body) {
      expect(res.body).not.toHaveProperty('accessToken');
    }
  });
});
