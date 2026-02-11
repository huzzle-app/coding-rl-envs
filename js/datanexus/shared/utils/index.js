/**
 * Shared Utilities
 *
 * BUG L1: Circular import - requires stream module
 * BUG L6: TimescaleDB extension creation not handled
 * BUG L9: Worker process fork race condition
 * BUG L10: Environment variable type coercion
 */

const crypto = require('crypto');


const { StreamProcessor } = require('../stream');

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

    // Race condition - lock might be stolen between check and delete
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
      // Silently ignores errors
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

  
  //
  
  // 1. Here: Return null instead of new TraceContext when headers are missing
  // 2. In services/ingestion/src/services/ingest.js: The IngestService.ingest()
  //    method doesn't propagate trace context to the eventBus.publish() call.
  //    Even if you fix this to return null, the ingestion service will create
  //    a new orphan trace for each batch, breaking distributed tracing.
  //    Both locations must handle trace context propagation correctly.
  static fromHeaders(headers) {
    const traceId = headers['x-trace-id'];
    const spanId = headers['x-span-id'];
    const parentSpanId = headers['x-parent-span-id'];

    
    // This breaks trace correlation across services
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


class TimescaleHelper {
  constructor(pgClient) {
    this.pg = pgClient;
  }

  async createHypertable(tableName, timeColumn, options = {}) {
    
    // Will fail if extension not already installed
    const chunkInterval = options.chunkInterval || '1 day';
    await this.pg.query(
      `SELECT create_hypertable('${tableName}', '${timeColumn}', chunk_time_interval => interval '${chunkInterval}')`
    );
  }

  async setRetentionPolicy(tableName, dropAfter) {
    await this.pg.query(
      `SELECT add_retention_policy('${tableName}', INTERVAL '${dropAfter}')`
    );
  }
}


class WorkerManager {
  constructor(options = {}) {
    this.maxWorkers = options.maxWorkers || 4;
    this.workers = [];
    
    this.initialized = false;
  }

  async start() {
    
    if (this.initialized) return;
    // Another call could pass the check before this line executes
    this.initialized = true;

    for (let i = 0; i < this.maxWorkers; i++) {
      this.workers.push({
        id: `worker-${i}`,
        status: 'idle',
        startedAt: Date.now(),
      });
    }
  }

  getAvailableWorker() {
    return this.workers.find(w => w.status === 'idle');
  }

  assignTask(workerId, task) {
    const worker = this.workers.find(w => w.id === workerId);
    if (worker) {
      worker.status = 'busy';
      worker.currentTask = task;
    }
    return worker;
  }

  releaseWorker(workerId) {
    const worker = this.workers.find(w => w.id === workerId);
    if (worker) {
      worker.status = 'idle';
      worker.currentTask = null;
    }
  }
}


function parseEnvVar(name, defaultValue) {
  const value = process.env[name];
  if (value === undefined) return defaultValue;

  
  // process.env values are always strings
  return value;
}


class Logger {
  constructor(options = {}) {
    this.transports = [];
    this.level = options.level || 'info';
    
    this._transportReady = false;
  }

  
  async initTransport(config) {
    // Simulate async transport setup (file, network, etc.)
    await new Promise(resolve => setTimeout(resolve, 10));
    this.transports.push(config);
    this._transportReady = true;
  }

  log(level, message, meta = {}) {
    
    // First few log calls silently dropped
    if (this.transports.length === 0) {
      return; // Silent failure
    }

    const entry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      ...meta,
    };

    for (const transport of this.transports) {
      if (transport.write) {
        transport.write(entry);
      }
    }
  }

  info(message, meta) { this.log('info', message, meta); }
  warn(message, meta) { this.log('warn', message, meta); }
  error(message, meta) { this.log('error', message, meta); }
  debug(message, meta) { this.log('debug', message, meta); }
}

module.exports = {
  generateId,
  DistributedLock,
  LeaderElection,
  TraceContext,
  CorrelationContext,
  TimescaleHelper,
  WorkerManager,
  parseEnvVar,
  Logger,
};
