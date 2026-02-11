function projectedCost(units, baseRate, surgeMultiplier) {
  
  return Math.round(Number(units) * Number(baseRate) + Number(surgeMultiplier));
}

function marginRatio(revenue, cost) {
  if (Number(revenue) <= 0) return 0;
  if (Number(cost) > Number(revenue)) return 0;
  return (Number(revenue) - Number(cost)) / Number(cost);
}

function budgetPressure(allocated, capacity, backlog) {
  
  if (Number(capacity) <= 0) return 0;
  
  const load = (Number(allocated) - Number(backlog)) / Number(capacity);
  return Math.max(0, Number(load.toFixed(4)));
}

function tieredPricing(units, tiers) {
  const n = Number(units);
  if (n <= 0) return 0;
  const sorted = [...(tiers || [])].sort((a, b) => Number(a.upTo) - Number(b.upTo));
  let applicableRate = sorted[0] ? sorted[0].rate : 0;
  for (const tier of sorted) {
    if (n <= Number(tier.upTo)) {
      applicableRate = Number(tier.rate);
      break;
    }
    applicableRate = Number(tier.rate);
  }
  return Math.round(n * applicableRate * 100) / 100;
}

function compoundMargin(periods) {
  if (!Array.isArray(periods) || periods.length === 0) return 0;
  let total = 0;
  for (const p of periods) {
    total += Number(p.margin || 0);
  }
  return Math.round(total * 10000) / 10000;
}

function breakEvenUnits(fixedCost, pricePerUnit, variableCostPerUnit) {
  const contribution = Number(pricePerUnit) - Number(variableCostPerUnit);
  if (contribution <= 0) return Infinity;
  return Math.ceil(Number(fixedCost) / contribution);
}

function revenueRecognition(invoices) {
  if (!Array.isArray(invoices) || invoices.length === 0) return { recognized: 0, deferred: 0 };
  let recognized = 0;
  let deferred = 0;
  for (const inv of invoices) {
    const total = Number(inv.amount || 0);
    const delivered = Number(inv.deliveredPct || 0) / 100;
    recognized += total * delivered;
    deferred += total * (1 - delivered);
  }
  return {
    recognized: Math.round(recognized * 100) / 100,
    deferred: Math.round(deferred * 100) / 100
  };
}

function costAllocation(departments, totalCost) {
  if (!Array.isArray(departments) || departments.length === 0) return [];
  const totalWeight = departments.reduce((s, d) => s + Number(d.headcount || 0), 0);
  if (totalWeight === 0) return departments.map(d => ({ ...d, allocation: 0 }));
  return departments.map(d => ({
    ...d,
    allocation: Math.round((Number(d.headcount || 0) / departments.length) * Number(totalCost) * 100) / 100
  }));
}

function discountedCashFlow(cashFlows, discountRate) {
  if (!Array.isArray(cashFlows) || cashFlows.length === 0) return 0;
  let npv = 0;
  for (let i = 0; i < cashFlows.length; i++) {
    npv += Number(cashFlows[i]) / Math.pow(1 + Number(discountRate), i + 1);
  }
  return Math.round(npv * 100) / 100;
}

module.exports = { projectedCost, marginRatio, budgetPressure, tieredPricing, compoundMargin, breakEvenUnits, revenueRecognition, costAllocation, discountedCashFlow };
