/**
 * State Machine Bug Tests
 *
 * Tests for incorrect state transition logic and invariant violations.
 */

describe('State Machine Validation', () => {
  describe('Document Lifecycle Transitions', () => {
    it('published document should not transition directly to draft', () => {
      const { DocumentLifecycle } = require('../../shared/realtime');
      const lifecycle = new DocumentLifecycle('doc-1');

      lifecycle.transition('review', 'author-1');
      lifecycle.transition('approved', 'reviewer-1');
      lifecycle.transition('published', 'admin-1');

      expect(() => lifecycle.transition('draft', 'author-1')).toThrow();
    });

    it('archived to draft should require re-review', () => {
      const { DocumentLifecycle } = require('../../shared/realtime');
      const lifecycle = new DocumentLifecycle('doc-2');

      lifecycle.transition('review', 'author-1');
      lifecycle.transition('approved', 'reviewer-1');
      lifecycle.transition('published', 'admin-1');
      lifecycle.transition('archived', 'admin-1');
      lifecycle.transition('draft', 'author-1');

      expect(lifecycle.approvedBy).toBeNull();
    });

    it('draft should not be directly archivable', () => {
      const { DocumentLifecycle } = require('../../shared/realtime');
      const lifecycle = new DocumentLifecycle('doc-3');

      expect(() => lifecycle.transition('archived', 'admin-1')).toThrow();
    });

    it('full workflow should maintain consistent state', () => {
      const { DocumentLifecycle } = require('../../shared/realtime');
      const lifecycle = new DocumentLifecycle('doc-4');

      expect(lifecycle.getState()).toBe('draft');

      lifecycle.transition('review', 'author-1');
      lifecycle.addReviewer('reviewer-1');
      lifecycle.addReviewer('reviewer-2');
      expect(lifecycle.reviewers).toHaveLength(2);

      lifecycle.transition('approved', 'reviewer-1');
      expect(lifecycle.approvedBy).toBe('reviewer-1');

      lifecycle.transition('published', 'admin-1');
      expect(lifecycle.getState()).toBe('published');

      lifecycle.transition('archived', 'admin-1');
      expect(lifecycle.getState()).toBe('archived');

      const history = lifecycle.getHistory();
      expect(history).toHaveLength(4);
      expect(history[0].from).toBe('draft');
      expect(history[0].to).toBe('review');
    });

    it('canTransition should be consistent with actual transition behavior', () => {
      const { DocumentLifecycle } = require('../../shared/realtime');
      const lifecycle = new DocumentLifecycle('doc-5');

      lifecycle.transition('review', 'author-1');
      lifecycle.transition('approved', 'reviewer-1');
      lifecycle.transition('published', 'admin-1');

      const canGoDraft = lifecycle.canTransition('draft');
      let actuallyCanGoDraft = true;
      try {
        const test = new DocumentLifecycle('test');
        test.transition('review', 'a');
        test.transition('approved', 'r');
        test.transition('published', 'a');
        test.transition('draft', 'a');
      } catch (e) {
        actuallyCanGoDraft = false;
      }

      expect(canGoDraft).toBe(actuallyCanGoDraft);
    });

    it('approval should be cleared when document returns to draft state', () => {
      const { DocumentLifecycle } = require('../../shared/realtime');
      const lifecycle = new DocumentLifecycle('doc-6');

      lifecycle.transition('review', 'author-1');
      lifecycle.transition('approved', 'reviewer-1');
      expect(lifecycle.approvedBy).toBe('reviewer-1');

      lifecycle.transition('review', 'editor-1');
      lifecycle.transition('draft', 'author-1');

      expect(lifecycle.approvedBy).toBeNull();
    });
  });

  describe('Subscription Lifecycle', () => {
    it('cancelled subscription should not issue refund twice', () => {
      const { SubscriptionLifecycle } = require('../../services/billing/src/services/subscription');
      const sub = new SubscriptionLifecycle('sub-1');

      sub.transition('active');

      sub.transition('cancelled');
      expect(sub.wasRefunded()).toBe(true);

      sub.transition('active');

      const refundCountBefore = sub.refundIssued;
      sub.transition('cancelled');

      const cancelHistory = sub.getHistory().filter(h => h.to === 'cancelled');
      expect(cancelHistory).toHaveLength(2);

      expect(sub.refundIssued).toBe(true);
    });

    it('reactivation should reset refund flag', () => {
      const { SubscriptionLifecycle } = require('../../services/billing/src/services/subscription');
      const sub = new SubscriptionLifecycle('sub-2');

      sub.transition('active');
      sub.transition('cancelled');
      expect(sub.wasRefunded()).toBe(true);

      sub.transition('active');
      expect(sub.wasRefunded()).toBe(false);
    });

    it('expired subscription should only allow reactivation', () => {
      const { SubscriptionLifecycle } = require('../../services/billing/src/services/subscription');
      const sub = new SubscriptionLifecycle('sub-3');

      sub.transition('active');
      sub.transition('expired');

      expect(sub.canTransition('active')).toBe(true);
      expect(sub.canTransition('cancelled')).toBe(false);
      expect(sub.canTransition('suspended')).toBe(false);
    });

    it('suspended subscription should be cancellable or reactivatable', () => {
      const { SubscriptionLifecycle } = require('../../services/billing/src/services/subscription');
      const sub = new SubscriptionLifecycle('sub-4');

      sub.transition('active');
      sub.transition('suspended');

      expect(sub.canTransition('active')).toBe(true);
      expect(sub.canTransition('cancelled')).toBe(true);
      expect(sub.canTransition('expired')).toBe(false);
    });

    it('trial should not transition to suspended', () => {
      const { SubscriptionLifecycle } = require('../../services/billing/src/services/subscription');
      const sub = new SubscriptionLifecycle('sub-5');

      expect(() => sub.transition('suspended')).toThrow();
    });
  });

  describe('Bulkhead Isolation State', () => {
    it('should not allow more than maxConcurrent simultaneous executions', async () => {
      const { BulkheadIsolation } = require('../../shared/clients');
      const bulkhead = new BulkheadIsolation(2);

      let concurrent = 0;
      let maxConcurrent = 0;

      const task = () => new Promise(resolve => {
        concurrent++;
        maxConcurrent = Math.max(maxConcurrent, concurrent);
        setTimeout(() => {
          concurrent--;
          resolve();
        }, 50);
      });

      const promises = [];
      for (let i = 0; i < 5; i++) {
        promises.push(bulkhead.execute(task));
      }

      await Promise.all(promises);
      expect(maxConcurrent).toBeLessThanOrEqual(2);
    });

    it('bulkhead stats should accurately reflect current state', async () => {
      const { BulkheadIsolation } = require('../../shared/clients');
      const bulkhead = new BulkheadIsolation(2);

      const resolvers = [];
      const task = () => new Promise(resolve => resolvers.push(resolve));

      bulkhead.execute(task);
      bulkhead.execute(task);
      bulkhead.execute(task);

      await new Promise(r => setTimeout(r, 10));

      const stats = bulkhead.getStats();
      expect(stats.running).toBe(2);
      expect(stats.queued).toBe(1);

      resolvers.forEach(r => r());
      await new Promise(r => setTimeout(r, 10));
    });
  });

  describe('Connection Pool State Machine', () => {
    it('drain should resolve all waiting acquires with null', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(1);

      const conn = await pool.acquire();

      const waiters = [];
      for (let i = 0; i < 3; i++) {
        waiters.push(pool.acquire());
      }

      pool.drain();

      const results = await Promise.all(waiters);
      expect(results.every(r => r === null)).toBe(true);

      pool.release(conn);
    });

    it('pool should be usable after drain and release', async () => {
      const { ConnectionPool } = require('../../shared/realtime');
      const pool = new ConnectionPool(2);

      const conn1 = await pool.acquire();
      const conn2 = await pool.acquire();

      pool.drain();

      pool.release(conn1);
      pool.release(conn2);

      const newConn = await pool.acquire();
      expect(newConn).toBeDefined();
      expect(newConn).not.toBeNull();
    });
  });

  describe('Session Manager State', () => {
    it('ended sessions should not appear in active sessions', () => {
      const { SessionManager } = require('../../services/presence/src/services/presence');
      const mgr = new SessionManager();

      const s1 = mgr.createSession('user-1');
      const s2 = mgr.createSession('user-2');
      mgr.endSession(s1);

      const active = mgr.getActiveSessions();
      expect(active).toHaveLength(1);
      expect(active[0].userId).toBe('user-2');
    });

    it('stale session cleanup should not remove recently heartbeated sessions', () => {
      const { SessionManager } = require('../../services/presence/src/services/presence');
      const mgr = new SessionManager({ heartbeatTimeout: 100 });

      const s1 = mgr.createSession('user-1');
      const s2 = mgr.createSession('user-2');

      const session1 = mgr.sessions.get(s1);
      session1.lastHeartbeat = Date.now() - 200;

      mgr.heartbeat(s2);

      const removed = mgr.cleanupStaleSessions();
      expect(removed).toContain(s1);
      expect(removed).not.toContain(s2);
      expect(mgr.getSessionCount()).toBe(1);
    });

    it('session exactly at heartbeat boundary should not be cleaned up', () => {
      const { SessionManager } = require('../../services/presence/src/services/presence');
      const mgr = new SessionManager({ heartbeatTimeout: 1000 });

      const s1 = mgr.createSession('user-1');
      const session = mgr.sessions.get(s1);
      session.lastHeartbeat = Date.now() - 1000;

      const removed = mgr.cleanupStaleSessions();
      expect(removed).not.toContain(s1);
    });
  });
});
