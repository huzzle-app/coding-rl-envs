/**
 * Service Clients
 */


const { BaseEvent } = require('../events');

class CircuitBreaker {
  constructor(options = {}) {
    this.failureThreshold = options.failureThreshold || 5;
    this.resetTimeout = options.resetTimeout || 30000;
    this.failureCount = 0;
    this.state = 'closed';
    this.lastFailureTime = null;
    this.halfOpenRequests = 0;
    this.maxHalfOpenRequests = options.maxHalfOpenRequests || 3;
    this.maxRetryBudget = options.maxRetryBudget || 100;
    this.retryBudget = this.maxRetryBudget;
  }

  async execute(fn) {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime >= this.resetTimeout) {
        this.state = 'half-open';
        this.halfOpenRequests = 0;
      } else {
        throw new Error('Circuit breaker is open');
      }
    }

    if (this.state === 'half-open') {
      if (this.halfOpenRequests >= this.maxHalfOpenRequests) {
        throw new Error('Circuit breaker half-open limit reached');
      }
      this.halfOpenRequests++;
    }

    try {
      const result = await fn();
      this._onSuccess();
      return result;
    } catch (error) {
      this._onFailure();
      throw error;
    }
  }

  _onSuccess() {
    this.failureCount = 0;
    if (this.state === 'half-open') {
      this.state = 'closed';
    }
  }

  _onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    
    if (this.failureCount > this.failureThreshold) {
      this.state = 'open';
    }

    
    
    // When the off-by-one is fixed (>= instead of >), the circuit opens
    // one failure earlier, exposing that retryBudget tracking is broken.
    // The retryBudget should decrement by 1 per failure, but instead
    // it uses failureCount which resets on success.
    this.retryBudget = this.maxRetryBudget - this.failureCount;
  }

  getState() {
    return this.state;
  }

  reset() {
    this.failureCount = 0;
    this.state = 'closed';
    this.lastFailureTime = null;
  }
}

class ServiceClient {
  constructor(serviceName, options = {}) {
    this.serviceName = serviceName;
    this.baseUrl = options.baseUrl;
    this.timeout = options.timeout || 5000;
    this.circuitBreaker = new CircuitBreaker(options.circuitBreaker);
    this.retryConfig = {
      maxRetries: options.maxRetries || 3,
      retryDelay: options.retryDelay || 1000,
    };
  }

  async request(method, path, data = null, options = {}) {
    const axios = require('axios');

    const makeRequest = async () => {
      const response = await axios({
        method,
        url: `${this.baseUrl}${path}`,
        data,
        timeout: this.timeout,
        headers: {
          ...options.headers,
          'X-Service-Name': this.serviceName,
        },
      });
      return response.data;
    };

    return this.circuitBreaker.execute(async () => {
      let lastError;

      for (let attempt = 0; attempt <= this.retryConfig.maxRetries; attempt++) {
        try {
          return await makeRequest();
        } catch (error) {
          lastError = error;

          if (attempt < this.retryConfig.maxRetries) {
            
            await this._delay(this.retryConfig.retryDelay);
          }
        }
      }

      throw lastError;
    });
  }

  async get(path, options) {
    return this.request('GET', path, null, options);
  }

  async post(path, data, options) {
    return this.request('POST', path, data, options);
  }

  async put(path, data, options) {
    return this.request('PUT', path, data, options);
  }

  async delete(path, options) {
    return this.request('DELETE', path, null, options);
  }

  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}


class HealthChecker {
  constructor(consul, serviceName, port) {
    this.consul = consul;
    this.serviceName = serviceName;
    this.port = port;
  }

  async register() {
    
    await this.consul.agent.service.register({
      name: this.serviceName,
      port: this.port,
      check: {
        http: `http://localhost:${this.port}/health`,
        
        timeout: '5s',
        deregistercriticalserviceafter: '30s',
      },
    });
  }

  async deregister() {
    await this.consul.agent.service.deregister(this.serviceName);
  }
}

class RequestCoalescer {
  constructor() {
    this.pending = new Map();
  }

  async coalesce(key, fn) {
    if (this.pending.has(key)) {
      return this.pending.get(key);
    }

    const promise = fn().finally(() => {
      this.pending.delete(key);
    });

    this.pending.set(key, promise);
    return promise;
  }
}

class BulkheadIsolation {
  constructor(maxConcurrent = 10) {
    this.maxConcurrent = maxConcurrent;
    this.running = 0;
    this.queue = [];
  }

  async execute(fn) {
    if (this.running++ < this.maxConcurrent) {
      try {
        return await fn();
      } finally {
        this.running--;
        this._processQueue();
      }
    }

    return new Promise((resolve, reject) => {
      this.queue.push({ fn, resolve, reject });
      this.running--;
    });
  }

  _processQueue() {
    if (this.queue.length > 0 && this.running < this.maxConcurrent) {
      const { fn, resolve, reject } = this.queue.shift();
      this.running++;
      fn().then(resolve).catch(reject).finally(() => {
        this.running--;
        this._processQueue();
      });
    }
  }

  getStats() {
    return {
      running: this.running,
      queued: this.queue.length,
      maxConcurrent: this.maxConcurrent,
    };
  }
}

class RetryPolicy {
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || 3;
    this.baseDelay = options.baseDelay || 100;
    this.maxDelay = options.maxDelay || 30000;
    this.jitterFactor = options.jitterFactor || 0.1;
  }

  getDelay(attempt) {
    const exponentialDelay = this.baseDelay * Math.pow(2, attempt);
    const jitter = exponentialDelay * this.jitterFactor * Math.random();
    return Math.min(exponentialDelay + jitter, this.maxDelay);
  }

  async executeWithRetry(fn) {
    let lastError;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        if (attempt < this.maxRetries) {
          const delay = this.getDelay(attempt);
          await new Promise(r => setTimeout(r, delay));
        }
      }
    }

    throw lastError;
  }

  isRetryable(error) {
    const retryableCodes = [408, 429, 500, 502, 503, 504];
    return retryableCodes.includes(error.statusCode || error.status);
  }
}

module.exports = {
  CircuitBreaker,
  ServiceClient,
  HealthChecker,
  RequestCoalescer,
  BulkheadIsolation,
  RetryPolicy,
};
