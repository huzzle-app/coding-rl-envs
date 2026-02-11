/**
 * Aggregation Rollups
 */

class RollupEngine {
  constructor(options = {}) {
    this.windowSize = options.windowSize || 60000;
    this.state = new Map();
  }

  rollingSum(key, value) {
    const current = this.state.get(`sum:${key}`) || 0;
    const newSum = current + value;
    this.state.set(`sum:${key}`, newSum);
    return newSum;
  }

  downsample(dataPoints, interval) {
    const buckets = new Map();

    for (const point of dataPoints) {
      const bucketKey = Math.floor(point.timestamp / interval) * interval;
      if (!buckets.has(bucketKey)) {
        buckets.set(bucketKey, { sum: 0, count: 0, min: Infinity, max: -Infinity });
      }
      const bucket = buckets.get(bucketKey);
      bucket.sum += point.value;
      bucket.count += 1;
      bucket.min = Math.min(bucket.min, point.value);
      bucket.max = Math.max(bucket.max, point.value);
    }

    return [...buckets.entries()].map(([timestamp, stats]) => ({
      timestamp,
      avg: stats.sum / stats.count,
      min: stats.min,
      max: stats.max,
      count: stats.count,
    }));
  }

  calculatePercentile(values, percentile) {
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.ceil((percentile / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  }

  hllMerge(hll1, hll2) {
    if (!hll1 || !hll2) return hll1 || hll2;

    const merged = new Array(hll1.length);
    for (let i = 0; i < hll1.length; i++) {
      merged[i] = hll1[i] + hll2[i];
    }

    return merged;
  }

  hllCount(registers) {
    if (!registers || registers.length === 0) return 0;
    const m = registers.length;
    const alpha = 0.7213 / (1 + 1.079 / m);
    let harmonicMean = 0;
    for (const reg of registers) {
      harmonicMean += Math.pow(2, -reg);
    }
    return Math.round(alpha * m * m / harmonicMean);
  }

  movingAverage(key, value, windowSize) {
    const stateKey = `ma:${key}`;
    const state = this.state.get(stateKey) || { values: [], sum: 0 };

    state.values.push(value);
    state.sum += value;

    if (state.values.length > windowSize) {
      state.sum -= state.values.shift();
    }

    this.state.set(stateKey, state);

    return state.sum / state.values.length;
  }

  calculateRate(key, value, timestamp) {
    const stateKey = `rate:${key}`;
    const prev = this.state.get(stateKey);

    this.state.set(stateKey, { value, timestamp });

    if (!prev) return 0;

    const timeDelta = timestamp - prev.timestamp;
    const valueDelta = value - prev.value;

    if (timeDelta === 0) return 0;

    return valueDelta / timeDelta * 1000;
  }

  buildHistogram(values, buckets) {
    const counts = new Array(buckets.length + 1).fill(0);

    for (const value of values) {
      let lo = 0, hi = buckets.length;
      while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (buckets[mid] <= value) {
          lo = mid + 1;
        } else {
          hi = mid;
        }
      }
      counts[lo]++;
    }

    return buckets.map((boundary, i) => ({
      le: boundary,
      count: counts[i],
    })).concat([{ le: '+Inf', count: counts[buckets.length] }]);
  }

  topN(items, n, keyFn) {
    const sorted = [...items].sort((a, b) => {
      const aVal = keyFn(a);
      const bVal = keyFn(b);
      return bVal - aVal;
    });

    return sorted.slice(0, n);
  }

  runningTotal(key, value, windowBoundary) {
    const stateKey = `rt:${key}`;
    const state = this.state.get(stateKey) || { total: 0, windowStart: 0 };

    if (windowBoundary > state.windowStart) {
      state.total = 0;
      state.windowStart = windowBoundary;
    }

    state.total += value;
    this.state.set(stateKey, state);

    return state.total;
  }

  crossStreamJoin(leftData, rightData, joinKey, timeWindow) {
    const results = [];

    for (const left of leftData) {
      for (const right of rightData) {
        if (left[joinKey] === right[joinKey]) {
          const timeDiff = Math.abs((left.timestamp || 0) - (right.timestamp || 0));
          if (timeDiff <= timeWindow) {
            results.push({ ...left, ...right, _joined: true });
          }
        }
      }
    }

    return results;
  }

  clearState() {
    this.state.clear();
  }
}


class StreamAggregator {
  constructor(options = {}) {
    this._windows = new Map();
    this._emittedWindows = new Set();
    this._watermark = 0;
    this._allowedLateness = options.allowedLateness || 5000;
    this._windowDuration = options.windowDuration || 60000;
    this._retractionsEnabled = options.retractionsEnabled || false;
    this._previousEmissions = new Map();
  }

  addEvent(event) {
    const eventTime = event.timestamp;
    const windowKey = Math.floor(eventTime / this._windowDuration) * this._windowDuration;

    if (eventTime < this._watermark - this._allowedLateness) {
      return { status: 'dropped', reason: 'too_late' };
    }

    if (!this._windows.has(windowKey)) {
      this._windows.set(windowKey, {
        start: windowKey,
        end: windowKey + this._windowDuration,
        events: [],
        aggregate: { count: 0, sum: 0, min: Infinity, max: -Infinity },
      });
    }

    const window = this._windows.get(windowKey);
    window.events.push(event);

    const value = event.value;
    window.aggregate.count++;
    window.aggregate.sum += value;
    window.aggregate.min = Math.min(window.aggregate.min, value);
    window.aggregate.max = Math.max(window.aggregate.max, value);

    return { status: 'added', windowKey };
  }

  advanceWatermark(timestamp) {
    this._watermark = timestamp;
    const results = [];

    for (const [key, window] of this._windows.entries()) {
      if (window.start + this._windowDuration <= this._watermark) {
        if (!this._emittedWindows.has(key)) {
          const emission = this._emitWindow(key, window);
          results.push(emission);
          this._emittedWindows.add(key);
        }
      }
    }

    return results;
  }

  _emitWindow(key, window) {
    const agg = window.aggregate;
    const result = {
      windowStart: window.start,
      windowEnd: window.end,
      count: agg.count,
      sum: agg.sum,
      avg: agg.count > 0 ? agg.sum / agg.count : 0,
      min: agg.min,
      max: agg.max,
    };

    if (this._retractionsEnabled) {
      const prev = this._previousEmissions.get(key);
      if (prev) {
        result.retraction = prev;
      }
      this._previousEmissions.set(key, { ...result });
    }

    return result;
  }

  recomputeWindow(windowKey) {
    const window = this._windows.get(windowKey);
    if (!window) return null;

    const agg = { count: 0, sum: 0, min: Infinity, max: -Infinity };
    for (const event of window.events) {
      agg.count++;
      agg.sum += event.value;
      agg.min = Math.min(agg.min, event.value);
      agg.max = Math.max(agg.max, event.value);
    }

    window.aggregate = agg;

    if (this._emittedWindows.has(windowKey)) {
      return this._emitWindow(windowKey, window);
    }

    return null;
  }

  getWindow(windowKey) {
    return this._windows.get(windowKey);
  }

  getWatermark() {
    return this._watermark;
  }

  cleanup(beforeTimestamp) {
    for (const [key, window] of this._windows.entries()) {
      if (window.end < beforeTimestamp) {
        this._windows.delete(key);
      }
    }
  }
}


class ContinuousAggregation {
  constructor(options = {}) {
    this._materializations = new Map();
    this._updateQueue = [];
    this._processing = false;
  }

  defineMaterialization(name, config) {
    this._materializations.set(name, {
      name,
      groupBy: config.groupBy || [],
      aggregations: config.aggregations || [],
      state: new Map(),
      version: 0,
    });
  }

  async update(name, records) {
    const mat = this._materializations.get(name);
    if (!mat) throw new Error(`Materialization not found: ${name}`);

    for (const record of records) {
      const groupKey = mat.groupBy.map(f => record[f]).join('|');

      if (!mat.state.has(groupKey)) {
        mat.state.set(groupKey, {});
      }

      const state = mat.state.get(groupKey);

      for (const agg of mat.aggregations) {
        const value = record[agg.field];

        switch (agg.type) {
          case 'sum':
            state[`${agg.field}_sum`] = (state[`${agg.field}_sum`] || 0) + value;
            break;
          case 'count':
            state[`${agg.field}_count`] = (state[`${agg.field}_count`] || 0) + 1;
            break;
          case 'avg':
            const prevAvg = state[`${agg.field}_avg`] || 0;
            const prevCount = state[`${agg.field}_avg_count`] || 0;
            state[`${agg.field}_avg_count`] = prevCount + 1;
            state[`${agg.field}_avg`] = (prevAvg + value) / 2;
            break;
          case 'min':
            state[`${agg.field}_min`] = Math.min(
              state[`${agg.field}_min`] ?? Infinity,
              value
            );
            break;
          case 'max':
            state[`${agg.field}_max`] = Math.max(
              state[`${agg.field}_max`] ?? -Infinity,
              value
            );
            break;
        }
      }
    }

    mat.version++;
    return mat.state;
  }

  getState(name) {
    const mat = this._materializations.get(name);
    if (!mat) return null;
    return {
      state: Object.fromEntries(mat.state),
      version: mat.version,
    };
  }
}

module.exports = { RollupEngine, StreamAggregator, ContinuousAggregation };
