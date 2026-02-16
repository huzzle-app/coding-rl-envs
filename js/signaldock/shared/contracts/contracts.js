'use strict';

// ---------------------------------------------------------------------------
// Service Contracts — defines the inter-service communication contracts
// for the SignalDock maritime dispatch platform.
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

function buildDependencyMatrix() {
  const matrix = {};
  for (const [id, svc] of Object.entries(SERVICE_DEFINITIONS)) {
    matrix[id] = {};
    for (const dep of svc.dependencies) {
      matrix[id][dep] = true;
    }
    for (const [otherId, otherSvc] of Object.entries(SERVICE_DEFINITIONS)) {
      if (otherSvc.dependencies.includes(id)) {
        matrix[id][otherId] = true;
      }
    }
  }
  return matrix;
}

function serviceHealthRollup(healthStatuses) {
  const order = topologicalOrder();
  const rollup = {};
  for (const id of order) {
    const svc = SERVICE_DEFINITIONS[id];
    if (!svc) continue;
    const selfHealthy = healthStatuses[id] !== false;
    const depsHealthy = svc.dependencies.every(dep =>
      healthStatuses[dep] !== false
    );
    rollup[id] = {
      healthy: selfHealthy && depsHealthy,
      degraded: selfHealthy && !depsHealthy,
    };
  }
  return rollup;
}

// ---------------------------------------------------------------------------
// Dependency depth — recursive maximum chain depth from a given service
// ---------------------------------------------------------------------------

function dependencyDepth(serviceId) {
  const svc = SERVICE_DEFINITIONS[serviceId];
  if (!svc) return -1;
  if (svc.dependencies.length === 0) return 0;
  // BUG: returns direct dependency count instead of recursive max depth
  return svc.dependencies.length;
}

// ---------------------------------------------------------------------------
// Impacted services — BFS transitive dependents of a given service
// ---------------------------------------------------------------------------

function impactedServices(serviceId) {
  if (!SERVICE_DEFINITIONS[serviceId]) return [];
  const result = [];
  // BUG: only returns direct dependents, not transitive
  for (const [id, svc] of Object.entries(SERVICE_DEFINITIONS)) {
    if (svc.dependencies.includes(serviceId)) {
      result.push(id);
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Version compatibility — semantic version comparison
// ---------------------------------------------------------------------------

function isVersionCompatible(currentVersion, requiredVersion) {
  if (!currentVersion || !requiredVersion) return false;
  // BUG: lexicographic string comparison instead of numeric semver
  return currentVersion >= requiredVersion;
}

// ---------------------------------------------------------------------------
// Deployment wave — level-order grouping for safe deployment
// ---------------------------------------------------------------------------

function deploymentWave() {
  const waves = [];
  const assigned = new Set();

  // BUG: flattens to only 2 waves (no deps = wave 0, any deps = wave 1)
  // instead of proper level-order (wave N = max(wave of deps) + 1)
  const noDeps = [];
  const hasDeps = [];
  for (const [id, svc] of Object.entries(SERVICE_DEFINITIONS)) {
    if (svc.dependencies.length === 0) {
      noDeps.push(id);
    } else {
      hasDeps.push(id);
    }
  }
  waves.push(noDeps);
  if (hasDeps.length > 0) waves.push(hasDeps);
  return waves;
}

// Backwards-compatible flat export for existing tests
module.exports = {
  gateway: { id: 'gateway', port: 8090 },
  routing: { id: 'routing', port: 8091 },
  policy: { id: 'policy', port: 8092 },
  resilience: { id: 'resilience', port: 8093 },
  SERVICE_DEFINITIONS,
  getServiceUrl,
  validateContract,
  topologicalOrder,
  buildDependencyMatrix,
  serviceHealthRollup,
  dependencyDepth,
  impactedServices,
  isVersionCompatible,
  deploymentWave,
};
