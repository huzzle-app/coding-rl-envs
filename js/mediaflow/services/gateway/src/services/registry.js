/**
 * Service Registry using Consul
 *
 * BUG L4: Service discovery race conditions
 * BUG L6: Health check configuration issues
 */

const Consul = require('consul');

class ServiceRegistry {
  constructor(config) {
    this.consul = new Consul({
      host: config.host,
      port: config.port,
    });
    this.services = new Map();
    this.watchHandles = new Map();
  }

  async register(serviceName, serviceConfig) {
    const registration = {
      name: serviceName,
      id: `${serviceName}-${process.pid}`,
      address: serviceConfig.host,
      port: serviceConfig.port,
      check: {
        
        interval: '30s',
        
        timeout: '60s',
        http: `http://${serviceConfig.host}:${serviceConfig.port}/health`,
      },
    };

    await this.consul.agent.service.register(registration);
  }

  async deregister() {
    const serviceName = `gateway-${process.pid}`;
    await this.consul.agent.service.deregister(serviceName);
  }

  
  discoverServices() {
    const serviceNames = [
      'auth', 'users', 'upload', 'transcode', 'catalog',
      'streaming', 'recommendations', 'billing', 'analytics',
    ];

    for (const name of serviceNames) {
      
      this._watchService(name);
    }

    // Returns immediately, services not yet discovered
  }

  async _watchService(serviceName) {
    const watch = this.consul.watch({
      method: this.consul.health.service,
      options: {
        service: serviceName,
        passing: true,
      },
    });

    watch.on('change', (data) => {
      const instances = data.map(entry => ({
        id: entry.Service.ID,
        address: entry.Service.Address,
        port: entry.Service.Port,
      }));

      this.services.set(serviceName, instances);
    });

    watch.on('error', (err) => {
      
      console.error(`Watch error for ${serviceName}:`, err);
    });

    this.watchHandles.set(serviceName, watch);
  }

  getService(serviceName) {
    const instances = this.services.get(serviceName);

    if (!instances || instances.length === 0) {
      return null;
    }

    // Simple round-robin
    
    if (!this._roundRobinCounters) {
      this._roundRobinCounters = {};
    }

    const counter = this._roundRobinCounters[serviceName] || 0;
    this._roundRobinCounters[serviceName] = (counter + 1) % instances.length;

    return instances[counter];
  }
}

module.exports = { ServiceRegistry };
