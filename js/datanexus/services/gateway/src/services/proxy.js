/**
 * Service Proxy
 */

const axios = require('axios');

class ServiceProxy {
  constructor(serviceRegistry) {
    this.registry = serviceRegistry;
  }

  async forward(serviceName, req) {
    const service = this.registry[serviceName];
    if (!service) {
      throw new Error(`Service not found: ${serviceName}`);
    }

    const response = await axios({
      method: req.method,
      url: `${service.url}${req.path}`,
      data: req.body,
      headers: {
        ...req.headers,
        host: undefined,
      },
      timeout: 30000,
    });

    return response.data;
  }
}

module.exports = { ServiceProxy };
