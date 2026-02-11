# Finance Audit Report: Route Cost Calculation Discrepancies

**Report ID:** FIN-AUD-2024-Q3-172
**Department:** Maritime Operations Finance
**Auditor:** K. Fernandez, Senior Financial Analyst
**Date:** 2024-09-15

---

## Executive Summary

During Q3 cost reconciliation, significant discrepancies were identified between projected route costs from NimbusFlow and actual invoiced amounts. The variance pattern suggests systematic underestimation of route costs, particularly on high-port-fee routes.

## Findings

### Finding 1: Consistent Route Cost Underestimation

Actual costs consistently exceed NimbusFlow projections. The variance correlates strongly with port fee amounts.

**Sample Route Cost Analysis:**

| Route | Distance (nm) | Fuel Rate | Port Fee | NimbusFlow Est. | Actual | Variance |
|-------|---------------|-----------|----------|-----------------|--------|----------|
| SIN-HKG | 1,450 | $2.50/nm | $5,000 | -$1,375 | $8,625 | -$10,000 |
| LAX-YOK | 5,200 | $2.20/nm | $8,500 | $2,940 | $19,940 | -$17,000 |
| ROT-NYC | 3,600 | $2.80/nm | $12,000 | -$1,920 | $22,080 | -$24,000 |
| DXB-MUM | 1,100 | $2.40/nm | $3,200 | -$560 | $5,840 | -$6,400 |

**Observation:** Higher port fees correlate with larger negative variances. Some estimates are actually negative, which is impossible for a cost.

### Finding 2: Channel Scoring Anomalies

Route selection appears biased toward high-latency channels. Analysis of 847 route selections in Q3:

| Latency Range | Expected Selection % | Actual Selection % |
|---------------|---------------------|-------------------|
| 0-50ms | 45% | 8% |
| 50-100ms | 30% | 12% |
| 100-200ms | 15% | 28% |
| 200+ms | 10% | 52% |

Routes with higher latency are being scored MORE favorably than low-latency alternatives, contrary to operational requirements.

### Finding 3: Cost Estimation Impact on Budgeting

The underestimation has led to:
- Q3 fuel budget overrun: $2.3M
- Port fee budget overrun: $1.8M
- Total unplanned costs: $4.1M

## Technical Observations

1. **Port Fee Handling:** The formula appears to treat port fees as revenue rather than cost. When port fee = $5,000, the estimate drops by roughly $5,000.

2. **Channel Score Formula:** Higher latency values produce higher scores. A channel with 200ms latency scores 4x higher than one with 50ms, when the inverse should be true.

3. **Data Quality:** Input data (distance, fuel rates, port fees, latency) verified as accurate. The issue is in calculation, not input.

## Recommendations

1. Immediate review of route cost estimation formula in NimbusFlow
2. Audit channel scoring algorithm for latency weighting
3. Reconcile Q3 budget projections with corrected estimates

## Appendix: Sample API Responses

```json
// Route cost estimate request
POST /api/routing/estimate-cost
{
  "distanceNm": 1450,
  "fuelRatePerNm": 2.50,
  "portFee": 5000
}

// Response (INCORRECT)
{
  "estimatedCost": -1375.0,
  "breakdown": {
    "fuelCost": 3625.0,
    "portFee": 5000.0,
    "total": -1375.0
  }
}
```

```json
// Channel score request
POST /api/routing/channel-score
{
  "latency": 200,
  "reliability": 0.95,
  "priority": 3
}

// Response (SUSPICIOUS)
{
  "score": 570.0
}

// Compare with low latency
POST /api/routing/channel-score
{
  "latency": 25,
  "reliability": 0.95,
  "priority": 3
}

// Response (LOWER SCORE FOR BETTER LATENCY?)
{
  "score": 71.25
}
```

---

**Distribution:** VP Operations, CFO, Platform Engineering Lead
**Classification:** Internal - Financial
