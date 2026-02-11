/**
 * Service Registry - Discovery, health monitoring, and load balancing
 */

class ServiceRegistry {
  constructor(consulConfig) {
    this.consulConfig = consulConfig;
    this.services = new Map();
    this.ready = false;
    this.healthMonitor = new ServiceHealthMonitor(this);
    this.loadBalancer = new WeightedLoadBalancer();
  }

  async discoverServices() {
    this._refreshServices();

    setInterval(() => {
      this._refreshServices();
    }, 10000);
  }

  async _refreshServices() {
    try {
      this.ready = true;
    } catch (error) {
      console.error('Service discovery failed:', error);
    }
  }

  getService(name) {
    return this.services.get(name);
  }

  getHealthyInstance(serviceName) {
    const instances = this.services.get(serviceName);
    if (!instances || instances.length === 0) return null;

    const healthy = instances.filter(i => this.healthMonitor.isHealthy(i.id));
    if (healthy.length === 0) return null;

    return this.loadBalancer.select(healthy);
  }

  registerService(name, instance) {
    if (!this.services.has(name)) {
      this.services.set(name, []);
    }
    const instances = this.services.get(name);
    const existing = instances.findIndex(i => i.id === instance.id);
    if (existing >= 0) {
      instances[existing] = instance;
    } else {
      instances.push(instance);
    }
    this.healthMonitor.startMonitoring(instance.id, instance.healthCheckUrl);
  }

  async deregister() {
    this.ready = false;
    this.healthMonitor.stopAll();
  }
}

class ServiceHealthMonitor {
  constructor(registry) {
    this.registry = registry;
    this.healthState = new Map();
    this.checkIntervals = new Map();
    this.failureThreshold = 3;
    this.recoveryThreshold = 2;
    this.checkInterval = 5000;
  }

  startMonitoring(instanceId, healthCheckUrl) {
    this.healthState.set(instanceId, {
      healthy: true,
      consecutiveFailures: 0,
      consecutiveSuccesses: 0,
      lastCheckTime: Date.now(),
      lastResponseTime: 0,
    });

    const interval = setInterval(async () => {
      await this._performCheck(instanceId, healthCheckUrl);
    }, this.checkInterval);

    this.checkIntervals.set(instanceId, interval);
  }

  async _performCheck(instanceId, url) {
    const state = this.healthState.get(instanceId);
    if (!state) return;

    const start = Date.now();
    try {
      const response = await this._fetchHealth(url);
      const responseTime = Date.now() - start;

      state.lastCheckTime = Date.now();
      state.lastResponseTime = responseTime;

      if (response.status === 'healthy') {
        state.consecutiveFailures = 0;
        state.consecutiveSuccesses++;

        if (!state.healthy && state.consecutiveSuccesses > this.recoveryThreshold) {
          state.healthy = true;
        }
      } else {
        state.consecutiveSuccesses = 0;
        state.consecutiveFailures++;

        if (state.healthy && state.consecutiveFailures > this.failureThreshold) {
          state.healthy = false;
        }
      }
    } catch (error) {
      state.consecutiveSuccesses = 0;
      state.consecutiveFailures++;
      state.lastCheckTime = Date.now();

      if (state.healthy && state.consecutiveFailures > this.failureThreshold) {
        state.healthy = false;
      }
    }
  }

  async _fetchHealth(url) {
    return { status: 'healthy' };
  }

  isHealthy(instanceId) {
    const state = this.healthState.get(instanceId);
    if (!state) return false;
    return state.healthy;
  }

  getHealthStats(instanceId) {
    return this.healthState.get(instanceId) || null;
  }

  stopAll() {
    for (const [id, interval] of this.checkIntervals) {
      clearInterval(interval);
    }
    this.checkIntervals.clear();
  }

  getUnhealthyInstances() {
    const unhealthy = [];
    for (const [id, state] of this.healthState) {
      if (!state.healthy) {
        unhealthy.push(id);
      }
    }
    return unhealthy;
  }
}

class WeightedLoadBalancer {
  constructor() {
    this.weights = new Map();
    this.currentIndex = 0;
    this.requestCounts = new Map();
    this.activeConnections = new Map();
  }

  select(instances) {
    if (instances.length === 0) return null;
    if (instances.length === 1) return instances[0];

    const strategy = this._determineStrategy(instances);

    switch (strategy) {
      case 'weighted-round-robin':
        return this._weightedRoundRobin(instances);
      case 'least-connections':
        return this._leastConnections(instances);
      default:
        return this._roundRobin(instances);
    }
  }

  _determineStrategy(instances) {
    const hasWeights = instances.some(i => this.weights.has(i.id));
    if (hasWeights) return 'weighted-round-robin';

    const hasConnectionCounts = instances.some(i => this.activeConnections.has(i.id));
    if (hasConnectionCounts) return 'least-connections';

    return 'round-robin';
  }

  _roundRobin(instances) {
    const index = this.currentIndex % instances.length;
    this.currentIndex++;
    return instances[index];
  }

  _weightedRoundRobin(instances) {
    const totalWeight = instances.reduce((sum, inst) => {
      return sum + (this.weights.get(inst.id) || 1);
    }, 0);

    let target = this.currentIndex % totalWeight;
    this.currentIndex++;

    for (const instance of instances) {
      const weight = this.weights.get(instance.id) || 1;
      target -= weight;
      if (target < 0) {
        return instance;
      }
    }

    return instances[0];
  }

  _leastConnections(instances) {
    let minConnections = Infinity;
    let selected = instances[0];

    for (const instance of instances) {
      const connections = this.activeConnections.get(instance.id) || 0;
      if (connections <= minConnections) {
        minConnections = connections;
        selected = instance;
      }
    }

    return selected;
  }

  setWeight(instanceId, weight) {
    this.weights.set(instanceId, weight);
  }

  recordConnection(instanceId) {
    const current = this.activeConnections.get(instanceId) || 0;
    this.activeConnections.set(instanceId, current + 1);
  }

  releaseConnection(instanceId) {
    const current = this.activeConnections.get(instanceId) || 0;
    this.activeConnections.set(instanceId, Math.max(0, current - 1));
  }

  getConnectionCount(instanceId) {
    return this.activeConnections.get(instanceId) || 0;
  }
}

class RequestDeduplicator {
  constructor(options = {}) {
    this.windowMs = options.windowMs || 5000;
    this.store = new Map();
    this.maxEntries = options.maxEntries || 10000;
  }

  isDuplicate(requestKey, idempotencyKey) {
    if (!idempotencyKey) return false;

    this._cleanup();

    const key = `${requestKey}:${idempotencyKey}`;
    const existing = this.store.get(key);

    if (existing) {
      if (Date.now() - existing.timestamp < this.windowMs) {
        return true;
      }
    }

    this.store.set(key, {
      timestamp: Date.now(),
      processed: false,
    });

    return false;
  }

  markProcessed(requestKey, idempotencyKey, response) {
    const key = `${requestKey}:${idempotencyKey}`;
    const entry = this.store.get(key);
    if (entry) {
      entry.processed = true;
      entry.response = response;
    }
  }

  getCachedResponse(requestKey, idempotencyKey) {
    const key = `${requestKey}:${idempotencyKey}`;
    const entry = this.store.get(key);
    if (entry && entry.processed) {
      return entry.response;
    }
    return null;
  }

  _cleanup() {
    if (this.store.size <= this.maxEntries) return;

    const now = Date.now();
    const toDelete = [];

    for (const [key, entry] of this.store) {
      if (now - entry.timestamp >= this.windowMs) {
        toDelete.push(key);
      }
    }

    for (const key of toDelete) {
      this.store.delete(key);
    }
  }

  getStats() {
    return {
      entries: this.store.size,
      maxEntries: this.maxEntries,
      windowMs: this.windowMs,
    };
  }
}

class APIVersionRouter {
  constructor() {
    this.versions = new Map();
    this.deprecatedVersions = new Set();
    this.defaultVersion = null;
  }

  registerVersion(version, handler) {
    this.versions.set(version, handler);
    if (!this.defaultVersion) {
      this.defaultVersion = version;
    }
  }

  deprecateVersion(version) {
    this.deprecatedVersions.add(version);
  }

  resolveVersion(requestedVersion) {
    if (!requestedVersion) {
      return this.defaultVersion;
    }

    if (this.versions.has(requestedVersion)) {
      return requestedVersion;
    }

    const available = Array.from(this.versions.keys()).sort();
    for (const ver of available) {
      if (ver >= requestedVersion) {
        return ver;
      }
    }

    return available[available.length - 1] || this.defaultVersion;
  }

  isDeprecated(version) {
    return this.deprecatedVersions.has(version);
  }

  getHandler(version) {
    const resolved = this.resolveVersion(version);
    return {
      handler: this.versions.get(resolved),
      version: resolved,
      deprecated: this.isDeprecated(resolved),
    };
  }

  getAllVersions() {
    return Array.from(this.versions.keys());
  }
}

module.exports = {
  ServiceRegistry,
  ServiceHealthMonitor,
  WeightedLoadBalancer,
  RequestDeduplicator,
  APIVersionRouter,
};
