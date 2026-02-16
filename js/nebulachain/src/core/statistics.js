'use strict';

const { replay } = require('./resilience');

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
  const sorted = [...values].sort((a, b) => a - b);
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
  return sum / values.length;
}


function variance(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  let sumSq = 0;
  for (const v of values) {
    const diff = v - avg;
    sumSq += diff * diff;
  }
  return sumSq / (values.length - 1); 
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
    if (this._samples.length > 0 && this._samples[this._samples.length - 1] === durationMs) {
      return;
    }
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
    totalEvents: Object.values(cells).reduce((s, c) => s + c, 0),
    hotspots: Object.entries(cells)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([key, count]) => ({ zone: key, count })),
  };
}

// ---------------------------------------------------------------------------
// Moving average
// ---------------------------------------------------------------------------


function movingAverage(values, windowSize) {
  if (!values.length || windowSize <= 0) return [];
  const result = [];
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - windowSize + 1); 
    const window = values.slice(start, i + 1);
    result.push(mean(window));
  }
  return result;
}

// ---------------------------------------------------------------------------
// Replay analysis — combines event replay with statistical analysis
// ---------------------------------------------------------------------------

function replayAndAnalyze(events) {
  const replayed = replay(events);
  if (replayed.length === 0) return { eventCount: 0, meanSequence: 0, medianSequence: 0, maxSequence: 0, events: [] };
  const sequences = replayed.map(e => e.sequence);
  return {
    eventCount: replayed.length,
    meanSequence: mean(sequences),
    medianSequence: median(sequences),
    maxSequence: Math.max(...sequences),
    events: replayed,
  };
}

module.exports = {
  percentile,
  mean,
  variance,
  stddev,
  median,
  replayAndAnalyze,
  ResponseTimeTracker,
  generateHeatmap,
  movingAverage,
};
