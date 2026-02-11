/**
 * System Startup Tests
 *
 * Tests bugs F1 (package conflicts), F2 (circular import), F3 (startup order), F4 (env types)
 */

describe('System Startup', () => {
  let originalEnv;

  beforeAll(() => {
    originalEnv = { ...process.env };
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    jest.resetModules();
  });

  describe('package dependencies', () => {
    
    it('package version conflict test', () => {
      const packageJson = require('../../../package.json');

      const socketIoVersion = packageJson.dependencies['socket.io'];
      const socketIoClientVersion = packageJson.devDependencies['socket.io-client'];

      // Major versions should match
      const serverMajor = parseInt(socketIoVersion.replace(/[\^~]/, '').split('.')[0]);
      const clientMajor = parseInt(socketIoClientVersion.replace(/[\^~]/, '').split('.')[0]);

      expect(serverMajor).toBe(clientMajor);
    });

    
    it('dependency resolution test', () => {
      const packageJson = require('../../../package.json');

      // Check for conflicting peer dependencies
      const deps = { ...packageJson.dependencies, ...packageJson.devDependencies };

      // Common conflict patterns
      const expressVersion = deps['express'];
      const socketIoVersion = deps['socket.io'];

      expect(expressVersion).toBeDefined();
      expect(socketIoVersion).toBeDefined();

      // These should be compatible versions
      const expressMajor = parseInt(expressVersion.replace(/[\^~]/, '').split('.')[0]);
      expect(expressMajor).toBeGreaterThanOrEqual(4);
    });
  });

  describe('configuration loading', () => {
    
    it('circular import test', () => {
      expect(() => {
        require('../../../src/config/index');
      }).not.toThrow();
    });

    
    it('config loading test', () => {
      let config;
      let error;

      try {
        jest.resetModules();
        config = require('../../../src/config/index');
      } catch (e) {
        error = e;
      }

      expect(error).toBeUndefined();
      expect(config).toBeDefined();
      expect(config.database).toBeDefined();
    });

    it('should load all config modules', () => {
      jest.resetModules();

      expect(() => require('../../../src/config/database')).not.toThrow();
      expect(() => require('../../../src/config/redis')).not.toThrow();
      expect(() => require('../../../src/config/jwt')).not.toThrow();
      expect(() => require('../../../src/config/websocket')).not.toThrow();
    });
  });

  describe('database initialization', () => {
    
    it('should wait for database before starting', async () => {
      process.env.DB_HOST = 'localhost';
      process.env.DB_PORT = '5432';

      jest.resetModules();

      let syncCompleted = false;
      let serverStarted = false;

      // Mock the database sync
      jest.mock('../../../src/models', () => ({
        sequelize: {
          sync: jest.fn().mockImplementation(() => {
            return new Promise(resolve => {
              setTimeout(() => {
                syncCompleted = true;
                resolve();
              }, 50);
            });
          }),
          authenticate: jest.fn().mockResolvedValue(true),
        },
      }));

      const server = require('../../../src/server');

      // Wait a bit for potential race
      await new Promise(resolve => setTimeout(resolve, 100));

      
      // Server should only start AFTER sync completes
      expect(syncCompleted).toBe(true);
    });

    
    it('startup order test', async () => {
      const order = [];

      jest.resetModules();

      // Track initialization order
      jest.mock('../../../src/models', () => ({
        sequelize: {
          sync: jest.fn().mockImplementation(async () => {
            order.push('db-sync');
          }),
          authenticate: jest.fn().mockImplementation(async () => {
            order.push('db-auth');
          }),
        },
      }));

      jest.mock('../../../src/config/redis', () => ({
        connect: jest.fn().mockImplementation(async () => {
          order.push('redis-connect');
        }),
      }));

      // Server should wait for both
      // Expected order: db-auth, db-sync, redis-connect, server-start
      expect(order.indexOf('db-sync')).toBeLessThan(order.indexOf('server-start') || Infinity);
    });
  });

  describe('environment variables', () => {
    
    it('should handle string environment variables', () => {
      process.env.DB_POOL_SIZE = '5';
      process.env.DB_POOL_MIN = '2';

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      // Should be numbers, not strings
      expect(typeof dbConfig.pool.max).toBe('number');
      expect(typeof dbConfig.pool.min).toBe('number');
    });

    
    it('pool size type test', () => {
      process.env.DB_POOL_SIZE = '5';

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      // String '5' > '10' is false, but number 5 > 2 is true
      // This tests that the value is properly parsed
      expect(dbConfig.pool.max > 2).toBe(true);
      expect(dbConfig.pool.max < 10).toBe(true);
    });

    it('should validate required environment variables', () => {
      delete process.env.JWT_SECRET;

      jest.resetModules();

      // Should throw or use secure default
      expect(() => {
        const jwtConfig = require('../../../src/config/jwt');
        if (!jwtConfig.secret || jwtConfig.secret === 'undefined') {
          throw new Error('JWT_SECRET not set');
        }
      }).toThrow();
    });
  });

  describe('graceful shutdown', () => {
    it('should close database connections on shutdown', async () => {
      const mockClose = jest.fn().mockResolvedValue(undefined);

      jest.resetModules();
      jest.mock('../../../src/models', () => ({
        sequelize: {
          close: mockClose,
          sync: jest.fn().mockResolvedValue(undefined),
        },
      }));

      const server = require('../../../src/server');

      if (server.close) {
        await server.close();
        expect(mockClose).toHaveBeenCalled();
      }
    });

    it('should close Redis connections on shutdown', async () => {
      const mockQuit = jest.fn().mockResolvedValue('OK');

      jest.resetModules();
      jest.mock('../../../src/config/redis', () => ({
        client: { quit: mockQuit },
        pubClient: { quit: mockQuit },
        subClient: { quit: mockQuit },
      }));

      const server = require('../../../src/server');

      if (server.close) {
        await server.close();
        expect(mockQuit).toHaveBeenCalled();
      }
    });
  });
});
