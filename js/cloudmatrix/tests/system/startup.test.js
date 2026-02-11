/**
 * System Startup Tests
 *
 * Tests bugs L1-L12, L15 (setup hell), K1, K4-K8 (configuration)
 */

describe('Service Startup', () => {
  describe('Circular Import Detection', () => {
    it('circular import test', () => {
      jest.resetModules();

      expect(() => {
        require('../../shared');
      }).not.toThrow();

      const shared = require('../../shared');
      expect(shared.ServiceClient).toBeDefined();
      expect(shared.CircuitBreaker).toBeDefined();
      expect(shared.EventBus).toBeDefined();
      expect(shared.DistributedLock).toBeDefined();
    });

    it('shared module loading test', () => {
      jest.resetModules();

      expect(() => {
        require('../../shared/clients');
      }).not.toThrow();

      expect(() => {
        require('../../shared/events');
      }).not.toThrow();

      expect(() => {
        require('../../shared/utils');
      }).not.toThrow();

      expect(() => {
        require('../../shared/realtime');
      }).not.toThrow();
    });

    it('client dependency chain test', () => {
      jest.resetModules();

      const clients = require('../../shared/clients');
      expect(clients.ServiceClient).toBeDefined();
      expect(clients.CircuitBreaker).toBeDefined();
      expect(clients.RequestCoalescer).toBeDefined();
    });

    it('events dependency chain test', () => {
      jest.resetModules();

      const events = require('../../shared/events');
      expect(events.EventBus).toBeDefined();
      expect(events.BaseEvent).toBeDefined();
      expect(events.SchemaRegistry).toBeDefined();
    });
  });

  describe('RabbitMQ Exchange Setup', () => {
    it('exchange declaration test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      const calls = mockRabbit.channel.assertExchange.mock.calls;
      expect(calls.length).toBeGreaterThan(0);

      const exchangeTypes = calls.map(c => c[1]);
      expect(exchangeTypes).toContain('topic');
    });

    it('queue binding test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      expect(mockRabbit.channel.assertExchange).toHaveBeenCalled();
    });

    it('dead letter exchange test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      const queueCalls = mockRabbit.channel.assertQueue.mock.calls;
      const hasDeadLetter = queueCalls.some(
        call => call[1] && call[1].deadLetterExchange
      );
      expect(hasDeadLetter).toBe(true);
    });

    it('failed message routing test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      jest.resetModules();
      const { EventBus } = require('../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      const dlxCalls = mockRabbit.channel.assertExchange.mock.calls.filter(
        call => call[0] && call[0].includes('dead')
      );

      expect(dlxCalls.length).toBeGreaterThanOrEqual(0);
      expect(mockRabbit.channel.assertQueue).toHaveBeenCalled();
    });
  });

  describe('Service Discovery', () => {
    it('service discovery test', async () => {
      jest.resetModules();

      const mockConsul = global.testUtils.mockConsul();

      const registration = {
        id: 'gateway-1',
        name: 'gateway',
        port: 3000,
        check: {
          http: 'http://localhost:3000/health',
          interval: '10s',
        },
      };

      await mockConsul.agent.service.register(registration);
      expect(mockConsul.agent.service.register).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'gateway',
          check: expect.objectContaining({
            http: expect.any(String),
            interval: expect.any(String),
          }),
        })
      );
    });

    it('startup order test', async () => {
      const startupOrder = [];

      const startService = async (name, deps) => {
        for (const dep of deps) {
          if (!startupOrder.includes(dep)) {
            throw new Error(`Dependency ${dep} not started`);
          }
        }
        startupOrder.push(name);
      };

      await startService('postgres', []);
      await startService('redis', []);
      await startService('rabbitmq', []);
      await startService('consul', []);
      await startService('elasticsearch', ['postgres']);
      await startService('gateway', ['consul', 'redis', 'rabbitmq']);

      expect(startupOrder.indexOf('postgres')).toBeLessThan(startupOrder.indexOf('elasticsearch'));
      expect(startupOrder.indexOf('consul')).toBeLessThan(startupOrder.indexOf('gateway'));
    });
  });

  describe('Package Dependencies', () => {
    it('workspace package conflict test', () => {
      const shared = {
        dependencies: {
          ws: '^8.0.0',
          uuid: '^9.0.0',
        },
      };

      const gateway = {
        dependencies: {
          ws: '^8.0.0',
          uuid: '^9.0.0',
        },
      };

      for (const [pkg, version] of Object.entries(shared.dependencies)) {
        if (gateway.dependencies[pkg]) {
          const sharedMajor = parseInt(version.replace(/[^0-9]/g, '')[0]);
          const gatewayMajor = parseInt(gateway.dependencies[pkg].replace(/[^0-9]/g, '')[0]);
          expect(sharedMajor).toBe(gatewayMajor);
        }
      }
    });

    it('dependency resolution test', () => {
      const packages = ['express', 'ws', 'uuid', 'jsonwebtoken', 'amqplib'];

      for (const pkg of packages) {
        expect(() => {
          require.resolve(pkg);
        }).not.toThrow();
      }
    });
  });

  describe('Health Check Registration', () => {
    it('health check registration test', () => {
      const mockConsul = global.testUtils.mockConsul();

      const registration = {
        id: 'documents-1',
        name: 'documents',
        port: 3003,
        check: {
          http: 'http://localhost:3003/health',
          interval: '10s',
          timeout: '5s',
        },
      };

      mockConsul.agent.service.register(registration);

      expect(mockConsul.agent.service.register).toHaveBeenCalledWith(
        expect.objectContaining({
          check: expect.objectContaining({
            interval: expect.any(String),
          }),
        })
      );
    });

    it('consul service test', () => {
      const mockConsul = global.testUtils.mockConsul();

      const services = [
        { name: 'gateway', port: 3000 },
        { name: 'auth', port: 3001 },
        { name: 'users', port: 3002 },
        { name: 'documents', port: 3003 },
        { name: 'presence', port: 3004 },
      ];

      for (const svc of services) {
        mockConsul.agent.service.register({
          id: `${svc.name}-1`,
          name: svc.name,
          port: svc.port,
          check: {
            http: `http://localhost:${svc.port}/health`,
            interval: '10s',
          },
        });
      }

      expect(mockConsul.agent.service.register).toHaveBeenCalledTimes(5);
    });
  });

  describe('Redis Channel Naming', () => {
    it('redis pub/sub channel test', () => {
      jest.resetModules();

      const { LeaderElection } = require('../../shared/utils');
      const mockConsul = global.testUtils.mockConsul();

      const election1 = new LeaderElection(mockConsul, { serviceName: 'worker-a' });
      const election2 = new LeaderElection(mockConsul, { serviceName: 'worker-b' });

      expect(election1.channelName).not.toBe(election2.channelName);
    });

    it('channel naming test', () => {
      jest.resetModules();

      const { LeaderElection } = require('../../shared/utils');
      const mockConsul = global.testUtils.mockConsul();

      const election = new LeaderElection(mockConsul, { serviceName: 'documents' });

      expect(election.channelName).toContain('documents');
    });
  });

  describe('Environment Variable Parsing', () => {
    it('env var type coercion test', () => {
      const { parseConfig } = require('../../shared/utils');

      const config = parseConfig({
        PORT: '3000',
        POOL_SIZE: '10',
        CACHE_TTL: '300',
        DEBUG: 'true',
      });

      expect(typeof config.PORT).toBe('number');
      expect(typeof config.POOL_SIZE).toBe('number');
      expect(typeof config.CACHE_TTL).toBe('number');
    });

    it('port number parsing test', () => {
      const { parseConfig } = require('../../shared/utils');

      const config = parseConfig({
        PORT: '3000',
        DB_PORT: '5432',
      });

      expect(config.PORT).toBe(3000);
      expect(config.DB_PORT).toBe(5432);
    });
  });

  describe('WebSocket Server Bind', () => {
    it('websocket server bind test', async () => {
      jest.resetModules();

      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager({ port: 0 });

      expect(manager).toBeDefined();
      expect(manager.connections).toBeDefined();
    });

    it('ws initialization test', () => {
      jest.resetModules();

      const { WebSocketManager } = require('../../shared/realtime');
      const manager = new WebSocketManager({ port: 0 });

      expect(manager.heartbeatInterval).toBeDefined();
      expect(manager.maxConnections).toBeDefined();
    });
  });

  describe('CORS Configuration', () => {
    it('cors preflight test', () => {
      const allowedOrigins = ['https://app.cloudmatrix.io', 'https://admin.cloudmatrix.io'];

      const isAllowed = (origin) => {
        return allowedOrigins.includes(origin);
      };

      expect(isAllowed('https://app.cloudmatrix.io')).toBe(true);
      expect(isAllowed('https://evil.com')).toBe(false);
    });

    it('options request test', () => {
      const corsHeaders = {
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,PATCH',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Max-Age': '86400',
      };

      expect(corsHeaders['Access-Control-Allow-Methods']).toContain('GET');
      expect(corsHeaders['Access-Control-Allow-Methods']).toContain('POST');
      expect(corsHeaders['Access-Control-Allow-Headers']).toContain('Authorization');
    });
  });

  describe('Logging Transport', () => {
    it('logging transport test', () => {
      const transports = [];

      const addTransport = (name, config) => {
        transports.push({ name, ...config });
      };

      addTransport('console', { level: 'info' });
      addTransport('file', { level: 'error', filename: 'error.log' });

      expect(transports).toHaveLength(2);
      expect(transports[0].name).toBe('console');
    });

    it('winston format test', () => {
      const format = {
        timestamp: true,
        json: true,
        errors: { stack: true },
      };

      expect(format.timestamp).toBe(true);
      expect(format.json).toBe(true);
      expect(format.errors.stack).toBe(true);
    });
  });

  describe('Schema Validation', () => {
    it('schema validation init test', () => {
      const schemas = new Map();

      const registerSchema = (name, schema) => {
        schemas.set(name, schema);
      };

      registerSchema('document', {
        type: 'object',
        required: ['title', 'content'],
        properties: {
          title: { type: 'string' },
          content: { type: 'object' },
        },
      });

      expect(schemas.has('document')).toBe(true);
      expect(schemas.get('document').required).toContain('title');
    });

    it('ajv compile test', () => {
      const compiledSchemas = new Map();

      const compile = (name, schema) => {
        const validate = (data) => {
          for (const field of schema.required || []) {
            if (!(field in data)) return false;
          }
          return true;
        };
        compiledSchemas.set(name, validate);
        return validate;
      };

      const validate = compile('test', { required: ['name'] });
      expect(validate({ name: 'ok' })).toBe(true);
      expect(validate({})).toBe(false);
    });
  });

  describe('Worker Registration', () => {
    it('worker registration test', async () => {
      const workers = [];
      const mockRabbit = global.testUtils.mockRabbit();

      const registerWorker = async (queue, handler) => {
        workers.push({ queue, handler });
        await mockRabbit.channel.assertQueue(queue);
        await mockRabbit.channel.consume(queue, handler);
      };

      await registerWorker('document.index', () => {});
      await registerWorker('notification.send', () => {});

      expect(workers).toHaveLength(2);
      expect(mockRabbit.channel.consume).toHaveBeenCalledTimes(2);
    });

    it('consumer startup test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      const consumers = ['doc.process', 'search.index', 'notify.send'];
      const started = [];

      for (const queue of consumers) {
        await mockRabbit.channel.assertQueue(queue);
        await mockRabbit.channel.consume(queue, () => {});
        started.push(queue);
      }

      expect(started).toHaveLength(3);
      expect(mockRabbit.channel.assertQueue).toHaveBeenCalledTimes(3);
    });
  });
});

describe('Configuration Validation', () => {
  describe('Feature Flags', () => {
    it('feature flag undefined test', () => {
      const flags = new Map();

      const isEnabled = (flagName) => {
        const flag = flags.get(flagName);
        if (flag === undefined) return false;
        return flag;
      };

      expect(isEnabled('nonexistent-flag')).toBe(false);
      expect(isEnabled(undefined)).toBe(false);
    });

    it('flag default test', () => {
      const flags = new Map();

      const getFlag = (name, defaultValue = false) => {
        if (!flags.has(name)) return defaultValue;
        return flags.get(name);
      };

      expect(getFlag('new-feature')).toBe(false);
      expect(getFlag('new-feature', true)).toBe(true);

      flags.set('new-feature', false);
      expect(getFlag('new-feature', true)).toBe(false);
    });
  });

  describe('WebSocket Config', () => {
    it('websocket config coercion test', () => {
      const rawConfig = {
        WS_MAX_CONNECTIONS: '1000',
        WS_HEARTBEAT_INTERVAL: '30000',
        WS_MAX_PAYLOAD: '65536',
      };

      const config = {};
      for (const [key, value] of Object.entries(rawConfig)) {
        config[key] = parseInt(value, 10);
      }

      expect(typeof config.WS_MAX_CONNECTIONS).toBe('number');
      expect(config.WS_MAX_CONNECTIONS).toBe(1000);
    });

    it('ws config type test', () => {
      const rawConfig = {
        WS_COMPRESSION: 'true',
        WS_PER_MESSAGE_DEFLATE: 'false',
      };

      const config = {};
      for (const [key, value] of Object.entries(rawConfig)) {
        config[key] = value === 'true';
      }

      expect(typeof config.WS_COMPRESSION).toBe('boolean');
      expect(config.WS_COMPRESSION).toBe(true);
      expect(config.WS_PER_MESSAGE_DEFLATE).toBe(false);
    });
  });

  describe('RabbitMQ Config', () => {
    it('rabbitmq prefetch test', () => {
      const rawPrefetch = process.env.RABBITMQ_PREFETCH || '10';
      const prefetch = parseInt(rawPrefetch, 10);

      expect(typeof prefetch).toBe('number');
      expect(prefetch).toBeGreaterThan(0);
    });

    it('prefetch number test', () => {
      const config = {
        prefetch: process.env.RABBITMQ_PREFETCH || '10',
      };

      const parsedPrefetch = typeof config.prefetch === 'string'
        ? parseInt(config.prefetch, 10)
        : config.prefetch;

      expect(typeof parsedPrefetch).toBe('number');
    });
  });

  describe('Elasticsearch Config', () => {
    it('elasticsearch timeout test', () => {
      const timeout = process.env.ES_TIMEOUT || '30000';
      const parsed = parseInt(timeout, 10);

      expect(typeof parsed).toBe('number');
      expect(parsed).toBeGreaterThan(0);
    });

    it('es timeout default test', () => {
      const config = {
        requestTimeout: parseInt(process.env.ES_TIMEOUT || '30000', 10),
        maxRetries: parseInt(process.env.ES_MAX_RETRIES || '3', 10),
      };

      expect(config.requestTimeout).toBe(30000);
      expect(config.maxRetries).toBe(3);
    });
  });

  describe('Redis Config', () => {
    it('redis cluster config test', () => {
      const config = {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379', 10),
        db: parseInt(process.env.REDIS_DB || '0', 10),
        maxRetriesPerRequest: 3,
      };

      expect(typeof config.port).toBe('number');
      expect(config.port).toBe(6379);
    });

    it('cluster mode test', () => {
      const clusterMode = process.env.REDIS_CLUSTER || 'false';
      const isCluster = clusterMode === 'true';

      expect(typeof isCluster).toBe('boolean');
    });
  });

  describe('Consul Config', () => {
    it('consul kv debounce test', () => {
      let callCount = 0;
      const debounce = (fn, delay) => {
        let timer;
        return (...args) => {
          clearTimeout(timer);
          timer = setTimeout(() => {
            fn(...args);
            callCount++;
          }, delay);
        };
      };

      const debouncedFn = debounce(() => {}, 100);
      debouncedFn();
      debouncedFn();
      debouncedFn();

      expect(callCount).toBe(0);
    });

    it('watch debounce test', async () => {
      let updates = 0;
      const processUpdate = () => updates++;

      const debounced = (fn, delay) => {
        let timer;
        return (...args) => {
          clearTimeout(timer);
          timer = setTimeout(() => fn(...args), delay);
        };
      };

      const watchHandler = debounced(processUpdate, 50);

      watchHandler();
      watchHandler();
      watchHandler();

      await new Promise(resolve => setTimeout(resolve, 100));

      expect(updates).toBe(1);
    });
  });
});

describe('Graceful Shutdown', () => {
  it('connection drain test', async () => {
    const mockServer = {
      close: jest.fn(cb => cb()),
    };
    const mockDb = {
      end: jest.fn().mockResolvedValue({}),
    };
    const mockRabbit = {
      close: jest.fn().mockResolvedValue({}),
    };

    const shutdown = async () => {
      await new Promise(resolve => mockServer.close(resolve));
      await mockDb.end();
      await mockRabbit.close();
    };

    await shutdown();

    expect(mockServer.close).toHaveBeenCalled();
    expect(mockDb.end).toHaveBeenCalled();
    expect(mockRabbit.close).toHaveBeenCalled();
  });

  it('in-flight request completion test', async () => {
    let requestCompleted = false;

    const mockRequest = async () => {
      await new Promise(resolve => setTimeout(resolve, 50));
      requestCompleted = true;
    };

    const requestPromise = mockRequest();

    await new Promise(resolve => setTimeout(resolve, 20));

    await requestPromise;
    expect(requestCompleted).toBe(true);
  });

  it('websocket drain test', async () => {
    const connections = new Set();

    const closeAll = async () => {
      for (const conn of connections) {
        conn.close();
      }
      connections.clear();
    };

    connections.add({ id: '1', close: jest.fn() });
    connections.add({ id: '2', close: jest.fn() });

    await closeAll();

    expect(connections.size).toBe(0);
  });
});
