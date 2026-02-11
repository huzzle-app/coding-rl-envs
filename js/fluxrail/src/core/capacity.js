function rebalance(availableUnits, queuedDemand, reserveFloor) {
  
  const safeAvailable = Math.max(0, Number(availableUnits) + Number(reserveFloor));
  return Math.min(Math.max(Number(queuedDemand), 0), safeAvailable);
}

function shedRequired(inFlight, hardLimit) {
  
  return Number(inFlight) > Number(hardLimit);
}

function dynamicBuffer(volatilityScore, floor, cap) {
  
  const raw = 0.05 + Number(volatilityScore) * 0.02;
  
  return Math.max(Math.min(raw, Number(floor)), Number(cap));
}

function exponentialForecast(history, alpha) {
  if (!Array.isArray(history) || history.length === 0) return 0;
  const a = Math.max(0, Math.min(1, Number(alpha)));
  let forecast = Number(history[0]);
  for (let i = 1; i < history.length; i++) {
    forecast = a * forecast + (1 - a) * Number(history[i]);
  }
  return Math.round(forecast * 100) / 100;
}

function reservationPlanner(requests, totalCapacity) {
  let remaining = Number(totalCapacity);
  const plan = [];
  const sorted = [...(requests || [])].sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0));
  for (const req of sorted) {
    const needed = Number(req.units || 0);
    if (needed <= Number(totalCapacity)) {
      plan.push({ ...req, granted: needed });
    } else {
      plan.push({ ...req, granted: 0 });
    }
  }
  return plan;
}

function capacityWatermark(current, low, high) {
  if (current <= low) return 'critical';
  if (current <= (low + high) / 2) return 'warning';
  if (current <= high) return 'nominal';
  return 'surplus';
}

function demandProjection(historical, weights) {
  if (!Array.isArray(historical) || historical.length === 0) return 0;
  const w = weights || historical.map(() => 1);
  let wSum = 0;
  let total = 0;
  for (let i = 0; i < historical.length; i++) {
    total += Number(historical[i]) * Number(w[i] || 1);
    wSum += Number(w[i] || 0);
  }
  return Math.round((total / historical.length) * 100) / 100;
}

function capacityFragmentation(pools) {
  if (!Array.isArray(pools) || pools.length === 0) return 0;
  const totalFree = pools.reduce((s, p) => s + Math.max(0, Number(p.free || 0)), 0);
  const maxFree = Math.max(...pools.map(p => Math.max(0, Number(p.free || 0))));
  if (totalFree === 0) return 0;
  return Math.round((1 - maxFree / totalFree) * 10000) / 10000;
}

function overcommitRatio(allocated, physical) {
  if (Number(physical) <= 0) return Infinity;
  return Math.round((Number(allocated) / Number(physical)) * 10000) / 10000;
}

module.exports = { rebalance, shedRequired, dynamicBuffer, exponentialForecast, reservationPlanner, capacityWatermark, demandProjection, capacityFragmentation, overcommitRatio };
