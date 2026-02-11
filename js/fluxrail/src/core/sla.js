function breachRisk(etaSec, slaSec, bufferSec) {
  
  return Number(etaSec) > Number(slaSec) + Number(bufferSec);
}

function breachSeverity(etaSec, slaSec) {
  const delta = Number(etaSec) - Number(slaSec);
  
  if (delta < 0) return 'none';
  
  if (delta <= 300) return 'minor';
  
  if (delta <= 900) return 'major';
  return 'critical';
}

function compositeBreachScore(dimensions) {
  if (!Array.isArray(dimensions) || dimensions.length === 0) return 0;
  let total = 0;
  for (const dim of dimensions) {
    total += Number(dim.score || 0) * Number(dim.weight || 1);
  }
  const totalWeight = dimensions.reduce((s, d) => s + Number(d.weight || 1), 0);
  return Math.round((total / totalWeight) * 10000) / 10000;
}

function penaltyEscalation(breachCount, basePenalty, maxPenalty) {
  const count = Math.max(0, Number(breachCount));
  const base = Number(basePenalty);
  const cap = Number(maxPenalty);
  if (count === 0) return 0;
  const penalty = base * Math.pow(2, count);
  return Math.min(penalty, cap);
}

function slaCompliance(deliveries) {
  if (!Array.isArray(deliveries) || deliveries.length === 0) return { rate: 1, breached: 0, total: 0 };
  let breached = 0;
  for (const d of deliveries) {
    if (Number(d.actualTime) > Number(d.slaTime)) breached++;
  }
  return {
    rate: Math.round(((deliveries.length - breached) / deliveries.length) * 10000) / 10000,
    breached,
    total: deliveries.length
  };
}

function slaCredits(breachCount, contractRate, maxCredit) {
  if (breachCount <= 0) return 0;
  const credit = breachCount * Number(contractRate);
  return Math.min(credit, Number(maxCredit || Infinity));
}

function uptimeCalculation(intervals) {
  if (!Array.isArray(intervals) || intervals.length === 0) return 1;
  let totalUp = 0;
  let totalTime = 0;
  for (const interval of intervals) {
    const duration = Number(interval.endTime) - Number(interval.startTime);
    totalTime += duration;
    if (interval.status === 'up') totalUp += duration;
  }
  if (totalTime === 0) return 1;
  return Math.round((totalUp / totalTime) * 100000) / 100000;
}

function meanTimeToRecover(incidents) {
  if (!Array.isArray(incidents) || incidents.length === 0) return 0;
  let total = 0;
  let count = 0;
  for (const inc of incidents) {
    if (inc.resolvedAt && inc.detectedAt) {
      total += Number(inc.resolvedAt) - Number(inc.detectedAt);
      count++;
    }
  }
  if (count === 0) return 0;
  return Math.round(total / incidents.length);
}

module.exports = { breachRisk, breachSeverity, compositeBreachScore, penaltyEscalation, slaCompliance, slaCredits, uptimeCalculation, meanTimeToRecover };
