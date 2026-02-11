/**
 * Distributed System Tests
 *
 * Tests distributed consensus, leader election, split-brain scenarios
 */

describe('Distributed Consensus', () => {
  describe('Leader Election', () => {
    
    it('leader election test', async () => {
      const mockConsul = global.testUtils.mockConsul();

      const { LeaderElection } = require('../../../shared/utils');
      const election1 = new LeaderElection(mockConsul, 'transcode-workers');
      const election2 = new LeaderElection(mockConsul, 'transcode-workers');

      // Start both competing for leadership
      const leader1 = election1.start();
      const leader2 = election2.start();

      await Promise.all([leader1, leader2]);

      
      const isLeader1 = await election1.isLeader();
      const isLeader2 = await election2.isLeader();

      expect(isLeader1 !== isLeader2).toBe(true);
    });

    
    it('leader failover test', async () => {
      const mockConsul = global.testUtils.mockConsul();

      const { LeaderElection } = require('../../../shared/utils');
      const election1 = new LeaderElection(mockConsul, 'workers');
      const election2 = new LeaderElection(mockConsul, 'workers');

      await election1.start();
      await election2.start();

      // Leader dies
      if (await election1.isLeader()) {
        await election1.stop();
      }

      // Wait for failover
      await global.testUtils.delay(1000);

      
      expect(await election2.isLeader()).toBe(true);
    });
  });

  describe('Split Brain Prevention', () => {
    
    it('split brain transcode test', async () => {
      const mockRedis = global.testUtils.mockRedis();

      const { DistributedLock } = require('../../../shared/utils');

      // Two workers try to process same video
      const lock1 = new DistributedLock(mockRedis);
      const lock2 = new DistributedLock(mockRedis);

      const videoId = 'video-123';

      // Both try to acquire lock
      const [result1, result2] = await Promise.all([
        lock1.acquire(`transcode:${videoId}`),
        lock2.acquire(`transcode:${videoId}`),
      ]);

      
      const acquiredCount = [result1, result2].filter(Boolean).length;
      expect(acquiredCount).toBe(1);
    });

    
    it('network partition test', async () => {
      const mockRedis = global.testUtils.mockRedis();

      const { DistributedLock } = require('../../../shared/utils');
      const lock = new DistributedLock(mockRedis);

      // Acquire lock
      await lock.acquire('resource-1');

      // Simulate network partition - Redis becomes unavailable
      mockRedis.set.mockRejectedValue(new Error('Connection refused'));

      // Lock should be considered invalid
      const isValid = await lock.isValid('resource-1');
      expect(isValid).toBe(false);
    });
  });

  describe('Distributed Lock', () => {
    
    it('lock timeout test', async () => {
      const mockRedis = global.testUtils.mockRedis();

      const { DistributedLock } = require('../../../shared/utils');
      const lock = new DistributedLock(mockRedis, { timeout: 5000 });

      await lock.acquire('long-operation');

      // Simulate long operation (10 seconds)
      await global.testUtils.delay(10000);

      
      const stillHeld = await lock.isHeld('long-operation');
      expect(stillHeld).toBe(true);
    }, 15000);

    it('lock contention test', async () => {
      const mockRedis = global.testUtils.mockRedis();

      const { DistributedLock } = require('../../../shared/utils');
      const lock = new DistributedLock(mockRedis);

      // Multiple requests for same lock
      const results = await Promise.all(
        Array(10).fill(null).map(() => lock.acquire('shared-resource'))
      );

      // Only one should acquire
      const acquired = results.filter(Boolean).length;
      expect(acquired).toBe(1);
    });

    it('lock release test', async () => {
      const mockRedis = global.testUtils.mockRedis();

      const { DistributedLock } = require('../../../shared/utils');
      const lock1 = new DistributedLock(mockRedis);
      const lock2 = new DistributedLock(mockRedis);

      await lock1.acquire('resource');

      // Should not be able to acquire
      expect(await lock2.acquire('resource', { wait: false })).toBe(false);

      // Release
      await lock1.release('resource');

      // Now should acquire
      expect(await lock2.acquire('resource')).toBe(true);
    });
  });
});

describe('Event Ordering', () => {
  
  it('event ordering test', async () => {
    const mockRabbit = global.testUtils.mockRabbit();

    const { EventBus } = require('../../../shared/events');
    const bus = new EventBus(mockRabbit);

    const receivedEvents = [];

    await bus.subscribe('video.updated', (event) => {
      receivedEvents.push(event);
    });

    // Publish events with sequence numbers
    await bus.publish('video.updated', { seq: 1, data: 'first' });
    await bus.publish('video.updated', { seq: 2, data: 'second' });
    await bus.publish('video.updated', { seq: 3, data: 'third' });

    await global.testUtils.delay(100);

    
    expect(receivedEvents.map(e => e.seq)).toEqual([1, 2, 3]);
  });

  
  it('event idempotency test', async () => {
    const mockRabbit = global.testUtils.mockRabbit();

    const { EventBus } = require('../../../shared/events');
    const bus = new EventBus(mockRabbit);

    let processCount = 0;

    await bus.subscribe('video.created', (event) => {
      processCount++;
    });

    // Same event published twice (e.g., retry)
    const eventId = 'event-123';
    await bus.publish('video.created', { id: eventId, data: 'video' });
    await bus.publish('video.created', { id: eventId, data: 'video' });

    await global.testUtils.delay(100);

    
    expect(processCount).toBe(1);
  });
});

describe('Saga Coordination', () => {
  
  it('saga rollback test', async () => {
    const compensations = [];

    const saga = {
      steps: [
        { name: 'createRecord', compensate: () => compensations.push('deleteRecord') },
        { name: 'uploadFile', compensate: () => compensations.push('deleteFile') },
        { name: 'updateIndex', compensate: () => { throw new Error('Compensation failed'); } },
        { name: 'notify', compensate: () => compensations.push('cancelNotify') },
      ],
    };

    // Execute saga that fails at notify
    const executeSaga = async () => {
      const completed = [];
      for (const step of saga.steps) {
        if (step.name === 'notify') {
          throw new Error('Notify failed');
        }
        completed.push(step);
      }
    };

    try {
      await executeSaga();
    } catch (e) {
      // Compensate in reverse
      for (const step of saga.steps.reverse()) {
        try {
          if (step.compensate) step.compensate();
        } catch (e) {
          
        }
      }
    }

    
    expect(compensations).toContain('deleteRecord');
    expect(compensations).toContain('deleteFile');
  });
});
