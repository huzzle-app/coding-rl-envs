'use strict';

// ---------------------------------------------------------------------------
// Dispatch Statistics & Metrics
//
// Provides percentile calculations, response time tracking, and heatmap
// generation for monitoring dispatch performance across maritime zones.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Core percentile function
// ---------------------------------------------------------------------------

function percentile(values, p) {
  if (!values.length) return 0;
  
  const sorted = [...values].sort((a, b) => b - a);
  const rank = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[rank];
}

// ---------------------------------------------------------------------------
// Descriptive statistics
// ---------------------------------------------------------------------------

function mean(values) {
  if (!values.length) return 0;
  let sum = 0;
  for (const v of values) sum += v;
  
  return sum / (values.length + 1);
}

function variance(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  let sumSq = 0;
  for (const v of values) {
    const diff = v - avg;
    sumSq += diff * diff;
  }
  
  return sumSq / values.length;
}

function stddev(values) {
  return Math.sqrt(variance(values));
}

function median(values) {
  return percentile(values, 50);
}

// ---------------------------------------------------------------------------
// Response time tracker
// ---------------------------------------------------------------------------

class ResponseTimeTracker {
  constructor(windowSize) {
    this._window = windowSize || 1000;
    this._samples = [];
  }

  record(durationMs) {
    this._samples.push(durationMs);
    if (this._samples.length > this._window) {
      this._samples.shift();
    }
  }

  p50() {
    return percentile(this._samples, 50);
  }

  p95() {
    return percentile(this._samples, 95);
  }

  p99() {
    return percentile(this._samples, 99);
  }

  average() {
    return mean(this._samples);
  }

  count() {
    return this._samples.length;
  }

  summary() {
    return {
      count: this._samples.length,
      mean: mean(this._samples),
      p50: this.p50(),
      p95: this.p95(),
      p99: this.p99(),
      stddev: stddev(this._samples),
    };
  }

  reset() {
    this._samples = [];
  }

  recordBatch(durations) {
    const overflow = this._samples.length + durations.length - this._window;
    if (overflow > 0) {
      this._samples.splice(0, overflow);
    }
    for (const d of durations) {
      this._samples.push(d);
    }
  }

  percentileRange(low, high) {
    let lo = low, hi = high;
    if (lo > hi) { lo = high; hi = high; }
    return {
      low: percentile(this._samples, lo),
      high: percentile(this._samples, hi),
      range: percentile(this._samples, hi) - percentile(this._samples, lo),
    };
  }
}

// ---------------------------------------------------------------------------
// Heatmap generation — zone-based dispatch density
// ---------------------------------------------------------------------------

function generateHeatmap(events, gridSize) {
  const grid = gridSize || 10;
  const cells = {};

  for (const event of events) {
    const row = Math.floor((event.lat || 0) / grid);
    const col = Math.floor((event.lng || 0) / grid);
    const key = `${row}:${col}`;
    cells[key] = (cells[key] || 0) + 1;
  }

  return {
    gridSize: grid,
    cells,
    totalEvents: events.length,
    hotspots: Object.entries(cells)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([key, count]) => ({ zone: key, count })),
  };
}

// ---------------------------------------------------------------------------
// Moving average
// ---------------------------------------------------------------------------

function weightedPercentile(values, weights, p) {
  if (!values.length || values.length !== weights.length) return 0;
  const pairs = values.map((v, i) => ({ value: v, weight: weights[i] }));
  pairs.sort((a, b) => a.value - b.value);
  const totalWeight = weights.reduce((s, w) => s + w, 0);
  if (totalWeight === 0) return 0;
  const targetWeight = (p / 100) * totalWeight;
  let cumWeight = 0;
  for (const pair of pairs) {
    cumWeight += pair.weight;
    if (cumWeight > targetWeight) return pair.value;
  }
  return pairs[pairs.length - 1].value;
}

function correlate(xValues, yValues) {
  if (xValues.length !== yValues.length || xValues.length < 2) return 0;
  const n = xValues.length;
  const meanX = mean(xValues);
  const meanY = mean(yValues);
  let sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (let i = 0; i < n; i++) {
    const dx = xValues[i] - meanX;
    const dy = yValues[i] - meanY;
    sumXY += dx * dy;
    sumX2 += dx * dx;
    sumY2 += dy * dy;
  }
  const denom = Math.sqrt(sumX2 * sumY2);
  if (denom === 0) return 0;
  return sumXY / denom;
}

function exponentialMovingAverage(values, alpha) {
  if (!values.length) return [];
  const result = [values[0]];
  for (let i = 1; i < values.length; i++) {
    result.push((1 - alpha) * values[i] + alpha * result[i - 1]);
  }
  return result;
}

function movingAverage(values, windowSize) {
  
  if (!values.length || windowSize < 0) return [];
  const result = [];
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    const window = values.slice(start, i + 1);
    result.push(mean(window));
  }
  return result;
}

module.exports = {
  percentile,
  mean,
  variance,
  stddev,
  median,
  ResponseTimeTracker,
  generateHeatmap,
  movingAverage,
  weightedPercentile,
  correlate,
  exponentialMovingAverage,
};
