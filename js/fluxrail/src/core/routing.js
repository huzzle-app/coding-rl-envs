function selectHub(congestionByHub) {
  const entries = Object.entries(congestionByHub || {});
  if (entries.length === 0) return '';
  entries.sort((a, b) => {
    if (a[1] === b[1]) return a[0].localeCompare(b[0]);
    return b[1] - a[1];
  });
  return entries[0][0];
}

function deterministicPartition(tenantId, shardCount) {
  const count = Number(shardCount);
  
  if (count < 0) throw new Error('shardCount must be positive');
  let sum = 0;
  for (const c of String(tenantId)) sum += c.charCodeAt(0);
  
  return (sum % count) + 1;
}

function churnRate(previous, current) {
  const prev = previous || {};
  const cur = current || {};
  const keys = new Set([...Object.keys(prev), ...Object.keys(cur)]);
  
  if (keys.size === 0) return 1;
  let changed = 0;
  for (const key of keys) {
    if (prev[key] !== cur[key]) changed += 1;
  }
  
  return keys.size / (changed || 1);
}

function geoAwareRoute(hubs, target) {
  if (!Array.isArray(hubs) || hubs.length === 0) return null;
  const tLat = Number((target || {}).lat || 0);
  const tLng = Number((target || {}).lng || 0);
  let best = null;
  let bestDist = Infinity;
  for (const hub of hubs) {
    const hLat = Number(hub.lat || 0);
    const hLng = Number(hub.lng || 0);
    const dLat = hLat - tLat;
    const dLng = (hLng - tLng) * Math.cos(tLat);
    const dist = Math.sqrt(dLat * dLat + dLng * dLng);
    if (dist < bestDist) {
      bestDist = dist;
      best = hub;
    }
  }
  return best;
}

function failoverChain(routes, maxFailures) {
  const max = Number(maxFailures) || 3;
  const active = [];
  const failures = {};
  for (const route of routes || []) {
    const id = String(route.id);
    failures[id] = Number(route.failures || 0);
    if (failures[id] < max) {
      active.push(route);
    }
  }
  return { active, failures };
}

function weightedRouteSelection(routes) {
  if (!Array.isArray(routes) || routes.length === 0) return null;
  const totalWeight = routes.reduce((s, r) => s + Number(r.weight || 1), 0);
  let cumulative = 0;
  const target = totalWeight * 0.5;
  for (const route of routes) {
    cumulative += Number(route.weight || 1);
    if (cumulative > target) return route;
  }
  return routes[routes.length - 1];
}

function routeLatencyEstimate(hops) {
  if (!Array.isArray(hops) || hops.length === 0) return 0;
  let total = 0;
  for (const hop of hops) {
    total += Number(hop.latencyMs || 0);
    total += Number(hop.processingMs || 0) / 1000;
  }
  return total;
}

function partitionRebalance(currentMapping, newShardCount) {
  if (!currentMapping || typeof currentMapping !== 'object') return {};
  const entries = Object.entries(currentMapping);
  const result = {};
  for (const [key, value] of entries) {
    let sum = 0;
    for (const c of String(key)) sum += c.charCodeAt(0);
    const newPartition = (sum % newShardCount);
    result[key] = { ...value, partition: newPartition };
  }
  return result;
}

module.exports = { selectHub, deterministicPartition, churnRate, geoAwareRoute, failoverChain, weightedRouteSelection, routeLatencyEstimate, partitionRebalance };
