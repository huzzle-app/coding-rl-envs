/**
 * Latent Bug Tests
 *
 * Tests for bugs that don't directly crash but produce subtly wrong results,
 * corrupt state silently, or compound over time.
 */

const { IngestService } = require('../../services/ingestion/src/services/ingest');
const { WriteAheadLog, CompactionManager } = require('../../services/store/src/services/timeseries');
const { UsageAggregator } = require('../../services/billing/src/services/metering');
const { MaterializedViewManager, QueryOptimizer } = require('../../services/query/src/services/engine');
const { StreamAggregator } = require('../../services/aggregate/src/services/rollups');

describe('Latent Bugs', () => {
  describe('IngestService deduplication', () => {
    test('records with future timestamps should not permanently block their dedup key', () => {
      const service = new IngestService(null, { batchSize: 100 });

      // Record with future timestamp
      const futureTime = Date.now() + 3600000; // 1 hour in future
      const record1 = { id: 'rec-1', deduplicationKey: 'key-1', timestamp: futureTime, value: 1 };
      const result1 = service._deduplicateRecord(record1);
      expect(result1).not.toBeNull();

      // Same key, current timestamp - should NOT be deduplicated since it's a different time
      // But because dedup window uses record timestamp, the future timestamp blocks this key
      const record2 = { id: 'rec-2', deduplicationKey: 'key-1', timestamp: Date.now(), value: 2 };
      const result2 = service._deduplicateRecord(record2);
      expect(result2).not.toBeNull(); // Fails: future timestamp permanently blocks
    });

    test('dedup window calculation should use wall clock not record timestamps', () => {
      const service = new IngestService(null, { batchSize: 100 });

      // Insert record normally
      const record1 = { id: 'rec-1', deduplicationKey: 'dup-key', timestamp: Date.now(), value: 1 };
      service._deduplicateRecord(record1);

      // 70 seconds later (past 60s dedup window) with same key, should be accepted
      const record2 = {
        id: 'rec-2',
        deduplicationKey: 'dup-key',
        timestamp: Date.now() + 70000,
        value: 2,
      };
      const result = service._deduplicateRecord(record2);
      expect(result).not.toBeNull();
    });

    test('schema validation should not coerce boolean "false" string to true', () => {
      const service = new IngestService(null, { batchSize: 100 });
      service.schemaCache.set('pipeline-1', {
        fields: { active: 'boolean', name: 'string' },
      });

      const record = { active: 'false', name: 'test' };
      const result = service.validateSchema('pipeline-1', record);

      // Boolean("false") === true in JS, which is wrong
      expect(result.active).toBe(false);
    });

    test('schema validation with boolean 0 should coerce to false', () => {
      const service = new IngestService(null, { batchSize: 100 });
      service.schemaCache.set('pipeline-1', {
        fields: { active: 'boolean' },
      });

      const record = { active: 0 };
      const result = service.validateSchema('pipeline-1', record);

      // Boolean(0) === false, which is correct, but Boolean("0") would be true
      expect(result.active).toBe(false);
    });

    test('backpressure should not prevent resume when buffer drains below threshold', async () => {
      const mockEventBus = {
        publish: jest.fn().mockResolvedValue(true),
      };

      const service = new IngestService(mockEventBus, {
        batchSize: 10,
        backpressureThreshold: 20,
      });

      // Fill buffer past threshold
      const records = Array.from({ length: 25 }, (_, i) => ({ id: `r-${i}`, value: i }));
      await service.ingest('p1', records);

      expect(service._ingestionState).toBe('paused');

      // Drain the buffer
      await service.drain();

      // Should be accepting again
      expect(service._ingestionState).toBe('accepting');

      // New records should be accepted
      const result = await service.ingest('p1', [{ id: 'new', value: 100 }]);
      expect(result.accepted).toBe(1);
    });
  });

  describe('WriteAheadLog silent data loss', () => {
    test('WAL truncation should not remove uncommitted entries', () => {
      const wal = new WriteAheadLog({ maxEntries: 5 });

      // Append entries, commit some
      const lsns = [];
      for (let i = 0; i < 5; i++) {
        lsns.push(wal.append({ operation: 'insert', data: { id: i }, tableName: 'metrics' }));
      }

      // Commit first 3
      wal.commit(lsns[0]);
      wal.commit(lsns[1]);
      wal.commit(lsns[2]);

      // Append more entries (triggers truncation)
      const newLsn = wal.append({ operation: 'insert', data: { id: 'new' }, tableName: 'metrics' });

      // Uncommitted entries 3 and 4 should still exist
      const entry3 = wal.getEntry(lsns[3]);
      const entry4 = wal.getEntry(lsns[4]);
      expect(entry3).toBeDefined();
      expect(entry4).toBeDefined();
      expect(entry3.committed).toBe(false);
      expect(entry4.committed).toBe(false);
    });

    test('checkpoint should only remove entries before checkpoint LSN', () => {
      const wal = new WriteAheadLog({ maxEntries: 100 });

      const lsn1 = wal.append({ operation: 'insert', data: { a: 1 }, tableName: 't1' });
      const lsn2 = wal.append({ operation: 'insert', data: { a: 2 }, tableName: 't1' });
      const lsn3 = wal.append({ operation: 'insert', data: { a: 3 }, tableName: 't1' });

      // Commit 1 and 3 (not 2)
      wal.commit(lsn1);
      wal.commit(lsn3);

      const checkpointLsn = wal.checkpoint();

      // After checkpoint, entry 2 (uncommitted) should remain
      expect(wal.getUncommitted().length).toBe(1);
      expect(wal.getUncommitted()[0].lsn).toBe(lsn2);

      // Entry 3 was committed but recent - should still be available for recovery
      // But checkpoint removes ALL committed entries
      const recovered = wal.recover(lsn3);
      expect(recovered.length).toBeGreaterThan(0);
    });

    test('recovery after truncation should include all necessary entries', () => {
      const wal = new WriteAheadLog({ maxEntries: 3 });

      // Append 6 entries (first 3 get truncated)
      for (let i = 0; i < 6; i++) {
        wal.append({ operation: 'insert', data: { id: i }, tableName: 'test' });
      }

      // Recovery from LSN 0 should include all entries, but truncation lost the first ones
      const recovered = wal.recover(0);
      expect(recovered.length).toBe(6);
    });
  });

  describe('CompactionManager deduplication', () => {
    test('merge should keep most recent version of each key', () => {
      const compactor = new CompactionManager({ mergeThreshold: 2 });

      // Add two segments with same key but different values
      compactor.addSegment({
        level: 0,
        data: [
          { key: 'metric-1', value: 10, timestamp: 1000 },
          { key: 'metric-2', value: 20, timestamp: 1000 },
        ],
      });

      compactor.addSegment({
        level: 0,
        data: [
          { key: 'metric-1', value: 50, timestamp: 2000 }, // newer value
          { key: 'metric-3', value: 30, timestamp: 2000 },
        ],
      });

      compactor.compact();

      // metric-1 should have the NEWEST value (50), not the oldest (10)
      const result = compactor.lookup('metric-1');
      expect(result.value).toBe(50);
    });

    test('merge should respect tombstones', () => {
      const compactor = new CompactionManager({ mergeThreshold: 2 });

      compactor.addSegment({
        level: 0,
        data: [{ key: 'deleted-key', value: 100, timestamp: 1000 }],
      });

      compactor.markDeleted('deleted-key');

      compactor.addSegment({
        level: 0,
        data: [{ key: 'other-key', value: 200, timestamp: 2000 }],
      });

      compactor.compact();

      // Deleted key should not appear after compaction
      const result = compactor.lookup('deleted-key');
      expect(result).toBeNull();

      // Other key should be fine
      const other = compactor.lookup('other-key');
      expect(other).not.toBeNull();
    });

    test('lookup should search newest segments first', () => {
      const compactor = new CompactionManager({ mergeThreshold: 10 });

      // Old segment
      compactor.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'old', timestamp: 1000 }],
      });

      // New segment
      compactor.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'new', timestamp: 2000 }],
      });

      // Should find "new" first
      const result = compactor.lookup('k1');
      expect(result.value).toBe('new');
    });
  });

  describe('UsageAggregator rollup correctness', () => {
    test('double rollup should not double-count usage', () => {
      const aggregator = new UsageAggregator();

      const tenantId = 'tenant-1';
      const hour = Math.floor(Date.now() / 3600000) * 3600000;

      // Record hourly usage
      aggregator.recordHourly(tenantId, hour, { dataPoints: 100, bytes: 1000, queries: 5 });
      aggregator.recordHourly(tenantId, hour + 3600000, { dataPoints: 200, bytes: 2000, queries: 10 });

      // First rollup
      aggregator.rollupToDaily(tenantId);

      // Record more hourly usage
      aggregator.recordHourly(tenantId, hour + 7200000, { dataPoints: 50, bytes: 500, queries: 2 });

      // Second rollup - should not double-count the already-rolled-up data
      aggregator.rollupToDaily(tenantId);

      const dayStart = Math.floor(hour / 86400000) * 86400000;
      const daily = aggregator.getDailyUsage(tenantId, dayStart, dayStart);

      // Total should be 350, not 650 (350 + 300 double-counted)
      expect(daily.length).toBeGreaterThan(0);
      expect(daily[0].dataPoints).toBe(350);
    });

    test('daily usage results should be sorted by date', () => {
      const aggregator = new UsageAggregator();

      const tenantId = 'tenant-1';
      const day1 = 1704067200000; // Jan 1, 2024
      const day2 = 1704153600000; // Jan 2, 2024
      const day3 = 1704240000000; // Jan 3, 2024

      // Record out of order
      aggregator.recordHourly(tenantId, day3, { dataPoints: 300, bytes: 3000, queries: 30 });
      aggregator.recordHourly(tenantId, day1, { dataPoints: 100, bytes: 1000, queries: 10 });
      aggregator.recordHourly(tenantId, day2, { dataPoints: 200, bytes: 2000, queries: 20 });

      aggregator.rollupToDaily(tenantId);

      const results = aggregator.getDailyUsage(tenantId, day1, day3);
      expect(results.length).toBe(3);

      // Results should be sorted by date
      for (let i = 1; i < results.length; i++) {
        expect(results[i].dayStart).toBeGreaterThan(results[i - 1].dayStart);
      }
    });
  });

  describe('MaterializedViewManager dependency ordering', () => {
    test('refreshView should refresh dependencies before dependents', async () => {
      const mockDb = { query: jest.fn().mockResolvedValue({ rows: [{ id: 1 }] }) };
      const { QueryEngine } = require('../../services/query/src/services/engine');
      const engine = new QueryEngine(mockDb);
      const mvManager = new MaterializedViewManager(engine);

      const refreshOrder = [];

      // Create views with dependencies
      mvManager.createView('base_view', 'SELECT id FROM metrics', { refreshInterval: 60000 });
      mvManager.createView('derived_view', 'SELECT id FROM metrics', {
        refreshInterval: 60000,
        dependencies: ['base_view'],
      });

      // Override execute to track order
      const origRefresh = mvManager.refreshView.bind(mvManager);
      mvManager.refreshView = async function(name) {
        refreshOrder.push(name);
        return origRefresh(name);
      };

      await mvManager.refreshView('derived_view');

      // base_view should be refreshed before derived_view
      const baseIdx = refreshOrder.indexOf('base_view');
      const derivedIdx = refreshOrder.indexOf('derived_view');
      expect(baseIdx).toBeLessThan(derivedIdx);
    });

    test('invalidation should cascade to dependent views', () => {
      const mockDb = { query: jest.fn().mockResolvedValue({ rows: [] }) };
      const { QueryEngine } = require('../../services/query/src/services/engine');
      const engine = new QueryEngine(mockDb);
      const mvManager = new MaterializedViewManager(engine);

      mvManager.createView('parent', 'SELECT * FROM t1');
      mvManager.createView('child', 'SELECT * FROM t2', { dependencies: ['parent'] });

      // Set both views as fresh
      mvManager.views.get('parent').state = 'fresh';
      mvManager.views.get('parent').data = [{ id: 1 }];
      mvManager.views.get('child').state = 'fresh';
      mvManager.views.get('child').data = [{ id: 2 }];

      // Invalidate parent - child should also be invalidated
      mvManager.invalidateView('parent');

      const parent = mvManager.getView('parent');
      const child = mvManager.getView('child');

      expect(parent.state).toBe('stale');
      expect(child.state).toBe('stale');
    });
  });

  describe('QueryOptimizer cost estimation', () => {
    test('limit step should account for offset cost', () => {
      const optimizer = new QueryOptimizer();
      optimizer.recordTableStats('metrics', { rowCount: 10000 });

      const planWithOffset = {
        parsed: { from: 'metrics' },
        steps: [
          { type: 'limit', count: 10, offset: 9990 },
        ],
      };

      const planWithoutOffset = {
        parsed: { from: 'metrics' },
        steps: [
          { type: 'limit', count: 10, offset: 0 },
        ],
      };

      const costWithOffset = optimizer.estimateCost(planWithOffset);
      const costWithoutOffset = optimizer.estimateCost(planWithoutOffset);

      // Query with large offset should cost more than without
      expect(costWithOffset.cost).toBeGreaterThan(costWithoutOffset.cost);
    });

    test('join strategy should consider table sizes in bytes not just row count', () => {
      const optimizer = new QueryOptimizer();

      // Small row count but large row size
      optimizer.recordTableStats('wide_table', {
        rowCount: 500,
        avgRowSize: 10000, // 10KB per row = 5MB total
      });

      // Large row count but small row size
      optimizer.recordTableStats('narrow_table', {
        rowCount: 5000,
        avgRowSize: 50, // 50 bytes per row = 250KB total
      });

      const strategy = optimizer.chooseJoinStrategy('wide_table', 'narrow_table');

      // wide_table has fewer rows but is much larger in bytes
      // Hash join on wide_table would be expensive (5MB in memory)
      // Strategy should consider byte size, not just row count
      expect(strategy).not.toBe('nested-loop'); // Both under 1000 rows, but wide_table is huge
    });
  });

  describe('StreamAggregator watermark boundary', () => {
    test('events exactly at watermark minus allowedLateness should be accepted', () => {
      const aggregator = new StreamAggregator({
        allowedLateness: 5000,
        windowDuration: 60000,
      });

      aggregator._watermark = 100000;

      // Event exactly at boundary: watermark(100000) - allowedLateness(5000) = 95000
      const event = { timestamp: 95000, value: 42 };
      const result = aggregator.addEvent(event);

      // Should be accepted (at the boundary), not dropped
      expect(result.status).toBe('added');
    });

    test('window emission should use window end time not start time', () => {
      const aggregator = new StreamAggregator({
        windowDuration: 60000,
        allowedLateness: 0,
      });

      // Add event at time 30000 (falls in window [0, 60000))
      aggregator.addEvent({ timestamp: 30000, value: 10 });

      // Advance watermark past window start (60000) but not past window end
      const results1 = aggregator.advanceWatermark(60000);

      // Window [0, 60000) should NOT emit yet because watermark equals window end
      // In correct implementation, watermark needs to pass window.end
      expect(results1.length).toBe(0);

      // Advance watermark past window end
      const results2 = aggregator.advanceWatermark(60001);
      expect(results2.length).toBe(1);
      expect(results2[0].count).toBe(1);
    });
  });
});
