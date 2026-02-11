/**
 * Auth Integration Tests
 *
 * Tests bugs E1 (JWT claims), E2 (refresh race), K2 (secret validation)
 */

describe('Auth Service', () => {
  let app;
  let request;
  let jwt;

  beforeEach(() => {
    jest.resetModules();
    process.env.JWT_SECRET = 'test-secret-key';

    const auth = require('../../../services/auth/src/index');
    app = auth;
    request = global.testUtils.mockRequest(app);
    jwt = require('jsonwebtoken');
  });

  afterEach(() => {
    delete process.env.JWT_SECRET;
  });

  describe('JWT claims validation', () => {
    
    it('JWT claims test', async () => {
      // Register and login
      await request.post('/register').send({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      const loginResponse = await request.post('/login').send({
        email: 'test@example.com',
        password: 'password123',
      });

      const { accessToken } = loginResponse.body;
      const decoded = jwt.decode(accessToken);

      
      expect(decoded).toHaveProperty('iss', 'mediaflow');
      expect(decoded).toHaveProperty('aud', 'mediaflow-api');
      expect(decoded).toHaveProperty('type', 'access');
    });

    
    it('token type validation test', async () => {
      await request.post('/register').send({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      const loginResponse = await request.post('/login').send({
        email: 'test@example.com',
        password: 'password123',
      });

      const { refreshToken } = loginResponse.body;

      // Try to use refresh token as access token
      const validateResponse = await request.post('/validate').send({
        token: refreshToken,
      });

      
      // The validation should check the 'type' claim
      expect(validateResponse.body.valid).toBe(false);
    });

    it('access token validation test', async () => {
      await request.post('/register').send({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      const loginResponse = await request.post('/login').send({
        email: 'test@example.com',
        password: 'password123',
      });

      const { accessToken } = loginResponse.body;

      const validateResponse = await request.post('/validate').send({
        token: accessToken,
      });

      expect(validateResponse.body.valid).toBe(true);
    });
  });

  describe('token refresh race condition', () => {
    
    it('token refresh race test', async () => {
      await request.post('/register').send({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      const loginResponse = await request.post('/login').send({
        email: 'test@example.com',
        password: 'password123',
      });

      const { refreshToken } = loginResponse.body;

      // Concurrent refresh requests with same token
      const refreshRequests = Array(5).fill(null).map(() =>
        request.post('/refresh').send({ refreshToken })
      );

      const results = await Promise.all(refreshRequests);

      
      const successCount = results.filter(r => r.status === 200).length;
      expect(successCount).toBe(1);
    });

    
    it('refresh token reuse test', async () => {
      await request.post('/register').send({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      const loginResponse = await request.post('/login').send({
        email: 'test@example.com',
        password: 'password123',
      });

      const { refreshToken } = loginResponse.body;

      // First refresh
      const firstRefresh = await request.post('/refresh').send({ refreshToken });
      expect(firstRefresh.status).toBe(200);

      // Try to reuse same token
      const secondRefresh = await request.post('/refresh').send({ refreshToken });

      
      expect(secondRefresh.status).toBe(401);
    });
  });

  describe('JWT secret validation', () => {
    
    it('JWT secret test', async () => {
      delete process.env.JWT_SECRET;
      jest.resetModules();

      // Should throw or use secure default
      expect(() => {
        require('../../../services/auth/src/index');
      }).toThrow();
    });

    it('weak secret rejection test', async () => {
      process.env.JWT_SECRET = 'weak';
      jest.resetModules();

      // Should reject weak secrets
      expect(() => {
        require('../../../services/auth/src/index');
      }).toThrow();
    });
  });

  describe('authentication flow', () => {
    it('registration test', async () => {
      const response = await request.post('/register').send({
        email: 'new@example.com',
        password: 'password123',
        name: 'New User',
      });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id');
      expect(response.body).not.toHaveProperty('password');
    });

    it('duplicate registration test', async () => {
      await request.post('/register').send({
        email: 'dup@example.com',
        password: 'password123',
        name: 'User 1',
      });

      const response = await request.post('/register').send({
        email: 'dup@example.com',
        password: 'password456',
        name: 'User 2',
      });

      expect(response.status).toBe(409);
    });

    it('login failure test', async () => {
      const response = await request.post('/login').send({
        email: 'nonexistent@example.com',
        password: 'password123',
      });

      expect(response.status).toBe(401);
    });

    it('logout test', async () => {
      await request.post('/register').send({
        email: 'test@example.com',
        password: 'password123',
        name: 'Test User',
      });

      const loginResponse = await request.post('/login').send({
        email: 'test@example.com',
        password: 'password123',
      });

      const { refreshToken } = loginResponse.body;

      const logoutResponse = await request.post('/logout').send({ refreshToken });
      expect(logoutResponse.status).toBe(204);

      // Token should be invalidated
      const refreshResponse = await request.post('/refresh').send({ refreshToken });
      expect(refreshResponse.status).toBe(401);
    });
  });
});
