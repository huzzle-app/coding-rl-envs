/**
 * Distributed Systems Chaos Tests
 *
 * Tests bugs A1-A8 (distributed consensus)
 */

describe('Distributed Lock', () => {
  let DistributedLock;
  let mockRedis;

  beforeEach(() => {
    jest.resetModules();

    mockRedis = global.testUtils.mockRedis();

    const utils = require('../../../shared/utils');
    DistributedLock = utils.DistributedLock;
  });

  describe('clock skew', () => {
    
    it('clock skew test', async () => {
      const lock = new DistributedLock(mockRedis, { timeout: 5000 });

      // Simulate clock skew - one node thinks it's 2 seconds ahead
      const originalDateNow = Date.now;
      let clockOffset = 0;

      Date.now = () => originalDateNow() + clockOffset;

      // Acquire lock
      const acquired = await lock.acquire('test-key');

      // Simulate clock skew on another node
      clockOffset = 2000;

      // Lock should still be valid considering skew
      const isValid = acquired && Date.now() < acquired.expireAt;

      
      expect(isValid).toBe(true);

      Date.now = originalDateNow;
    });

    it('lock timeout test', async () => {
      const lock = new DistributedLock(mockRedis, { timeout: 100 });

      const acquired = await lock.acquire('test-key');

      // Wait for expiry
      await global.testUtils.delay(150);

      // Lock should be expired
      expect(Date.now()).toBeGreaterThan(acquired.expireAt);
    });
  });

  describe('lock operations', () => {
    
    it('lock timeout for long operations', async () => {
      const lock = new DistributedLock(mockRedis);

      const acquired = await lock.acquire('long-operation');

      // Simulate long operation (10 seconds)
      const operationTime = 10000;

      
      // Lock will expire during operation
      expect(acquired.expireAt - Date.now()).toBeGreaterThanOrEqual(operationTime);
    });

    it('operation completion test', async () => {
      const lock = new DistributedLock(mockRedis, { timeout: 30000 });

      const acquired = await lock.acquire('test-key');

      // Simulate 5 second operation
      await global.testUtils.delay(100); // Fast for test

      // Should still be valid
      expect(Date.now()).toBeLessThan(acquired.expireAt);
    });
  });

  describe('concurrent access', () => {
    
    it('lock release race test', async () => {
      const lock = new DistributedLock(mockRedis);

      let currentHolder = null;

      mockRedis.set = jest.fn(async (key, value, options) => {
        if (options?.NX && currentHolder) {
          return null; // Already locked
        }
        currentHolder = value;
        return 'OK';
      });

      mockRedis.get = jest.fn(async () => currentHolder);

      mockRedis.del = jest.fn(async () => {
        currentHolder = null;
        return 1;
      });

      const acquired1 = await lock.acquire('test-key');

      // Simulate concurrent release attempt
      const fakeRelease = lock.release({ key: acquired1.key, value: 'wrong-value' });
      const realRelease = lock.release(acquired1);

      const [fake, real] = await Promise.all([fakeRelease, realRelease]);

      // Only the real owner should succeed
      expect(fake).toBe(false);
      expect(real).toBe(true);
    });

    it('concurrent release test', async () => {
      const lock = new DistributedLock(mockRedis);

      const acquired = await lock.acquire('test-key');

      // Multiple release attempts
      const results = await Promise.all([
        lock.release(acquired),
        lock.release(acquired),
        lock.release(acquired),
      ]);

      // Only one should succeed
      const successCount = results.filter(r => r).length;
      expect(successCount).toBeLessThanOrEqual(1);
    });
  });
});

describe('Leader Election', () => {
  let LeaderElection;
  let mockConsul;

  beforeEach(() => {
    jest.resetModules();

    mockConsul = {
      session: {
        create: jest.fn().mockResolvedValue({ ID: 'session-123' }),
        renew: jest.fn().mockResolvedValue({}),
        destroy: jest.fn().mockResolvedValue({}),
      },
      kv: {
        set: jest.fn().mockResolvedValue(true),
        get: jest.fn().mockResolvedValue(null),
      },
      watch: jest.fn().mockReturnValue({
        on: jest.fn(),
      }),
    };

    const utils = require('../../../shared/utils');
    LeaderElection = utils.LeaderElection;
  });

  describe('split-brain prevention', () => {
    
    it('split-brain test', async () => {
      const election1 = new LeaderElection(mockConsul, { serviceName: 'test' });
      const election2 = new LeaderElection(mockConsul, { serviceName: 'test' });

      // Both try to acquire leadership
      mockConsul.kv.set
        .mockResolvedValueOnce(true)
        .mockResolvedValueOnce(true); 

      await election1.start();
      await election2.start();

      // Only one should be leader
      const leaderCount = [election1.getIsLeader(), election2.getIsLeader()]
        .filter(Boolean).length;

      expect(leaderCount).toBe(1);

      await election1.stop();
      await election2.stop();
    });

    it('leader consistency test', async () => {
      const elections = [];

      for (let i = 0; i < 5; i++) {
        const election = new LeaderElection(mockConsul, { serviceName: 'test' });
        elections.push(election);
      }

      // Only first should become leader
      mockConsul.kv.set
        .mockResolvedValueOnce(true)
        .mockResolvedValue(false);

      for (const election of elections) {
        await election.start();
      }

      const leaderCount = elections.filter(e => e.getIsLeader()).length;
      expect(leaderCount).toBe(1);

      for (const election of elections) {
        await election.stop();
      }
    });
  });
});
