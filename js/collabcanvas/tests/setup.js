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
    hgetall: jest.fn().mockResolvedValue({}),
    expire: jest.fn().mockResolvedValue(1),
    setex: jest.fn().mockResolvedValue('OK'),
    publish: jest.fn().mockResolvedValue(1),
    subscribe: jest.fn().mockResolvedValue(),
    on: jest.fn(),
    quit: jest.fn().mockResolvedValue(),
  }));
  return Redis;
});

// Mock sharp (native binary may not be available in test environment)
jest.mock('sharp', () => {
  const mockSharp = jest.fn().mockImplementation((input) => {
    const instance = {
      resize: jest.fn().mockReturnThis(),
      toBuffer: jest.fn().mockImplementation((callback) => {
        if (typeof input === 'string' && !require('fs').existsSync(input)) {
          callback(new Error('Input file is missing'));
          return;
        }
        // Simulate image processing
        const buffer = Buffer.from('processed-image');
        callback(null, buffer, { width: 100, height: 100, size: buffer.length });
      }),
      toFile: jest.fn().mockResolvedValue({ width: 100, height: 100, size: 100 }),
      metadata: jest.fn().mockResolvedValue({ width: 800, height: 600, format: 'png' }),
    };
    return instance;
  });
  return mockSharp;
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
