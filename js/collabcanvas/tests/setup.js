/**
 * Jest Test Setup
 */

const { Sequelize } = require('sequelize');

// Mock Redis
jest.mock('ioredis', () => {
  const Redis = jest.fn().mockImplementation(() => ({
    get: jest.fn().mockResolvedValue(null),
    set: jest.fn().mockResolvedValue('OK'),
    del: jest.fn().mockResolvedValue(1),
    hset: jest.fn().mockResolvedValue(1),
    hget: jest.fn().mockResolvedValue(null),
    hdel: jest.fn().mockResolvedValue(1),
    expire: jest.fn().mockResolvedValue(1),
    publish: jest.fn().mockResolvedValue(1),
    subscribe: jest.fn().mockResolvedValue(),
    on: jest.fn(),
    quit: jest.fn().mockResolvedValue(),
  }));
  return Redis;
});

// Test database configuration
const testDbConfig = {
  database: 'collabcanvas_test',
  username: 'collabcanvas',
  password: 'collabcanvas_dev',
  host: process.env.TEST_DB_HOST || 'localhost',
  port: process.env.TEST_DB_PORT || 5432,
  dialect: 'postgres',
  logging: false,
};

// Global test sequelize instance
let sequelize;

beforeAll(async () => {
  // Initialize test database connection
  sequelize = new Sequelize(
    testDbConfig.database,
    testDbConfig.username,
    testDbConfig.password,
    {
      host: testDbConfig.host,
      port: testDbConfig.port,
      dialect: testDbConfig.dialect,
      logging: testDbConfig.logging,
    }
  );

  try {
    await sequelize.authenticate();
  } catch (error) {
    console.warn('Database not available, some tests may be skipped');
  }
});

afterAll(async () => {
  if (sequelize) {
    await sequelize.close();
  }
});

// Global test timeout
jest.setTimeout(30000);

// Export for use in tests
global.testDbConfig = testDbConfig;
global.testSequelize = sequelize;
