/**
 * Shared Utilities
 */

const crypto = require('crypto');


const { WebSocketManager } = require('../realtime');

function generateId() {
  return crypto.randomUUID();
}

class DistributedLock {
  constructor(redisClient, options = {}) {
    this.redis = redisClient;
    this.lockPrefix = options.prefix || 'lock:';
    this.defaultTimeout = options.timeout || 5000;
    this.retryDelay = options.retryDelay || 100;
    this.maxRetries = options.maxRetries || 50;
  }

  async acquire(key, timeout = this.defaultTimeout) {
    const lockKey = `${this.lockPrefix}${key}`;
    const lockValue = generateId();
    const startTime = Date.now();

    for (let i = 0; i < this.maxRetries; i++) {
      const expireAt = Date.now() + timeout;

      const acquired = await this.redis.set(lockKey, lockValue, {
        NX: true,
        PX: timeout,
      });

      if (acquired) {
        return {
          key: lockKey,
          value: lockValue,
          expireAt,
        };
      }

      if (Date.now() - startTime > timeout) {
        return null;
      }

      await this._delay(this.retryDelay);
    }

    return null;
  }

  async release(lock) {
    if (!lock) return false;

    const lockKey = lock.key;
    const lockValue = lock.value;

    
    const currentValue = await this.redis.get(lockKey);

    if (currentValue === lockValue) {
      await this.redis.del(lockKey);
      return true;
    }

    return false;
  }

  async extend(lock, additionalTime) {
    if (!lock) return false;

    const lockKey = lock.key;
    const lockValue = lock.value;

    const currentValue = await this.redis.get(lockKey);

    if (currentValue === lockValue) {
      const newExpire = Date.now() + additionalTime;
      await this.redis.pexpire(lockKey, additionalTime);
      lock.expireAt = newExpire;
      return true;
    }

    return false;
  }

  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

class LeaderElection {
  constructor(consulClient, options = {}) {
    this.consul = consulClient;
    this.serviceName = options.serviceName;
    this.sessionId = null;
    this.isLeader = false;
    this.heartbeatInterval = options.heartbeatInterval || 5000;
    this.sessionTTL = options.sessionTTL || '10s';
    this.onLeaderChange = options.onLeaderChange || (() => {});
  }

  async start() {
    const session = await this.consul.session.create({
      name: `${this.serviceName}-leader`,
      ttl: this.sessionTTL,
      behavior: 'release',
    });

    this.sessionId = session.ID;
    await this._tryAcquireLeadership();
    this._startHeartbeat();
    this._watchLeadership();
  }

  async _tryAcquireLeadership() {
    const key = `service/${this.serviceName}/leader`;

    const acquired = await this.consul.kv.set({
      key,
      value: JSON.stringify({
        nodeId: this.sessionId,
        timestamp: Date.now(),
      }),
      acquire: this.sessionId,
    });

    const wasLeader = this.isLeader;
    this.isLeader = acquired;

    if (wasLeader !== this.isLeader) {
      this.onLeaderChange(this.isLeader);
    }

    return acquired;
  }

  _startHeartbeat() {
    this.heartbeatTimer = setInterval(async () => {
      try {
        await this.consul.session.renew(this.sessionId);
      } catch (error) {
        console.error('Heartbeat failed:', error);
      }
    }, this.heartbeatInterval);
  }

  _watchLeadership() {
    const key = `service/${this.serviceName}/leader`;

    
    const watch = this.consul.watch({
      method: this.consul.kv.get,
      options: { key },
    });

    watch.on('change', async () => {
      await this._tryAcquireLeadership();
    });

    watch.on('error', () => {
      
    });
  }

  async stop() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }

    if (this.sessionId) {
      await this.consul.session.destroy(this.sessionId);
    }

    this.isLeader = false;
  }

  getIsLeader() {
    return this.isLeader;
  }
}


class TraceContext {
  constructor(traceId, spanId, parentSpanId = null) {
    this.traceId = traceId || generateId();
    this.spanId = spanId || generateId();
    this.parentSpanId = parentSpanId;
  }

  
  static fromHeaders(headers) {
    const traceId = headers['x-trace-id'];
    const spanId = headers['x-span-id'];
    const parentSpanId = headers['x-parent-span-id'];

    
    return new TraceContext(traceId, spanId, parentSpanId);
  }

  static fromWebSocket(ws) {
    
    return new TraceContext();
  }

  toHeaders() {
    return {
      'x-trace-id': this.traceId,
      'x-span-id': this.spanId,
      'x-parent-span-id': this.parentSpanId,
    };
  }

  createChildSpan() {
    return new TraceContext(this.traceId, generateId(), this.spanId);
  }
}


class CorrelationContext {
  static current = null;

  static get() {
    
    return CorrelationContext.current;
  }

  static set(correlationId) {
    CorrelationContext.current = correlationId;
  }

  static createMiddleware() {
    return (req, res, next) => {
      const correlationId = req.headers['x-correlation-id'] || generateId();
      
      CorrelationContext.set(correlationId);
      res.setHeader('x-correlation-id', correlationId);
      next();
    };
  }
}


class MetricsCollector {
  constructor() {
    this.metrics = new Map();
  }

  increment(name, labels = {}) {
    
    const key = `${name}:${JSON.stringify(labels)}`;
    const current = this.metrics.get(key) || 0;
    this.metrics.set(key, current + 1);
  }

  getMetrics() {
    return Object.fromEntries(this.metrics);
  }
}


class StructuredLogger {
  constructor(serviceName) {
    this.serviceName = serviceName;
  }

  log(level, message, fields = {}) {
    
    const entry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      service: this.serviceName,
      ...fields,
    };
    return entry;
  }
}


function parseConfig(env) {
  return {
    port: env.PORT || 3000, 
    redisHost: env.REDIS_HOST || 'localhost',
    
    maxConnections: env.MAX_CONNECTIONS || '10',
    requestTimeout: env.REQUEST_TIMEOUT || '5000',
    cacheEnabled: env.CACHE_ENABLED || 'true',
    debugMode: env.DEBUG_MODE || 'false',
  };
}

class TokenBucketRateLimiter {
  constructor(options = {}) {
    this.maxTokens = options.maxTokens || 100;
    this.refillRate = options.refillRate || 10;
    this.tokens = options.initialTokens !== undefined ? options.initialTokens : this.maxTokens;
    this.lastRefillTime = Date.now();
  }

  tryConsume(count = 1) {
    this._refill();

    if (this.tokens >= count) {
      this.tokens -= count;
      return true;
    }

    return false;
  }

  _refill() {
    const now = Date.now();
    const elapsed = (now - this.lastRefillTime) / 1000;
    const tokensToAdd = elapsed * this.refillRate;

    this.tokens = this.tokens + tokensToAdd;
    if (this.tokens > this.maxTokens) {
      this.tokens = this.maxTokens;
    }

    this.lastRefillTime = now;
  }

  getAvailableTokens() {
    this._refill();
    return this.tokens;
  }

  reset() {
    this.tokens = this.maxTokens;
    this.lastRefillTime = Date.now();
  }
}

class ConsistentHashRing {
  constructor(replicas = 100) {
    this.replicas = replicas;
    this.ring = new Map();
    this.sortedKeys = [];
    this.nodes = new Set();
  }

  addNode(nodeId) {
    this.nodes.add(nodeId);
    for (let i = 0; i < this.replicas; i++) {
      const hash = this._hash(`${nodeId}:${i}`);
      this.ring.set(hash, nodeId);
      this.sortedKeys.push(hash);
    }
    this.sortedKeys.sort((a, b) => a - b);
  }

  removeNode(nodeId) {
    this.nodes.delete(nodeId);
    for (let i = 0; i < this.replicas; i++) {
      const hash = this._hash(`${nodeId}:${i}`);
      this.ring.delete(hash);
    }
    this.sortedKeys = this.sortedKeys.filter(k => this.ring.has(k));
  }

  getNode(key) {
    if (this.sortedKeys.length === 0) return null;

    const hash = this._hash(key);

    for (const ringKey of this.sortedKeys) {
      if (ringKey >= hash) {
        return this.ring.get(ringKey);
      }
    }

    return this.ring.get(this.sortedKeys[0]);
  }

  _hash(key) {
    const str = String(key);
    let hash = 0;
    for (let i = 0; i < Math.min(str.length, 4); i++) {
      hash = (hash << 8) + str.charCodeAt(i);
    }
    return hash >>> 0;
  }

  getDistribution(keys) {
    const distribution = {};
    for (const node of this.nodes) {
      distribution[node] = 0;
    }

    for (const key of keys) {
      const node = this.getNode(key);
      if (node) {
        distribution[node]++;
      }
    }

    return distribution;
  }

  getNodeCount() {
    return this.nodes.size;
  }
}

class BloomFilter {
  constructor(size = 1024, hashCount = 3) {
    this.size = size;
    this.hashCount = hashCount;
    this.bits = new Uint8Array(size);
    this.itemCount = 0;
  }

  add(item) {
    const hashes = this._getHashes(item);
    for (const hash of hashes) {
      this.bits[hash % this.size] = 1;
    }
    this.itemCount++;
  }

  mightContain(item) {
    const hashes = this._getHashes(item);
    for (const hash of hashes) {
      if (!this.bits[hash % this.size]) {
        return false;
      }
    }
    return true;
  }

  _getHashes(item) {
    const str = String(item);
    const hashes = [];

    for (let i = 0; i <= this.hashCount; i++) {
      let hash = i * 0x9e3779b9;
      for (let j = 0; j < str.length; j++) {
        hash = ((hash << 5) + hash) + str.charCodeAt(j);
        hash = hash & hash;
      }
      hashes.push(Math.abs(hash));
    }

    return hashes;
  }

  getExpectedFalsePositiveRate() {
    const bitsPerItem = this.size / Math.max(this.itemCount, 1);
    return Math.pow(1 - Math.exp(-this.hashCount / bitsPerItem), this.hashCount);
  }

  getStats() {
    const setBits = this.bits.reduce((count, bit) => count + bit, 0);
    return {
      size: this.size,
      hashCount: this.hashCount,
      itemCount: this.itemCount,
      setBits,
      fillRatio: setBits / this.size,
    };
  }
}

module.exports = {
  generateId,
  DistributedLock,
  LeaderElection,
  TraceContext,
  CorrelationContext,
  MetricsCollector,
  StructuredLogger,
  parseConfig,
  TokenBucketRateLimiter,
  ConsistentHashRing,
  BloomFilter,
};
