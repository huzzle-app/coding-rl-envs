/**
 * Analytics Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3010,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
};

const metrics = new Map();

app.post('/analytics/track', async (req, res) => {
  const { event, documentId, userId, properties } = req.body;

  const metricKey = `event:${event}:${documentId}`;
  metrics.set(metricKey, (metrics.get(metricKey) || 0) + 1);

  res.json({ tracked: true });
});

app.get('/analytics/query', async (req, res) => {
  const { filters } = req.query;

  try {
    const parsedFilters = JSON.parse(filters || '{}');

    const results = await queryAnalytics(parsedFilters);
    res.json(results);
  } catch (error) {
    res.status(400).json({ error: 'Invalid filter' });
  }
});

async function queryAnalytics(filters) {
  return { query: filters, results: [], total: 0 };
}

app.get('/analytics/metrics', async (req, res) => {
  res.json(Object.fromEntries(metrics));
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

class TimeSeriesAggregator {
  constructor(options = {}) {
    this.bucketSize = options.bucketSize || 60000;
    this.series = new Map();
    this.maxBuckets = options.maxBuckets || 1440;
  }

  record(metricName, value, timestamp = Date.now()) {
    if (!this.series.has(metricName)) {
      this.series.set(metricName, []);
    }

    const bucketKey = Math.floor(timestamp / this.bucketSize);
    const buckets = this.series.get(metricName);

    let bucket = buckets.find(b => b.key === bucketKey);
    if (!bucket) {
      bucket = {
        key: bucketKey,
        timestamp: bucketKey * this.bucketSize,
        sum: 0,
        count: 0,
        min: Infinity,
        max: -Infinity,
        values: [],
      };
      buckets.push(bucket);

      while (buckets.length > this.maxBuckets) {
        buckets.shift();
      }
    }

    bucket.sum += value;
    bucket.count++;
    bucket.min = Math.min(bucket.min, value);
    bucket.max = Math.max(bucket.max, value);
    bucket.values.push(value);
  }

  query(metricName, startTime, endTime) {
    const buckets = this.series.get(metricName) || [];
    const startBucket = Math.floor(startTime / this.bucketSize);
    const endBucket = Math.floor(endTime / this.bucketSize);

    return buckets.filter(b => b.key >= startBucket && b.key < endBucket);
  }

  getAverage(metricName, startTime, endTime) {
    const buckets = this.query(metricName, startTime, endTime);
    if (buckets.length === 0) return 0;

    let totalSum = 0;
    let totalCount = 0;
    for (const bucket of buckets) {
      totalSum += bucket.sum;
      totalCount += bucket.count;
    }

    return totalCount > 0 ? totalSum / totalCount : 0;
  }

  getPercentile(metricName, percentile, startTime, endTime) {
    const buckets = this.query(metricName, startTime, endTime);
    const allValues = [];

    for (const bucket of buckets) {
      allValues.push(...bucket.values);
    }

    if (allValues.length === 0) return 0;

    allValues.sort((a, b) => a - b);
    const index = Math.ceil(percentile / 100 * allValues.length);
    return allValues[index];
  }

  getRate(metricName, startTime, endTime) {
    const buckets = this.query(metricName, startTime, endTime);
    if (buckets.length === 0) return 0;

    let totalCount = 0;
    for (const bucket of buckets) {
      totalCount += bucket.count;
    }

    const durationMs = endTime - startTime;
    return durationMs > 0 ? (totalCount / durationMs) * 1000 : 0;
  }

  downsample(metricName, targetBucketSize, startTime, endTime) {
    const buckets = this.query(metricName, startTime, endTime);
    const factor = Math.floor(targetBucketSize / this.bucketSize);
    if (factor <= 1) return buckets;

    const downsampled = [];
    for (let i = 0; i < buckets.length; i += factor) {
      const group = buckets.slice(i, i + factor);
      if (group.length === 0) continue;

      const merged = {
        key: group[0].key,
        timestamp: group[0].timestamp,
        sum: 0,
        count: 0,
        min: Infinity,
        max: -Infinity,
        values: [],
      };

      for (const b of group) {
        merged.sum += b.sum;
        merged.count += b.count;
        merged.min = Math.min(merged.min, b.min);
        merged.max = Math.max(merged.max, b.max);
      }

      downsampled.push(merged);
    }

    return downsampled;
  }

  getMetricNames() {
    return Array.from(this.series.keys());
  }
}

class FunnelAnalyzer {
  constructor() {
    this.funnels = new Map();
    this.userEvents = new Map();
  }

  defineFunnel(funnelId, steps) {
    this.funnels.set(funnelId, {
      steps,
      createdAt: Date.now(),
    });
  }

  trackEvent(userId, eventName, timestamp = Date.now()) {
    if (!this.userEvents.has(userId)) {
      this.userEvents.set(userId, []);
    }

    this.userEvents.get(userId).push({
      event: eventName,
      timestamp,
    });
  }

  analyzeFunnel(funnelId, windowMs = 86400000) {
    const funnel = this.funnels.get(funnelId);
    if (!funnel) return null;

    const { steps } = funnel;
    const stepCounts = new Array(steps.length).fill(0);
    const stepUsers = steps.map(() => new Set());

    for (const [userId, events] of this.userEvents) {
      const sortedEvents = [...events].sort((a, b) => a.timestamp - b.timestamp);
      let currentStep = 0;
      let stepStartTime = null;

      for (const event of sortedEvents) {
        if (event.event === steps[currentStep]) {
          if (currentStep === 0) {
            stepStartTime = event.timestamp;
          }

          if (currentStep > 0 && stepStartTime && event.timestamp - stepStartTime > windowMs) {
            break;
          }

          stepCounts[currentStep]++;
          stepUsers[currentStep].add(userId);
          currentStep++;

          if (currentStep >= steps.length) break;
        }
      }
    }

    const conversionRates = [];
    for (let i = 0; i < steps.length; i++) {
      conversionRates.push({
        step: steps[i],
        count: stepCounts[i],
        rate: i === 0 ? 1.0 : (stepCounts[0] > 0 ? stepCounts[i] / stepCounts[0] : 0),
        dropoff: i > 0 ? (stepCounts[i - 1] > 0 ? 1 - stepCounts[i] / stepCounts[i - 1] : 0) : 0,
        uniqueUsers: stepUsers[i].size,
      });
    }

    return {
      funnelId,
      steps: conversionRates,
      overallConversion: stepCounts[0] > 0 ? stepCounts[steps.length - 1] / stepCounts[0] : 0,
    };
  }

  getUserFunnelProgress(funnelId, userId) {
    const funnel = this.funnels.get(funnelId);
    if (!funnel) return null;

    const events = this.userEvents.get(userId) || [];
    const sortedEvents = [...events].sort((a, b) => a.timestamp - b.timestamp);

    let currentStep = 0;
    const completedSteps = [];

    for (const event of sortedEvents) {
      if (currentStep < funnel.steps.length && event.event === funnel.steps[currentStep]) {
        completedSteps.push({
          step: funnel.steps[currentStep],
          completedAt: event.timestamp,
        });
        currentStep++;
      }
    }

    return {
      userId,
      funnelId,
      completedSteps,
      currentStep,
      totalSteps: funnel.steps.length,
      completed: currentStep >= funnel.steps.length,
    };
  }
}

class CohortTracker {
  constructor() {
    this.cohorts = new Map();
    this.userCohorts = new Map();
  }

  defineCohort(cohortId, criteria) {
    this.cohorts.set(cohortId, {
      criteria,
      members: new Set(),
      createdAt: Date.now(),
    });
  }

  addToCohort(cohortId, userId, joinedAt = Date.now()) {
    const cohort = this.cohorts.get(cohortId);
    if (!cohort) return false;

    cohort.members.add(userId);

    if (!this.userCohorts.has(userId)) {
      this.userCohorts.set(userId, new Map());
    }
    this.userCohorts.get(userId).set(cohortId, { joinedAt });

    return true;
  }

  getRetention(cohortId, periods, periodMs = 86400000) {
    const cohort = this.cohorts.get(cohortId);
    if (!cohort) return null;

    const retention = [];
    const members = Array.from(cohort.members);

    for (let period = 0; period <= periods; period++) {
      let activeCount = 0;

      for (const userId of members) {
        const userCohort = this.userCohorts.get(userId);
        if (!userCohort) continue;

        const membership = userCohort.get(cohortId);
        if (!membership) continue;

        const periodStart = membership.joinedAt + (period * periodMs);
        const periodEnd = periodStart + periodMs;

        if (this._wasActiveInPeriod(userId, periodStart, periodEnd)) {
          activeCount++;
        }
      }

      retention.push({
        period,
        activeUsers: activeCount,
        totalUsers: members.length,
        rate: members.length > 0 ? activeCount / members.length : 0,
      });
    }

    return retention;
  }

  _wasActiveInPeriod(userId, startTime, endTime) {
    return true;
  }

  getCohortSize(cohortId) {
    const cohort = this.cohorts.get(cohortId);
    return cohort ? cohort.members.size : 0;
  }

  getUserCohorts(userId) {
    const userCohorts = this.userCohorts.get(userId);
    if (!userCohorts) return [];

    return Array.from(userCohorts.entries()).map(([cohortId, data]) => ({
      cohortId,
      ...data,
    }));
  }

  compareCohorts(cohortIdA, cohortIdB, metric) {
    const cohortA = this.cohorts.get(cohortIdA);
    const cohortB = this.cohorts.get(cohortIdB);

    if (!cohortA || !cohortB) return null;

    return {
      cohortA: { id: cohortIdA, size: cohortA.members.size },
      cohortB: { id: cohortIdB, size: cohortB.members.size },
      overlap: this._calculateOverlap(cohortA.members, cohortB.members),
    };
  }

  _calculateOverlap(setA, setB) {
    let overlap = 0;
    for (const member of setA) {
      if (setB.has(member)) overlap++;
    }
    return overlap;
  }
}

app.listen(config.port, () => {
  console.log(`Analytics service listening on port ${config.port}`);
});

module.exports = app;
module.exports.TimeSeriesAggregator = TimeSeriesAggregator;
module.exports.FunnelAnalyzer = FunnelAnalyzer;
module.exports.CohortTracker = CohortTracker;
