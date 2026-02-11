# Customer Escalation: Statistical Analysis Producing Incorrect Results

## Zendesk Ticket #89234

**Priority**: Urgent
**Customer**: National Genomics Research Institute (NGRI)
**Account Value**: $1.2M ARR
**CSM**: David Park
**Created**: 2024-03-20 09:15 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> Our biostatistics team has identified significant discrepancies between GeneForge's statistical outputs and our validated R/Python implementations. These errors are affecting our publication submissions and we need immediate resolution. We've attached detailed comparisons below.

### Issue 1: Mean Calculation Off By ~8%

```
Dataset: WGS coverage depths for 847 samples
Values: [32.5, 34.2, 29.8, 31.1, ..., 33.4] (847 values)
Sum: 27,436.8

GeneForge mean: 32.38 (divides by 848 ??)
Expected mean: 32.39 (divides by 847)
R validation: mean(data) = 32.39
```

The error appears to add 1 to the denominator consistently.

### Issue 2: Variance Calculation Using Population Formula

```
Dataset: Quality scores [0.92, 0.87, 0.91, 0.88, 0.90]
n = 5

GeneForge variance: 0.000340 (dividing by n)
Expected variance: 0.000425 (dividing by n-1 for sample variance)
R validation: var(data) = 0.000425
```

This is a critical error for sample-based statistics. We're using sample data, not population data.

### Issue 3: Median Calculation Wrong for Even-Length Arrays

```
Dataset: [10, 20, 30, 40]
n = 4 (even)

GeneForge median: 30 (just takes mid index)
Expected median: 25 (average of 20 and 30)
R validation: median(data) = 25
```

This is causing significant issues with our percentile-based QC thresholds.

### Issue 4: F1 Score Formula Missing Factor of 2

```
Precision: 0.85
Recall: 0.80

GeneForge F1: 0.4121 (precision * recall / (precision + recall))
Expected F1: 0.8242 (2 * precision * recall / (precision + recall))
```

This is off by exactly 50%, which is a textbook error in the F1 formula.

### Issue 5: 95% Confidence Interval Using Wrong Z-Score

```
Mean: 100.0
Standard Error: 5.0

GeneForge 95% CI: (91.8, 108.2) using z=1.64
Expected 95% CI: (90.2, 109.8) using z=1.96

Note: z=1.64 is for 90% CI, not 95% CI
```

### Issue 6: Cohen's d Effect Size Calculation Wrong

```
Mean1: 50.0
Mean2: 45.0
Pooled SD: 10.0

GeneForge Cohen's d: 0.25 (divides by 2*SD for some reason)
Expected Cohen's d: 0.50
```

### Issue 7: Bonferroni Correction Off By One

```
Alpha: 0.05
Number of tests: 10

GeneForge threshold: 0.00455 (alpha / 11)
Expected threshold: 0.005 (alpha / 10)
```

### Issue 8: Percentile Indexing Error

```
Dataset: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
Percentile: 90th

GeneForge result: 100 (out of bounds access?)
Expected result: 90

The calculation seems to sometimes access index 10 in a 10-element array.
```

---

## Internal Slack Thread

**#eng-biostatistics** - March 20, 2024

**@david.park** (09:30):
> NGRI is furious. Their biostatistics team found 8 separate calculation errors in our statistics module. These are basic formulas - mean, variance, median. How did this pass review?

**@dev.lisa** (09:45):
> Looking at the code now. The mean function has `sum / (values.len() + 1)` - that's clearly wrong. Should just be `values.len()`.

**@dev.marcus** (09:52):
> The variance is using `n` instead of `n-1`. That's population variance, not sample variance. For clinical genomics, we should always be using sample variance.

**@dev.lisa** (10:05):
> Found the median bug. For even-length arrays, it just returns `sorted[mid]` instead of averaging `sorted[mid-1]` and `sorted[mid]`.

**@dev.marcus** (10:12):
> The confidence interval is using 1.64 as the z-score for 95% CI. That's the z-score for 90% CI. Classic mistake - 1.96 is the correct value for 95%.

**@qa.jennifer** (10:20):
> How did our tests not catch this?

**@dev.lisa** (10:25):
> Our tests were written against the buggy implementation. They test that the code does what it does, not that it does what it should.

**@dev.marcus** (10:30):
> Same with F1 score. The formula is `precision * recall / (precision + recall)`, but it should be `2 * precision * recall / (precision + recall)`. Missing the factor of 2.

**@data.science.lead** (10:45):
> This is catastrophic for our credibility. NGRI publishes in Nature and Cell. If they submitted papers with our wrong statistics...

---

## Test Output Failures

```
running 14 tests
test statistics::test_mean ... FAILED
test statistics::test_variance ... FAILED
test statistics::test_std_dev ... FAILED
test statistics::test_median ... FAILED
test statistics::test_f1_score ... FAILED
test statistics::test_percentile ... FAILED
test statistics::test_confidence_interval ... FAILED
test statistics::test_cohens_d ... FAILED
test statistics::test_chi_squared ... FAILED
test statistics::test_bonferroni ... FAILED
test statistics::test_z_score ... FAILED
test statistics::test_correlation_bounds ... FAILED
test statistics::test_moving_average ... FAILED
test statistics::test_variant_quality ... FAILED

failures:
    mean returned 32.38, expected 32.39
    variance returned 0.000340, expected 0.000425
    median([10,20,30,40]) returned 30, expected 25
    f1_score(0.85, 0.80) returned 0.4121, expected 0.8242
    ...
```

---

## Impact Assessment

- **Publications Affected**: 3 papers pending submission with GeneForge-generated statistics
- **Data Reports**: 847 clinical samples with potentially incorrect statistical summaries
- **Customer Trust**: NGRI considering switch to competitor platform

---

**Status**: CRITICAL - Requires immediate fix
**Assigned**: @biostatistics-team
**Deadline**: March 21, 2024 EOD
