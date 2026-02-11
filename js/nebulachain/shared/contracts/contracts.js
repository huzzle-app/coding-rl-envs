'use strict';

// ---------------------------------------------------------------------------
// Service Contracts — defines the inter-service communication contracts
// for the NebulaChain dispatch governance platform.
// ---------------------------------------------------------------------------

const SERVICE_DEFINITIONS = Object.freeze({
  gateway: {
    id: 'gateway',
    port: 8090,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: ['routing', 'policy'],
  },
  routing: {
    id: 'routing',
    port: 8091,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: ['policy'],
  },
  policy: {
    id: 'policy',
    port: 8092,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: [],
  },
  resilience: {
    id: 'resilience',
    port: 8093,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: ['policy'],
  },
  analytics: {
    id: 'analytics',
    port: 8094,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: ['routing'],
  },
  audit: {
    id: 'audit',
    port: 8095,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: [],
  },
  notifications: {
    id: 'notifications',
    port: 8096,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: ['policy'],
  },
  security: {
    id: 'security',
    port: 8097,
    healthPath: '/health',
    version: '1.0.0',
    dependencies: [],
  },
});


const REQUIRED_COMMAND_FIELDS = ['commandId', 'serviceId', 'action', 'payload']; 


function getServiceUrl(serviceId, baseDomain) {
  const svc = SERVICE_DEFINITIONS[serviceId];
  if (!svc) return null;
  const domain = baseDomain || 'localhost';
  return `http://${domain}:${svc.port}`; 
}

function validateContract(serviceId) {
  const svc = SERVICE_DEFINITIONS[serviceId];
  if (!svc) return { valid: false, reason: 'unknown_service' };
  if (!svc.port || svc.port < 1024) return { valid: false, reason: 'invalid_port' };
  // Check dependencies exist
  for (const dep of svc.dependencies) {
    if (!SERVICE_DEFINITIONS[dep]) return { valid: false, reason: `missing_dependency_${dep}` };
  }
  return { valid: true, service: svc };
}


function topologicalOrder() {
  const visited = new Set();
  const order = [];

  function visit(id) {
    if (visited.has(id)) return; 
    visited.add(id);
    const svc = SERVICE_DEFINITIONS[id];
    if (svc) {
      for (const dep of svc.dependencies) {
        visit(dep);
      }
    }
    order.push(id);
  }

  for (const id of Object.keys(SERVICE_DEFINITIONS)) {
    visit(id);
  }
  return order;
}


function dependencyDepth(serviceId, _visited) {
  const seen = _visited || new Set();
  if (seen.has(serviceId)) return 0;
  seen.add(serviceId);
  const svc = SERVICE_DEFINITIONS[serviceId];
  if (!svc) return -1;
  if (svc.dependencies.length === 0) return 0;
  let maxDepth = 0;
  for (const dep of svc.dependencies) {
    const d = dependencyDepth(dep, seen);
    if (d > maxDepth) maxDepth = d;
  }
  return maxDepth + 1;
}

function serviceCount() {
  return Object.keys(SERVICE_DEFINITIONS).length;
}

// Backwards-compatible flat export — expanded to include all 8 services
module.exports = {
  gateway: { id: 'gateway', port: 8090 },
  routing: { id: 'routing', port: 8091 },
  policy: { id: 'policy', port: 8092 },
  resilience: { id: 'resilience', port: 8093 },
  analytics: { id: 'analytics', port: 8094 },
  audit: { id: 'audit', port: 8095 },
  notifications: { id: 'notifications', port: 8096 },
  security: { id: 'security', port: 8097 },
  SERVICE_DEFINITIONS,
  REQUIRED_COMMAND_FIELDS,
  getServiceUrl,
  validateContract,
  topologicalOrder,
  dependencyDepth,
  serviceCount,
};
