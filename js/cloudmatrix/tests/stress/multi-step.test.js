/**
 * Multi-Step Bug Tests
 *
 * Tests where fixing one issue reveals another hidden bug.
 */

describe('Multi-Step Bug Chains', () => {
  describe('CircuitBreaker Threshold → Retry Budget', () => {
    it('circuit should open at exactly failureThreshold failures', () => {
      const { CircuitBreaker } = require('../../shared/clients');
      const breaker = new CircuitBreaker({ failureThreshold: 3, resetTimeout: 1000 });

      for (let i = 0; i < 3; i++) {
        breaker._onFailure();
      }

      expect(breaker.getState()).toBe('open');
    });

    it('retry budget should correctly track cumulative failures across resets', async () => {
      const { CircuitBreaker } = require('../../shared/clients');
      const breaker = new CircuitBreaker({
        failureThreshold: 3,
        resetTimeout: 50,
        maxRetryBudget: 10,
      });

      for (let i = 0; i < 3; i++) {
        breaker._onFailure();
      }
      expect(breaker.getState()).toBe('open');

      await new Promise(r => setTimeout(r, 100));

      try {
        await breaker.execute(async () => 'success');
      } catch (e) {}

      breaker._onSuccess();

      for (let i = 0; i < 3; i++) {
        breaker._onFailure();
      }

      expect(breaker.retryBudget).toBeLessThanOrEqual(4);
    });

    it('retry budget should decrement monotonically with each failure', () => {
      const { CircuitBreaker } = require('../../shared/clients');
      const breaker = new CircuitBreaker({
        failureThreshold: 10,
        maxRetryBudget: 100,
      });

      const budgets = [];
      for (let i = 0; i < 5; i++) {
        breaker._onFailure();
        budgets.push(breaker.retryBudget);
      }

      breaker._onSuccess();

      for (let i = 0; i < 3; i++) {
        breaker._onFailure();
        budgets.push(breaker.retryBudget);
      }

      for (let i = 1; i < budgets.length; i++) {
        expect(budgets[i]).toBeLessThanOrEqual(budgets[i - 1]);
      }
    });
  });

  describe('Autocomplete Cache → Sort Order', () => {
    it('autocomplete suggestions should be sorted by relevance descending', async () => {
      const { SearchService } = require('../../services/search/src/services/search');
      const svc = new SearchService();

      svc._fetchSuggestions = async () => [
        { text: 'javascript', score: 100, createdAt: 1000 },
        { text: 'java', score: 50, createdAt: 3000 },
        { text: 'json', score: 200, createdAt: 2000 },
      ];

      svc.autocompleteCache.clear();

      const result = await svc.autocomplete('j');

      expect(result.suggestions[0].score).toBeGreaterThanOrEqual(result.suggestions[1].score);
      expect(result.suggestions[1].score).toBeGreaterThanOrEqual(result.suggestions[2].score);
    });

    it('autocomplete should return fresh results after cache invalidation', async () => {
      const { SearchService } = require('../../services/search/src/services/search');
      const svc = new SearchService();

      let callCount = 0;
      svc._fetchSuggestions = async () => {
        callCount++;
        return [{ text: `result-${callCount}`, score: 1, createdAt: Date.now() }];
      };

      await svc.autocomplete('test');
      const result1 = await svc.autocomplete('test');

      svc.autocompleteCache.delete('test');

      const result2 = await svc.autocomplete('test');
      expect(result2.suggestions[0].text).not.toBe(result1.suggestions[0].text);
    });
  });

  describe('Saga Compensation Order', () => {
    it('saga should compensate in reverse order on failure', async () => {
      const { SagaOrchestrator } = require('../../shared/events');
      const saga = new SagaOrchestrator();

      const compensationOrder = [];
      const steps = [
        {
          execute: async () => 'step-1-done',
          compensate: async () => compensationOrder.push('compensate-1'),
        },
        {
          execute: async () => 'step-2-done',
          compensate: async () => compensationOrder.push('compensate-2'),
        },
        {
          execute: async () => { throw new Error('step-3-failed'); },
          compensate: async () => compensationOrder.push('compensate-3'),
        },
      ];

      await expect(saga.executeSaga('saga-1', steps)).rejects.toThrow();

      expect(compensationOrder).toEqual(['compensate-2', 'compensate-1']);
    });

    it('saga should only compensate completed steps', async () => {
      const { SagaOrchestrator } = require('../../shared/events');
      const saga = new SagaOrchestrator();

      const compensated = [];
      const steps = [
        {
          execute: async () => 'done',
          compensate: async () => compensated.push('step-1'),
        },
        {
          execute: async () => { throw new Error('fail'); },
          compensate: async () => compensated.push('step-2'),
        },
        {
          execute: async () => 'never-reached',
          compensate: async () => compensated.push('step-3'),
        },
      ];

      await expect(saga.executeSaga('saga-2', steps)).rejects.toThrow();
      expect(compensated).not.toContain('step-3');
    });

    it('saga compensation state should be isolated between executions', async () => {
      const { SagaOrchestrator } = require('../../shared/events');
      const saga = new SagaOrchestrator();

      const firstCompensations = [];
      await expect(saga.executeSaga('saga-a', [
        {
          execute: async () => 'ok',
          compensate: async () => firstCompensations.push('a-1'),
        },
        {
          execute: async () => { throw new Error('fail'); },
          compensate: async () => firstCompensations.push('a-2'),
        },
      ])).rejects.toThrow();

      const secondCompensations = [];
      await expect(saga.executeSaga('saga-b', [
        {
          execute: async () => { throw new Error('fail'); },
          compensate: async () => secondCompensations.push('b-1'),
        },
      ])).rejects.toThrow();

      expect(secondCompensations).not.toContain('a-1');
      expect(secondCompensations).not.toContain('a-2');
    });
  });

  describe('Event Replay Buffer Ordering', () => {
    it('merged partitions should be ordered by timestamp not by id', () => {
      const { EventReplayBuffer } = require('../../shared/events');
      const buffer = new EventReplayBuffer();

      buffer.addEvent({ id: 'z-event', timestamp: 100, data: 'first' }, 'partition-a');
      buffer.addEvent({ id: 'a-event', timestamp: 200, data: 'second' }, 'partition-b');
      buffer.addEvent({ id: 'm-event', timestamp: 150, data: 'middle' }, 'partition-a');

      const merged = buffer.mergePartitions();

      expect(merged[0].timestamp).toBe(100);
      expect(merged[1].timestamp).toBe(150);
      expect(merged[2].timestamp).toBe(200);
    });

    it('events from same partition should maintain insertion order', () => {
      const { EventReplayBuffer } = require('../../shared/events');
      const buffer = new EventReplayBuffer();

      buffer.addEvent({ id: '3', timestamp: 300, data: 'third' }, 'p1');
      buffer.addEvent({ id: '1', timestamp: 100, data: 'first' }, 'p1');
      buffer.addEvent({ id: '2', timestamp: 200, data: 'second' }, 'p1');

      const partitionEvents = buffer.getPartitionEvents('p1');

      expect(partitionEvents[0].timestamp).toBe(300);
      expect(partitionEvents[1].timestamp).toBe(100);
      expect(partitionEvents[2].timestamp).toBe(200);
    });
  });

  describe('Document Merge → Version Comparison', () => {
    it('three-way merge should flag conflicting changes as conflicts', () => {
      const { ThreeWayMerge } = require('../../services/documents/src/services/document');
      const merger = new ThreeWayMerge();

      const base = { title: 'Original', status: 'draft' };
      const ours = { title: 'Our Title', status: 'review' };
      const theirs = { title: 'Their Title', status: 'published' };

      const { result, conflicts } = merger.merge(base, ours, theirs);

      expect(conflicts).toContain('title');
      expect(conflicts).toContain('status');
    });

    it('version comparison should use numeric ordering', () => {
      const { DocumentVersionManager } = require('../../services/documents/src/services/document');
      const mgr = new DocumentVersionManager();

      mgr.addVersion({ version: 2, content: 'v2' });
      mgr.addVersion({ version: 10, content: 'v10' });
      mgr.addVersion({ version: 1, content: 'v1' });

      const latest = mgr.getLatestVersion();
      expect(latest.version).toBe(10);

      const comparison = mgr.compareVersions('2', '10');
      expect(comparison).toBe(-1);
    });

    it('getVersionsSince should return only newer versions', () => {
      const { DocumentVersionManager } = require('../../services/documents/src/services/document');
      const mgr = new DocumentVersionManager();

      for (let i = 1; i <= 5; i++) {
        mgr.addVersion({ version: i, content: `v${i}` });
      }

      const since3 = mgr.getVersionsSince(3);
      expect(since3).toHaveLength(2);
      expect(since3.every(v => v.version > 3)).toBe(true);
    });
  });

  describe('Subscription Batch → Error Reporting', () => {
    it('batch creation should correctly report failures', async () => {
      const { SubscriptionService } = require('../../services/billing/src/services/subscription');
      const svc = new SubscriptionService();

      let callIndex = 0;
      svc._chargePayment = async () => {
        callIndex++;
        if (callIndex === 2) throw new Error('Payment declined');
        return { id: 'pay-1', amount: 25, status: 'completed' };
      };

      const results = await svc.batchCreateSubscriptions([
        { userId: 'u1', plan: 'pro', billingCycle: 'monthly' },
        { userId: 'u2', plan: 'pro', billingCycle: 'monthly' },
        { userId: 'u3', plan: 'pro', billingCycle: 'monthly' },
      ]);

      const failedItems = results.filter(r => !r.success || !r.data);
      expect(failedItems.length).toBeGreaterThan(0);
      expect(failedItems[0].success).toBe(false);
    });
  });
});
