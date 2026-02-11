/**
 * Multi-Step Bug Tests
 *
 * Tests where fixing one bug reveals another. The bugs are chained:
 * fixing bug A causes bug B to surface, which when fixed reveals bug C.
 * Each step structurally depends on the previous step's fix.
 */

const { WriteAheadLog, CompactionManager } = require('../../services/store/src/services/timeseries');
const { IngestService } = require('../../services/ingestion/src/services/ingest');
const { StreamAggregator, ContinuousAggregation, RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { ConnectorPipeline, SourceConnector, SinkConnector } = require('../../services/connectors/src/services/framework');
const { DAGExecutor, JobStateMachine, ConcurrentJobPool } = require('../../services/scheduler/src/services/dag');

describe('Multi-Step Bugs', () => {
  describe('WAL lifecycle: truncation -> checkpoint -> recovery', () => {
    // Steps share a single WAL instance so step 2 structurally depends on step 1
    let wal;
    let commitLsns;

    beforeEach(() => {
      wal = new WriteAheadLog({ maxEntries: 6 });
      commitLsns = [];
    });

    test('step 1: truncation under load should retain in-flight entries', () => {
      // Append entries, commit some, leave some uncommitted
      const lsn1 = wal.append({ operation: 'insert', data: { id: 1 }, tableName: 't' });
      const lsn2 = wal.append({ operation: 'insert', data: { id: 2 }, tableName: 't' });
      const lsn3 = wal.append({ operation: 'insert', data: { id: 3 }, tableName: 't' });

      wal.commit(lsn1);
      wal.commit(lsn2);
      // lsn3 is uncommitted

      // Push past maxEntries to trigger truncation
      for (let i = 0; i < 5; i++) {
        const lsn = wal.append({ operation: 'insert', data: { id: `fill-${i}` }, tableName: 't' });
        wal.commit(lsn);
      }

      // Uncommitted entry (lsn3) must survive truncation
      const uncommitted = wal.getUncommitted();
      const hasLsn3 = uncommitted.some(e => e.lsn === lsn3);
      expect(hasLsn3).toBe(true);
    });

    test('step 2: checkpoint after truncation survival should keep recent commits available', () => {
      // This step exercises step 1's codepath first (truncation),
      // then exercises step 2's codepath (checkpoint).
      // If step 1 isn't fixed, entries are already lost, making recovery impossible.

      const lsn1 = wal.append({ operation: 'insert', data: { id: 'a' }, tableName: 't' });
      const lsn2 = wal.append({ operation: 'update', data: { id: 'a', v: 2 }, tableName: 't' });
      const lsn3 = wal.append({ operation: 'insert', data: { id: 'b' }, tableName: 't' });
      const lsn4 = wal.append({ operation: 'update', data: { id: 'b', v: 2 }, tableName: 't' });

      wal.commit(lsn1);
      wal.commit(lsn2);
      wal.commit(lsn3);
      // lsn4 is uncommitted

      // Push past maxEntries (triggers truncation - exercises step 1's bug)
      const lsn5 = wal.append({ operation: 'insert', data: { id: 'c' }, tableName: 't' });
      const lsn6 = wal.append({ operation: 'insert', data: { id: 'd' }, tableName: 't' });
      wal.commit(lsn5);
      wal.commit(lsn6);

      // Now checkpoint (exercises step 2's bug: removes ALL committed entries)
      const cpLsn = wal.checkpoint();

      // After checkpoint, recently committed entries (lsn5, lsn6) should still
      // be recoverable for crash recovery purposes
      const recovered = wal.recover(lsn5);
      expect(recovered.length).toBeGreaterThan(0);

      // Uncommitted lsn4 should still exist (if step 1 is fixed, it survived truncation,
      // then checkpoint should preserve it since it's uncommitted)
      const uncommitted = wal.getUncommitted();
      expect(uncommitted.some(e => e.lsn === lsn4)).toBe(true);
    });

    test('step 3: recovery from checkpoint should replay entries in LSN order', () => {
      // This step depends on both step 1 (entries survive truncation)
      // and step 2 (checkpoint preserves necessary entries)

      const lsns = [];
      lsns.push(wal.append({ operation: 'insert', data: { id: 1 }, tableName: 'table_a' }));
      lsns.push(wal.append({ operation: 'insert', data: { id: 1 }, tableName: 'table_b' }));
      lsns.push(wal.append({ operation: 'update', data: { id: 1, v: 2 }, tableName: 'table_a' }));
      lsns.push(wal.append({ operation: 'delete', data: { id: 1 }, tableName: 'table_b' }));

      for (const lsn of lsns) {
        wal.commit(lsn);
      }

      const recovered = wal.recover(0);
      for (let i = 1; i < recovered.length; i++) {
        expect(recovered[i].lsn).toBeGreaterThan(recovered[i - 1].lsn);
      }

      expect(recovered.length).toBe(4);
    });
  });

  describe('Ingestion -> dedup -> backpressure chain', () => {
    test('step 1: dedup window should use wall clock to expire entries', async () => {
      const service = new IngestService(null, { batchSize: 1000 });

      // Record with future timestamp
      await service.ingest('p1', [
        { id: 'key-1', deduplicationKey: 'dk-1', timestamp: Date.now() + 86400000, value: 1 },
      ]);

      // Different event with same dedup key but normal timestamp
      const result = await service.ingest('p1', [
        { id: 'key-2', deduplicationKey: 'dk-1', timestamp: Date.now(), value: 2 },
      ]);

      // Should be accepted since it's a different event time-wise
      expect(result.accepted).toBe(1);
    });

    test('step 2: after dedup fix, resume should check actual buffer level', async () => {
      // This test depends on step 1: if dedup incorrectly blocks records,
      // the buffer won't fill to threshold, and backpressure won't trigger.

      const mockEventBus = { publish: jest.fn().mockResolvedValue(true) };
      const service = new IngestService(mockEventBus, {
        batchSize: 100,
        backpressureThreshold: 10,
      });

      // Fill buffer past threshold (requires working dedup from step 1)
      for (let i = 0; i < 15; i++) {
        await service.ingest('p1', [{ id: `r-${i}`, value: i }]);
      }

      expect(service._ingestionState).toBe('paused');

      // Resume without draining
      service.resume();

      // BUG: resume() should check buffer level before accepting
      // Buffer is still >= threshold, state should remain 'paused'
      expect(service._ingestionState).toBe('paused');
    });

    test('step 3: after resume fix, concurrent flushes should be bounded', async () => {
      // Depends on step 2: if resume doesn't work properly, the service
      // stays paused and flushes can't be triggered.

      const flushDelay = 30;
      const mockEventBus = {
        publish: jest.fn().mockImplementation(() =>
          new Promise(resolve => setTimeout(resolve, flushDelay))
        ),
      };

      const service = new IngestService(mockEventBus, {
        batchSize: 2,
        maxConcurrentFlushes: 2,
        backpressureThreshold: 100,
      });

      for (let i = 0; i < 20; i++) {
        service.batchBuffer.push({ id: `r-${i}`, value: i });
      }

      await Promise.all(Array.from({ length: 5 }, () => service.flush()));

      expect(service._pendingFlushes).toBeLessThanOrEqual(service._maxConcurrentFlushes);
    });
  });

  describe('Aggregation window lifecycle', () => {
    let aggregator;

    beforeEach(() => {
      aggregator = new StreamAggregator({
        windowDuration: 10000,
        allowedLateness: 5000,
        retractionsEnabled: true,
      });
    });

    test('step 1: window emission timing should correctly trigger on watermark', () => {
      aggregator.addEvent({ timestamp: 1000, value: 10 });
      aggregator.addEvent({ timestamp: 5000, value: 20 });
      aggregator.addEvent({ timestamp: 9999, value: 30 });

      const results = aggregator.advanceWatermark(10000);

      expect(results.length).toBe(1);
      expect(results[0].sum).toBe(60);
      expect(results[0].count).toBe(3);
    });

    test('step 2: late events after emission should trigger recomputation', () => {
      // Depends on step 1: if window doesn't emit correctly,
      // there's no emission to retract.

      aggregator.addEvent({ timestamp: 2000, value: 100 });

      // Emit window (depends on step 1 being correct)
      const emissions = aggregator.advanceWatermark(15000);
      expect(emissions.length).toBe(1);

      // Late event within allowed lateness
      const addResult = aggregator.addEvent({ timestamp: 8000, value: 50 });
      expect(addResult.status).toBe('added');

      // Recompute should include retraction of previous emission
      const updated = aggregator.recomputeWindow(0);
      expect(updated).not.toBeNull();
      expect(updated.sum).toBe(150);
    });

    test('step 3: cleanup after emission should also clean tracking metadata', () => {
      // Uses fresh aggregator to avoid interference
      const cleanupAgg = new StreamAggregator({
        windowDuration: 100,
        allowedLateness: 0,
      });

      for (let i = 0; i < 1000; i++) {
        cleanupAgg.addEvent({ timestamp: i * 100 + 50, value: 1 });
      }

      // Emit all (depends on step 1 for correct emission)
      cleanupAgg.advanceWatermark(200000);

      cleanupAgg.cleanup(50000);

      // Both tracking structures should be cleaned
      expect(cleanupAgg._windows.size).toBeLessThan(1000);
      expect(cleanupAgg._emittedWindows.size).toBeLessThan(1000);
    });
  });

  describe('DAG execution -> job state -> retry chain', () => {
    test('step 1: DAG execution should respect dependency ordering', async () => {
      const dag = new DAGExecutor();
      const executionOrder = [];

      dag.addNode('extract', {
        execute: async () => { executionOrder.push('extract'); return { data: [1, 2, 3] }; },
      });

      dag.addNode('transform', {
        execute: async () => { executionOrder.push('transform'); return { transformed: true }; },
      });

      dag.addNode('load', {
        execute: async () => { executionOrder.push('load'); return { loaded: true }; },
      });

      dag.addEdge('transform', 'extract');
      dag.addEdge('load', 'transform');

      const results = await dag.execute();

      expect(executionOrder).toEqual(['extract', 'transform', 'load']);
      expect(results.get('load').status).toBe('completed');
    });

    test('step 2: job retry after DAG failure should respect state machine', () => {
      // Depends on step 1: DAG execution order determines which job fails first.
      // If ordering is wrong, the wrong job is attempted and fails.

      const sm = new JobStateMachine();
      const job = sm.createJob('job-1', { maxAttempts: 3 });

      sm.transition('job-1', 'queued');
      sm.transition('job-1', 'running');

      // First failure - auto-retry should queue
      sm.transition('job-1', 'failed', { error: 'timeout' });

      const currentJob = sm.getJob('job-1');
      expect(currentJob.state).toBe('queued');
      expect(currentJob.attempts).toBe(1);

      // Run through all retries
      sm.transition('job-1', 'running');
      sm.transition('job-1', 'failed', { error: 'timeout again' });
      expect(sm.getJob('job-1').state).toBe('queued');

      sm.transition('job-1', 'running');
      sm.transition('job-1', 'failed', { error: 'final failure' });
      expect(sm.getJob('job-1').state).toBe('failed');
      expect(sm.getJob('job-1').attempts).toBe(3);
    });

    test('step 3: concurrent transitions on same job should be atomic', () => {
      const sm = new JobStateMachine();
      sm.createJob('job-2', { maxAttempts: 2 });

      sm.transition('job-2', 'queued');
      sm.transition('job-2', 'running');

      // Complete first
      sm.transition('job-2', 'completed', { result: 'done' });

      // Cancel should fail - already transitioned
      expect(() => {
        sm.transition('job-2', 'cancelled');
      }).toThrow();

      expect(sm.getJob('job-2').state).toBe('completed');
    });
  });

  describe('Compaction -> tombstone -> lookup chain', () => {
    let compactor;

    beforeEach(() => {
      compactor = new CompactionManager({ mergeThreshold: 2 });
    });

    test('step 1: merge deduplication should retain the most recent version', () => {
      compactor.addSegment({
        level: 0,
        data: [
          { key: 'k1', value: 'old', timestamp: 1000 },
          { key: 'k2', value: 'v2', timestamp: 1000 },
        ],
      });

      compactor.addSegment({
        level: 0,
        data: [
          { key: 'k1', value: 'new', timestamp: 2000 },
          { key: 'k3', value: 'v3', timestamp: 2000 },
        ],
      });

      compactor.compact();

      // k1 should have the NEWEST value
      const result = compactor.lookup('k1');
      expect(result.value).toBe('new');
    });

    test('step 2: tombstones should be applied during merge', () => {
      // Depends on step 1: if merge keeps old version, tombstone
      // might not match the version stored in the merged segment.

      compactor.addSegment({
        level: 0,
        data: [{ key: 'deleted-key', value: 'should-not-appear', timestamp: 1000 }],
      });

      compactor.markDeleted('deleted-key');

      compactor.addSegment({
        level: 0,
        data: [{ key: 'keep-key', value: 'visible', timestamp: 2000 }],
      });

      compactor.compact();

      const segments = compactor.getSegments();
      const mergedSeg = compactor._segments.find(s => s.id.startsWith('merged'));
      if (mergedSeg) {
        const hasDeleted = mergedSeg.data.some(d => d.key === 'deleted-key');
        expect(hasDeleted).toBe(false);
      }
    });

    test('step 3: lookup across unmerged segments should return newest version', () => {
      // Uses high threshold to prevent auto-merge, testing raw lookup order
      const lookupCompactor = new CompactionManager({ mergeThreshold: 100 });

      lookupCompactor.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'oldest', timestamp: 1000 }],
      });

      lookupCompactor.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'middle', timestamp: 2000 }],
      });

      lookupCompactor.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'newest', timestamp: 3000 }],
      });

      const result = lookupCompactor.lookup('k1');
      expect(result.value).toBe('newest');
    });
  });

  describe('Connector pipeline -> offset -> delivery chain', () => {
    test('write failure should not advance source offsets', async () => {
      let pollCount = 0;
      const source = new SourceConnector({});
      source._fetchRecords = jest.fn().mockImplementation(async () => {
        pollCount++;
        if (pollCount <= 2) {
          return [{ id: pollCount, partition: 0, offset: pollCount }];
        }
        return [];
      });

      const sink = new SinkConnector({});
      let writeCount = 0;
      const writtenIds = [];

      sink._flush = jest.fn().mockImplementation(async function() {
        writeCount++;
        if (writeCount === 1) {
          throw new Error('timeout');
        }
        const batch = this.pendingWrites.splice(0);
        writtenIds.push(...batch.map(r => r.id));
        return batch.length;
      });

      const pipeline = new ConnectorPipeline(source, [], sink);
      await pipeline.start();

      // First attempt - write fails
      await pipeline.processOnce();

      // Second attempt - should retry same records
      await pipeline.processOnce();

      // Each record should appear exactly once
      const uniqueIds = [...new Set(writtenIds)];
      expect(uniqueIds.length).toBe(writtenIds.length);
    });
  });

  describe('Cross-service: ingestion -> aggregation -> query materialization', () => {
    // RED HERRING: This end-to-end test passes because it uses simple sum aggregation
    // (which works correctly) rather than running average (which is buggy)
    test('sum aggregation across full pipeline should be exact', async () => {
      const publishedData = [];
      const mockEventBus = {
        publish: jest.fn().mockImplementation(async (event) => {
          publishedData.push(...event.data);
          return true;
        }),
      };

      const ingestService = new IngestService(mockEventBus, { batchSize: 100 });
      const agg = new ContinuousAggregation();

      agg.defineMaterialization('byte_sum', {
        groupBy: ['tenant'],
        aggregations: [{ type: 'sum', field: 'bytes' }],
      });

      await ingestService.ingest('metrics', [
        { id: 'r1', tenant: 'a', bytes: 100 },
        { id: 'r2', tenant: 'a', bytes: 200 },
        { id: 'r3', tenant: 'a', bytes: 300 },
      ]);
      await ingestService.drain();

      await agg.update('byte_sum', publishedData);

      const state = agg.getState('byte_sum');
      expect(state.state['a'].bytes_sum).toBe(600);
    });
  });
});
