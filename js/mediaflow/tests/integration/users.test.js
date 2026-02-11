/**
 * Users Service Integration Tests
 */

describe('Users Service', () => {
  let app;
  let request;

  beforeEach(() => {
    jest.resetModules();
    const users = require('../../../services/users/src/index');
    app = users.app;
    request = global.testUtils.mockRequest(app);
  });

  describe('user creation', () => {
    it('should create user', async () => {
      const response = await request.post('/users').send({
        id: 'user-new',
        email: 'new@example.com',
        name: 'New User',
      });

      expect(response.status).toBe(201);
      expect(response.body.id).toBe('user-new');
    });

    it('should reject duplicate user', async () => {
      await request.post('/users').send({
        id: 'user-1',
        email: 'user1@example.com',
        name: 'User 1',
      });

      const response = await request.post('/users').send({
        id: 'user-1',
        email: 'user1@example.com',
        name: 'User 1',
      });

      expect(response.status).toBe(409);
    });

    it('should initialize profile', async () => {
      await request.post('/users').send({
        id: 'user-2',
        email: 'user2@example.com',
        name: 'User 2',
      });

      const response = await request.get('/users/user-2/profile');
      expect(response.status).toBe(200);
    });
  });

  describe('user retrieval', () => {
    it('should get user by ID', async () => {
      await request.post('/users').send({
        id: 'user-3',
        email: 'user3@example.com',
        name: 'User 3',
      });

      const response = await request.get('/users/user-3');
      expect(response.status).toBe(200);
      expect(response.body.name).toBe('User 3');
    });

    it('should return 404 for unknown user', async () => {
      const response = await request.get('/users/unknown');
      expect(response.status).toBe(404);
    });
  });

  describe('profile management', () => {
    it('should get profile', async () => {
      await request.post('/users').send({
        id: 'user-4',
        email: 'user4@example.com',
        name: 'User 4',
      });

      const response = await request.get('/users/user-4/profile');
      expect(response.status).toBe(200);
      expect(response.body.userId).toBe('user-4');
    });

    it('should update profile', async () => {
      await request.post('/users').send({
        id: 'user-5',
        email: 'user5@example.com',
        name: 'User 5',
      });

      const response = await request
        .put('/users/user-5/profile')
        .set('x-user-id', 'user-5')
        .send({ bio: 'My bio' });

      expect(response.status).toBe(200);
      expect(response.body.bio).toBe('My bio');
    });

    it('should reject unauthorized update', async () => {
      await request.post('/users').send({
        id: 'user-6',
        email: 'user6@example.com',
        name: 'User 6',
      });

      const response = await request
        .put('/users/user-6/profile')
        .set('x-user-id', 'user-other')
        .send({ bio: 'Hacked!' });

      expect(response.status).toBe(403);
    });
  });

  describe('preferences', () => {
    it('should get preferences', async () => {
      await request.post('/users').send({
        id: 'user-7',
        email: 'user7@example.com',
        name: 'User 7',
      });

      const response = await request.get('/users/user-7/preferences');
      expect(response.status).toBe(200);
    });

    it('should update preferences', async () => {
      await request.post('/users').send({
        id: 'user-8',
        email: 'user8@example.com',
        name: 'User 8',
      });

      const response = await request
        .put('/users/user-8/preferences')
        .send({ theme: 'dark' });

      expect(response.status).toBe(200);
      expect(response.body.theme).toBe('dark');
    });
  });

  describe('batch operations', () => {
    it('should batch get users', async () => {
      await request.post('/users').send({ id: 'batch-1', email: 'b1@example.com', name: 'B1' });
      await request.post('/users').send({ id: 'batch-2', email: 'b2@example.com', name: 'B2' });

      const response = await request.post('/users/batch').send({
        userIds: ['batch-1', 'batch-2'],
      });

      expect(response.status).toBe(200);
      expect(response.body.users).toHaveLength(2);
    });

    it('should handle missing users in batch', async () => {
      const response = await request.post('/users/batch').send({
        userIds: ['missing-1', 'missing-2'],
      });

      expect(response.status).toBe(200);
    });
  });

  describe('health check', () => {
    it('should return healthy', async () => {
      const response = await request.get('/health');
      expect(response.status).toBe(200);
      expect(response.body.status).toBe('healthy');
    });
  });
});
