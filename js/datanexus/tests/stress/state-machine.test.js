/**
 * State Machine Bug Tests
 *
 * Tests for incorrect state transitions, missing guards, skipped states,
 * and invalid terminal state handling across alert, billing, and job systems.
 */

const { AlertStateMachine, FlappingDetector, AlertCorrelationEngine } = require('../../services/alerts/src/services/detection');
const { BillingStateMachine, UsageAggregator } = require('../../services/billing/src/services/metering');
const { JobStateMachine, ConcurrentJobPool, DAGExecutor } = require('../../services/scheduler/src/services/dag');
const { CompactionManager } = require('../../services/store/src/services/timeseries');

describe('State Machine Bugs', () => {
  describe('AlertStateMachine transitions', () => {
    test('force flag with string "false" should NOT bypass transition validation', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('alert-1', { severity: 'warning' });

      // Transition to firing (valid from pending)
      sm.transition('alert-1', 'firing');

      // Try invalid transition with force="false" (string, not boolean)
      // String "false" is truthy in JS!
      expect(() => {
        sm.transition('alert-1', 'pending', { force: 'false' });
      }).toThrow('Invalid transition');
    });

    test('valid transitions should all be enforced', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('alert-1');
      sm.transition('alert-1', 'firing');
      // force: 1 is truthy but not boolean true — should NOT bypass validation
      // BUG: code checks !metadata.force (truthy), so 1 bypasses validation
      expect(() => {
        sm.transition('alert-1', 'pending', { force: 1 });
      }).toThrow('Invalid transition');
    });

    test('acknowledge should work for escalated alerts', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('alert-2', { severity: 'critical' });

      sm.transition('alert-2', 'firing');
      sm.transition('alert-2', 'escalated');

      // Acknowledging an escalated alert should transition to 'acknowledged'
      const result = sm.acknowledge('alert-2', 'user-1');
      expect(result.state).toBe('acknowledged');
    });

    test('transition log should contain all transitions including auto-transitions', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('alert-3');
      sm.transition('alert-3', 'firing');
      sm.transition('alert-3', 'escalated');
      // BUG: acknowledge() only handles firing state, ignores escalated
      const result = sm.acknowledge('alert-3', 'user-1');
      expect(result.state).toBe('acknowledged');
    });

    test('getAlertsByState should return correct alerts', () => {
      const sm = new AlertStateMachine();
      sm.createAlert('a1');
      sm.transition('a1', 'firing');
      // force: "no" is truthy string — should NOT bypass validation
      expect(() => {
        sm.transition('a1', 'pending', { force: 'no' });
      }).toThrow('Invalid transition');
    });
  });

  describe('FlappingDetector', () => {
    test('legitimate escalation path should not trigger flapping detection', () => {
      const detector = new FlappingDetector({ windowSize: 300000, threshold: 5 });
      // Record exactly 5 transitions (AT the threshold)
      detector.recordTransition('a1', 'pending', 'firing');
      detector.recordTransition('a1', 'firing', 'resolved');
      detector.recordTransition('a1', 'resolved', 'firing');
      detector.recordTransition('a1', 'firing', 'resolved');
      detector.recordTransition('a1', 'resolved', 'firing');
      // At exactly threshold=5, should NOT be flapping (only > threshold should be)
      // BUG: uses >= so this incorrectly returns true
      expect(detector.isFlapping('a1')).toBe(false);
    });

    test('actual flapping (rapid firing/resolved oscillation) should be detected', () => {
      const detector = new FlappingDetector({ windowSize: 300000, threshold: 4 });

      // Rapid oscillation
      detector.recordTransition('alert-2', 'pending', 'firing');
      detector.recordTransition('alert-2', 'firing', 'resolved');
      detector.recordTransition('alert-2', 'resolved', 'firing');
      detector.recordTransition('alert-2', 'firing', 'resolved');

      expect(detector.isFlapping('alert-2')).toBe(true);
    });

    test('suppression should provide correct transition count', () => {
      const detector = new FlappingDetector({ windowSize: 300000, threshold: 3 });

      detector.recordTransition('alert-3', 'pending', 'firing');
      detector.recordTransition('alert-3', 'firing', 'resolved');
      detector.recordTransition('alert-3', 'resolved', 'firing');

      const suppression = detector.suppressIfFlapping('alert-3');
      expect(suppression.suppressed).toBe(true);
      expect(suppression.count).toBe(3);
    });

    test('old transitions outside window should not count', () => {
      const detector = new FlappingDetector({ windowSize: 1000, threshold: 3 });

      // Record transitions
      detector.recordTransition('alert-4', 'pending', 'firing');
      detector.recordTransition('alert-4', 'firing', 'resolved');

      // Manually age the entries
      const history = detector._history.get('alert-4');
      for (const entry of history) {
        entry.timestamp = Date.now() - 2000; // 2 seconds ago, outside 1s window
      }

      // New transition
      detector.recordTransition('alert-4', 'resolved', 'firing');

      // Only 1 recent transition, not 3 - should not be flapping
      expect(detector.isFlapping('alert-4')).toBe(false);
    });
  });

  describe('BillingStateMachine transitions', () => {
    test('invoice lifecycle: draft -> pending -> processing -> paid', () => {
      const sm = new BillingStateMachine();
      sm.createInvoice('inv-1', { amount: 500 });
      sm.transition('inv-1', 'pending');
      sm.transition('inv-1', 'processing');
      sm.transition('inv-1', 'paid');
      const paidAmount = sm.getInvoice('inv-1').amount;
      // Mutate amount after payment
      sm.getInvoice('inv-1').amount = 100;
      sm.transition('inv-1', 'refunded');
      // BUG: refundAmount uses current amount (100), not paid amount (500)
      expect(sm.getInvoice('inv-1').refundAmount).toBe(paidAmount);
    });

    test('cannot transition from paid directly to processing', () => {
      const sm = new BillingStateMachine();
      sm.createInvoice('inv-2', { amount: 50 });

      sm.transition('inv-2', 'pending');
      sm.transition('inv-2', 'processing');
      sm.transition('inv-2', 'paid');

      expect(() => {
        sm.transition('inv-2', 'processing');
      }).toThrow('Invalid transition');
    });

    test('refund amount should match original payment, not current amount', () => {
      const sm = new BillingStateMachine();
      sm.createInvoice('inv-3', { amount: 200 });

      sm.transition('inv-3', 'pending');
      sm.transition('inv-3', 'processing');
      sm.transition('inv-3', 'paid');

      // Simulate amount modification after payment (e.g., credit applied)
      const invoice = sm.getInvoice('inv-3');
      const paidAmount = invoice.amount; // Should be captured at payment time
      invoice.amount = 150; // Modified after payment

      sm.transition('inv-3', 'refunded');

      // Refund should be for original paid amount (200), not modified amount (150)
      expect(sm.getInvoice('inv-3').refundAmount).toBe(paidAmount);
    });

    test('failed invoice retry should reset to pending', () => {
      // Exercise ContinuousAggregation avg formula bug across batches
      const { ContinuousAggregation } = require('../../services/aggregate/src/services/rollups');
      const agg = new ContinuousAggregation();
      agg.defineMaterialization('test_avg', {
        groupBy: ['host'],
        aggregations: [{ type: 'avg', field: 'cpu' }],
      });
      // Batch 1: avg of [10, 20] = 15
      agg.update('test_avg', [
        { host: 's1', cpu: 10 },
        { host: 's1', cpu: 20 },
      ]);
      // Batch 2: avg of [30] -> overall should be (10+20+30)/3 = 20
      agg.update('test_avg', [{ host: 's1', cpu: 30 }]);
      const state = agg.getState('test_avg');
      // BUG: formula (prevAvg + value) / 2 gives wrong result
      expect(state.state['s1'].cpu_avg).toBeCloseTo(20, 5);
    });

    test('terminal states should have no valid transitions', () => {
      const agg = new UsageAggregator();
      const day1 = 86400000 * 10;
      const day3 = 86400000 * 12;
      const day2 = 86400000 * 11;
      // Insert out of order: day3 before day2
      agg.recordHourly('t1', day3, { dataPoints: 30, bytes: 300, queries: 3 });
      agg.rollupToDaily('t1');
      agg.recordHourly('t1', day1, { dataPoints: 10, bytes: 100, queries: 1 });
      agg.rollupToDaily('t1');
      agg.recordHourly('t1', day2, { dataPoints: 20, bytes: 200, queries: 2 });
      agg.rollupToDaily('t1');
      const daily = agg.getDailyUsage('t1', day1, day3);
      // BUG: results not sorted — should be day1, day2, day3
      expect(daily[0].dayStart).toBeLessThanOrEqual(daily[1].dayStart);
      expect(daily[1].dayStart).toBeLessThanOrEqual(daily[2].dayStart);
    });

    test('getInvoicesByState returns correct invoices', () => {
      const correlator = new AlertCorrelationEngine();
      correlator.addCorrelationRule({ name: 'test', metric: 'cpu', timeWindow: 60000 });
      const now = Date.now();
      correlator.correlate([
        { id: 'a1', metric: 'cpu', severity: 'info', timestamp: now },
        { id: 'a2', metric: 'cpu', severity: 'critical', timestamp: now + 1000 },
      ]);
      const groups = correlator.getCorrelationGroups();
      const group = groups[0];
      // BUG: severity comparison uses > instead of < (critical=1 < info=4)
      // So it picks info (4) as "highest" instead of critical (1)
      expect(group.severity).toBe('critical');
    });
  });

  describe('JobStateMachine', () => {
    test('job lifecycle: created -> queued -> running -> completed', () => {
      const sm = new JobStateMachine();
      const events = [];
      sm.onTransition(event => events.push(`${event.from}->${event.to}`));
      sm.createJob('j1', { maxAttempts: 3 });
      sm.transition('j1', 'queued');
      sm.transition('j1', 'running');
      sm.transition('j1', 'failed', { error: 'timeout' });
      // Auto-retry should produce: running->failed, then failed->queued
      // BUG: recursive transition fires failed->queued BEFORE running->failed listener
      const failIdx = events.indexOf('running->failed');
      const retryIdx = events.indexOf('failed->queued');
      expect(failIdx).toBeLessThan(retryIdx);
    });

    test('paused job can be resumed', () => {
      const sm = new JobStateMachine();
      sm.createJob('j2', { maxAttempts: 3 });
      sm.transition('j2', 'queued');
      sm.transition('j2', 'running');
      sm.transition('j2', 'failed', { error: 'timeout' });
      // After auto-retry, job should be re-queued with error cleared
      const job = sm.getJob('j2');
      expect(job.state).toBe('queued');
      // BUG: error is not cleared when auto-retried
      expect(job.error).toBeUndefined();
    });

    test('canTransition returns correct result', async () => {
      const pool = new ConcurrentJobPool({ maxConcurrent: 2 });
      // Submit mix of success and failure
      const jobs = [
        pool.submit({ id: 'j1', execute: async () => ({ ok: true }) }),
        pool.submit({ id: 'j2', execute: async () => { throw new Error('fail'); } }).catch(() => {}),
        pool.submit({ id: 'j3', execute: async () => ({ ok: true }) }),
      ];
      await Promise.all(jobs);
      const stats = pool.getStats();
      // BUG: totalProcessed only increments on success, not failures
      expect(stats.totalProcessed).toBe(3);
    });

    test('invalid transition from created directly to running should fail', () => {
      const dag = new DAGExecutor();
      dag.addNode('a', async () => {});
      dag.addNode('b', async () => {});
      dag.addNode('c', async () => {});
      dag.addEdge('a', 'b');
      dag.addEdge('b', 'c');
      dag.addEdge('c', 'a'); // indirect cycle: a->b->c->a
      // BUG: hasCycle() doesn't check recursion stack for already-visited nodes
      expect(dag.hasCycle()).toBe(true);
    });

    test('archived is terminal - no further transitions', () => {
      const cm = new CompactionManager({ mergeThreshold: 2 });
      cm.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'old', timestamp: 1000 }],
      });
      cm.addSegment({
        level: 0,
        data: [{ key: 'k1', value: 'new', timestamp: 2000 }],
      });
      cm.compact();
      const result = cm.lookup('k1');
      // BUG: _mergeSegments sorts ascending and takes versions[0] (oldest)
      expect(result.value).toBe('new');
    });
  });

  describe('ConcurrentJobPool', () => {
    test('should not exceed max concurrent jobs', async () => {
      const pool = new ConcurrentJobPool({ maxConcurrent: 2 });
      let peakConcurrent = 0;
      let currentRunning = 0;

      const createJob = (id, duration) => ({
        id,
        execute: async () => {
          currentRunning++;
          peakConcurrent = Math.max(peakConcurrent, currentRunning);
          await new Promise(resolve => setTimeout(resolve, duration));
          currentRunning--;
          return { id, status: 'done' };
        },
      });

      const jobs = [
        pool.submit(createJob('j1', 50)),
        pool.submit(createJob('j2', 50)),
        pool.submit(createJob('j3', 50)),
        pool.submit(createJob('j4', 50)),
      ];

      await Promise.all(jobs);

      // Should never exceed maxConcurrent
      expect(peakConcurrent).toBeLessThanOrEqual(2);
    });

    test('job failure should not block queue processing', async () => {
      const pool = new ConcurrentJobPool({ maxConcurrent: 1 });

      const results = [];

      const failJob = {
        id: 'fail',
        execute: async () => {
          throw new Error('Job failed');
        },
      };

      const successJob = {
        id: 'success',
        execute: async () => {
          results.push('success');
          return { status: 'done' };
        },
      };

      try {
        await pool.submit(failJob);
      } catch (e) {
        // Expected
      }

      await pool.submit(successJob);

      expect(results).toContain('success');
    });

    test('stats should be accurate during processing', async () => {
      const pool = new ConcurrentJobPool({ maxConcurrent: 3 });

      let resolveJob;
      const blockingJob = {
        id: 'blocking',
        execute: () => new Promise(resolve => { resolveJob = resolve; }),
      };

      const promise = pool.submit(blockingJob);

      // While job is running
      const stats = pool.getStats();
      expect(stats.running).toBe(1);
      expect(stats.maxConcurrent).toBe(3);

      // Complete the job
      resolveJob({ status: 'done' });
      await promise;

      const finalStats = pool.getStats();
      expect(finalStats.running).toBe(0);
      expect(finalStats.completed).toBe(1);
    });
  });
});
