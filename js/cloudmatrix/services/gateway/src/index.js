/**
 * CloudMatrix API Gateway
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');

const config = require('./config');
const routes = require('./routes');
const { authMiddleware } = require('./middleware/auth');
const { errorHandler } = require('./middleware/error');

const app = express();

app.use(helmet());

app.use(cors(config.cors));
app.use(compression());

const limiter = rateLimit({
  windowMs: config.rateLimit.windowMs,
  max: config.rateLimit.max,
  keyGenerator: (req) => {
    return req.headers['x-forwarded-for'] || req.ip;
  },
});
app.use(limiter);

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: Date.now() });
});

app.use('/api', authMiddleware);

app.use('/api', routes);

app.use(errorHandler);

class RequestPipeline {
  constructor() {
    this.preProcessors = [];
    this.postProcessors = [];
    this.transformers = [];
  }

  addPreProcessor(fn) {
    this.preProcessors.push(fn);
  }

  addPostProcessor(fn) {
    this.postProcessors.push(fn);
  }

  addTransformer(fn) {
    this.transformers.push(fn);
  }

  async processRequest(req) {
    let context = { req, metadata: {}, startTime: Date.now() };

    for (const processor of this.preProcessors) {
      context = await processor(context);
      if (context.aborted) return context;
    }

    return context;
  }

  async processResponse(res, context) {
    let result = { res, context };

    for (const processor of this.postProcessors) {
      result = await processor(result);
    }

    result.context.metadata.processingTime = Date.now() - result.context.startTime;
    return result;
  }

  transformBody(body, contentType) {
    let transformed = body;

    for (const transformer of this.transformers) {
      transformed = transformer(transformed, contentType);
    }

    return transformed;
  }
}

class CircuitBreakerGateway {
  constructor(options = {}) {
    this.services = new Map();
    this.halfOpenMax = options.halfOpenMax || 3;
    this.resetTimeout = options.resetTimeout || 30000;
    this.failureThreshold = options.failureThreshold || 5;
    this.monitorInterval = options.monitorInterval || 10000;
  }

  getServiceState(serviceName) {
    if (!this.services.has(serviceName)) {
      this.services.set(serviceName, {
        state: 'closed',
        failures: 0,
        successes: 0,
        lastFailureTime: 0,
        halfOpenAttempts: 0,
      });
    }
    return this.services.get(serviceName);
  }

  async executeRequest(serviceName, requestFn) {
    const state = this.getServiceState(serviceName);

    if (state.state === 'open') {
      const elapsed = Date.now() - state.lastFailureTime;
      if (elapsed < this.resetTimeout) {
        throw new Error(`Circuit breaker open for ${serviceName}`);
      }
      state.state = 'half-open';
      state.halfOpenAttempts = 0;
    }

    if (state.state === 'half-open') {
      if (state.halfOpenAttempts >= this.halfOpenMax) {
        state.state = 'open';
        state.lastFailureTime = Date.now();
        throw new Error(`Circuit breaker re-opened for ${serviceName}`);
      }
      state.halfOpenAttempts++;
    }

    try {
      const result = await requestFn();
      this._recordSuccess(serviceName);
      return result;
    } catch (error) {
      this._recordFailure(serviceName);
      throw error;
    }
  }

  _recordSuccess(serviceName) {
    const state = this.getServiceState(serviceName);
    state.successes++;

    if (state.state === 'half-open') {
      if (state.successes >= this.halfOpenMax) {
        state.state = 'closed';
        state.failures = 0;
        state.successes = 0;
      }
    } else {
      state.failures = 0;
    }
  }

  _recordFailure(serviceName) {
    const state = this.getServiceState(serviceName);
    state.failures++;
    state.lastFailureTime = Date.now();

    if (state.state === 'half-open') {
      state.state = 'open';
    } else if (state.failures > this.failureThreshold) {
      state.state = 'open';
    }
  }

  getStatus() {
    const result = {};
    for (const [name, state] of this.services) {
      result[name] = {
        state: state.state,
        failures: state.failures,
      };
    }
    return result;
  }

  reset(serviceName) {
    this.services.delete(serviceName);
  }
}

class ResponseCache {
  constructor(options = {}) {
    this.cache = new Map();
    this.maxSize = options.maxSize || 500;
    this.defaultTTL = options.defaultTTL || 60000;
    this.varyHeaders = options.varyHeaders || ['accept', 'accept-encoding'];
  }

  generateKey(req) {
    const varyParts = this.varyHeaders.map(h => req.headers[h] || '').join('|');
    return `${req.method}:${req.url}:${varyParts}`;
  }

  get(req) {
    const key = this.generateKey(req);
    const entry = this.cache.get(key);

    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    entry.hits++;
    return entry;
  }

  set(req, responseData, ttl) {
    if (this.cache.size >= this.maxSize) {
      this._evictLRU();
    }

    const key = this.generateKey(req);
    this.cache.set(key, {
      data: responseData,
      createdAt: Date.now(),
      expiresAt: Date.now() + (ttl || this.defaultTTL),
      hits: 0,
    });
  }

  invalidate(pattern) {
    const toDelete = [];
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        toDelete.push(key);
      }
    }
    for (const key of toDelete) {
      this.cache.delete(key);
    }
    return toDelete.length;
  }

  _evictLRU() {
    let oldestKey = null;
    let oldestTime = Infinity;

    for (const [key, entry] of this.cache) {
      if (entry.createdAt < oldestTime) {
        oldestTime = entry.createdAt;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      this.cache.delete(oldestKey);
    }
  }

  getStats() {
    let totalHits = 0;
    let expired = 0;
    const now = Date.now();

    for (const entry of this.cache.values()) {
      totalHits += entry.hits;
      if (now > entry.expiresAt) expired++;
    }

    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      totalHits,
      expired,
    };
  }
}

async function start() {
  const { ServiceRegistry } = require('./services/registry');
  const registry = new ServiceRegistry(config.consul);

  registry.discoverServices();

  const server = app.listen(config.port, () => {
    console.log(`Gateway listening on port ${config.port}`);
  });

  process.on('SIGTERM', async () => {
    console.log('Shutting down gateway...');
    server.close();
    await registry.deregister();
    process.exit(0);
  });
}

start().catch(console.error);

module.exports = app;
module.exports.RequestPipeline = RequestPipeline;
module.exports.CircuitBreakerGateway = CircuitBreakerGateway;
module.exports.ResponseCache = ResponseCache;
