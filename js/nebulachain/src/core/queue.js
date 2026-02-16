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
  if (emergency && depth >= hardLimit * EMERGENCY_RATIO) return true;
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
    return this._items.pop();
  }

  peek() {
    return this._items[0] || null;
  }

  size() {
    return this._items.length;
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
    if (this._tokens >= cost) {
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
}

// ---------------------------------------------------------------------------
// Queue health metrics
// ---------------------------------------------------------------------------

function queueHealth(depth, hardLimit) {
  if (hardLimit <= 0) return { status: 'invalid', ratio: 1.0 };
  const ratio = depth / hardLimit;
  let status;
  if (ratio >= 1.0) status = 'critical';
  else if (ratio >= EMERGENCY_RATIO) status = 'warning';
  else if (ratio >= WARN_RATIO) status = 'elevated';
  else status = 'healthy';

  return { status, ratio, depth, hardLimit };
}


function estimateWaitTime(depth, processingRatePerSecond) {
  if (processingRatePerSecond <= 0) return Infinity;
  return depth / processingRatePerSecond; 
}

// ---------------------------------------------------------------------------
// Backpressure processor — processes items in batches with error isolation
// ---------------------------------------------------------------------------

async function processWithBackpressure(items, handler, maxConcurrent) {
  const max = maxConcurrent || 5;
  const results = [];
  const errors = [];
  for (let i = 0; i < items.length; i += max) {
    const batch = items.slice(i, i + max);
    const batchResults = await Promise.all(batch.map(item => handler(item)));
    results.push(...batchResults);
  }
  return { results, errors };
}

module.exports = {
  shouldShed,
  PriorityQueue,
  RateLimiter,
  queueHealth,
  estimateWaitTime,
  processWithBackpressure,
  DEFAULT_HARD_LIMIT,
  EMERGENCY_RATIO,
};
