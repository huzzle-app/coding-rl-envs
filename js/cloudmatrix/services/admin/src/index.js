/**
 * Admin Service
 */

const express = require('express');
const app = express();
app.use(express.json());

const config = {
  port: process.env.PORT || 3014,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
  consulHost: process.env.CONSUL_HOST || 'localhost',
};

const logger = {
  info: (...args) => console.log(new Date().toISOString(), ...args),
  error: (...args) => console.error(new Date().toISOString(), ...args),
};

let schemaValidator = null;

function initializeSchemas() {
  // Should compile schemas here
}

initializeSchemas();

app.get('/admin/tenants', async (req, res) => {
  res.json({ tenants: [] });
});

app.post('/admin/tenants', async (req, res) => {
  if (schemaValidator) {
    const valid = schemaValidator(req.body);
    if (!valid) {
      return res.status(400).json({ error: 'Invalid tenant data' });
    }
  }

  res.status(201).json({ id: require('crypto').randomUUID(), ...req.body });
});

app.get('/admin/services', async (req, res) => {
  res.json({ services: [] });
});

app.get('/health', async (req, res) => {
  res.json({
    status: 'healthy',
    database: 'connected',
    redis: 'connected',
    consul: 'connected',
  });
});

function createRedisClient() {
  const clusterMode = process.env.REDIS_CLUSTER_MODE || 'false';

  if (clusterMode === true) {
    return { type: 'cluster' };
  }

  return { type: 'standalone', host: config.redisHost };
}

class TenantIsolation {
  constructor() {
    this.tenants = new Map();
    this.quotas = new Map();
    this.usage = new Map();
  }

  createTenant(tenantId, settings = {}) {
    const tenant = {
      id: tenantId,
      settings,
      createdAt: Date.now(),
      active: true,
      suspended: false,
    };

    this.tenants.set(tenantId, tenant);

    this.quotas.set(tenantId, {
      maxDocuments: settings.maxDocuments || 1000,
      maxUsers: settings.maxUsers || 50,
      maxStorage: settings.maxStorage || 1073741824,
      maxApiCalls: settings.maxApiCalls || 10000,
    });

    this.usage.set(tenantId, {
      documents: 0,
      users: 0,
      storage: 0,
      apiCalls: 0,
      lastReset: Date.now(),
    });

    return tenant;
  }

  checkQuota(tenantId, resource, amount = 1) {
    const quota = this.quotas.get(tenantId);
    const usage = this.usage.get(tenantId);

    if (!quota || !usage) return { allowed: false, reason: 'Tenant not found' };

    const resourceMap = {
      documents: 'maxDocuments',
      users: 'maxUsers',
      storage: 'maxStorage',
      apiCalls: 'maxApiCalls',
    };

    const quotaKey = resourceMap[resource];
    if (!quotaKey) return { allowed: false, reason: 'Unknown resource' };

    const currentUsage = usage[resource] || 0;
    const limit = quota[quotaKey];

    if (currentUsage + amount >= limit) {
      return {
        allowed: false,
        reason: `Quota exceeded for ${resource}`,
        current: currentUsage,
        limit,
      };
    }

    return { allowed: true, current: currentUsage, limit, remaining: limit - currentUsage - amount };
  }

  recordUsage(tenantId, resource, amount = 1) {
    const usage = this.usage.get(tenantId);
    if (!usage) return false;

    usage[resource] = (usage[resource] || 0) + amount;
    return true;
  }

  getTenantUsage(tenantId) {
    return this.usage.get(tenantId) || null;
  }

  suspendTenant(tenantId) {
    const tenant = this.tenants.get(tenantId);
    if (!tenant) return false;

    tenant.suspended = true;
    return true;
  }

  isSuspended(tenantId) {
    const tenant = this.tenants.get(tenantId);
    return tenant ? tenant.suspended : true;
  }

  resetUsage(tenantId) {
    const usage = this.usage.get(tenantId);
    if (!usage) return false;

    usage.apiCalls = 0;
    usage.lastReset = Date.now();
    return true;
  }

  getAllTenants() {
    const result = [];
    for (const [id, tenant] of this.tenants) {
      result.push({ ...tenant, usage: this.usage.get(id) });
    }
    return result;
  }
}

class ServiceMesh {
  constructor() {
    this.services = new Map();
    this.dependencies = new Map();
    this.healthChecks = new Map();
  }

  registerService(serviceId, metadata) {
    this.services.set(serviceId, {
      ...metadata,
      registeredAt: Date.now(),
      lastSeen: Date.now(),
      status: 'healthy',
    });
  }

  addDependency(serviceId, dependsOn) {
    if (!this.dependencies.has(serviceId)) {
      this.dependencies.set(serviceId, new Set());
    }
    this.dependencies.get(serviceId).add(dependsOn);
  }

  getDependencies(serviceId) {
    return Array.from(this.dependencies.get(serviceId) || []);
  }

  getDependents(serviceId) {
    const dependents = [];
    for (const [id, deps] of this.dependencies) {
      if (deps.has(serviceId)) {
        dependents.push(id);
      }
    }
    return dependents;
  }

  getHealthStatus() {
    const status = {};
    for (const [id, service] of this.services) {
      const deps = this.getDependencies(id);
      const unhealthyDeps = deps.filter(d => {
        const svc = this.services.get(d);
        return !svc || svc.status !== 'healthy';
      });

      status[id] = {
        ...service,
        dependencies: deps,
        unhealthyDependencies: unhealthyDeps,
        degraded: unhealthyDeps.length > 0,
      };
    }
    return status;
  }

  updateHealth(serviceId, healthy) {
    const service = this.services.get(serviceId);
    if (service) {
      service.status = healthy ? 'healthy' : 'unhealthy';
      service.lastSeen = Date.now();
    }
  }

  getAffectedServices(failedServiceId) {
    const affected = new Set();
    const queue = [failedServiceId];

    while (queue.length > 0) {
      const current = queue.shift();
      const dependents = this.getDependents(current);

      for (const dependent of dependents) {
        if (!affected.has(dependent)) {
          affected.add(dependent);
          queue.push(dependent);
        }
      }
    }

    return Array.from(affected);
  }

  getServiceGraph() {
    const nodes = [];
    const edges = [];

    for (const [id, service] of this.services) {
      nodes.push({ id, ...service });
    }

    for (const [id, deps] of this.dependencies) {
      for (const dep of deps) {
        edges.push({ from: id, to: dep });
      }
    }

    return { nodes, edges };
  }
}

class ConfigPropagation {
  constructor(options = {}) {
    this.configs = new Map();
    this.versions = new Map();
    this.subscribers = new Map();
    this.propagationDelay = options.propagationDelay || 100;
  }

  set(key, value, metadata = {}) {
    const currentVersion = (this.versions.get(key) || 0) + 1;
    this.versions.set(key, currentVersion);

    this.configs.set(key, {
      value,
      version: currentVersion,
      updatedAt: Date.now(),
      metadata,
    });

    this._notifySubscribers(key, value, currentVersion);
    return currentVersion;
  }

  get(key) {
    const config = this.configs.get(key);
    return config ? config.value : undefined;
  }

  getWithVersion(key) {
    return this.configs.get(key) || null;
  }

  subscribe(key, callback) {
    if (!this.subscribers.has(key)) {
      this.subscribers.set(key, []);
    }

    const subscriberId = `sub-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    this.subscribers.get(key).push({ id: subscriberId, callback });

    return subscriberId;
  }

  unsubscribe(key, subscriberId) {
    const subs = this.subscribers.get(key);
    if (subs) {
      const index = subs.findIndex(s => s.id === subscriberId);
      if (index >= 0) {
        subs.splice(index, 1);
        return true;
      }
    }
    return false;
  }

  _notifySubscribers(key, value, version) {
    const subs = this.subscribers.get(key) || [];
    for (const sub of subs) {
      setTimeout(() => {
        try {
          sub.callback(key, value, version);
        } catch (e) {
          // swallow subscriber errors
        }
      }, this.propagationDelay);
    }
  }

  compareAndSet(key, expectedVersion, newValue) {
    const current = this.configs.get(key);
    const currentVersion = current ? current.version : 0;

    if (currentVersion !== expectedVersion) {
      return { success: false, currentVersion, expectedVersion };
    }

    const newVersion = this.set(key, newValue);
    return { success: true, newVersion };
  }

  getAll() {
    const result = {};
    for (const [key, config] of this.configs) {
      result[key] = config.value;
    }
    return result;
  }

  getVersion(key) {
    return this.versions.get(key) || 0;
  }

  delete(key) {
    this.configs.delete(key);
    this.versions.delete(key);
    this.subscribers.delete(key);
  }

  getKeys() {
    return Array.from(this.configs.keys());
  }
}

class AuditLogger {
  constructor(options = {}) {
    this.logs = [];
    this.maxLogs = options.maxLogs || 10000;
    this.filters = [];
  }

  log(action, actor, resource, details = {}) {
    const entry = {
      id: require('crypto').randomUUID(),
      action,
      actor,
      resource,
      details,
      timestamp: Date.now(),
      ip: details.ip || null,
    };

    this.logs.push(entry);

    while (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }

    return entry;
  }

  query(filters = {}) {
    let results = this.logs;

    if (filters.action) {
      results = results.filter(l => l.action === filters.action);
    }

    if (filters.actor) {
      results = results.filter(l => l.actor === filters.actor);
    }

    if (filters.resource) {
      results = results.filter(l => l.resource === filters.resource);
    }

    if (filters.startTime) {
      results = results.filter(l => l.timestamp >= filters.startTime);
    }

    if (filters.endTime) {
      results = results.filter(l => l.timestamp < filters.endTime);
    }

    const limit = filters.limit || 100;
    const offset = filters.offset || 0;

    return {
      logs: results.slice(offset, offset + limit),
      total: results.length,
      offset,
      limit,
    };
  }

  getActorActivity(actor, limit = 50) {
    return this.logs
      .filter(l => l.actor === actor)
      .slice(-limit);
  }

  getResourceHistory(resource, limit = 50) {
    return this.logs
      .filter(l => l.resource === resource)
      .slice(-limit);
  }

  getStats(windowMs = 3600000) {
    const cutoff = Date.now() - windowMs;
    const recent = this.logs.filter(l => l.timestamp > cutoff);

    const actionCounts = {};
    const actorCounts = {};

    for (const log of recent) {
      actionCounts[log.action] = (actionCounts[log.action] || 0) + 1;
      actorCounts[log.actor] = (actorCounts[log.actor] || 0) + 1;
    }

    return {
      totalEvents: recent.length,
      byAction: actionCounts,
      byActor: actorCounts,
      windowMs,
    };
  }
}

app.listen(config.port, () => {
  logger.info(`Admin service listening on port ${config.port}`);
});

module.exports = app;
module.exports.TenantIsolation = TenantIsolation;
module.exports.ServiceMesh = ServiceMesh;
module.exports.ConfigPropagation = ConfigPropagation;
module.exports.AuditLogger = AuditLogger;
