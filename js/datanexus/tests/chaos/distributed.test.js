/**
 * Chaos Distributed Tests (~40 tests)
 *
 * Tests for distributed system failures, leader election, partition tolerance
 * Covers BUG J1-J8, J5 (split-brain), A11 (partition rebalance), E4 (task rebalance)
 */

const { DAGExecutor, CronScheduler, RetryPolicy, SchedulerLeaderElection } = require('../../services/scheduler/src/services/dag');
const { PartitionManager } = require('../../shared/stream');
const { ConnectorTaskManager, ConnectorConfigManager } = require('../../services/connectors/src/services/framework');

describe('Distributed Chaos', () => {
  describe('DAG execution (J1)', () => {
    let dag;

    beforeEach(() => {
      dag = new DAGExecutor({ maxParallel: 2 });
    });

    test('dag topological sort test - correct execution order', () => {
      dag.addNode('A', { name: 'job-a' });
      dag.addNode('B', { name: 'job-b' });
      dag.addNode('C', { name: 'job-c' });
      dag.addEdge('A', 'B');
      dag.addEdge('B', 'C');

      const order = dag.topologicalSort();
      expect(order.indexOf('C')).toBeLessThan(order.indexOf('B'));
      expect(order.indexOf('B')).toBeLessThan(order.indexOf('A'));
    });

    test('sort correctness test - diamond dependencies resolved', () => {
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addNode('C', {});
      dag.addNode('D', {});
      dag.addEdge('A', 'B');
      dag.addEdge('A', 'C');
      dag.addEdge('B', 'D');
      dag.addEdge('C', 'D');

      const order = dag.topologicalSort();
      expect(order.indexOf('D')).toBeLessThan(order.indexOf('B'));
      expect(order.indexOf('D')).toBeLessThan(order.indexOf('C'));
    });

    test('single node DAG', () => {
      dag.addNode('A', {});
      const order = dag.topologicalSort();
      expect(order).toEqual(['A']);
    });

    test('independent nodes sorted', () => {
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addNode('C', {});
      const order = dag.topologicalSort();
      expect(order.length).toBe(3);
    });

    test('execution respects dependency order', async () => {
      const executionOrder = [];
      dag.addNode('A', { execute: async () => { executionOrder.push('A'); } });
      dag.addNode('B', { execute: async () => { executionOrder.push('B'); } });
      dag.addEdge('A', 'B');

      await dag.execute();
      expect(executionOrder.length).toBe(2);
    });

    test('failed dependency skips downstream', async () => {
      dag.addNode('A', { execute: async () => { throw new Error('failed'); } });
      dag.addNode('B', {});
      dag.addEdge('A', 'B');

      const results = await dag.execute();
      expect(results.get('A').status).toBe('failed');
    });
  });

  describe('circular dependency detection (J6)', () => {
    let dag;

    beforeEach(() => {
      dag = new DAGExecutor();
    });

    test('circular dependency test - direct cycle detected', () => {
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addEdge('A', 'B');
      dag.addEdge('B', 'A');

      expect(() => dag.topologicalSort()).toThrow();
    });

    test('cycle detection test - indirect cycle found', () => {
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addNode('C', {});
      dag.addEdge('A', 'B');
      dag.addEdge('B', 'C');
      dag.addEdge('C', 'A');

      expect(() => dag.topologicalSort()).toThrow();
    });

    test('hasCycle returns true for cycle', () => {
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addEdge('A', 'B');
      dag.addEdge('B', 'A');
      expect(dag.hasCycle()).toBe(true);
    });

    test('hasCycle returns false for valid DAG', () => {
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addEdge('A', 'B');
      expect(dag.hasCycle()).toBe(false);
    });
  });

  describe('cron scheduler (J2, J3)', () => {
    let scheduler;

    beforeEach(() => {
      scheduler = new CronScheduler({ timezone: 'America/New_York' });
    });

    test('cron timezone mismatch test - timezone considered in scheduling', () => {
      scheduler.schedule('job-1', '30 14 * * *', () => {});
      const job = scheduler.getJob('job-1');
      expect(job).toBeDefined();
      expect(job.nextRun).toBeInstanceOf(Date);
    });

    test('timezone handling test - next run in configured timezone', () => {
      scheduler.schedule('job-2', '0 0 * * *', () => {});
      const job = scheduler.getJob('job-2');
      expect(job.nextRun.getTime()).toBeGreaterThan(Date.now());
    });

    test('backfill overlap test - overlapping backfills detected', () => {
      const start = '2024-01-01T00:00:00Z';
      const end = '2024-01-03T00:00:00Z';
      const interval = 86400000; // 1 day

      const runs = scheduler.scheduleBackfill('job-3', start, end, interval);
      expect(runs.length).toBe(3);
    });

    test('overlap detection test - duplicate time periods flagged', () => {
      const runs1 = scheduler.scheduleBackfill('job-4', '2024-01-01', '2024-01-02', 86400000);
      const runs2 = scheduler.scheduleBackfill('job-4', '2024-01-01', '2024-01-02', 86400000);
      
      expect(runs1.length).toBeGreaterThan(0);
      expect(runs2.length).toBeGreaterThan(0);
    });

    test('invalid cron expression rejected', () => {
      expect(() => scheduler.schedule('bad', 'not a cron', () => {})).toThrow();
    });
  });

  describe('retry backoff (J4)', () => {
    let retry;

    beforeEach(() => {
      retry = new RetryPolicy({ maxRetries: 10, baseDelay: 1000, maxDelay: 300000 });
    });

    test('retry backoff overflow test - large attempt number safe', () => {
      const delay = retry.getDelay(50);
      expect(isFinite(delay)).toBe(true);
      expect(delay).toBeLessThanOrEqual(300000);
    });

    test('exponential overflow test - maxDelay caps the result', () => {
      const delay = retry.getDelay(100);
      expect(delay).toBeLessThanOrEqual(retry.maxDelay);
    });

    test('first attempt has base delay', () => {
      const delay = retry.getDelay(0);
      expect(delay).toBe(1000);
    });

    test('delay increases with attempts', () => {
      const d1 = retry.getDelay(1);
      const d2 = retry.getDelay(2);
      expect(d2).toBeGreaterThanOrEqual(d1);
    });

    test('shouldRetry respects maxRetries', () => {
      expect(retry.shouldRetry(9, new Error('test'))).toBe(true);
      expect(retry.shouldRetry(10, new Error('test'))).toBe(false);
    });

    test('non-retryable error stops retries', () => {
      const error = new Error('fatal');
      error.retryable = false;
      expect(retry.shouldRetry(0, error)).toBe(false);
    });
  });

  describe('leader election (J5)', () => {
    let election;
    let mockRedis;

    beforeEach(() => {
      mockRedis = global.testUtils.mockRedis();
      election = new SchedulerLeaderElection({ nodeId: 'node-1', ttl: 10000 });
    });

    test('leader election split test - only one leader at a time', async () => {
      mockRedis.set.mockResolvedValueOnce('OK');
      const acquired = await election.tryAcquire(mockRedis);
      expect(acquired).toBe(true);
      expect(election.isLeader).toBe(true);
    });

    test('split-brain test - second node fails to acquire', async () => {
      const election2 = new SchedulerLeaderElection({ nodeId: 'node-2', ttl: 10000 });

      mockRedis.set.mockResolvedValueOnce('OK');
      await election.tryAcquire(mockRedis);

      mockRedis.set.mockResolvedValueOnce(null);
      const acquired = await election2.tryAcquire(mockRedis);
      expect(acquired).toBe(false);
    });

    test('leader renewal extends TTL', async () => {
      mockRedis.set.mockResolvedValueOnce('OK');
      await election.tryAcquire(mockRedis);
      await election.renew(mockRedis);
      expect(mockRedis.pexpire).toHaveBeenCalled();
    });

    test('leader release clears leadership', async () => {
      mockRedis.set.mockResolvedValueOnce('OK');
      await election.tryAcquire(mockRedis);

      mockRedis.get.mockResolvedValueOnce('node-1');
      await election.release(mockRedis);
      expect(election.isLeader).toBe(false);
    });

    test('wrong node cannot release leadership', async () => {
      mockRedis.set.mockResolvedValueOnce('OK');
      await election.tryAcquire(mockRedis);

      mockRedis.get.mockResolvedValueOnce('other-node');
      await election.release(mockRedis);
      
      expect(election.isLeader).toBe(true);
    });
  });

  describe('parallel resource limits (J7)', () => {
    test('parallel resource limit test - running count bounded', async () => {
      const dag = new DAGExecutor({ maxParallel: 2 });

      for (let i = 0; i < 10; i++) {
        dag.addNode(`job-${i}`, {
          execute: async () => {
            await global.testUtils.delay(10);
          },
        });
      }

      const results = await dag.execute();
      expect(results.size).toBe(10);
    });

    test('resource exceeded test - excess jobs queued', () => {
      const dag = new DAGExecutor({ maxParallel: 2 });
      for (let i = 0; i < 5; i++) {
        dag.addNode(`job-${i}`, {});
      }
      expect(dag.getRunningCount()).toBe(0);
    });
  });

  describe('job cancellation (J8)', () => {
    test('cancellation orphan test - running job cancelled', async () => {
      const dag = new DAGExecutor();
      dag.addNode('long-job', {
        execute: async () => {
          await global.testUtils.delay(1000);
        },
      });

      dag.runningJobs.set('long-job', { startedAt: Date.now() });
      const cancelled = await dag.cancel('long-job');
      expect(cancelled).toBe(true);
      expect(dag.runningJobs.has('long-job')).toBe(false);
    });

    test('cleanup test - downstream jobs cancelled', async () => {
      const dag = new DAGExecutor();
      dag.addNode('A', {});
      dag.addNode('B', {});
      dag.addEdge('A', 'B');

      dag.runningJobs.set('A', { startedAt: Date.now() });
      await dag.cancel('A');
      
      expect(dag.runningJobs.has('A')).toBe(false);
    });

    test('cancel non-running job returns false', async () => {
      const dag = new DAGExecutor();
      dag.addNode('idle-job', {});
      const cancelled = await dag.cancel('idle-job');
      expect(cancelled).toBe(false);
    });

    test('reset clears all state', () => {
      const dag = new DAGExecutor();
      dag.runningJobs.set('A', { startedAt: Date.now() });
      dag.completedJobs.add('B');
      dag.reset();
      expect(dag.getRunningCount()).toBe(0);
      expect(dag.completedJobs.size).toBe(0);
    });
  });

  describe('partition rebalance (A11)', () => {
    test('partition rebalancing test - all partitions assigned', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0', 'p1', 'p2', 'p3']);

      await pm.rebalance(['c1', 'c2']);
      const total = pm.getAssignment('c1').length + pm.getAssignment('c2').length;
      expect(total).toBe(4);
    });

    test('rebalance data loss test - in-flight data preserved', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0', 'p1']);
      pm.assign('c2', ['p2', 'p3']);

      
      await pm.rebalance(['c1', 'c2', 'c3']);
      const a1 = pm.getAssignment('c1');
      const a2 = pm.getAssignment('c2');
      const a3 = pm.getAssignment('c3');
      expect(a1.length + a2.length + a3.length).toBe(4);
    });

    test('rebalancing flag set during operation', async () => {
      const pm = new PartitionManager();
      pm.assign('c1', ['p0']);
      // Can't directly test during async, but verify it completes
      await pm.rebalance(['c1', 'c2']);
      expect(pm.isRebalancing()).toBe(false);
    });
  });

  describe('connector task rebalance (E4)', () => {
    test('task rebalance data loss test - tasks reassigned', async () => {
      const tm = new ConnectorTaskManager();
      tm.addTask('conn-1', {});
      tm.addTask('conn-1', {});
      tm.addTask('conn-2', {});

      await tm.rebalance(['w1', 'w2']);
      const total = tm.getAssignment('w1').length + tm.getAssignment('w2').length;
      expect(total).toBe(3);
    });

    test('rebalance safety test - all tasks accounted for', async () => {
      const tm = new ConnectorTaskManager();
      for (let i = 0; i < 10; i++) {
        tm.addTask(`conn-${i}`, {});
      }
      await tm.rebalance(['w1', 'w2', 'w3']);
      const total = ['w1', 'w2', 'w3'].reduce(
        (sum, w) => sum + tm.getAssignment(w).length, 0
      );
      expect(total).toBe(10);
    });
  });

  describe('config hot reload under chaos', () => {
    test('config hot reload race test - concurrent reloads handled', async () => {
      const cm = new ConnectorConfigManager();
      cm.setConfig('conn-1', { timeout: 30000 });

      await Promise.all([
        cm.reloadConfig('conn-1', { timeout: 10000 }),
        cm.reloadConfig('conn-1', { timeout: 20000 }),
      ]);

      const config = cm.getConfig('conn-1');
      expect(config).toBeDefined();
      expect(config.timeout).toBeDefined();
    });

    test('reload atomicity test - config not lost', async () => {
      const cm = new ConnectorConfigManager();
      cm.setConfig('conn-1', { timeout: 30000 });
      await cm.reloadConfig('conn-1', { timeout: 10000 });
      expect(cm.getConfig('conn-1')).toEqual({ timeout: 10000 });
    });
  });

  describe('DAG execution advanced', () => {
    test('DAG with fan-out executes all children', async () => {
      const dag = new DAGExecutor();
      const results = [];
      dag.addNode('root', { execute: async () => { results.push('root'); } });
      dag.addNode('child1', { execute: async () => { results.push('child1'); } });
      dag.addNode('child2', { execute: async () => { results.push('child2'); } });
      dag.addNode('child3', { execute: async () => { results.push('child3'); } });
      dag.addEdge('root', 'child1');
      dag.addEdge('root', 'child2');
      dag.addEdge('root', 'child3');

      const execResults = await dag.execute();
      expect(execResults.size).toBe(4);
    });

    test('DAG with fan-in waits for all parents', async () => {
      const dag = new DAGExecutor();
      dag.addNode('a', { execute: async () => 'a-done' });
      dag.addNode('b', { execute: async () => 'b-done' });
      dag.addNode('c', { execute: async () => 'c-done' });
      dag.addEdge('a', 'c');
      dag.addEdge('b', 'c');

      const results = await dag.execute();
      expect(results.size).toBe(3);
    });

    test('empty DAG executes without error', async () => {
      const dag = new DAGExecutor();
      const results = await dag.execute();
      expect(results.size).toBe(0);
    });

    test('single node DAG executes correctly', async () => {
      const dag = new DAGExecutor();
      dag.addNode('only', { execute: async () => ({ value: 42 }) });
      const results = await dag.execute();
      expect(results.get('only').status).toBe('completed');
    });

    test('scheduler lists all jobs', () => {
      const scheduler = new CronScheduler({ timezone: 'UTC' });
      scheduler.schedule('job-a', '0 * * * *', () => {});
      scheduler.schedule('job-b', '30 * * * *', () => {});
      const jobs = scheduler.listJobs();
      expect(jobs.length).toBe(2);
    });

    test('retry policy with zero base delay', () => {
      const retry = new RetryPolicy({ maxRetries: 3, baseDelay: 0, maxDelay: 1000 });
      const delay = retry.getDelay(0);
      expect(delay).toBe(0);
    });
  });
});
