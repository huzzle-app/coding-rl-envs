# Incident Report: Excessive Sample Rejections in QC Pipeline

## PagerDuty Alert

**Severity**: High (P2)
**Triggered**: 2024-03-18 14:23 UTC
**Acknowledged**: 2024-03-18 14:28 UTC
**Team**: Genomics Platform Engineering

---

## Alert Details

```
WARNING: qc_batch_pass_rate dropped below threshold
Service: geneforge-qc-pipeline
Metric: qc_batch_pass_rate
Expected: >= 0.85
Actual: 0.71
Samples Affected: 847 in last 6 hours
```

## Executive Summary

Our clinical genomics QC pipeline is rejecting an abnormally high percentage of samples. Lab operations reports that their sample quality has not changed, and external validation on the same samples using competitor platforms shows normal pass rates.

## Timeline

**14:23 UTC** - Alert fired for QC batch pass rate below 85%

**14:45 UTC** - Lab operations escalated: "We're seeing 30% rejection rate but our internal QC on the sequencer shows all samples are within spec"

**15:02 UTC** - Compared with competitor platform (GenomicsCloud): same samples show 94% pass rate there

**15:30 UTC** - Noticed pattern: samples with exactly 30x coverage depth are being rejected

**16:00 UTC** - Samples with 2% contamination (exactly at threshold) also failing

## Symptoms Observed

### 1. Boundary Cases Failing

Samples that should be passing are being rejected:

```
Sample ID: CLIN-2024-8847
Coverage Depth: 30.0x  (threshold: >= 30x)
Contamination: 0.018   (threshold: <= 2%)
Duplication: 0.12      (threshold: <= 15%)
Expected: PASS
Actual: FAIL
Reason: "low_coverage" (but 30x is NOT low!)
```

### 2. Coverage Tier Misclassification

```
Sample: CLIN-2024-9012
Coverage: 22.5x
Expected Tier: "marginal" (clinical samples at this level need review)
Actual Tier: "low"
Impact: Samples routed to wrong workflow
```

### 3. Extended QC Missing Checks

The extended QC for WGS samples is passing samples that should fail:

```
Sample: WGS-BATCH-442
Mapping Rate: 0.87 (threshold: >= 95%)
GC Bias: 0.05 (acceptable)
Insert Size: valid
Basic QC: PASS
Extended QC: PASS (should be FAIL due to mapping rate!)
```

### 4. QC Score Calculation Anomalies

Quality scores are inconsistent with manual calculations:

```
Sample: CLIN-2024-8890
Coverage: 50.0 (score component: 0.5)
Contamination: 0.01 (score component: 0.9)
Duplication: 0.08 (score component: 0.84)
Expected Score: 0.4*0.5 + 0.35*0.9 + 0.25*0.84 = 0.725
Actual Score: 0.662
```

## Lab Operations Feedback

> "We've been running at 30x coverage as our target for years. Suddenly samples are failing that have always passed. Our contamination controls are showing 2.0% which is exactly at the clinical threshold - those samples should pass!" - Dr. Maria Chen, Lab Director

## Grafana Dashboard

### QC Pass Rate (7-day rolling)
```
Day    | Pass Rate | Expected
-------|-----------|----------
Mar 11 | 0.94      | >= 0.90
Mar 12 | 0.93      | >= 0.90
Mar 13 | 0.92      | >= 0.90
Mar 14 | 0.78      | >= 0.90 <-- Deployment of v2.4.1
Mar 15 | 0.74      | >= 0.90
Mar 16 | 0.72      | >= 0.90
Mar 17 | 0.71      | >= 0.90
Mar 18 | 0.71      | >= 0.90
```

### Samples by Rejection Reason
```
Reason              | Count | % of Rejections
--------------------|-------|----------------
low_coverage        | 312   | 38%
high_contamination  | 187   | 23%
(unknown/other)     | 321   | 39%  <-- Many have no reason!
```

## Test Environment Observations

When running unit tests:
- Tests for samples at exact thresholds (30x, 0.02 contamination) are flaky
- Batch pass rate tests fail with "expected 0.9, got 0.818"
- Extended QC tests fail: "sample should fail for low mapping rate"

## Questions for Investigation

1. Why are samples at exactly 30x coverage being rejected?
2. Why are samples at exactly 2% contamination failing?
3. Why is the extended QC not checking mapping rate?
4. Why do some rejections have no failure reason assigned?
5. Why is the QC score calculation not matching expected values?
6. Why is the batch pass rate consistently lower than expected?

## Files Likely Involved

Based on error patterns:
- QC metrics and pass/fail logic
- Score calculation functions
- Batch aggregation functions
- Threshold comparison logic

---

**Status**: INVESTIGATING
**Assigned**: @genomics-platform
**Customer Impact**: 312 samples delayed for reprocessing
**Escalation**: If not resolved by EOD, clinical reporting SLA will be breached
