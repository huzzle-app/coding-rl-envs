/**
 * Shared Utilities
 *
 * BUG L1: Circular import - requires clients
 * BUG A1: Distributed lock doesn't handle clock skew
 * BUG A2: Leader election split-brain
 * BUG A3: Lock timeout too short
 */

const crypto = require('crypto');


const { ServiceClient } = require('../clients');

function generateId() {
  return crypto.randomUUID();
}

class DistributedLock {
  constructor(redisClient, options = {}) {
    this.redis = redisClient;
    this.lockPrefix = options.prefix || 'lock:';
    
    this.defaultTimeout = options.timeout || 5000; // 5 seconds
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

      // Check if we've exceeded our timeout
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
    // Create session
    const session = await this.consul.session.create({
      name: `${this.serviceName}-leader`,
      ttl: this.sessionTTL,
      
      behavior: 'release',
    });

    this.sessionId = session.ID;

    // Try to acquire leadership
    await this._tryAcquireLeadership();

    // Start heartbeat
    this._startHeartbeat();

    // Watch for changes
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
        
        // Should try to re-establish session
        console.error('Heartbeat failed:', error);
      }
    }, this.heartbeatInterval);
  }

  _watchLeadership() {
    
    // Connection loss causes silent failure
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

// Trace context propagation
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

    
    // This breaks trace correlation
    return new TraceContext(traceId, spanId, parentSpanId);
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

// Correlation ID for request tracking
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

module.exports = {
  generateId,
  DistributedLock,
  LeaderElection,
  TraceContext,
  CorrelationContext,
};
