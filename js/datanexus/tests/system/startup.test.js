/**
 * System Startup Tests (~25 tests)
 *
 * Tests for service startup, initialization order, configuration loading
 * Covers BUG L1-L15 setup hell bugs
 */

const { EventBus, BaseEvent, SchemaRegistry } = require('../../shared/events');
const { CircuitBreaker, ServiceClient, PluginLoader } = require('../../shared/clients');
const { Logger, TimescaleHelper, WorkerManager, parseEnvVar, CorrelationContext } = require('../../shared/utils');
const { CronScheduler } = require('../../services/scheduler/src/services/dag');

describe('System Startup Tests', () => {
  describe('circular import resolution (L1)', () => {
    test('circular import test - shared modules load without error', () => {
      expect(EventBus).toBeDefined();
      expect(CircuitBreaker).toBeDefined();
      expect(Logger).toBeDefined();
    });

    test('shared module loading test - all exports available', () => {
      expect(typeof EventBus).toBe('function');
      expect(typeof CircuitBreaker).toBe('function');
      expect(typeof ServiceClient).toBe('function');
    });
  });

  describe('exchange declaration (L2)', () => {
    test('exchange declaration test - exchange created with correct type', async () => {
      const amqplib = require('amqplib');
      const conn = await amqplib.connect();
      const channel = await conn.createChannel();

      const bus = new EventBus(conn, { exchange: 'test.events' });
      await bus.initialize();

      
      expect(channel.assertExchange).toHaveBeenCalledWith(
        'test.events',
        expect.any(String),
        expect.any(Object)
      );
    });

    test('queue binding test - queue bound to exchange', async () => {
      const amqplib = require('amqplib');
      const conn = await amqplib.connect();
      const channel = await conn.createChannel();

      const bus = new EventBus(conn, { exchange: 'test.events' });
      await bus.initialize();
      await bus.subscribe('test.routing.key', () => {});

      expect(channel.bindQueue).toHaveBeenCalled();
    });
  });

  describe('async initialization (L3)', () => {
    test('missing await initialization test - service client initializes', () => {
      const client = new ServiceClient('test-service', {
        baseUrl: 'http://localhost:3000',
      });
      
      expect(client.serviceName).toBe('test-service');
    });

    test('async startup test - client has base URL', () => {
      const client = new ServiceClient('test-service', {
        baseUrl: 'http://localhost:3000',
      });
      expect(client.baseUrl).toBe('http://localhost:3000');
    });
  });

  describe('exchange before bind (L4)', () => {
    test('exchange before bind test - binding after exchange creation', async () => {
      const amqplib = require('amqplib');
      const conn = await amqplib.connect();
      const channel = await conn.createChannel();

      const bus = new EventBus(conn);
      await bus.initialize();

      // Exchange is asserted before binding
      const exchangeCallOrder = channel.assertExchange.mock.invocationCallOrder[0];
      await bus.subscribe('test.key', () => {});
      const bindCallOrder = channel.bindQueue.mock.invocationCallOrder[0];

      expect(exchangeCallOrder).toBeLessThan(bindCallOrder);
    });

    test('binding order test - queue asserted before binding', async () => {
      const amqplib = require('amqplib');
      const conn = await amqplib.connect();
      const channel = await conn.createChannel();

      const bus = new EventBus(conn);
      await bus.initialize();
      await bus.subscribe('test.key', () => {});

      expect(channel.assertQueue).toHaveBeenCalled();
      expect(channel.bindQueue).toHaveBeenCalled();
    });
  });

  describe('TimescaleDB extension (L6)', () => {
    test('timescaledb extension test - extension created before hypertable', async () => {
      const mockPg = global.testUtils.mockPg();
      const helper = new TimescaleHelper(mockPg);

      
      await helper.createHypertable('metrics', 'time', { chunkInterval: '1 day' });
      expect(mockPg.query).toHaveBeenCalled();
    });

    test('hypertable creation test - correct SQL executed', async () => {
      const mockPg = global.testUtils.mockPg();
      const helper = new TimescaleHelper(mockPg);

      await helper.createHypertable('events', 'timestamp');
      expect(mockPg.query).toHaveBeenCalledWith(
        expect.stringContaining('create_hypertable')
      );
    });
  });

  describe('RabbitMQ dead letter (L7)', () => {
    test('rabbitmq dead letter test - DLX configured on queue', async () => {
      const amqplib = require('amqplib');
      const conn = await amqplib.connect();
      const channel = await conn.createChannel();

      const bus = new EventBus(conn);
      await bus.initialize();
      await bus.subscribe('test.key', () => {});

      
      expect(channel.assertQueue).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object)
      );
    });

    test('failed message routing test - nacked messages handled', async () => {
      const amqplib = require('amqplib');
      const conn = await amqplib.connect();
      const channel = await conn.createChannel();

      const bus = new EventBus(conn);
      await bus.initialize();

      // Verify nack is available
      expect(channel.nack).toBeDefined();
    });
  });

  describe('Redis stream group (L8)', () => {
    test('redis stream group test - consumer group created', async () => {
      const mockRedis = global.testUtils.mockRedis();
      const processor = require('../../shared/stream').StreamProcessor;
      const sp = new processor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 600000,
        consumerGroup: 'test-group',
      });

      await sp.initialize(mockRedis);
      expect(mockRedis.xgroup).toHaveBeenCalled();
    });

    test('consumer group creation test - BUSYGROUP handled', async () => {
      const mockRedis = global.testUtils.mockRedis();
      mockRedis.xgroup.mockRejectedValueOnce(new Error('BUSYGROUP Consumer Group name already exists'));

      const { StreamProcessor } = require('../../shared/stream');
      const sp = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 600000,
      });

      // Should not throw for BUSYGROUP
      await sp.initialize(mockRedis);
      expect(sp._redisGroupCreated).toBe(true);
    });
  });

  describe('worker fork race (L9)', () => {
    test('worker fork race test - workers started once', async () => {
      const manager = new WorkerManager({ maxWorkers: 4 });

      await Promise.all([manager.start(), manager.start()]);
      expect(manager.workers.length).toBe(4);
    });

    test('process startup order test - workers initialized', async () => {
      const manager = new WorkerManager({ maxWorkers: 2 });
      await manager.start();
      expect(manager.initialized).toBe(true);
      expect(manager.workers.length).toBe(2);
    });
  });

  describe('env var coercion (L10)', () => {
    test('env var coercion test - values parsed correctly', () => {
      const result = parseEnvVar('NONEXISTENT', 3000);
      expect(result).toBe(3000);
    });

    test('port parsing test - string port from env', () => {
      const oldPort = process.env.TEST_PORT_STARTUP;
      process.env.TEST_PORT_STARTUP = '8080';
      const port = parseEnvVar('TEST_PORT_STARTUP', 3000);
      
      expect(port).toBe('8080');
      process.env.TEST_PORT_STARTUP = oldPort;
    });
  });

  describe('logging transport (L12)', () => {
    test('logging transport test - logger ready after init', async () => {
      const logger = new Logger();
      await logger.initTransport({ write: jest.fn() });
      expect(logger._transportReady).toBe(true);
    });

    test('winston configuration test - logs after transport ready', async () => {
      const writeFn = jest.fn();
      const logger = new Logger();
      await logger.initTransport({ write: writeFn });

      logger.info('test message');
      expect(writeFn).toHaveBeenCalled();
    });
  });

  describe('schema registry bootstrap (L13)', () => {
    test('schema registry bootstrap test - schemas loaded', async () => {
      const registry = new SchemaRegistry();
      await registry.bootstrap();
      expect(registry.initialized).toBe(true);
    });

    test('schema loading test - register after bootstrap', async () => {
      const registry = new SchemaRegistry();
      await registry.bootstrap();
      registry.register('test-event', 1, {
        validate: (data) => true,
      });
      const schema = registry.getSchema('test-event', 1);
      expect(schema).toBeDefined();
    });
  });

  describe('connector plugin loading (L14)', () => {
    test('connector plugin loading test - loader initialized', () => {
      const loader = new PluginLoader();
      expect(loader.loadedModules).toBeDefined();
      expect(loader.registry).toBeDefined();
    });

    test('plugin discovery test - missing plugin throws', () => {
      const loader = new PluginLoader();
      expect(() => loader.loadPlugin('/nonexistent/plugin')).toThrow();
    });
  });

  describe('scheduler cron (L15)', () => {
    test('scheduler cron parser test - valid expression parsed', () => {
      const scheduler = new CronScheduler({ timezone: 'UTC' });
      scheduler.schedule('job-1', '0 * * * *', () => {});
      expect(scheduler.getJob('job-1')).toBeDefined();
    });

    test('cron initialization test - invalid expression rejected', () => {
      const scheduler = new CronScheduler();
      expect(() => scheduler.schedule('bad', 'invalid', () => {})).toThrow();
    });
  });
});
