/**
 * Jest Test Setup
 */

// Increase timeout for integration tests
jest.setTimeout(30000);

// Mock external services by default
jest.mock('amqplib', () => ({
  connect: jest.fn().mockResolvedValue({
    createChannel: jest.fn().mockResolvedValue({
      assertExchange: jest.fn().mockResolvedValue({}),
      assertQueue: jest.fn().mockResolvedValue({ queue: 'test-queue' }),
      bindQueue: jest.fn().mockResolvedValue({}),
      bindExchange: jest.fn().mockResolvedValue({}),
      publish: jest.fn().mockReturnValue(true),
      consume: jest.fn().mockResolvedValue({}),
      ack: jest.fn(),
      nack: jest.fn(),
      close: jest.fn(),
      prefetch: jest.fn(),
    }),
    close: jest.fn(),
  }),
}));

jest.mock('ws', () => {
  const EventEmitter = require('events');
  class MockWebSocket extends EventEmitter {
    constructor() {
      super();
      this.readyState = 1;
      this.send = jest.fn();
      this.close = jest.fn();
      this.terminate = jest.fn();
    }
  }
  MockWebSocket.Server = class extends EventEmitter {
    constructor() {
      super();
    }
  };
  MockWebSocket.OPEN = 1;
  return MockWebSocket;
});

jest.mock('@elastic/elasticsearch', () => ({
  Client: jest.fn().mockImplementation(() => ({
    indices: {
      create: jest.fn().mockResolvedValue({ acknowledged: true }),
      exists: jest.fn().mockResolvedValue(false),
      delete: jest.fn().mockResolvedValue({ acknowledged: true }),
    },
    index: jest.fn().mockResolvedValue({ result: 'created' }),
    search: jest.fn().mockResolvedValue({ hits: { hits: [], total: { value: 0 } } }),
    bulk: jest.fn().mockResolvedValue({ errors: false }),
  })),
}));

// Suppress console output during tests
global.console = {
  ...console,
  log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};

// Clean up after each test
afterEach(() => {
  jest.clearAllMocks();
});

// Global test utilities
global.testUtils = {
  delay: (ms) => new Promise(resolve => setTimeout(resolve, ms)),

  generateId: () => `test-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,

  mockRedis: () => ({
    get: jest.fn().mockResolvedValue(null),
    set: jest.fn().mockResolvedValue('OK'),
    setex: jest.fn().mockResolvedValue('OK'),
    del: jest.fn().mockResolvedValue(1),
    keys: jest.fn().mockResolvedValue([]),
    expire: jest.fn().mockResolvedValue(1),
    pexpire: jest.fn().mockResolvedValue(1),
    watch: jest.fn().mockResolvedValue('OK'),
    unwatch: jest.fn().mockResolvedValue('OK'),
    multi: jest.fn().mockReturnValue({
      set: jest.fn().mockReturnThis(),
      exec: jest.fn().mockResolvedValue(['OK']),
    }),
    publish: jest.fn().mockResolvedValue(1),
    subscribe: jest.fn().mockResolvedValue('OK'),
  }),

  mockDb: () => ({
    query: jest.fn().mockResolvedValue({ rows: [] }),
    connect: jest.fn().mockResolvedValue({ connected: true }),
    end: jest.fn().mockResolvedValue({}),
  }),

  mockRabbit: () => {
    const channel = {
      assertExchange: jest.fn().mockResolvedValue({}),
      assertQueue: jest.fn().mockResolvedValue({ queue: 'test-queue' }),
      bindQueue: jest.fn().mockResolvedValue({}),
      bindExchange: jest.fn().mockResolvedValue({}),
      publish: jest.fn().mockReturnValue(true),
      consume: jest.fn().mockResolvedValue({}),
      ack: jest.fn(),
      nack: jest.fn(),
      close: jest.fn(),
      prefetch: jest.fn(),
    };
    return {
      createChannel: jest.fn().mockResolvedValue(channel),
      channel,
      close: jest.fn(),
    };
  },

  mockConsul: () => ({
    agent: {
      service: {
        register: jest.fn().mockResolvedValue({}),
        deregister: jest.fn().mockResolvedValue({}),
      },
    },
    kv: {
      get: jest.fn().mockResolvedValue(null),
      set: jest.fn().mockResolvedValue(true),
    },
    session: {
      create: jest.fn().mockResolvedValue({ ID: 'session-1' }),
      destroy: jest.fn().mockResolvedValue(true),
      renew: jest.fn().mockResolvedValue(true),
    },
    watch: jest.fn().mockReturnValue({
      on: jest.fn(),
    }),
  }),

  mockElasticsearch: () => ({
    indices: {
      create: jest.fn().mockResolvedValue({ acknowledged: true }),
      exists: jest.fn().mockResolvedValue(false),
    },
    index: jest.fn().mockResolvedValue({ result: 'created' }),
    search: jest.fn().mockResolvedValue({ hits: { hits: [], total: { value: 0 } } }),
  }),

  mockFeatureFlags: () => ({
    get: jest.fn().mockResolvedValue(null),
    set: jest.fn().mockResolvedValue(true),
  }),

  mockSecrets: () => ({
    getSecret: jest.fn().mockResolvedValue('secret-value'),
    rotate: jest.fn().mockResolvedValue(true),
  }),
};
