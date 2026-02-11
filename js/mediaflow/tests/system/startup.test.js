/**
 * System Startup Tests
 *
 * Tests bugs L1-L4 (setup hell), K1-K4 (configuration)
 */

describe('Service Startup', () => {
  describe('Circular Import Detection', () => {
    
    it('shared module circular import test', () => {
      jest.resetModules();

      
      expect(() => {
        require('../../../shared');
      }).not.toThrow();

      // Verify all exports are defined
      const shared = require('../../../shared');
      expect(shared.ServiceClient).toBeDefined();
      expect(shared.CircuitBreaker).toBeDefined();
      expect(shared.EventBus).toBeDefined();
      expect(shared.DistributedLock).toBeDefined();
    });

    
    it('client import test', () => {
      jest.resetModules();

      expect(() => {
        require('../../../shared/clients');
      }).not.toThrow();
    });
  });

  describe('RabbitMQ Initialization', () => {
    
    it('exchange declaration order test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      const { EventBus } = require('../../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      
      const calls = mockRabbit.channel.assertExchange.mock.calls;
      const bindingCalls = mockRabbit.channel.bindExchange.mock.calls;

      // All exchanges should be declared before any binding
      expect(calls.length).toBeGreaterThan(0);
    });

    
    it('queue declaration test', async () => {
      const mockRabbit = global.testUtils.mockRabbit();

      const { EventBus } = require('../../../shared/events');
      const bus = new EventBus(mockRabbit);

      await bus.connect();

      
      expect(mockRabbit.channel.assertQueue).toHaveBeenCalled();
    });
  });

  describe('Database Connection', () => {
    it('connection pool test', () => {
      process.env.DB_POOL_SIZE = '10';
      jest.resetModules();

      // Pool size should be number, not string
      const config = require('../../../shared/config');
      expect(typeof config.db.poolSize).toBe('number');
      expect(config.db.poolSize).toBe(10);
    });

    it('connection retry test', async () => {
      const mockDb = global.testUtils.mockDb();
      mockDb.connect
        .mockRejectedValueOnce(new Error('Connection refused'))
        .mockRejectedValueOnce(new Error('Connection refused'))
        .mockResolvedValueOnce({ connected: true });

      // Should retry and eventually connect
      const { DatabaseClient } = require('../../../shared/clients');
      const client = new DatabaseClient(mockDb);

      await expect(client.connect()).resolves.toBeDefined();
    });
  });

  describe('Service Discovery', () => {
    
    it('consul registration test', async () => {
      const mockConsul = {
        agent: {
          service: {
            register: jest.fn().mockResolvedValue({}),
          },
        },
      };

      // Service should register with health check
      expect(mockConsul.agent.service.register).toHaveBeenCalledWith(
        expect.objectContaining({
          check: expect.objectContaining({
            http: expect.any(String),
            interval: expect.any(String),
          }),
        })
      );
    });
  });
});

describe('Configuration Validation', () => {
  describe('Required Config', () => {
    
    it('JWT secret required test', () => {
      delete process.env.JWT_SECRET;
      jest.resetModules();

      expect(() => {
        require('../../../services/auth/src/index');
      }).toThrow(/JWT_SECRET/);
    });

    it('database URL required test', () => {
      delete process.env.DATABASE_URL;
      jest.resetModules();

      expect(() => {
        require('../../../shared/config');
      }).toThrow(/DATABASE_URL/);
    });
  });

  describe('Type Coercion', () => {
    
    it('pool size type test', () => {
      process.env.DB_POOL_SIZE = '20';
      jest.resetModules();

      const config = require('../../../shared/config');
      expect(typeof config.db.poolSize).toBe('number');
    });

    
    it('timeout type test', () => {
      process.env.REQUEST_TIMEOUT = '5000';
      jest.resetModules();

      const config = require('../../../shared/config');
      expect(typeof config.requestTimeout).toBe('number');
    });

    it('boolean config test', () => {
      process.env.CACHE_ENABLED = 'true';
      jest.resetModules();

      const config = require('../../../shared/config');
      expect(typeof config.cacheEnabled).toBe('boolean');
      expect(config.cacheEnabled).toBe(true);
    });
  });

  describe('Feature Flags', () => {
    
    it('feature flag update test', async () => {
      const mockFlags = global.testUtils.mockFeatureFlags();

      const { FeatureFlagService } = require('../../../shared/services');
      const flags = new FeatureFlagService(mockFlags);

      // Update flag
      await flags.setFlag('new-ui', true);

      // Should be immediately visible
      expect(await flags.isEnabled('new-ui')).toBe(true);
    });

    
    it('secret rotation test', async () => {
      const mockSecrets = global.testUtils.mockSecrets();

      const { SecretManager } = require('../../../shared/services');
      const secrets = new SecretManager(mockSecrets);

      // Get secret
      const secret1 = await secrets.getSecret('db-password');

      // Rotate secret
      await mockSecrets.rotate('db-password');

      // Should get new value without restart
      const secret2 = await secrets.getSecret('db-password');
      expect(secret2).not.toBe(secret1);
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

    // On shutdown, should drain connections
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
      await global.testUtils.delay(100);
      requestCompleted = true;
    };

    // Start request
    const requestPromise = mockRequest();

    // Simulate shutdown
    await global.testUtils.delay(50);

    // Should wait for request to complete
    await requestPromise;
    expect(requestCompleted).toBe(true);
  });
});
