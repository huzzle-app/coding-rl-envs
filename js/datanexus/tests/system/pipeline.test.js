/**
 * System Pipeline Tests (~30 tests)
 *
 * End-to-end system tests: full pipeline lifecycle, multi-service coordination
 * Covers cross-cutting concerns, observability, and system-level behaviors
 */

const { StreamProcessor, WindowManager, WatermarkTracker, PartitionManager } = require('../../shared/stream');
const { TransformPipeline, mergeTransformConfig } = require('../../services/transform/src/services/pipeline');
const { RollupEngine } = require('../../services/aggregate/src/services/rollups');
const { QueryEngine } = require('../../services/query/src/services/engine');
const { AlertDetector } = require('../../services/alerts/src/services/detection');
const { TimeSeriesStore } = require('../../services/store/src/services/timeseries');
const { DAGExecutor, CronScheduler, RetryPolicy } = require('../../services/scheduler/src/services/dag');
const { DashboardService } = require('../../services/dashboards/src/services/dashboard');
const { UsageMeter } = require('../../services/billing/src/services/metering');
const { TraceContext, CorrelationContext, Logger } = require('../../shared/utils');

describe('System Pipeline Tests', () => {
  describe('full pipeline lifecycle', () => {
    test('create, start, process, query lifecycle', async () => {
      // 1. Create stream processor
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 600000,
      });

      // 2. Process events
      const events = [
        { source: 's1', timestamp: 1000, value: 10, metric: 'cpu' },
        { source: 's1', timestamp: 2000, value: 20, metric: 'cpu' },
        { source: 's1', timestamp: 3000, value: 30, metric: 'cpu' },
      ];

      for (const e of events) {
        await processor.processEvent(e);
      }
      expect(processor.getStats().processedCount).toBe(3);

      // 3. Aggregate
      const engine = new RollupEngine({ windowSize: 60000 });
      for (const e of events) {
        engine.rollingSum('cpu', e.value);
      }
      const sum = engine.rollingSum('cpu', 0);
      expect(sum).toBe(60);

      // 4. Query
      const mockDb = global.testUtils.mockPg();
      const queryEngine = new QueryEngine(mockDb, { queryTimeout: 5000 });
      const data = events.map((e, i) => ({ ...e, id: i }));
      const filtered = queryEngine.queryTimeRange(data, 1000, 3000);
      expect(filtered.length).toBe(2); // start inclusive, end exclusive
    });

    test('pipeline with transforms and alerts', async () => {
      // Transform
      const pipeline = new TransformPipeline();
      pipeline.addTransform({
        type: 'map',
        mapping: { cpu_percent: 'value' },
        typeCoercion: { cpu_percent: 'number' },
      });

      const record = { value: '85.5' };
      const transformed = await pipeline.execute(record);
      expect(transformed.cpu_percent).toBe(85.5);

      // Alert on transformed value
      const detector = new AlertDetector({ deduplicationWindow: 0 });
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 80, severity: 'warning' });
      const alerts = detector.evaluate('cpu', transformed.cpu_percent);
      expect(alerts.length).toBe(1);
      detector.clearAll();
    });

    test('pipeline DAG execution', async () => {
      const dag = new DAGExecutor();

      const results = [];
      dag.addNode('ingest', { execute: async () => { results.push('ingest'); return { count: 100 }; } });
      dag.addNode('transform', { execute: async () => { results.push('transform'); return { count: 100 }; } });
      dag.addNode('aggregate', { execute: async () => { results.push('aggregate'); return { count: 10 }; } });
      dag.addNode('store', { execute: async () => { results.push('store'); return { count: 10 }; } });

      dag.addEdge('ingest', 'transform');
      dag.addEdge('transform', 'aggregate');
      dag.addEdge('transform', 'store');

      const execResults = await dag.execute();
      expect(execResults.size).toBe(4);
    });
  });

  describe('multi-service coordination', () => {
    test('trace context flows through pipeline', () => {
      const trace = new TraceContext('trace-pipeline-1', 'span-gateway');

      // Gateway creates trace
      const gatewaySpan = trace.createChildSpan();
      expect(gatewaySpan.parentSpanId).toBe('span-gateway');

      // Passed to transform
      const transformSpan = gatewaySpan.createChildSpan();
      expect(transformSpan.traceId).toBe('trace-pipeline-1');

      // Passed to aggregate
      const aggregateSpan = transformSpan.createChildSpan();
      expect(aggregateSpan.traceId).toBe('trace-pipeline-1');
    });

    test('correlation ID maintained across services', () => {
      const correlationId = 'corr-pipeline-001';
      CorrelationContext.set(correlationId);

      // Simulating service hops
      expect(CorrelationContext.get()).toBe(correlationId);
      CorrelationContext.set(null);
    });

    test('billing metering tracks pipeline usage', () => {
      const meter = new UsageMeter();

      // Pipeline processes data
      meter.recordUsage('tenant-1', 1000, 5 * 1024 * 1024 * 1024);
      const usage = meter.getUsage('tenant-1');
      expect(usage.dataPoints).toBe(1000);
      expect(usage.bytesIngested).toBe(5 * 1024 * 1024 * 1024);

      // Calculate cost
      const cost = meter.calculateCost('tenant-1');
      expect(cost.totalCost).toBeGreaterThan(0);
    });

    test('dashboard reflects pipeline metrics', () => {
      const dashboard = new DashboardService();
      const d = dashboard.create({
        title: 'Pipeline Overview',
        tenantId: 't1',
        widgets: [
          { type: 'chart', title: 'Throughput' },
          { type: 'gauge', title: 'Error Rate' },
        ],
      });

      expect(d.id).toBeDefined();
      expect(d.title).toBe('Pipeline Overview');
    });
  });

  describe('error handling across services', () => {
    test('transform error triggers alert', async () => {
      const pipeline = new TransformPipeline();
      pipeline.addTransform({
        type: 'map',
        mapping: { out: 'nonexistent.path' },
      });

      let errorOccurred = false;
      try {
        await pipeline.execute({ data: 'test' });
      } catch (error) {
        errorOccurred = true;
      }
      expect(errorOccurred).toBe(true);
    });

    test('store failure triggers retry', async () => {
      const retry = new RetryPolicy({ maxRetries: 3, baseDelay: 10, maxDelay: 100 });

      let attempts = 0;
      const storeWithRetry = async () => {
        for (let i = 0; i <= retry.maxRetries; i++) {
          try {
            attempts++;
            if (attempts < 3) throw new Error('temp failure');
            return { success: true };
          } catch (error) {
            if (!retry.shouldRetry(i, error)) throw error;
            await global.testUtils.delay(retry.getDelay(i));
          }
        }
      };

      const result = await storeWithRetry();
      expect(result.success).toBe(true);
      expect(attempts).toBe(3);
    });

    test('cascading failure detection', () => {
      const detector = new AlertDetector({ deduplicationWindow: 0 });
      detector.addRule({ id: 'ingestion-error', metric: 'ingestion_errors', operator: 'gt', threshold: 10, severity: 'warning' });
      detector.addRule({ id: 'transform-error', metric: 'transform_errors', operator: 'gt', threshold: 5, severity: 'critical' });

      // Ingestion errors spike
      detector.evaluate('ingestion_errors', 20);
      // Transform errors follow
      detector.evaluate('transform_errors', 15);

      const active = detector.getActiveAlerts();
      expect(active.length).toBe(2);
      detector.clearAll();
    });
  });

  describe('partition and scaling', () => {
    test('partition rebalance across workers', async () => {
      const pm = new PartitionManager();
      pm.assign('worker-1', ['p0', 'p1', 'p2', 'p3', 'p4', 'p5']);

      // Scale up: add worker
      await pm.rebalance(['worker-1', 'worker-2', 'worker-3']);

      const totalPartitions = ['worker-1', 'worker-2', 'worker-3'].reduce(
        (sum, w) => sum + pm.getAssignment(w).length, 0
      );
      expect(totalPartitions).toBe(6);
    });

    test('window management under scale', () => {
      const wm = new WindowManager({ type: 'tumbling', size: 1000 });

      // Multiple partitions write to windows
      for (let partition = 0; partition < 10; partition++) {
        for (let event = 0; event < 100; event++) {
          const ts = partition * 100000 + event * 10;
          const win = wm.getWindowKey(ts);
          wm.addEvent(win.key, { partition, event });
        }
      }

      expect(wm.windows.size).toBeGreaterThan(10);
    });
  });

  describe('data consistency', () => {
    test('pipeline produces consistent aggregations', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = [10, 20, 30, 40, 50];

      for (const v of values) {
        engine.rollingSum('metric', v);
      }

      const total = engine.rollingSum('metric', 0);
      expect(total).toBe(150);
    });

    test('query results match ingested data', () => {
      const mockDb = global.testUtils.mockPg();
      const queryEngine = new QueryEngine(mockDb, { queryTimeout: 5000 });

      const data = [
        { id: 1, name: 'Alice', age: 30, city: 'NYC' },
        { id: 2, name: 'Bob', age: 25, city: 'LA' },
        { id: 3, name: 'Charlie', age: 35, city: 'NYC' },
      ];

      const nycUsers = queryEngine._applyFilter(data, ['city = NYC'], {});
      expect(nycUsers.length).toBe(2);

      const grouped = queryEngine._applyGroupBy(data, ['city']);
      expect(grouped.length).toBe(2);
    });

    test('percentile calculation matches manual computation', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      const p50 = engine.calculatePercentile(values, 50);
      expect(p50).toBe(5);
    });

    test('histogram bucket counts sum to total', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = Array.from({ length: 100 }, () => Math.random() * 100);
      const result = engine.buildHistogram(values, [25, 50, 75, 100]);

      const totalCount = result.reduce((sum, b) => sum + b.count, 0);
      expect(totalCount).toBe(100);
    });
  });

  describe('system-level observability', () => {
    test('health aggregation test - overall system health', () => {
      const serviceHealth = [
        { service: 'gateway', healthy: true },
        { service: 'ingestion', healthy: true },
        { service: 'transform', healthy: true },
        { service: 'aggregate', healthy: false },
        { service: 'store', healthy: true },
      ];

      const healthyCount = serviceHealth.filter(s => s.healthy).length;
      const totalCount = serviceHealth.length;
      const overallStatus = healthyCount === totalCount ? 'healthy'
        : healthyCount >= totalCount * 0.8 ? 'degraded'
        : 'unhealthy';

      expect(overallStatus).toBe('degraded');
    });

    test('aggregate health test - dependency chain health', () => {
      const dependencyChain = ['gateway', 'ingestion', 'transform', 'store'];
      const health = { gateway: true, ingestion: true, transform: false, store: true };

      let chainHealthy = true;
      for (const service of dependencyChain) {
        if (!health[service]) {
          chainHealthy = false;
          break;
        }
      }
      expect(chainHealthy).toBe(false);
    });

    test('log field conflict test - structured logging fields', () => {
      const logger = new Logger();
      const logEntry = {
        timestamp: new Date().toISOString(),
        level: 'info',
        message: 'Pipeline processed batch',
        service: 'transform',
        pipeline_id: 'p-123',
        batch_size: 1000,
      };

      
      expect(logEntry.timestamp).toBeDefined();
      expect(logEntry.service).toBeDefined();
    });

    test('worker log test - worker context in log entries', () => {
      const logEntry = {
        timestamp: new Date().toISOString(),
        level: 'info',
        message: 'Worker completed task',
        worker_id: 'worker-3',
        task_id: 'task-456',
        duration_ms: 150,
      };

      expect(logEntry.worker_id).toBe('worker-3');
      expect(logEntry.task_id).toBe('task-456');
    });

    test('pipeline metrics exported', () => {
      const processor = new StreamProcessor({
        window: { type: 'tumbling', size: 60000 },
        checkpointInterval: 600000,
      });

      const stats = processor.getStats();
      expect(stats).toHaveProperty('processedCount');
      expect(stats).toHaveProperty('openWindows');
      expect(stats).toHaveProperty('watermarks');
    });

    test('dashboard rendering with safe content', () => {
      const dashboard = new DashboardService();
      const widget = { title: 'System Health', content: '99.9% uptime' };
      const rendered = dashboard.renderWidget(widget);
      expect(rendered).toContain('System Health');
      expect(rendered).toContain('99.9% uptime');
    });
  });

  describe('end-to-end data flow', () => {
    test('ingestion through billing metering', async () => {
      const meter = new UsageMeter();

      // Simulate ingestion of 1000 events, 10MB
      meter.recordUsage('tenant-prod', 1000, 10 * 1024 * 1024);

      // Second batch
      meter.recordUsage('tenant-prod', 500, 5 * 1024 * 1024);

      const usage = meter.getUsage('tenant-prod');
      expect(usage.dataPoints).toBe(1500);
      expect(usage.bytesIngested).toBe(15 * 1024 * 1024);
    });

    test('scheduled pipeline execution', async () => {
      const scheduler = new CronScheduler({ timezone: 'UTC' });
      let executed = false;

      scheduler.schedule('daily-agg', '0 0 * * *', () => {
        executed = true;
      });

      const job = scheduler.getJob('daily-agg');
      expect(job).toBeDefined();
      expect(job.nextRun).toBeInstanceOf(Date);
    });

    test('multiple tenants tracked separately in billing', () => {
      const meter = new UsageMeter();
      meter.recordUsage('tenant-a', 100, 1024);
      meter.recordUsage('tenant-b', 200, 2048);
      meter.recordUsage('tenant-c', 300, 4096);

      expect(meter.getUsage('tenant-a').dataPoints).toBe(100);
      expect(meter.getUsage('tenant-b').dataPoints).toBe(200);
      expect(meter.getUsage('tenant-c').dataPoints).toBe(300);
    });

    test('pipeline DAG with failure recovery', async () => {
      const dag = new DAGExecutor();
      let retryCount = 0;
      dag.addNode('flaky', {
        execute: async () => {
          retryCount++;
          if (retryCount < 2) throw new Error('transient');
          return { ok: true };
        },
      });

      // First attempt fails
      const results = await dag.execute();
      expect(results.get('flaky').status).toBe('failed');
    });

    test('alert state persists across evaluations', () => {
      const detector = new AlertDetector({ deduplicationWindow: 0 });
      detector.addRule({ id: 'r1', metric: 'cpu', operator: 'gt', threshold: 0.5 });
      detector.evaluate('cpu', 0.9);
      detector.evaluate('cpu', 0.3); // recovery
      detector.evaluate('cpu', 0.8); // new alert
      expect(detector.getActiveAlerts().length).toBe(1);
      detector.clearAll();
    });

    test('dashboard CRUD lifecycle', () => {
      const dashboard = new DashboardService();
      const d = dashboard.create({ title: 'Test', tenantId: 't1' });
      expect(d.id).toBeDefined();

      const fetched = dashboard.get(d.id);
      expect(fetched.title).toBe('Test');

      const list = dashboard.list('t1');
      expect(list.length).toBe(1);
    });

    test('query engine parsing round trip', () => {
      const mockDb = global.testUtils.mockPg();
      const queryEngine = new QueryEngine(mockDb, { queryTimeout: 5000 });
      const parsed = queryEngine.parse('SELECT name, age FROM users WHERE age > 25 LIMIT 10');
      expect(parsed.select).toContain('name');
      expect(parsed.from).toBe('users');
      expect(parsed.limit).toBe(10);
    });

    test('store batch insert and query roundtrip', async () => {
      const store = new TimeSeriesStore(global.testUtils.mockPg(), { batchSize: 100 });
      const records = Array.from({ length: 5 }, (_, i) => ({
        timestamp: Date.now() + i * 1000,
        value: i * 10,
      }));
      const insertResult = await store.batchInsert(records);
      expect(insertResult.inserted).toBeDefined();
    });

    test('dashboard with multiple widgets', () => {
      const dashboard = new DashboardService();
      const d = dashboard.create({
        title: 'Multi-Widget',
        tenantId: 't1',
        widgets: [
          { type: 'chart', title: 'CPU' },
          { type: 'chart', title: 'Memory' },
          { type: 'gauge', title: 'Latency' },
          { type: 'table', title: 'Top Errors' },
        ],
      });
      expect(d.widgets.length).toBe(4);
    });

    test('rolling sum integrated with percentile', () => {
      const engine = new RollupEngine({ windowSize: 60000 });
      const values = [];
      for (let i = 0; i < 100; i++) {
        const v = Math.random() * 100;
        engine.rollingSum('metric', v);
        values.push(v);
      }
      const p90 = engine.calculatePercentile(values, 90);
      expect(p90).toBeGreaterThan(0);
    });
  });
});
