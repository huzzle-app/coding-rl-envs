/**
 * Integration Bug Tests
 *
 * Tests that only manifest when multiple services interact:
 * contract violations, protocol mismatches, cascading failures,
 * and cross-service state inconsistencies.
 */

const { IngestService } = require('../../services/ingestion/src/services/ingest');
const { StreamAggregator, ContinuousAggregation, RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { AlertDetector, AlertStateMachine, FlappingDetector, AlertCorrelationEngine } = require('../../services/alerts/src/services/detection');
const { UsageMeter, BillingStateMachine, UsageAggregator } = require('../../services/billing/src/services/metering');
const { ContentBasedRouter, LoadBalancedRouter } = require('../../services/router/src/services/routing');
const { ConnectorPipeline, SchemaEvolutionManager, SourceConnector, SinkConnector, ConnectorSchemaRegistry } = require('../../services/connectors/src/services/framework');
const { DAGExecutor, JobStateMachine, ConcurrentJobPool } = require('../../services/scheduler/src/services/dag');
const { WriteAheadLog, CompactionManager } = require('../../services/store/src/services/timeseries');
const { QueryEngine, MaterializedViewManager } = require('../../services/query/src/services/engine');

describe('Integration Bugs', () => {
  describe('Ingestion -> Aggregation pipeline', () => {
    test('ingested records should flow correctly through stream aggregator', async () => {
      const publishedData = [];
      const mockEventBus = {
        publish: jest.fn().mockImplementation(async (event) => {
          publishedData.push(...event.data);
          return true;
        }),
      };

      const ingestService = new IngestService(mockEventBus, { batchSize: 5 });
      const aggregator = new StreamAggregator({ windowDuration: 60000, allowedLateness: 5000 });

      // Ingest records
      const now = Date.now();
      const records = [];
      for (let i = 0; i < 10; i++) {
        records.push({ id: `r-${i}`, timestamp: now + i * 1000, value: (i + 1) * 10 });
      }

      await ingestService.ingest('pipeline-1', records);
      await ingestService.drain();

      // Feed published records to aggregator
      for (const record of publishedData) {
        aggregator.addEvent(record);
      }

      // Advance watermark to emit window
      const emissions = aggregator.advanceWatermark(now + 120000);

      // Should have aggregated all records
      expect(emissions.length).toBeGreaterThan(0);
      const totalCount = emissions.reduce((sum, e) => sum + e.count, 0);
      expect(totalCount).toBe(10);

      // Sum should be 10 + 20 + ... + 100 = 550
      const totalSum = emissions.reduce((sum, e) => sum + e.sum, 0);
      expect(totalSum).toBe(550);
    });

    test('continuous aggregation running average fed from ingestion should be correct', async () => {
      const publishedData = [];
      const mockEventBus = {
        publish: jest.fn().mockImplementation(async (event) => {
          publishedData.push(...event.data);
          return true;
        }),
      };

      const ingestService = new IngestService(mockEventBus, { batchSize: 100 });
      const agg = new ContinuousAggregation();

      agg.defineMaterialization('cpu_avg', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'cpu' }],
      });

      // Ingest CPU metrics across multiple batches
      await ingestService.ingest('metrics', [
        { id: 'r1', host: 'server-1', cpu: 10 },
        { id: 'r2', host: 'server-1', cpu: 20 },
        { id: 'r3', host: 'server-1', cpu: 30 },
        { id: 'r4', host: 'server-1', cpu: 40 },
        { id: 'r5', host: 'server-1', cpu: 50 },
      ]);
      await ingestService.drain();

      // Feed to continuous aggregation
      await agg.update('cpu_avg', publishedData);

      const state = agg.getState('cpu_avg');
      const avg = state.state['server-1'].cpu_avg;

      // True average of 10, 20, 30, 40, 50 is 30
      expect(avg).toBeCloseTo(30, 1);
    });
  });

  describe('Alert -> Billing integration', () => {
    test('alert state transitions should generate billing events', () => {
      const alertSM = new AlertStateMachine();
      const billingSM = new BillingStateMachine();
      const meter = new UsageMeter();

      // Create alert and track billing
      alertSM.createAlert('alert-1', { severity: 'critical' });

      // Each state transition should be metered
      alertSM.transition('alert-1', 'firing');
      meter.recordUsage('tenant-1', 1, 0);

      alertSM.transition('alert-1', 'acknowledged', { userId: 'user-1' });
      meter.recordUsage('tenant-1', 1, 0);

      alertSM.transition('alert-1', 'resolved');
      meter.recordUsage('tenant-1', 1, 0);

      const usage = meter.getUsage('tenant-1');
      expect(usage.dataPoints).toBe(3);
    });

    test('flapping alert suppression should not generate billing for suppressed alerts', () => {
      const flappingDetector = new FlappingDetector({ windowSize: 300000, threshold: 3 });
      const meter = new UsageMeter();
      let billedAlerts = 0;

      // Simulate flapping
      const transitions = [
        ['pending', 'firing'],
        ['firing', 'resolved'],
        ['resolved', 'firing'],
        ['firing', 'resolved'],
      ];

      for (const [from, to] of transitions) {
        flappingDetector.recordTransition('alert-1', from, to);

        // Only bill if not suppressed
        const suppression = flappingDetector.suppressIfFlapping('alert-1');
        if (!suppression.suppressed) {
          meter.recordUsage('tenant-1', 1, 0);
          billedAlerts++;
        }
      }

      // Should have stopped billing after flapping detected (threshold: 3)
      expect(billedAlerts).toBeLessThan(transitions.length);
    });

    test('billing refund should use original paid amount not modified amount', () => {
      const billingSM = new BillingStateMachine();
      const meter = new UsageMeter();

      billingSM.createInvoice('inv-1', { amount: 500 });
      billingSM.transition('inv-1', 'pending');
      billingSM.transition('inv-1', 'processing');
      billingSM.transition('inv-1', 'paid');

      // Record the paid amount
      const paidAmount = billingSM.getInvoice('inv-1').amount;

      // Simulate post-payment credit adjustment
      const invoice = billingSM.getInvoice('inv-1');
      invoice.amount = 300; // Modified after payment

      // Issue refund
      billingSM.transition('inv-1', 'refunded');

      // Refund should be for the original 500, not the modified 300
      expect(billingSM.getInvoice('inv-1').refundAmount).toBe(paidAmount);
    });
  });

  describe('Query -> Aggregation -> Materialized View', () => {
    test('materialized view refresh should use fresh query data', async () => {
      const mockDb = {
        query: jest.fn()
          .mockResolvedValueOnce({ rows: [{ id: 1, cpu: 50 }] })
          .mockResolvedValueOnce({ rows: [{ id: 1, cpu: 80 }] }),
      };

      const engine = new QueryEngine(mockDb);
      const mvManager = new MaterializedViewManager(engine);

      mvManager.createView('cpu_view', 'SELECT id, cpu FROM metrics', { refreshInterval: 1000 });

      // First refresh
      const data1 = await mvManager.refreshView('cpu_view');
      expect(data1).toEqual([{ id: 1, cpu: 50 }]);

      // Invalidate and refresh - should get fresh data
      mvManager.invalidateView('cpu_view');
      const data2 = await mvManager.refreshView('cpu_view');
      expect(data2).toEqual([{ id: 1, cpu: 80 }]);
    });

    test('invalidation of parent view should cascade to child views', async () => {
      const mockDb = { query: jest.fn().mockResolvedValue({ rows: [{ id: 1 }] }) };
      const engine = new QueryEngine(mockDb);
      const mvManager = new MaterializedViewManager(engine);

      mvManager.createView('base', 'SELECT * FROM raw_metrics');
      mvManager.createView('summary', 'SELECT * FROM base_agg', { dependencies: ['base'] });
      mvManager.createView('dashboard', 'SELECT * FROM summary_agg', { dependencies: ['summary'] });

      // Refresh all
      await mvManager.refreshView('base');
      await mvManager.refreshView('summary');
      await mvManager.refreshView('dashboard');

      expect(mvManager.getView('base').state).toBe('fresh');
      expect(mvManager.getView('summary').state).toBe('fresh');
      expect(mvManager.getView('dashboard').state).toBe('fresh');

      // Invalidate base - should cascade to summary and dashboard
      mvManager.invalidateView('base');

      expect(mvManager.getView('base').state).toBe('stale');
      expect(mvManager.getView('summary').state).toBe('stale');
      expect(mvManager.getView('dashboard').state).toBe('stale');
    });
  });

  describe('Router -> Connector pipeline', () => {
    test('high priority rules should be evaluated before low priority', async () => {
      const router = new ContentBasedRouter();

      router.addRule({
        name: 'catch-all',
        condition: (msg) => msg.type === 'event',
        destination: 'general-queue',
        priority: 1,
      });

      router.addRule({
        name: 'critical-events',
        condition: (msg) => msg.type === 'event' && msg.severity === 'critical',
        destination: 'priority-queue',
        priority: 10,
      });

      const criticalMsg = { type: 'event', severity: 'critical' };
      const result = await router.route(criticalMsg);

      // Critical events should go to priority-queue, not general-queue
      expect(result.destination).toBe('priority-queue');
      expect(result.rule).toBe('critical-events');
    });

    test('pipeline transform error should not write untransformed data to sink', async () => {
      const source = new SourceConnector({});
      source._fetchRecords = jest.fn().mockResolvedValueOnce([
        { id: 1, value: 'sensitive-raw', partition: 0, offset: 1 },
      ]).mockResolvedValue([]);

      const sink = new SinkConnector({});
      const writtenRecords = [];
      sink._flush = jest.fn().mockImplementation(async function() {
        writtenRecords.push(...this.pendingWrites.splice(0));
      });

      const failingTransform = async (record) => {
        throw new Error('Transform validation failed');
      };

      const pipeline = new ConnectorPipeline(source, [failingTransform], sink);
      pipeline.setErrorHandler(jest.fn());
      await pipeline.start();
      await pipeline.processOnce();

      // Should NOT have written the untransformed raw data
      const hasRaw = writtenRecords.some(r => r.value === 'sensitive-raw');
      expect(hasRaw).toBe(false);
    });
  });

  describe('Scheduler -> Store pipeline', () => {
    test('DAG execution should write results to WAL in order', async () => {
      const wal = new WriteAheadLog({ maxEntries: 100 });
      const executionOrder = [];

      const dag = new DAGExecutor();

      dag.addNode('extract', {
        execute: async () => {
          executionOrder.push('extract');
          const lsn = wal.append({
            operation: 'extract',
            data: { rows: 100 },
            tableName: 'staging',
          });
          wal.commit(lsn);
          return { lsn, rows: 100 };
        },
      });

      dag.addNode('transform', {
        execute: async () => {
          executionOrder.push('transform');
          const lsn = wal.append({
            operation: 'transform',
            data: { rows: 95 },
            tableName: 'staging',
          });
          wal.commit(lsn);
          return { lsn, rows: 95 };
        },
      });

      dag.addNode('load', {
        execute: async () => {
          executionOrder.push('load');
          const lsn = wal.append({
            operation: 'load',
            data: { rows: 95 },
            tableName: 'final',
          });
          wal.commit(lsn);
          return { lsn, rows: 95 };
        },
      });

      dag.addEdge('transform', 'extract');
      dag.addEdge('load', 'transform');

      const results = await dag.execute();

      expect(executionOrder).toEqual(['extract', 'transform', 'load']);
      expect(results.get('load').status).toBe('completed');

      // WAL should have 3 entries in order
      const recovered = wal.recover(0);
      expect(recovered.length).toBe(3);
      expect(recovered[0].operation).toBe('extract');
      expect(recovered[1].operation).toBe('transform');
      expect(recovered[2].operation).toBe('load');
    });
  });

  describe('Billing -> Usage Aggregation pipeline', () => {
    test('end-to-end billing: record usage -> aggregate -> calculate cost', () => {
      const meter = new UsageMeter();
      const aggregator = new UsageAggregator();

      const tenantId = 'tenant-billing-test';

      // Simulate hourly usage over a day
      const dayStart = Math.floor(Date.now() / 86400000) * 86400000;
      for (let hour = 0; hour < 24; hour++) {
        const timestamp = dayStart + hour * 3600000;
        const usage = {
          dataPoints: 1000,
          bytes: 100 * 1024 * 1024, // 100 MB per hour
          queries: 50,
        };

        aggregator.recordHourly(tenantId, timestamp, usage);

        // Also record to usage meter for billing
        meter.recordUsage(tenantId, usage.dataPoints, usage.bytes);
      }

      // Rollup to daily
      aggregator.rollupToDaily(tenantId);

      // Check daily totals
      const daily = aggregator.getDailyUsage(tenantId, dayStart, dayStart);
      expect(daily.length).toBeGreaterThan(0);
      expect(daily[0].dataPoints).toBe(24000);
      expect(daily[0].bytes).toBe(24 * 100 * 1024 * 1024);

      // Calculate cost from meter
      const cost = meter.calculateCost(tenantId);
      expect(cost.totalCost).toBeGreaterThan(0);
      expect(cost.gigabytes).toBeCloseTo(24 * 100 / 1024, 1);
    });

    test('daily usage results should be sorted chronologically', () => {
      const aggregator = new UsageAggregator();
      const tenantId = 'tenant-sort';

      // Record data across 3 days in random order
      const day1 = 1704067200000;
      const day2 = 1704153600000;
      const day3 = 1704240000000;

      aggregator.recordHourly(tenantId, day3, { dataPoints: 300, bytes: 3000, queries: 30 });
      aggregator.recordHourly(tenantId, day1, { dataPoints: 100, bytes: 1000, queries: 10 });
      aggregator.recordHourly(tenantId, day2, { dataPoints: 200, bytes: 2000, queries: 20 });

      aggregator.rollupToDaily(tenantId);

      const results = aggregator.getDailyUsage(tenantId, day1, day3);
      expect(results.length).toBe(3);

      // Results should be in chronological order
      for (let i = 1; i < results.length; i++) {
        expect(results[i].dayStart).toBeGreaterThan(results[i - 1].dayStart);
      }
    });
  });

  describe('Alert correlation -> Router integration', () => {
    test('correlated group severity should reflect highest actual severity', () => {
      const correlator = new AlertCorrelationEngine();

      correlator.addCorrelationRule({
        name: 'infra-alerts',
        metric: 'host.down',
        timeWindow: 600000,
      });

      const now = Date.now();
      const alerts = [
        { id: 'a1', metric: 'host.down', severity: 'critical', timestamp: now },
        { id: 'a2', metric: 'host.down', severity: 'warning', timestamp: now },
        { id: 'a3', metric: 'host.down', severity: 'info', timestamp: now },
      ];

      const groups = correlator.correlate(alerts);
      const infraGroup = groups.find(g => g.rule === 'infra-alerts');

      // Group severity should be 'critical' (highest actual severity)
      expect(infraGroup).toBeDefined();
      expect(infraGroup.severity).toBe('critical');
    });

    test('correlation root cause should be the earliest alert by timestamp', () => {
      const correlator = new AlertCorrelationEngine();

      correlator.addCorrelationRule({
        name: 'disk-alerts',
        metric: 'disk.usage',
        timeWindow: 600000,
      });

      const now = Date.now();
      const alerts = [
        { id: 'a3', metric: 'disk.usage', severity: 'warning', timestamp: now - 5000, createdAt: now - 5000 },
        { id: 'a1', metric: 'disk.usage', severity: 'critical', timestamp: now - 30000, createdAt: now - 30000 },
        { id: 'a2', metric: 'disk.usage', severity: 'warning', timestamp: now - 15000, createdAt: now - 15000 },
      ];

      const groups = correlator.correlate(alerts);
      const diskGroup = groups.find(g => g.rule === 'disk-alerts');

      // Root cause should be alert a1 (earliest at now - 30000), not a3 (first in array)
      expect(diskGroup.rootCause.id).toBe('a1');
    });
  });

  describe('Schema evolution across connector pipeline', () => {
    test('multi-step schema migration should be chained correctly', () => {
      const registry = new ConnectorSchemaRegistry();
      const evolution = new SchemaEvolutionManager(registry);

      // Register migrations v1->v2 and v2->v3
      evolution.registerMigration('events', 1, 2, (record) => ({
        ...record,
        fullName: `${record.firstName} ${record.lastName}`,
      }));

      evolution.registerMigration('events', 2, 3, (record) => ({
        ...record,
        email: record.email?.toLowerCase(),
        version: 3,
      }));

      // Migrate from v1 directly to v3 - should chain through v2
      const v1Record = { firstName: 'John', lastName: 'Doe', email: 'John@Example.com' };
      const migrated = evolution.evolve('events', v1Record, 1, 3);

      expect(migrated.fullName).toBe('John Doe');
      expect(migrated.email).toBe('john@example.com');
      expect(migrated.version).toBe(3);
    });

    test('pipeline with schema transform should produce correct output', async () => {
      const registry = new ConnectorSchemaRegistry();
      const evolution = new SchemaEvolutionManager(registry);

      evolution.registerMigration('events', 1, 2, (record) => ({
        ...record,
        unit: record.unit || 'unknown',
        _schemaVersion: 2,
      }));

      const source = new SourceConnector({});
      source._fetchRecords = jest.fn().mockResolvedValueOnce([
        { id: 1, partition: 0, offset: 1, name: 'cpu', value: 75, _schemaVersion: 1 },
        { id: 2, partition: 0, offset: 2, name: 'memory', value: 60, _schemaVersion: 2, unit: 'percent' },
      ]).mockResolvedValue([]);

      const sink = new SinkConnector({});
      const writtenRecords = [];
      sink._flush = jest.fn().mockImplementation(async function() {
        writtenRecords.push(...this.pendingWrites.splice(0));
      });

      const migrationTransform = async (record) => {
        if (record._schemaVersion < 2) {
          return evolution.evolve('events', record, record._schemaVersion, 2);
        }
        return record;
      };

      const pipeline = new ConnectorPipeline(source, [migrationTransform], sink);
      await pipeline.start();
      await pipeline.processOnce();

      expect(writtenRecords.length).toBe(2);
      expect(writtenRecords[0].unit).toBe('unknown');
      expect(writtenRecords[0]._schemaVersion).toBe(2);
      expect(writtenRecords[1].unit).toBe('percent');
    });
  });

  describe('Load balancer -> Health check integration', () => {
    test('unhealthy backends should be excluded from routing', () => {
      const router = new LoadBalancedRouter({ strategy: 'round-robin' });

      router.addBackend({ id: 'healthy-1', url: 'http://h1' });
      router.addBackend({ id: 'unhealthy', url: 'http://u1' });
      router.addBackend({ id: 'healthy-2', url: 'http://h2' });

      router.markUnhealthy('unhealthy');

      // Route many requests - none should go to unhealthy backend
      for (let i = 0; i < 20; i++) {
        const selected = router.selectBackend({});
        expect(selected.id).not.toBe('unhealthy');
      }
    });

    test('recovered backend should resume receiving traffic', () => {
      const router = new LoadBalancedRouter({ strategy: 'round-robin' });

      router.addBackend({ id: 'b1', url: 'http://b1' });
      router.addBackend({ id: 'b2', url: 'http://b2' });

      router.markUnhealthy('b1');

      // All traffic goes to b2
      for (let i = 0; i < 5; i++) {
        expect(router.selectBackend({}).id).toBe('b2');
      }

      // Recover b1
      router.markHealthy('b1');

      // Traffic should now go to both
      const selections = new Set();
      for (let i = 0; i < 10; i++) {
        selections.add(router.selectBackend({}).id);
      }

      expect(selections.has('b1')).toBe(true);
      expect(selections.has('b2')).toBe(true);
    });
  });

  describe('Full pipeline: Ingest -> Store -> Query -> Alert', () => {
    test('end-to-end: ingested data should be queryable and trigger alerts', async () => {
      // 1. Ingest records
      const publishedData = [];
      const mockEventBus = {
        publish: jest.fn().mockImplementation(async (event) => {
          publishedData.push(...event.data);
        }),
      };

      const ingestService = new IngestService(mockEventBus, { batchSize: 5 });

      const now = Date.now();
      await ingestService.ingest('metrics', [
        { id: 'r1', timestamp: now, metric: 'cpu', value: 95 },
        { id: 'r2', timestamp: now, metric: 'cpu', value: 92 },
        { id: 'r3', timestamp: now, metric: 'memory', value: 40 },
      ]);
      await ingestService.drain();

      expect(publishedData.length).toBe(3);

      // 2. Store in WAL
      const wal = new WriteAheadLog({ maxEntries: 100 });
      for (const record of publishedData) {
        const lsn = wal.append({
          operation: 'insert',
          data: record,
          tableName: 'metrics',
        });
        wal.commit(lsn);
      }

      // 3. Evaluate alerts
      const detector = new AlertDetector();
      detector.addRule({
        id: 'high-cpu',
        metric: 'cpu',
        operator: 'gt',
        threshold: 90,
        severity: 'critical',
      });

      const alerts = [];
      for (const record of publishedData) {
        const triggered = detector.evaluate(record.metric, record.value);
        alerts.push(...triggered);
      }

      // CPU values 95 and 92 both exceed threshold of 90
      expect(alerts.length).toBeGreaterThanOrEqual(1);
      expect(alerts[0].severity).toBe('critical');
    });
  });

  describe('Compaction -> WAL -> Recovery chain', () => {
    test('compacted data should be consistent with WAL recovery', () => {
      const wal = new WriteAheadLog({ maxEntries: 100 });
      const compactor = new CompactionManager({ mergeThreshold: 2 });

      // Write operations via WAL
      const ops = [
        { key: 'metric-1', value: 10, timestamp: 1000 },
        { key: 'metric-1', value: 20, timestamp: 2000 }, // update
        { key: 'metric-2', value: 30, timestamp: 1500 },
      ];

      for (const op of ops) {
        const lsn = wal.append({
          operation: op.timestamp > 1000 ? 'update' : 'insert',
          data: op,
          tableName: 'metrics',
        });
        wal.commit(lsn);
      }

      // Also store in compaction segments
      compactor.addSegment({
        level: 0,
        data: [{ key: 'metric-1', value: 10, timestamp: 1000 }, { key: 'metric-2', value: 30, timestamp: 1500 }],
      });

      compactor.addSegment({
        level: 0,
        data: [{ key: 'metric-1', value: 20, timestamp: 2000 }],
      });

      compactor.compact();

      // After compaction, metric-1 should reflect the latest value (20)
      const result = compactor.lookup('metric-1');
      expect(result.value).toBe(20);
    });
  });
});
