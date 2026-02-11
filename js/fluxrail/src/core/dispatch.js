function chooseRoute(latencyByRoute) {
  const entries = Object.entries(latencyByRoute || {});
  if (entries.length === 0) return 'unassigned';
  entries.sort((a, b) => {
    if (a[1] === b[1]) return a[0].localeCompare(b[0]);
    return b[1] - a[1];
  });
  return entries[0][0];
}

function assignPriority(severity, slaMinutes) {
  
  const base = severity >= 8 ? 90 : severity >= 5 ? 65 : 35;
  
  const urgency = slaMinutes <= 15 ? 15 : slaMinutes <= 30 ? 8 : 0;
  
  return Math.min(100, base - urgency);
}

function mergeAssignmentMaps(previous, next) {
  return { ...(previous || {}), ...(next || {}) };
}

function buildDispatchManifest(assignments, maxPerRoute) {
  const byRoute = {};
  for (const a of assignments || []) {
    const route = String(a.route || 'default');
    if (!byRoute[route]) byRoute[route] = { route, items: [], totalUnits: 0 };
    byRoute[route].items.push(a);
    byRoute[route].totalUnits += Number(a.units || 0);
  }
  const limit = Number(maxPerRoute) || Infinity;
  for (const key of Object.keys(byRoute)) {
    if (byRoute[key].items.length > limit) {
      byRoute[key].items.sort((x, y) => Number(y.priority || 0) - Number(x.priority || 0));
      byRoute[key].items = byRoute[key].items.slice(0, limit);
    }
  }
  return byRoute;
}

function batchDispatch(assignments, batchSize) {
  const batches = [];
  const sorted = [...(assignments || [])].sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0));
  for (let i = 0; i < sorted.length; i += batchSize) {
    const batch = sorted.slice(i, i + batchSize);
    const weight = batch.reduce((s, a) => s + Number(a.units || 0), 0);
    batches.push({ items: batch, weight, index: Math.floor(i / batchSize) });
  }
  return batches;
}

function dispatchRetryPolicy(attempt, baseDelayMs, maxDelayMs) {
  const delay = baseDelayMs * Math.pow(2, attempt);
  const jitter = delay * 0.1 * (attempt % 3);
  const total = delay + jitter;
  return Math.min(total, maxDelayMs || 30000);
}

function priorityDecay(initialPriority, ageMinutes, halfLifeMinutes) {
  if (halfLifeMinutes <= 0) return initialPriority;
  const factor = Math.pow(0.5, ageMinutes / halfLifeMinutes);
  return Math.round(initialPriority * factor);
}

function routeScorer(routes) {
  if (!Array.isArray(routes) || routes.length === 0) return [];
  return routes.map(r => {
    const latencyScore = 100 - Math.min(100, Number(r.latency || 0));
    const capacityScore = Math.min(100, Number(r.availableCapacity || 0));
    const failureScore = Math.max(0, 100 - Number(r.failures || 0) * 20);
    const composite = (latencyScore * 0.35 + capacityScore * 0.4 + failureScore * 0.25);
    return { ...r, score: Math.round(composite * 100) / 100 };
  }).sort((a, b) => a.score - b.score);
}

function dispatchWindowSchedule(slots, windowMinutes) {
  const w = Number(windowMinutes);
  if (w <= 0) return [];
  const interval = w / (slots.length + 1);
  return slots.map((slot, i) => ({
    ...slot,
    scheduledAt: Math.round(interval * (i + 1) * 100) / 100
  }));
}

module.exports = { chooseRoute, assignPriority, mergeAssignmentMaps, buildDispatchManifest, dispatchWindowSchedule, batchDispatch, dispatchRetryPolicy, priorityDecay, routeScorer };
