/**
 * Analytics Tracking Tests
 *
 * Tests TimeSeriesAggregator, FunnelAnalyzer, CohortTracker from actual source code.
 * Exercises analytics bugs: percentile off-by-one, hardcoded retention, funnel rate calculation.
 */

// Mock express to prevent service index files from starting HTTP servers
jest.mock('express', () => {
  const router = { use: jest.fn(), get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn(), patch: jest.fn() };
  const app = { use: jest.fn().mockReturnThis(), get: jest.fn().mockReturnThis(), post: jest.fn().mockReturnThis(), put: jest.fn().mockReturnThis(), delete: jest.fn().mockReturnThis(), patch: jest.fn().mockReturnThis(), listen: jest.fn((port, cb) => cb && cb()), set: jest.fn().mockReturnThis() };
  const express = jest.fn(() => app);
  express.json = jest.fn(() => jest.fn());
  express.urlencoded = jest.fn(() => jest.fn());
  express.static = jest.fn(() => jest.fn());
  express.Router = jest.fn(() => router);
  return express;
});

const { TimeSeriesAggregator, FunnelAnalyzer, CohortTracker } = require('../../../services/analytics/src/index');

describe('TimeSeriesAggregator', () => {
  let agg;

  beforeEach(() => {
    agg = new TimeSeriesAggregator({ bucketSize: 1000 }); // 1 second buckets
  });

  describe('recording', () => {
    it('should record values into buckets', () => {
      const ts = 5000;
      agg.record('latency', 100, ts);
      agg.record('latency', 200, ts + 500); // Same bucket
      agg.record('latency', 300, ts + 1500); // Next bucket

      const buckets = agg.query('latency', ts, ts + 2000);
      expect(buckets).toHaveLength(2);
      expect(buckets[0].count).toBe(2);
      expect(buckets[0].sum).toBe(300);
    });

    it('should track min and max', () => {
      const ts = 5000;
      agg.record('latency', 10, ts);
      agg.record('latency', 50, ts);
      agg.record('latency', 30, ts);

      const buckets = agg.query('latency', ts, ts + 1000);
      expect(buckets[0].min).toBe(10);
      expect(buckets[0].max).toBe(50);
    });
  });

  describe('average', () => {
    it('should calculate weighted average across buckets', () => {
      const ts = 10000;
      agg.record('latency', 100, ts);
      agg.record('latency', 200, ts);
      agg.record('latency', 300, ts + 1000);

      const avg = agg.getAverage('latency', ts, ts + 2000);
      expect(avg).toBe(200); // (100+200+300) / 3
    });

    it('should return 0 for empty range', () => {
      expect(agg.getAverage('latency', 0, 1000)).toBe(0);
    });
  });

  describe('percentile', () => {
    // BUG: getPercentile uses Math.ceil(percentile / 100 * length) as index
    // For percentile=100 and 10 values, index = Math.ceil(1.0 * 10) = 10
    // But allValues[10] is out of bounds (valid indices are 0-9), returning undefined
    it('should return correct p50 value', () => {
      const ts = 10000;
      for (let i = 1; i <= 100; i++) {
        agg.record('latency', i, ts);
      }

      const p50 = agg.getPercentile('latency', 50, ts, ts + 1000);
      expect(p50).toBeDefined();
      expect(typeof p50).toBe('number');
      expect(p50).toBeGreaterThanOrEqual(49);
      expect(p50).toBeLessThanOrEqual(51);
    });

    it('should return valid value for p100', () => {
      const ts = 10000;
      for (let i = 1; i <= 10; i++) {
        agg.record('latency', i * 10, ts);
      }

      const p100 = agg.getPercentile('latency', 100, ts, ts + 1000);
      // BUG: Returns undefined because index goes out of bounds
      expect(p100).toBeDefined();
      expect(p100).toBe(100); // Should be the maximum value
    });

    it('should return correct p99 value', () => {
      const ts = 10000;
      for (let i = 1; i <= 100; i++) {
        agg.record('latency', i, ts);
      }

      const p99 = agg.getPercentile('latency', 99, ts, ts + 1000);
      expect(p99).toBeDefined();
      expect(p99).toBeGreaterThanOrEqual(98);
      expect(p99).toBeLessThanOrEqual(100);
    });
  });

  describe('rate', () => {
    it('should calculate events per second', () => {
      const ts = 10000;
      for (let i = 0; i < 10; i++) {
        agg.record('requests', 1, ts + i * 100);
      }

      // 10 events over 1000ms = 10/s
      const rate = agg.getRate('requests', ts, ts + 1000);
      expect(rate).toBe(10);
    });
  });

  describe('downsample', () => {
    it('should merge buckets when downsampling', () => {
      const ts = 10000;
      // Create data in 4 buckets
      agg.record('cpu', 10, ts);
      agg.record('cpu', 20, ts + 1000);
      agg.record('cpu', 30, ts + 2000);
      agg.record('cpu', 40, ts + 3000);

      // Downsample to 2-second buckets
      const downsampled = agg.downsample('cpu', 2000, ts, ts + 4000);
      expect(downsampled.length).toBeLessThanOrEqual(2);
      expect(downsampled[0].sum).toBe(30); // 10 + 20
    });
  });

  describe('metric names', () => {
    it('should list all recorded metric names', () => {
      agg.record('cpu', 50, 1000);
      agg.record('memory', 1024, 1000);
      agg.record('disk', 500, 1000);

      const names = agg.getMetricNames();
      expect(names).toContain('cpu');
      expect(names).toContain('memory');
      expect(names).toContain('disk');
    });
  });

  describe('bucket eviction', () => {
    it('should evict oldest buckets when maxBuckets exceeded', () => {
      const agg2 = new TimeSeriesAggregator({ bucketSize: 1000, maxBuckets: 3 });
      for (let i = 0; i < 5; i++) {
        agg2.record('metric', i, i * 1000);
      }
      // Should only have last 3 buckets
      const buckets = agg2.query('metric', 0, 10000);
      expect(buckets.length).toBeLessThanOrEqual(3);
    });
  });
});

describe('FunnelAnalyzer', () => {
  let funnel;

  beforeEach(() => {
    funnel = new FunnelAnalyzer();
  });

  describe('funnel definition', () => {
    it('should define a funnel with steps', () => {
      funnel.defineFunnel('signup', ['visit', 'signup_start', 'email_confirm', 'profile_complete']);
      const progress = funnel.getUserFunnelProgress('signup', 'any-user');
      expect(progress.totalSteps).toBe(4);
    });
  });

  describe('event tracking and analysis', () => {
    it('should track user events through funnel', () => {
      funnel.defineFunnel('onboarding', ['signup', 'verify', 'setup']);
      funnel.trackEvent('user-1', 'signup', 1000);
      funnel.trackEvent('user-1', 'verify', 2000);
      funnel.trackEvent('user-1', 'setup', 3000);

      const progress = funnel.getUserFunnelProgress('onboarding', 'user-1');
      expect(progress.completed).toBe(true);
      expect(progress.completedSteps).toHaveLength(3);
    });

    it('should calculate conversion rates', () => {
      funnel.defineFunnel('purchase', ['view', 'cart', 'checkout', 'purchase']);

      // 3 users start, 2 add to cart, 1 purchases
      funnel.trackEvent('u1', 'view', 1000);
      funnel.trackEvent('u2', 'view', 1000);
      funnel.trackEvent('u3', 'view', 1000);
      funnel.trackEvent('u1', 'cart', 2000);
      funnel.trackEvent('u2', 'cart', 2000);
      funnel.trackEvent('u1', 'checkout', 3000);
      funnel.trackEvent('u1', 'purchase', 4000);

      const result = funnel.analyzeFunnel('purchase');
      expect(result.steps[0].count).toBe(3); // view
      expect(result.steps[1].count).toBe(2); // cart
      expect(result.steps[3].count).toBe(1); // purchase
      expect(result.overallConversion).toBeCloseTo(1/3, 2);
    });

    // BUG: Dropoff rate uses step[i-1] as denominator but rate uses step[0]
    // This means rate shows cumulative conversion but dropoff is step-to-step
    // which is inconsistent and confusing
    it('should calculate step-to-step dropoff rates correctly', () => {
      funnel.defineFunnel('flow', ['a', 'b', 'c']);

      funnel.trackEvent('u1', 'a', 1000);
      funnel.trackEvent('u2', 'a', 1000);
      funnel.trackEvent('u1', 'b', 2000);
      funnel.trackEvent('u2', 'b', 2000);
      funnel.trackEvent('u1', 'c', 3000);

      const result = funnel.analyzeFunnel('flow');
      // a=2, b=2, c=1
      // dropoff from b to c should be 1 - (1/2) = 0.5
      expect(result.steps[2].dropoff).toBeCloseTo(0.5, 2);
      // dropoff from a to b should be 0 (all made it)
      expect(result.steps[1].dropoff).toBe(0);
    });
  });

  describe('window expiry', () => {
    it('should expire funnel progress beyond window', () => {
      funnel.defineFunnel('fast', ['a', 'b']);
      funnel.trackEvent('u1', 'a', 1000);
      funnel.trackEvent('u1', 'b', 1000 + 86400000 + 1); // Past 24h window

      const result = funnel.analyzeFunnel('fast', 86400000);
      // User started step a but b was too late
      expect(result.steps[0].count).toBe(1);
      expect(result.steps[1].count).toBe(0);
    });
  });
});

describe('UserProfileManager - searchUsers', () => {
  let UserProfileManager;

  beforeEach(() => {
    jest.resetModules();
    // Re-require after express mock is set up
    const mod = require('../../../services/users/src/index');
    UserProfileManager = mod.UserProfileManager;
  });

  it('searchUsers page 1 should use offset 0', async () => {
    const manager = new UserProfileManager({});
    const result = await manager.searchUsers('test', { page: 1, limit: 20 });
    // BUG: uses page * limit = 20 instead of (page-1) * limit = 0
    expect(result.offset).toBe(0);
  });

  it('searchUsers page 2 should use offset equal to limit', async () => {
    const manager = new UserProfileManager({});
    const result = await manager.searchUsers('test', { page: 2, limit: 10 });
    // page 2, limit 10: offset should be (2-1)*10 = 10
    // BUG: uses 2*10 = 20
    expect(result.offset).toBe(10);
  });

  it('searchUsers first page offset should be zero not page*limit', async () => {
    const manager = new UserProfileManager({});
    const result = await manager.searchUsers('query', { page: 1, limit: 50 });
    // First page should start from 0
    expect(result.offset).toBe(0);
  });

  it('searchUsers pagination should follow (page-1)*limit formula', async () => {
    const manager = new UserProfileManager({});
    const page3 = await manager.searchUsers('q', { page: 3, limit: 25 });
    // (3-1)*25 = 50
    expect(page3.offset).toBe(50);
  });

  it('searchUsers page 1 should not skip any results', async () => {
    const manager = new UserProfileManager({});
    const result = await manager.searchUsers('query', { page: 1, limit: 10 });
    // Page 1 with limit 10 should retrieve first 10 results (offset=0)
    // BUG: offset = 1 * 10 = 10, skipping first page entirely
    expect(result.offset).toBe(0);
  });

  it('searchUsers page offset for page 5 with limit 20 should be 80', async () => {
    const manager = new UserProfileManager({});
    const result = await manager.searchUsers('query', { page: 5, limit: 20 });
    // (5-1)*20 = 80
    expect(result.offset).toBe(80);
  });
});

describe('UserActivityTracker', () => {
  let UserActivityTracker;

  beforeEach(() => {
    jest.resetModules();
    const mod = require('../../../services/users/src/index');
    UserActivityTracker = mod.UserActivityTracker;
  });

  it('record should remove oldest entries when exceeding max (FIFO)', () => {
    const tracker = new UserActivityTracker({ maxActivities: 3 });
    tracker.record('u1', 'action-1');
    tracker.record('u1', 'action-2');
    tracker.record('u1', 'action-3');
    tracker.record('u1', 'action-4');

    const activities = tracker.activities.get('u1');
    expect(activities).toHaveLength(3);
    // Should keep action-2, action-3, action-4 (oldest removed)
    // BUG: uses pop() which removes newest instead of oldest
    expect(activities[0].action).toBe('action-2');
  });

  it('record should use shift() to remove oldest, not pop() for newest', () => {
    const tracker = new UserActivityTracker({ maxActivities: 2 });
    tracker.record('u1', 'first');
    tracker.record('u1', 'second');
    tracker.record('u1', 'third');

    const activities = tracker.activities.get('u1');
    // Should have second and third (first was evicted)
    // BUG: pop() removes third (newest), keeping first and second
    expect(activities[activities.length - 1].action).toBe('third');
  });

  it('oldest activity should be evicted when capacity exceeded', () => {
    const tracker = new UserActivityTracker({ maxActivities: 3 });
    tracker.record('u1', 'a');
    tracker.record('u1', 'b');
    tracker.record('u1', 'c');
    tracker.record('u1', 'd');
    tracker.record('u1', 'e');

    const activities = tracker.activities.get('u1');
    expect(activities).toHaveLength(3);
    // Oldest (a, b) should be gone, newest (c, d, e) should remain
    const actions = activities.map(a => a.action);
    expect(actions).not.toContain('a');
    expect(actions).not.toContain('b');
    expect(actions).toContain('e');
  });

  it('newest activity should always be preserved after eviction', () => {
    const tracker = new UserActivityTracker({ maxActivities: 1 });
    tracker.record('u1', 'old');
    tracker.record('u1', 'new');

    const activities = tracker.activities.get('u1');
    expect(activities).toHaveLength(1);
    // Should keep 'new', not 'old'
    expect(activities[0].action).toBe('new');
  });

  it('getRecent should return the most recent activities in order', () => {
    const tracker = new UserActivityTracker({ maxActivities: 5 });
    tracker.record('u1', 'a');
    tracker.record('u1', 'b');
    tracker.record('u1', 'c');
    tracker.record('u1', 'd');
    tracker.record('u1', 'e');
    tracker.record('u1', 'f'); // should evict 'a'

    const recent = tracker.getRecent('u1', 3);
    const actions = recent.map(a => a.action);
    expect(actions).toContain('f');
    expect(actions).not.toContain('a');
  });
});

describe('CohortTracker', () => {
  let tracker;

  beforeEach(() => {
    tracker = new CohortTracker();
  });

  describe('cohort management', () => {
    it('should create and add members to cohorts', () => {
      tracker.defineCohort('jan2024', { month: 'january' });
      tracker.addToCohort('jan2024', 'u1');
      tracker.addToCohort('jan2024', 'u2');

      expect(tracker.getCohortSize('jan2024')).toBe(2);
    });

    it('should track user cohort membership', () => {
      tracker.defineCohort('trial', { type: 'trial' });
      tracker.addToCohort('trial', 'u1', 1000);

      const cohorts = tracker.getUserCohorts('u1');
      expect(cohorts).toHaveLength(1);
      expect(cohorts[0].cohortId).toBe('trial');
    });

    it('should return false for undefined cohort', () => {
      expect(tracker.addToCohort('nonexistent', 'u1')).toBe(false);
    });
  });

  // BUG: _wasActiveInPeriod always returns true, so retention is always 100%
  describe('retention analysis', () => {
    it('should calculate realistic retention rates (not always 100%)', () => {
      tracker.defineCohort('week1', { week: 1 });
      tracker.addToCohort('week1', 'u1', 1000);
      tracker.addToCohort('week1', 'u2', 1000);

      const retention = tracker.getRetention('week1', 3, 86400000);
      // BUG: All periods show 100% retention because _wasActiveInPeriod always returns true
      // In reality, retention should decrease over time
      // This test catches the bug by checking that retention is NOT always 1.0
      // Since we haven't actually recorded any activity events, retention should be less than 1.0
      const allPerfectRetention = retention.every(r => r.rate === 1.0);
      expect(allPerfectRetention).toBe(false);
    });
  });

  describe('cohort comparison', () => {
    it('should compare cohort sizes and overlap', () => {
      tracker.defineCohort('a', {});
      tracker.defineCohort('b', {});

      tracker.addToCohort('a', 'u1');
      tracker.addToCohort('a', 'u2');
      tracker.addToCohort('a', 'u3');

      tracker.addToCohort('b', 'u2');
      tracker.addToCohort('b', 'u3');
      tracker.addToCohort('b', 'u4');

      const comparison = tracker.compareCohorts('a', 'b', 'any');
      expect(comparison.cohortA.size).toBe(3);
      expect(comparison.cohortB.size).toBe(3);
      expect(comparison.overlap).toBe(2); // u2 and u3
    });

    it('should return null for missing cohorts', () => {
      tracker.defineCohort('a', {});
      expect(tracker.compareCohorts('a', 'nonexistent', 'x')).toBeNull();
    });
  });
});
