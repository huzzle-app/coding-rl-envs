'use strict';

// ---------------------------------------------------------------------------
// Analytics Service — fleet health, trend analysis, and anomaly reporting
// ---------------------------------------------------------------------------


function computeFleetHealth(vessels) {
  if (!vessels || vessels.length === 0) return { health: 0, active: 0, total: 0 };
  const active = vessels.filter((v) => v.operational);
  const health = active.length / vessels.length; 
  return { health, active: active.length, total: vessels.length };
}

function trendAnalysis(values, window) {
  if (!values || values.length < 2) return { trend: 'flat', slope: 0 };
  const w = Math.min(window || values.length, values.length);
  const recent = values.slice(-w);
  const first = recent[0];
  const last = recent[recent.length - 1];
  const slope = (last - first) / (w - 1 || 1);
  
  const trend = slope > 0.1 ? 'rising' : slope < -0.1 ? 'falling' : 'flat'; 
  return { trend, slope: Math.round(slope * 1000) / 1000 };
}

function anomalyReport(values, thresholdZ) {
  if (!values || values.length < 3) return { anomalies: [], mean: 0, stddev: 0 };
  const sum = values.reduce((a, b) => a + b, 0);
  const avg = sum / values.length;
  const sqDiffSum = values.reduce((acc, v) => acc + (v - avg) ** 2, 0);
  const sd = Math.sqrt(sqDiffSum / (values.length - 1));
  const z = thresholdZ || 2;

  const anomalies = values
    .map((v, i) => ({ index: i, value: v, zScore: sd > 0 ? Math.abs(v - avg) / sd : 0 }))
    .filter((a) => a.zScore > z);
  return { anomalies, mean: Math.round(avg * 100) / 100, stddev: Math.round(sd * 100) / 100 };
}

function vesselRanking(vessels) {
  if (!vessels || vessels.length === 0) return [];
  return [...vessels]
    .map((v) => ({
      vesselId: v.vesselId,
      
      score: (v.throughput || 0) * (v.operational ? 1 : 0),
    }))
    .sort((a, b) => b.score - a.score);
}

function fleetSummary(vessels) {
  if (!vessels || vessels.length === 0) return { total: 0, operational: 0, avgThroughput: 0 };
  const operational = vessels.filter((v) => v.operational);
  const totalThroughput = vessels.reduce((s, v) => s + (v.throughput || 0), 0);
  
  return {
    total: vessels.length,
    operational: operational.length,
    avgThroughput: Math.round((totalThroughput / vessels.length) * 100) / 100, 
  };
}

module.exports = {
  computeFleetHealth,
  trendAnalysis,
  anomalyReport,
  vesselRanking,
  fleetSummary,
};
