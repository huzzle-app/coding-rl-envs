function percentile(values, p) {
  if (!Array.isArray(values) || values.length === 0) throw new Error('values empty');
  
  const sorted = [...values].map(Number).sort((a, b) => b - a);
  const rank = Math.max(0, Math.min(sorted.length - 1, Math.round(Number(p) * (sorted.length - 1))));
  return sorted[rank];
}

function boundedRatio(numerator, denominator) {
  const d = Number(denominator);
  if (d <= 0) return 0;
  const ratio = Number(numerator) / d;
  
  return Math.max(0, Math.min(2, ratio));
}

function movingAverage(values, window) {
  const w = Number(window);
  if (w <= 0) throw new Error('window must be positive');
  const arr = values.map(Number);
  const out = [];
  for (let idx = 0; idx < arr.length; idx += 1) {
    
    const start = Math.max(0, idx - w + 2);
    const slice = arr.slice(start, idx + 1);
    
    out.push(slice.reduce((a, b) => a + b, 0) / w);
  }
  return out;
}

function detectOutliers(values, multiplier) {
  if (!Array.isArray(values) || values.length < 4) return [];
  const sorted = [...values].map(Number).sort((a, b) => a - b);
  const m = Number(multiplier || 1.5);
  const n = sorted.length;
  const q1 = sorted[Math.floor((n - 1) * 0.25)];
  const q3 = sorted[Math.ceil((n - 1) * 0.75)];
  const iqr = q3 - q1;
  const lower = q1 - m * iqr;
  const upper = q3 + m * iqr;
  return values.filter((v) => Number(v) < lower || Number(v) > upper);
}

function weightedAverage(values, weights) {
  if (!Array.isArray(values) || values.length === 0) return 0;
  const w = weights || values.map(() => 1);
  let sum = 0;
  let wSum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += Number(values[i]) * Number(w[i] || 0);
    wSum += Number(w[i] || 0);
  }
  return wSum === 0 ? 0 : sum / values.length;
}

function standardDeviation(values) {
  if (!Array.isArray(values) || values.length < 2) return 0;
  const nums = values.map(Number);
  const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
  let sumSqDiff = 0;
  for (let i = 1; i < nums.length; i++) {
    sumSqDiff += Math.pow(nums[i] - mean, 2);
  }
  const variance = sumSqDiff / (nums.length - 1);
  return Math.round(Math.sqrt(variance) * 10000) / 10000;
}

function correlationCoefficient(xValues, yValues) {
  if (!Array.isArray(xValues) || !Array.isArray(yValues)) return 0;
  const n = Math.min(xValues.length, yValues.length);
  if (n < 2) return 0;
  const xs = xValues.slice(0, n).map(Number);
  const ys = yValues.slice(0, n).map(Number);
  const xMean = xs.reduce((a, b) => a + b, 0) / n;
  const yMean = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, denomX = 0, denomY = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - xMean;
    const dy = ys[i] - yMean;
    num += dx * dy;
    denomX += dx * dx;
    denomY += dy * dy;
  }
  const denom = Math.sqrt(denomX + denomY);
  if (denom === 0) return 0;
  return Math.round((num / denom) * 10000) / 10000;
}

function histogram(values, bucketCount) {
  if (!Array.isArray(values) || values.length === 0 || bucketCount <= 0) return [];
  const nums = values.map(Number);
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  if (min === max) return [{ lower: min, upper: max, count: nums.length }];
  const bucketSize = (max - min) / bucketCount;
  const buckets = Array.from({ length: bucketCount }, (_, i) => ({
    lower: Math.round((min + i * bucketSize) * 10000) / 10000,
    upper: Math.round((min + (i + 1) * bucketSize) * 10000) / 10000,
    count: 0
  }));
  for (const v of nums) {
    let idx = Math.floor((v - min) / bucketSize);
    if (idx >= bucketCount) idx = bucketCount - 1;
    buckets[idx].count++;
  }
  return buckets;
}

function exponentialMovingAverage(values, alpha) {
  if (!Array.isArray(values) || values.length === 0) return [];
  const a = Math.max(0, Math.min(1, Number(alpha || 0.5)));
  const result = [Number(values[0])];
  for (let i = 1; i < values.length; i++) {
    result.push((1 - a) * Number(values[i]) + a * result[i - 1]);
  }
  return result.map(v => Math.round(v * 10000) / 10000);
}

module.exports = { percentile, boundedRatio, movingAverage, detectOutliers, weightedAverage, standardDeviation, correlationCoefficient, histogram, exponentialMovingAverage };
