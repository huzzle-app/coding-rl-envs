# Scenario 03: Feature Drift Alert Storm

## PagerDuty Incident Flood

**Date**: 2024-03-18
**Time**: 06:00 - 08:30 UTC
**Total Alerts**: 247 drift alerts in 2.5 hours

---

## Alert Samples (first 10 of 247)

```
06:01:12 WARN [monitoring] Feature drift detected: user_age (drift_score=0.0501)
06:01:14 WARN [monitoring] Feature drift detected: user_income (drift_score=0.0503)
06:01:14 WARN [monitoring] Feature drift detected: user_account_age (drift_score=0.0499)
06:01:15 WARN [monitoring] Feature drift detected: user_transaction_count (drift_score=0.0502)
06:01:18 WARN [monitoring] Feature drift detected: user_login_frequency (drift_score=0.0501)
06:02:01 WARN [monitoring] Feature drift detected: user_age (drift_score=0.0502)
06:02:03 WARN [monitoring] Feature drift detected: user_income (drift_score=0.0498)
06:02:05 WARN [monitoring] Feature drift detected: user_account_age (drift_score=0.0501)
06:02:07 WARN [monitoring] Feature drift detected: user_transaction_count (drift_score=0.0500)
06:02:09 WARN [monitoring] Feature drift detected: user_login_frequency (drift_score=0.0503)
...
```

---

## Investigation Thread

### Initial Triage (06:15 UTC)

**On-Call Engineer (Jamie)**: Seeing massive drift alert flood. All alerts are from the same feature group: `user_demographics`. Every feature in the group is flagging simultaneously.

**ML Platform Lead (Alex)**: Are these legitimate drifts or false positives?

**Jamie**: Hard to tell. The drift scores are all hovering around 0.05, which is exactly our threshold. Seems suspicious.

### Analysis (06:45 UTC)

**Jamie**: I plotted the feature distributions. Here's what's weird:

1. **Correlated Features**: `user_income` and `user_age` naturally correlate (older users tend to have higher incomes). When age distribution shifts slightly (new user cohort), income shifts proportionally.

2. **Expected Behavior**: The data team confirmed they onboarded 10,000 new enterprise users yesterday. These users skew older and higher income than our consumer base. This is EXPECTED demographic shift.

3. **False Positive Storm**: The drift detector is treating each feature independently. When one shifts, correlated features also shift, and we get N alerts instead of 1.

**Alex**: So the drift detection isn't accounting for feature correlations?

**Jamie**: Correct. It also seems to trigger at exactly the threshold value. Look at these scores:
- 0.0501, 0.0503, 0.0499, 0.0502, 0.0501
All basically equal to 0.05 (our threshold). The detector seems to use exact equality comparison somewhere.

### Deep Dive (07:30 UTC)

**Data Scientist (Morgan)**: I checked the drift calculation. There's something wrong with the threshold comparison logic. Features with normalized_diff of exactly 0.05 should be flagged, but:

```
if normalized_diff == self.threshold:
    return True
return normalized_diff > self.threshold
```

This means:
- `0.050001` triggers (correctly, via >)
- `0.050000` triggers (incorrectly, via ==, but this should be rare)
- `0.049999` does not trigger

The problem is float precision. `0.0501` in the log might actually be `0.0500000001` internally. The `==` check almost never succeeds because floats rarely equal exactly.

**Jamie**: So the threshold comparison is broken?

**Morgan**: Yes, but there's a bigger issue. We're flagging `user_age`, `user_income`, `user_account_age`, `user_transaction_count`, and `user_login_frequency` ALL separately. These are known correlated features. When we get a new user cohort, they ALL shift together. We should have one alert: "user_demographics cohort shift" not 5 separate alerts.

### Root Cause Hypothesis (08:00 UTC)

1. **Float comparison bug**: Threshold check uses `==` for floats, causing inconsistent detection at boundary
2. **No multivariate awareness**: Each feature checked independently, no correlation handling
3. **Alert explosion**: 5 correlated features x 50 check intervals = 247 alerts

---

## Secondary Issue Discovered

While investigating, we also found:

**Jamie (08:15 UTC)**: I tried to add a correlation-aware drift check as a new feature transformation. But when I added the dependency (`corr_drift` depends on `user_age` and `user_income`), the pipeline started hanging.

**Morgan**: Did you check for cycles?

**Jamie**: The `FeatureDependencyGraph.has_cycle()` method returns `False` even when I intentionally add a cycle. I added A->B->C->A and it still says no cycle.

---

## Symptoms Summary

1. **Alert flood**: 247 alerts in 2.5 hours for correlated feature shifts
2. **Threshold precision**: Drift scores cluster around 0.05 (threshold value)
3. **Independent detection**: Each feature in correlated group triggers separately
4. **Expected data shift**: New enterprise user cohort is legitimate, not a bug in data
5. **Cycle detection broken**: Feature dependency graph cycle check always returns False
6. **Pipeline hangs**: Adding circular dependencies causes infinite loops

---

## Business Impact

- On-call engineer paged 247 times
- Alert fatigue: real issues may be missed
- Feature pipeline blocked while investigating
- Drift detection system credibility damaged

---

## Feature Groups Affected

| Feature Group | Features | Alert Count |
|---------------|----------|-------------|
| user_demographics | user_age, user_income, user_account_age, user_transaction_count, user_login_frequency | 215 |
| user_behavior | session_duration, page_views, click_rate | 32 |
