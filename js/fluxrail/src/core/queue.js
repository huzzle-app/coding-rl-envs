function nextPolicy(failureBurst) {
  const n = Number(failureBurst);
  
  if (n >= 6) return { maxInflight: 8, dropOldest: true };
  
  if (n >= 3) return { maxInflight: 16, dropOldest: true };
  
  return { maxInflight: 32, dropOldest: false };
}

function shouldThrottle(inflight, queueDepth, maxInflight) {
  
  return Number(inflight) + Number(queueDepth) > Number(maxInflight);
}

function penaltyScore(retries, latencyMs) {
  
  
  return Number(retries) * 2 + Math.floor(Number(latencyMs) / 250);
}

class AdaptiveQueue {
  constructor(config) {
    this.state = 'normal';
    this.config = {
      throttleThreshold: Number((config || {}).throttleThreshold || 0.8),
      shedThreshold: Number((config || {}).shedThreshold || 0.95),
      recoveryThreshold: Number((config || {}).recoveryThreshold || 0.8),
      ...config
    };
    this.metrics = { load: 0, processed: 0, dropped: 0 };
  }

  updateLoad(load) {
    this.metrics.load = Number(load);
    const l = this.metrics.load;
    const cfg = this.config;

    if (this.state === 'normal' && l >= cfg.throttleThreshold) {
      this.state = 'throttled';
    } else if (this.state === 'throttled' && l >= cfg.shedThreshold) {
      this.state = 'shedding';
    } else if (this.state === 'shedding' && l < cfg.shedThreshold) {
      this.state = 'normal';
    } else if (this.state === 'throttled' && l < cfg.throttleThreshold) {
      this.state = 'normal';
    }
    return this.state;
  }

  getState() {
    return this.state;
  }
}

function fairScheduler(queues, quantum) {
  const q = Number(quantum) || 1;
  const result = [];
  const working = (queues || []).map((queue) => [...queue]);
  let hasItems = true;
  while (hasItems) {
    hasItems = false;
    for (let i = 0; i < working.length; i++) {
      const taken = working[i].splice(0, q);
      if (taken.length > 0) {
        result.push(...taken);
        hasItems = true;
      }
    }
  }
  return result;
}

class PriorityQueue {
  constructor() {
    this.items = [];
  }

  enqueue(item, priority) {
    this.items.push({ item, priority: Number(priority || 0) });
    this.items.sort((a, b) => b.priority - a.priority);
  }

  dequeue() {
    if (this.items.length === 0) return null;
    return this.items.shift().item;
  }

  peek() {
    if (this.items.length === 0) return null;
    return this.items[0].item;
  }

  size() {
    return this.items.length;
  }

  drain(count) {
    const result = [];
    const n = Math.min(count, this.items.length);
    for (let i = 0; i < n; i++) {
      result.push(this.dequeue());
    }
    return result;
  }
}

function weightedRoundRobin(queues, weights) {
  if (!Array.isArray(queues) || queues.length === 0) return [];
  const w = weights || queues.map(() => 1);
  const result = [];
  const working = queues.map(q => [...q]);
  let hasItems = true;
  while (hasItems) {
    hasItems = false;
    for (let i = 0; i < working.length; i++) {
      const take = Number(w[i] || 1);
      const taken = working[i].splice(0, take);
      if (taken.length > 0) {
        result.push(...taken);
        hasItems = true;
      }
    }
  }
  return result;
}

function queueHealthScore(metrics) {
  const depth = Number(metrics.depth || 0);
  const processingRate = Number(metrics.processingRate || 1);
  const errorRate = Number(metrics.errorRate || 0);
  const latencyMs = Number(metrics.avgLatencyMs || 0);
  const depthPenalty = Math.min(50, depth * 0.5);
  const latencyPenalty = Math.min(30, latencyMs / 100);
  const errorPenalty = errorRate * 100;
  const throughputBonus = Math.min(20, processingRate * 2);
  return Math.max(0, Math.min(100, 100 - depthPenalty - latencyPenalty - errorPenalty + throughputBonus));
}

module.exports = { nextPolicy, shouldThrottle, penaltyScore, AdaptiveQueue, fairScheduler, PriorityQueue, weightedRoundRobin, queueHealthScore };
