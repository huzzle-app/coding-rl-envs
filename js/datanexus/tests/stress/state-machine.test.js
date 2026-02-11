/**
 * State Machine Bug Tests
 *
 * Tests for incorrect state transitions, missing guards, skipped states,
 * and invalid terminal state handling across alert, billing, and job systems.
 */

const { AlertStateMachine, FlappingDetector } = require('../../services/alerts/src/services/detection');
const { BillingStateMachine } = require('../../services/billing/src/services/metering');
const { JobStateMachine, ConcurrentJobPool } = require('../../services/scheduler/src/services/dag');

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

      // pending -> firing (valid)
      sm.transition('alert-1', 'firing');
      expect(sm.getAlert('alert-1').state).toBe('firing');

      // firing -> resolved (invalid direct - should go through acknowledged)
      // Actually this IS valid per the transition table
      sm.transition('alert-1', 'resolved');
      expect(sm.getAlert('alert-1').state).toBe('resolved');

      // resolved -> firing (valid - re-fire)
      sm.transition('alert-1', 'firing');
      expect(sm.getAlert('alert-1').state).toBe('firing');

      // firing -> suppressed (invalid!)
      expect(() => {
        sm.transition('alert-1', 'suppressed');
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
      sm.transition('alert-3', 'acknowledged', { userId: 'user-1' });
      sm.transition('alert-3', 'resolved');

      const log = sm.getTransitionLog('alert-3');
      expect(log.length).toBe(3);

      // Verify each transition
      expect(log[0]).toMatchObject({ from: 'pending', to: 'firing' });
      expect(log[1]).toMatchObject({ from: 'firing', to: 'acknowledged' });
      expect(log[2]).toMatchObject({ from: 'acknowledged', to: 'resolved' });
    });

    test('getAlertsByState should return correct alerts', () => {
      const sm = new AlertStateMachine();

      sm.createAlert('a1', { severity: 'warning' });
      sm.createAlert('a2', { severity: 'critical' });
      sm.createAlert('a3', { severity: 'info' });

      sm.transition('a1', 'firing');
      sm.transition('a2', 'firing');
      // a3 stays in 'pending'

      const firing = sm.getAlertsByState('firing');
      expect(firing.length).toBe(2);
      expect(firing.map(a => a.id).sort()).toEqual(['a1', 'a2']);

      const pending = sm.getAlertsByState('pending');
      expect(pending.length).toBe(1);
      expect(pending[0].id).toBe('a3');
    });
  });

  describe('FlappingDetector', () => {
    test('legitimate escalation path should not trigger flapping detection', () => {
      const detector = new FlappingDetector({ windowSize: 300000, threshold: 5 });

      // Legitimate escalation path: pending -> firing -> escalated -> resolved
      // This is 3 transitions, NOT flapping
      detector.recordTransition('alert-1', 'pending', 'firing');
      detector.recordTransition('alert-1', 'firing', 'acknowledged');
      detector.recordTransition('alert-1', 'acknowledged', 'escalated');
      detector.recordTransition('alert-1', 'escalated', 'resolved');

      // 4 transitions, threshold is 5 - should NOT be flapping
      expect(detector.isFlapping('alert-1')).toBe(false);
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
      const invoice = sm.createInvoice('inv-1', { amount: 100 });

      expect(invoice.state).toBe('draft');

      sm.transition('inv-1', 'pending');
      expect(sm.getInvoice('inv-1').state).toBe('pending');

      sm.transition('inv-1', 'processing');
      expect(sm.getInvoice('inv-1').state).toBe('processing');

      sm.transition('inv-1', 'paid');
      const paid = sm.getInvoice('inv-1');
      expect(paid.state).toBe('paid');
      expect(paid.paidAt).toBeDefined();
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
      const sm = new BillingStateMachine();
      sm.createInvoice('inv-4', { amount: 75 });

      sm.transition('inv-4', 'pending');
      sm.transition('inv-4', 'processing');
      sm.transition('inv-4', 'failed');

      // Retry
      sm.transition('inv-4', 'pending');
      expect(sm.getInvoice('inv-4').state).toBe('pending');

      // History should show the full lifecycle
      expect(sm.getInvoice('inv-4').history.length).toBe(4);
    });

    test('terminal states should have no valid transitions', () => {
      const sm = new BillingStateMachine();
      sm.createInvoice('inv-5', { amount: 100 });

      sm.transition('inv-5', 'cancelled');

      expect(() => {
        sm.transition('inv-5', 'pending');
      }).toThrow('Invalid transition');

      expect(() => {
        sm.transition('inv-5', 'draft');
      }).toThrow('Invalid transition');
    });

    test('getInvoicesByState returns correct invoices', () => {
      const sm = new BillingStateMachine();

      sm.createInvoice('inv-a', { amount: 10 });
      sm.createInvoice('inv-b', { amount: 20 });
      sm.createInvoice('inv-c', { amount: 30 });

      sm.transition('inv-a', 'pending');
      sm.transition('inv-b', 'pending');
      sm.transition('inv-b', 'processing');

      const pending = sm.getInvoicesByState('pending');
      expect(pending.length).toBe(1);
      expect(pending[0].id).toBe('inv-a');

      const drafts = sm.getInvoicesByState('draft');
      expect(drafts.length).toBe(1);
      expect(drafts[0].id).toBe('inv-c');
    });
  });

  describe('JobStateMachine', () => {
    test('job lifecycle: created -> queued -> running -> completed', () => {
      const sm = new JobStateMachine();
      const job = sm.createJob('j1', { maxAttempts: 3 });

      expect(job.state).toBe('created');

      sm.transition('j1', 'queued');
      sm.transition('j1', 'running');
      sm.transition('j1', 'completed', { result: { rows: 100 } });

      const completed = sm.getJob('j1');
      expect(completed.state).toBe('completed');
      expect(completed.result).toEqual({ rows: 100 });
      expect(completed.attempts).toBe(1);
    });

    test('paused job can be resumed', () => {
      const sm = new JobStateMachine();
      sm.createJob('j2');

      sm.transition('j2', 'queued');
      sm.transition('j2', 'running');
      sm.transition('j2', 'paused');

      expect(sm.getJob('j2').state).toBe('paused');

      sm.transition('j2', 'running');
      expect(sm.getJob('j2').state).toBe('running');
    });

    test('canTransition returns correct result', () => {
      const sm = new JobStateMachine();
      sm.createJob('j3');

      expect(sm.canTransition('j3', 'queued')).toBe(true);
      expect(sm.canTransition('j3', 'running')).toBe(false);
      expect(sm.canTransition('j3', 'completed')).toBe(false);
    });

    test('invalid transition from created directly to running should fail', () => {
      const sm = new JobStateMachine();
      sm.createJob('j4');

      expect(() => {
        sm.transition('j4', 'running');
      }).toThrow('Invalid job transition');
    });

    test('archived is terminal - no further transitions', () => {
      const sm = new JobStateMachine();
      sm.createJob('j5');

      sm.transition('j5', 'queued');
      sm.transition('j5', 'running');
      sm.transition('j5', 'completed');
      sm.transition('j5', 'archived');

      expect(() => {
        sm.transition('j5', 'queued');
      }).toThrow('Invalid job transition');
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
