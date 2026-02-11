/**
 * Message Routing Service
 */

class MessageRouter {
  constructor(options = {}) {
    this.routes = new Map();
    this.fanoutGroups = new Map();
  }

  addRoute(topic, handler) {
    this.routes.set(topic, handler);
  }

  addFanout(group, topics) {
    this.fanoutGroups.set(group, topics);
  }

  async route(message) {
    const topic = message.topic || message.routingKey;
    const handler = this.routes.get(topic);

    if (handler) {
      return await handler(message);
    }

    for (const [group, topics] of this.fanoutGroups.entries()) {
      if (topics.includes(topic)) {
        const results = [];
        for (const t of topics) {
          const h = this.routes.get(t);
          if (h) results.push(await h(message));
        }
        return results;
      }
    }

    return null;
  }

  getRoutes() {
    return [...this.routes.keys()];
  }
}


class ContentBasedRouter {
  constructor() {
    this._rules = [];
    this._deadLetterHandler = null;
    this._metrics = { routed: 0, deadLettered: 0, errors: 0 };
  }

  addRule(rule) {
    this._rules.push({
      name: rule.name,
      condition: rule.condition,
      destination: rule.destination,
      priority: rule.priority || 0,
      transform: rule.transform || null,
    });
  }

  setDeadLetterHandler(handler) {
    this._deadLetterHandler = handler;
  }

  async route(message) {
    const sorted = [...this._rules].sort((a, b) => b.priority - a.priority);

    let matched = null;
    for (const rule of sorted) {
      try {
        if (rule.condition(message)) {
          let payload = message;

          if (rule.transform) {
            payload = rule.transform(message);
          }

          this._metrics.routed++;
          matched = {
            destination: rule.destination,
            payload,
            rule: rule.name,
          };
        }
      } catch (error) {
        this._metrics.errors++;
      }
    }

    if (matched) return matched;

    // No rule matched - dead letter
    this._metrics.deadLettered++;
    if (this._deadLetterHandler) {
      await this._deadLetterHandler(message);
    }
    return { destination: 'dead-letter', payload: message, rule: null };
  }

  getMetrics() {
    return { ...this._metrics };
  }
}


class LoadBalancedRouter {
  constructor(options = {}) {
    this._backends = [];
    this._strategy = options.strategy || 'round-robin';
    this._currentIndex = 0;
    this._healthStatus = new Map();
    this._weights = new Map();
  }

  addBackend(backend) {
    this._backends.push(backend);
    this._healthStatus.set(backend.id, { healthy: true, lastCheck: Date.now() });
    this._weights.set(backend.id, backend.weight || 1);
  }

  removeBackend(backendId) {
    this._backends = this._backends.filter(b => b.id !== backendId);
    this._healthStatus.delete(backendId);
    this._weights.delete(backendId);
  }

  selectBackend(request) {
    const healthy = this._backends.filter(b => {
      const status = this._healthStatus.get(b.id);
      return status && status.healthy;
    });

    if (healthy.length === 0) {
      return null;
    }

    switch (this._strategy) {
      case 'round-robin':
        return this._roundRobin(healthy);
      case 'weighted':
        return this._weighted(healthy);
      case 'least-connections':
        return this._leastConnections(healthy);
      default:
        return healthy[0];
    }
  }

  _roundRobin(backends) {
    const index = this._currentIndex % backends.length;
    this._currentIndex++;
    return backends[index];
  }

  _weighted(backends) {
    const totalWeight = backends.reduce((sum, b) => sum + (this._weights.get(b.id) || 1), 0);
    let random = Math.random() * totalWeight;

    for (const backend of backends) {
      random -= this._weights.get(backend.id) || 1;
      if (random <= 0) {
        return backend;
      }
    }

    return backends[backends.length - 1];
  }

  _leastConnections(backends) {
    return backends.sort((a, b) =>
      (a.connections || 0) - (b.connections || 0)
    )[0];
  }

  markHealthy(backendId) {
    this._healthStatus.set(backendId, { healthy: true, lastCheck: Date.now() });
  }

  markUnhealthy(backendId) {
    this._healthStatus.set(backendId, { healthy: false, lastCheck: Date.now() });
  }

  getHealthStatus() {
    return Object.fromEntries(this._healthStatus);
  }
}

module.exports = { MessageRouter, ContentBasedRouter, LoadBalancedRouter };
