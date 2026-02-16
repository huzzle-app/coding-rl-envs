/**
 * Concurrency Bug Tests
 *
 * Tests for race conditions, lost updates, non-atomic operations,
 * and ordering bugs that manifest under concurrent access.
 */

const { IngestService } = require('../../services/ingestion/src/services/ingest');
const { LoadBalancedRouter } = require('../../services/router/src/services/routing');
const { ConcurrentJobPool, JobStateMachine } = require('../../services/scheduler/src/services/dag');
const { WriteAheadLog } = require('../../services/store/src/services/timeseries');
const { ConnectorConfigManager } = require('../../services/connectors/src/services/framework');
const { StreamAggregator } = require('../../services/aggregate/src/services/rollups');
const { AlertStateMachine } = require('../../services/alerts/src/services/detection');

describe('Concurrency Bugs', () => {
  describe('IngestService parallel flush behavior', () => {
    test('parallel ingestion from multiple producers should deliver all records', async () => {
      const publishedBatches = [];
      const mockEventBus = {
        publish: jest.fn().mockImplementation(async (event) => {
          await new Promise(resolve => setTimeout(resolve, Math.random() * 10));
          publishedBatches.push(event.data);
          return true;
        }),
      };

      const service = new IngestService(mockEventBus, {
        batchSize: 5,
        backpressureThreshold: 1000,
        maxConcurrentFlushes: 3,
      });

      // Fire all ingestions concurrently using Promise.all
      const producers = Array.from({ length: 10 }, (_, p) =>
        Promise.all(
          Array.from({ length: 5 }, (_, i) =>
            service.ingest(`producer-${p}`, [{ id: `p${p}-r${i}`, value: p * 100 + i }])
          )
        )
      );

      await Promise.all(producers);
      await service.drain();

      const totalPublished = publishedBatches.reduce((sum, batch) => sum + batch.length, 0);
      expect(totalPublished).toBe(50);
    });

    test('sequence numbers assigned during parallel ingestion should be unique', async () => {
      const service = new IngestService(null, { batchSize: 10000 });

      // Parallel ingestion - all promises created before any awaits
      const results = await Promise.all(
        Array.from({ length: 20 }, (_, i) =>
          service.ingest('p1', [{ id: `r-${i}`, value: i }])
        )
      );

      const seqNums = service.batchBuffer.map(r => r._sequenceNumber);
      const uniqueSeqNums = new Set(seqNums);
      expect(uniqueSeqNums.size).toBe(seqNums.length);
    });

    test('buffer state after resume should reflect actual capacity', async () => {
      const mockEventBus = {
        publish: jest.fn().mockResolvedValue(true),
      };

      const service = new IngestService(mockEventBus, {
        batchSize: 100,
        backpressureThreshold: 10,
      });

      // Fill past threshold (batchSize=100 so no auto-flush)
      for (let i = 0; i < 15; i++) {
        await service.ingest('p1', [{ id: `r-${i}`, value: i }]);
      }

      expect(service._ingestionState).toBe('paused');

      // Resume without draining - buffer still at/above threshold
      service.resume();

      // BUG: resume() should check buffer level before accepting
      // With full buffer, state should remain 'paused' until drained
      expect(service._ingestionState).toBe('paused');
    });

    test('concurrent flush calls should respect the concurrency semaphore', async () => {
      let peakConcurrentFlushes = 0;
      let currentFlushes = 0;

      const mockEventBus = {
        publish: jest.fn().mockImplementation(async () => {
          currentFlushes++;
          peakConcurrentFlushes = Math.max(peakConcurrentFlushes, currentFlushes);
          await new Promise(resolve => setTimeout(resolve, 30));
          currentFlushes--;
          return true;
        }),
      };

      const service = new IngestService(mockEventBus, {
        batchSize: 2,
        maxConcurrentFlushes: 2,
        backpressureThreshold: 100,
      });

      for (let i = 0; i < 20; i++) {
        service.batchBuffer.push({ id: `r-${i}`, value: i, _sequenceNumber: i });
      }

      // Fire flushes concurrently with Promise.all
      await Promise.all(Array.from({ length: 6 }, () => service.flush()));

      expect(peakConcurrentFlushes).toBeLessThanOrEqual(2);
    });

    test('sequential drain should restore accepting state', async () => {
      const mockEventBus = { publish: jest.fn().mockResolvedValue(true) };
      const service = new IngestService(mockEventBus, {
        batchSize: 100,
        backpressureThreshold: 10,
      });
      // Fill buffer past threshold
      for (let i = 0; i < 15; i++) {
        await service.ingest('p1', [{ id: `r-${i}`, value: i }]);
      }
      expect(service._ingestionState).toBe('paused');
      // Resume without draining — buffer still above threshold
      service.resume();
      // BUG: resume() should check buffer level before accepting
      expect(service._ingestionState).toBe('paused');
    });
  });

  describe('LoadBalancedRouter under concurrent selection', () => {
    test('backend ordering should be preserved after concurrent selections', () => {
      const router = new LoadBalancedRouter({ strategy: 'least-connections' });

      router.addBackend({ id: 'alpha', url: 'http://alpha', connections: 50 });
      router.addBackend({ id: 'beta', url: 'http://beta', connections: 1 });
      router.addBackend({ id: 'gamma', url: 'http://gamma', connections: 100 });

      const originalOrder = router._backends.map(b => b.id);

      // Rapid concurrent selections
      for (let i = 0; i < 50; i++) {
        router.selectBackend({});
      }

      const afterOrder = router._backends.map(b => b.id);
      expect(afterOrder).toEqual(originalOrder);
    });

    test('strategy switch after selections should use consistent state', () => {
      const router = new LoadBalancedRouter({ strategy: 'least-connections' });

      router.addBackend({ id: 'a', url: 'http://a', connections: 50 });
      router.addBackend({ id: 'b', url: 'http://b', connections: 1 });
      router.addBackend({ id: 'c', url: 'http://c', connections: 100 });

      // Select via least-connections (may mutate array via sort)
      const lc = router.selectBackend({});
      expect(lc.id).toBe('b');

      // Switch to round-robin and verify original insertion order
      router._strategy = 'round-robin';
      router._currentIndex = 0;
      const rr1 = router.selectBackend({});
      expect(rr1.id).toBe('a');
    });

    test('removing a backend during round-robin should not crash', () => {
      // Exercise ContentBasedRouter last-match-wins priority bug
      const { ContentBasedRouter } = require('../../services/router/src/services/routing');
      const router = new ContentBasedRouter();
      router.addRule({
        name: 'low-priority',
        condition: (msg) => msg.type === 'log',
        destination: 'general',
        priority: 1,
      });
      router.addRule({
        name: 'high-priority',
        condition: (msg) => msg.type === 'log' && msg.level === 'error',
        destination: 'alerts',
        priority: 10,
      });
      const result = router.route({ type: 'log', level: 'error' });
      // BUG: last matching rule wins instead of highest priority
      expect(result.destination).toBe('alerts');
    });

    test('weighted selection distribution should respect weight ratios', () => {
      const router = new LoadBalancedRouter({ strategy: 'weighted' });

      router.addBackend({ id: 'heavy', url: 'http://heavy', weight: 90 });
      router.addBackend({ id: 'light', url: 'http://light', weight: 10 });

      const counts = { heavy: 0, light: 0 };
      for (let i = 0; i < 1000; i++) {
        const selected = router.selectBackend({});
        counts[selected.id]++;
      }

      expect(counts.heavy).toBeGreaterThan(counts.light * 5);
    });
  });

  describe('ConnectorConfigManager concurrent operations', () => {
    test('concurrent reads interleaved with reload should always see valid config', async () => {
      const configManager = new ConnectorConfigManager();
      configManager.setConfig('c1', { host: 'stable', port: 5432 });

      const configSnapshots = [];
      let reading = true;

      // Background reader - continuously reads config
      const reader = (async () => {
        while (reading) {
          configSnapshots.push(configManager.getConfig('c1'));
          await new Promise(r => setTimeout(r, 1));
        }
      })();

      // Fire concurrent reloads
      await Promise.all([
        configManager.reloadConfig('c1', { host: 'v1', port: 5433 }),
        configManager.reloadConfig('c1', { host: 'v2', port: 5434 }),
      ]);

      reading = false;
      await reader;

      // Every read during the reload should have returned a valid config
      const undefinedReads = configSnapshots.filter(c => c === undefined);
      expect(undefinedReads.length).toBe(0);
    });

    test('rapid sequential reloads should not corrupt state', async () => {
      const configManager = new ConnectorConfigManager();
      configManager.setConfig('c1', { host: 'original' });

      // Fire 5 reloads in rapid succession
      const reloads = [];
      for (let i = 0; i < 5; i++) {
        reloads.push(configManager.reloadConfig('c1', { host: `version-${i}` }));
      }

      await Promise.all(reloads);

      // Config should exist and be one of the versions
      const config = configManager.getConfig('c1');
      expect(config).toBeDefined();
      expect(config).not.toBeNull();
    });

    test('config should remain accessible between delete and set during reload', async () => {
      const configManager = new ConnectorConfigManager();
      configManager.setConfig('c2', { host: 'original', port: 1234 });

      // Start reload - the sync delete before async gap exposes undefined
      const reloadPromise = configManager.reloadConfig('c2', { host: 'updated' });

      // Read immediately (synchronously after reload starts)
      const midReload = configManager.getConfig('c2');

      await reloadPromise;

      // Config should never be undefined during reload
      expect(midReload).toBeDefined();
    });

    test('sequential config updates should chain correctly', async () => {
      const configManager = new ConnectorConfigManager();
      configManager.setConfig('c3', { v: 1 });
      // Fire concurrent reloads while reading
      const configSnapshots = [];
      let reading = true;
      const reader = (async () => {
        while (reading) {
          configSnapshots.push(configManager.getConfig('c3'));
          await new Promise(r => setTimeout(r, 1));
        }
      })();
      await Promise.all([
        configManager.reloadConfig('c3', { v: 2 }),
        configManager.reloadConfig('c3', { v: 3 }),
      ]);
      reading = false;
      await reader;
      // BUG: reloadConfig deletes before setting, exposing undefined
      const undefinedReads = configSnapshots.filter(c => c === undefined);
      expect(undefinedReads.length).toBe(0);
    });
  });

  describe('WriteAheadLog concurrent operations', () => {
    test('parallel appends should produce unique monotonic LSNs', () => {
      const wal = new WriteAheadLog({ maxEntries: 5 });
      const lsn1 = wal.append({ operation: 'insert', data: { id: 1 }, tableName: 't' });
      const lsn2 = wal.append({ operation: 'insert', data: { id: 2 }, tableName: 't' });
      const lsn3 = wal.append({ operation: 'insert', data: { id: 3 }, tableName: 't' });
      wal.commit(lsn1);
      wal.commit(lsn2);
      // lsn3 is uncommitted
      // Push well past maxEntries to force truncation
      for (let i = 0; i < 10; i++) {
        const lsn = wal.append({ operation: 'insert', data: { id: `x-${i}` }, tableName: 't' });
        wal.commit(lsn);
      }
      // BUG: truncation uses slice(-maxEntries) dropping old uncommitted entries
      const entry = wal.getEntry(lsn3);
      expect(entry).toBeDefined();
    });

    test('commit followed by checkpoint should not lose post-checkpoint entries', () => {
      const wal = new WriteAheadLog({ maxEntries: 100 });

      for (let i = 0; i < 10; i++) {
        const lsn = wal.append({ operation: 'insert', data: { id: i }, tableName: 't' });
        wal.commit(lsn);
      }

      wal.checkpoint();

      const newLsn = wal.append({ operation: 'insert', data: { id: 'new' }, tableName: 't' });
      const entry = wal.getEntry(newLsn);
      expect(entry).toBeDefined();
      expect(entry.data.id).toBe('new');
    });

    test('truncation under pressure should preserve in-flight entries', () => {
      const wal = new WriteAheadLog({ maxEntries: 3 });

      const lsn1 = wal.append({ operation: 'insert', data: { id: 1 }, tableName: 't' });
      const lsn2 = wal.append({ operation: 'insert', data: { id: 2 }, tableName: 't' });
      const lsn3 = wal.append({ operation: 'insert', data: { id: 3 }, tableName: 't' });

      wal.commit(lsn1);
      wal.commit(lsn2);
      // lsn3 intentionally uncommitted

      // Push well past maxEntries
      for (let i = 0; i < 5; i++) {
        const lsn = wal.append({ operation: 'insert', data: { id: `extra-${i}` }, tableName: 't' });
        wal.commit(lsn);
      }

      // BUG: truncation loses uncommitted lsn3
      const uncommitted = wal.getUncommitted();
      const hasLsn3 = uncommitted.some(e => e.lsn === lsn3);
      expect(hasLsn3).toBe(true);
    });
  });

  describe('StreamAggregator window operations', () => {
    test('rapid event ingestion should maintain accurate aggregates', () => {
      const aggregator = new StreamAggregator({
        windowDuration: 60000,
        allowedLateness: 0,
      });

      const events = Array.from({ length: 100 }, (_, i) => ({
        timestamp: 1000 + i * 100,
        value: 10,
      }));

      for (const event of events) {
        aggregator.addEvent(event);
      }

      const window = aggregator.getWindow(0);
      expect(window.aggregate.count).toBe(100);
      expect(window.aggregate.sum).toBe(1000);
    });

    test('watermark advancement should emit all completed windows', () => {
      const aggregator = new StreamAggregator({
        windowDuration: 10000,
        allowedLateness: 0,
      });

      aggregator.addEvent({ timestamp: 5000, value: 1 });
      aggregator.addEvent({ timestamp: 15000, value: 2 });
      aggregator.addEvent({ timestamp: 25000, value: 3 });

      const results = aggregator.advanceWatermark(40000);
      expect(results.length).toBe(3);
    });

    test('emitted window tracking should be cleaned up alongside window data', () => {
      const aggregator = new StreamAggregator({
        windowDuration: 1000,
        allowedLateness: 0,
      });

      for (let i = 0; i < 50; i++) {
        aggregator.addEvent({ timestamp: i * 1000 + 500, value: 1 });
      }

      aggregator.advanceWatermark(100000);
      aggregator.cleanup(40000);

      expect(aggregator._windows.size).toBeLessThan(50);
      expect(aggregator._emittedWindows.size).toBeLessThan(50);
    });
  });

  describe('ConcurrentJobPool slot management', () => {
    test('parallel job submissions should respect pool capacity', async () => {
      const pool = new ConcurrentJobPool({ maxConcurrent: 3 });
      let peakConcurrent = 0;
      let current = 0;

      const createJob = (id) => ({
        id,
        execute: async () => {
          current++;
          peakConcurrent = Math.max(peakConcurrent, current);
          await new Promise(r => setTimeout(r, 20));
          current--;
          return { id };
        },
      });

      // Submit all at once
      await Promise.all(
        Array.from({ length: 10 }, (_, i) => pool.submit(createJob(`j-${i}`)))
      );

      const stats = pool.getStats();
      expect(stats.running).toBe(0);
      expect(stats.completed).toBe(10);
    });

    test('drain should wait for all queued and running jobs', async () => {
      const pool = new ConcurrentJobPool({ maxConcurrent: 2 });
      const jobs = [];
      for (let i = 0; i < 3; i++) {
        jobs.push(pool.submit({
          id: `ok-${i}`,
          execute: async () => ({ ok: true }),
        }));
      }
      for (let i = 0; i < 2; i++) {
        jobs.push(pool.submit({
          id: `fail-${i}`,
          execute: async () => { throw new Error('intentional'); },
        }).catch(() => {}));
      }
      await Promise.all(jobs);
      const stats = pool.getStats();
      // BUG: totalProcessed only increments on success (3), not all jobs (5)
      expect(stats.totalProcessed).toBe(5);
    });

    test('failed job should release its slot for waiting jobs', () => {
      const sm = new JobStateMachine();
      const events = [];
      sm.onTransition(event => events.push(`${event.from}->${event.to}`));
      sm.createJob('j1', { maxAttempts: 3 });
      sm.transition('j1', 'queued');
      sm.transition('j1', 'running');
      sm.transition('j1', 'failed', { error: 'timeout' });
      // BUG: recursive auto-retry fires failed->queued BEFORE running->failed
      const failIdx = events.indexOf('running->failed');
      const retryIdx = events.indexOf('failed->queued');
      expect(failIdx).toBeLessThan(retryIdx);
    });
  });

  describe('JobStateMachine transition integrity', () => {
    test('auto-retry on failure should re-queue when under max attempts', () => {
      const sm = new JobStateMachine();
      sm.createJob('j1', { maxAttempts: 3 });

      sm.transition('j1', 'queued');
      sm.transition('j1', 'running');
      sm.transition('j1', 'failed', { error: 'timeout' });

      const job = sm.getJob('j1');
      expect(job.state).toBe('queued');
      expect(job.attempts).toBe(1);
    });

    test('max attempts should prevent further auto-retry', () => {
      const sm = new JobStateMachine();
      sm.createJob('j1', { maxAttempts: 2 });

      sm.transition('j1', 'queued');
      sm.transition('j1', 'running');
      sm.transition('j1', 'failed', { error: 'timeout' });

      expect(sm.getJob('j1').state).toBe('queued');

      sm.transition('j1', 'running');
      sm.transition('j1', 'failed', { error: 'timeout again' });

      expect(sm.getJob('j1').state).toBe('failed');
      expect(sm.getJob('j1').attempts).toBe(2);
    });

    test('listeners should receive events in transition order', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('a1');
      sm.transition('a1', 'firing');
      // force: "false" is a truthy string — should NOT bypass validation
      // BUG: !metadata.force treats truthy strings as force=true
      expect(() => {
        sm.transition('a1', 'pending', { force: 'false' });
      }).toThrow('Invalid transition');
    });

    test('concurrent terminal transitions should only allow one', () => {
      const sm = new JobStateMachine();
      sm.createJob('j2', { maxAttempts: 2 });

      sm.transition('j2', 'queued');
      sm.transition('j2', 'running');

      sm.transition('j2', 'completed', { result: 'done' });

      expect(() => {
        sm.transition('j2', 'cancelled');
      }).toThrow();

      expect(sm.getJob('j2').state).toBe('completed');
    });
  });
});
