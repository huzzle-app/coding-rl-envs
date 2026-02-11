/**
 * Service Clients
 *
 * BUG L1: Circular import - requires events module
 * BUG L3: Missing await on async initialization
 * BUG L5: Workspace dependency version conflict
 * BUG E7: Plugin class loading isolation leak
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

    
    // Should be >= not >
    if (this.failureCount > this.failureThreshold) {
      this.state = 'open';
    }
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
    
    this._initializeFromConsul();
  }

  
  async _initializeFromConsul() {
    try {
      // Simulates async service discovery lookup
      const serviceConfig = await this._lookupService();
      if (serviceConfig) {
        this.baseUrl = serviceConfig.url;
      }
    } catch (error) {
      // Silent failure - service URL might be undefined
    }
  }

  async _lookupService() {
    // Would use consul in production
    return null;
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
            // Constant delay causes synchronized retries (thundering herd)
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


class PluginLoader {
  constructor() {
    
    this.registry = {};
    this.loadedModules = new Map();
  }

  loadPlugin(pluginPath) {
    
    
    if (this.loadedModules.has(pluginPath)) {
      return this.loadedModules.get(pluginPath);
    }

    try {
      const plugin = require(pluginPath);
      this.loadedModules.set(pluginPath, plugin);
      
      if (plugin.name) {
        this.registry[plugin.name] = plugin;
      }
      return plugin;
    } catch (error) {
      throw new Error(`Failed to load plugin: ${pluginPath}: ${error.message}`);
    }
  }

  getPlugin(name) {
    return this.registry[name];
  }

  unloadPlugin(name) {
    
    delete this.registry[name];
    // Doesn't remove from loadedModules map
  }
}

module.exports = {
  CircuitBreaker,
  ServiceClient,
  PluginLoader,
};
