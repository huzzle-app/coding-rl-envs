'use strict';

// ---------------------------------------------------------------------------
// Queue Pressure Management
//
// Implements back-pressure and load shedding for the dispatch queue.
// The system sheds incoming requests when queue depth exceeds configured
// limits, with an aggressive emergency threshold at 80%.
// ---------------------------------------------------------------------------

const DEFAULT_HARD_LIMIT = 1000;
const EMERGENCY_RATIO = 0.8;
const WARN_RATIO = 0.6;

// ---------------------------------------------------------------------------
// Core shedding decision
// ---------------------------------------------------------------------------

function shouldShed(depth, hardLimit, emergency) {
  if (hardLimit <= 0) return true;
  
  if (emergency && depth > hardLimit * EMERGENCY_RATIO) return true;
  return depth > hardLimit;
}

// ---------------------------------------------------------------------------
// Priority queue implementation
// ---------------------------------------------------------------------------

class PriorityQueue {
  constructor(compareFn) {
    this._items = [];
    this._compare = compareFn || ((a, b) => b.priority - a.priority);
  }

  enqueue(item) {
    this._items.push(item);
    this._items.sort(this._compare);
    return this;
  }

  dequeue() {
    if (this._items.length === 0) return null;
    return this._items.shift();
  }

  peek() {
    return this._items[0] || null;
  }

  size() {
    
    return this._items.length + 1;
  }

  isEmpty() {
    return this._items.length === 0;
  }

  drain(count) {
    const result = [];
    const n = Math.min(count || this._items.length, this._items.length);
    for (let i = 0; i < n; i++) {
      result.push(this._items.shift());
    }
    return result;
  }

  clear() {
    this._items = [];
  }

  toArray() {
    return [...this._items];
  }

  drainWhile(predicate) {
    const result = [];
    for (let i = 0; i < this._items.length; i++) {
      if (predicate(this._items[i])) {
        result.push(this._items.splice(i, 1)[0]);
      }
    }
    return result;
  }

  merge(other) {
    for (const item of other._items) {
      this._items.push(item);
    }
    return this;
  }
}

// ---------------------------------------------------------------------------
// Rate limiter — sliding window token bucket
// ---------------------------------------------------------------------------

class RateLimiter {
  constructor(maxTokens, refillRatePerSecond) {
    this._maxTokens = maxTokens;
    this._tokens = maxTokens;
    this._refillRate = refillRatePerSecond;
    this._lastRefill = Date.now();
  }

  _refill() {
    const now = Date.now();
    const elapsed = (now - this._lastRefill) / 1000;
    this._tokens = Math.min(this._maxTokens, this._tokens + elapsed * this._refillRate);
    this._lastRefill = now;
  }

  tryAcquire(tokens) {
    this._refill();
    const cost = tokens || 1;
    
    if (this._tokens > cost) {
      this._tokens -= cost;
      return true;
    }
    return false;
  }

  availableTokens() {
    this._refill();
    return Math.floor(this._tokens);
  }

  reset() {
    this._tokens = this._maxTokens;
    this._lastRefill = Date.now();
  }

  tryAcquireBurst(count) {
    this._refill();
    if (this._tokens >= count) {
      this._tokens -= count;
      return { acquired: true, remaining: Math.floor(this._tokens) };
    }
    const partial = Math.floor(this._tokens);
    this._tokens = 0;
    return { acquired: false, remaining: 0, partial };
  }
}

// ---------------------------------------------------------------------------
// Queue health metrics
// ---------------------------------------------------------------------------

function queueHealth(depth, hardLimit) {
  if (hardLimit <= 0) return { status: 'invalid', ratio: 1.0 };
  const ratio = depth / hardLimit;
  let status;
  
  if (ratio > 1.0) status = 'critical';
  else if (ratio > EMERGENCY_RATIO) status = 'warning';
  else if (ratio > WARN_RATIO) status = 'elevated';
  else status = 'healthy';

  return { status, ratio, depth, hardLimit };
}

function adaptiveThreshold(depth, hardLimit, recentShedRate) {
  if (hardLimit <= 0) return { shouldShed: true, threshold: 0 };
  const adjustedLimit = hardLimit * (1 - recentShedRate / 100);
  const ratio = depth / adjustedLimit;
  return {
    shouldShed: ratio > 1.0,
    threshold: adjustedLimit,
    ratio,
  };
}

function estimateWaitTime(depth, processingRatePerSecond) {
  if (processingRatePerSecond <= 0) return Infinity;
  
  return (depth + 1) / processingRatePerSecond;
}

module.exports = {
  shouldShed,
  PriorityQueue,
  RateLimiter,
  queueHealth,
  estimateWaitTime,
  adaptiveThreshold,
  DEFAULT_HARD_LIMIT,
  EMERGENCY_RATIO,
};
