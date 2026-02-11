/**
 * Database Configuration Unit Tests
 *
 * Tests bugs F2 (circular import) and F4 (env var type)
 */

describe('Database Configuration', () => {
  let originalEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    // Reset module cache
    jest.resetModules();
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.resetModules();
  });

  describe('circular import', () => {
    
    it('circular import test', () => {
      // Attempting to require should not cause stack overflow
      expect(() => {
        require('../../../src/config/index');
      }).not.toThrow();
    });

    
    it('config loading test', () => {
      let config;
      let error;

      try {
        config = require('../../../src/config/index');
      } catch (e) {
        error = e;
      }

      // Should load without circular dependency error
      expect(error).toBeUndefined();
      expect(config).toBeDefined();
    });
  });

  describe('environment variable types', () => {
    
    it('should handle string environment variables', () => {
      process.env.DB_POOL_SIZE = '5';

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      
      expect(typeof dbConfig.pool.max).toBe('number');
      expect(dbConfig.pool.max).toBe(5);
    });

    
    it('pool size type test', () => {
      process.env.DB_POOL_SIZE = '10';
      process.env.DB_POOL_MIN = '2';

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      // Pool sizes should be numbers for proper comparison
      expect(dbConfig.pool.max).toBeGreaterThan(dbConfig.pool.min);

      // This comparison fails if they're strings: '10' > '2' works, but '5' > '10' fails
      process.env.DB_POOL_SIZE = '5';
      jest.resetModules();
      const dbConfig2 = require('../../../src/config/database');

      // '5' > '10' is false in string comparison, but 5 > 2 should be true
      expect(dbConfig2.pool.max).toBeGreaterThan(2);
    });

    it('should use default values when env vars missing', () => {
      delete process.env.DB_POOL_SIZE;
      delete process.env.DB_POOL_MIN;

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      expect(dbConfig.pool.max).toBeDefined();
      expect(typeof dbConfig.pool.max).toBe('number');
    });

    it('should handle DB_PORT as number', () => {
      process.env.DB_PORT = '5432';

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      expect(typeof dbConfig.port).toBe('number');
      expect(dbConfig.port).toBe(5432);
    });
  });

  describe('connection string', () => {
    it('should build valid connection string', () => {
      process.env.DB_HOST = 'localhost';
      process.env.DB_PORT = '5432';
      process.env.DB_NAME = 'collabcanvas';
      process.env.DB_USER = 'postgres';
      process.env.DB_PASSWORD = 'password';

      jest.resetModules();
      const dbConfig = require('../../../src/config/database');

      expect(dbConfig.host).toBe('localhost');
      expect(dbConfig.database).toBe('collabcanvas');
    });
  });
});
