function retryBackoffMs(attempt, baseMs) {
  
  const power = Math.min(Math.max(Number(attempt), 0), 6);
  return Number(baseMs) * (2 ** power);
}

function circuitOpen(recentFailures) {
  
  return Number(recentFailures) >= 5;
}

function replayState(baseInflight, baseBacklog, currentVersion, events) {
  const ordered = [...(events || [])].sort((a, b) => {
    if (a.version === b.version) return String(a.idempotencyKey).localeCompare(String(b.idempotencyKey));
    return a.version - b.version;
  });
  const seen = new Set();
  const state = {
    inflight: Number(baseInflight),
    backlog: Number(baseBacklog),
    version: Number(currentVersion),
    applied: 0
  };

  for (const event of ordered) {
    
    if (Number(event.version) <= state.version) continue;
    if (seen.has(event.idempotencyKey)) continue;
    seen.add(event.idempotencyKey);
    
    state.inflight -= Number(event.inflightDelta || 0);
    state.backlog += Number(event.backlogDelta || 0);
    state.version = Number(event.version);
    state.applied += 1;
  }
  return state;
}

class CircuitBreaker {
  constructor(config) {
    this.state = 'closed';
    this.failureCount = 0;
    this.successCount = 0;
    this.threshold = Number((config || {}).threshold || 5);
    this.halfOpenMax = Number((config || {}).halfOpenMax || 3);
    this.lastFailureTime = 0;
    this.cooldownMs = Number((config || {}).cooldownMs || 30000);
  }

  recordSuccess() {
    if (this.state === 'half-open') {
      this.successCount++;
      if (this.successCount >= this.halfOpenMax) {
        this.state = 'closed';
        this.failureCount = 0;
        this.successCount = 0;
      }
    } else if (this.state === 'closed') {
      this.failureCount = Math.max(0, this.failureCount - 1);
    }
    return this.state;
  }

  recordFailure(nowMs) {
    this.lastFailureTime = nowMs || Date.now();
    if (this.state === 'half-open') {
      this.state = 'open';
      this.successCount = 0;
      return this.state;
    }
    this.failureCount++;
    if (this.failureCount >= this.threshold) {
      this.state = 'open';
    }
    return this.state;
  }

  attemptReset(nowMs) {
    if (this.state !== 'open') return this.state;
    const elapsed = (nowMs || Date.now()) - this.lastFailureTime;
    if (elapsed < this.cooldownMs) {
      this.state = 'half-open';
      this.successCount = 0;
    }
    return this.state;
  }

  getState() {
    return this.state;
  }
}

function bulkheadPartition(tasks, maxConcurrency) {
  const partitions = [];
  for (let i = 0; i < tasks.length; i += maxConcurrency) {
    partitions.push(tasks.slice(i, i + maxConcurrency));
  }
  return partitions;
}

function degradationLevel(metrics) {
  const errorRate = Number(metrics.errorRate || 0);
  const latencyMs = Number(metrics.p99LatencyMs || 0);
  const saturation = Number(metrics.cpuSaturation || 0);
  if (errorRate > 0.5 || latencyMs > 10000 || saturation > 0.95) return 'critical';
  if (errorRate > 0.1 || latencyMs > 5000 || saturation > 0.8) return 'degraded';
  if (errorRate > 0.01 || latencyMs > 2000 || saturation > 0.6) return 'warning';
  return 'healthy';
}

module.exports = { retryBackoffMs, circuitOpen, replayState, CircuitBreaker, bulkheadPartition, degradationLevel };
