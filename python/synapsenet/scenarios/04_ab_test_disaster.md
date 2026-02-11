# Scenario 04: A/B Test Statistical Disaster

## Jira Ticket: ML-2847

**Title**: A/B test showing impossible traffic split - revenue attribution wrong
**Priority**: P1 - Blocker
**Reporter**: Data Analytics Team
**Assignee**: ML Platform Team
**Sprint**: 2024-Q1-W12

---

## Description

We ran a critical A/B test for our new recommendation model. The test was configured for a 50/25/25 split (control/variant-A/variant-B). After 2 weeks, the analytics dashboard shows:

| Variant | Expected Traffic | Actual Traffic | Difference |
|---------|-----------------|----------------|------------|
| control | 50.00% | 51.23% | +1.23% |
| variant-A | 25.00% | 24.12% | -0.88% |
| variant-B | 25.00% | 24.65% | -0.35% |

This might seem small, but with 10M requests, that's 123,000 requests misrouted. Our revenue attribution is now unreliable.

---

## Detailed Investigation

### Traffic Analysis

We analyzed the request routing over time:

**Hour 1-24**: Split was 50.1/24.9/25.0 (acceptable)
**Hour 25-48**: Split drifted to 50.8/24.5/24.7
**Hour 49-72**: Split was 51.2/24.2/24.6
**Hour 73+**: Stabilized around 51.2/24.1/24.7

The drift is consistent and unidirectional (always toward control).

### Hash Distribution Analysis

We checked the hash function used for traffic routing:

```python
hash_val = int(hashlib.md5(request_id.encode()).hexdigest(), 16) % 10000
normalized = hash_val / 10000.0
```

The MD5 hash should be uniformly distributed. We verified this is true. The problem is in the comparison logic.

### Cumulative Weight Issue

The router uses cumulative weights:
```
variants = {"control": 0.50, "variant-A": 0.25, "variant-B": 0.25}
cumulative = 0.0
for variant, weight in variants.items():
    cumulative += weight
    if normalized < cumulative:
        return variant
```

We noticed:
1. After adding 0.50 + 0.25 + 0.25, `cumulative` should be 1.0
2. But due to float precision: `0.50 + 0.25 + 0.25 = 0.9999999999999999` (not exactly 1.0)
3. Some edge-case request_ids with `normalized > 0.9999999999999999` fall through the loop
4. The fallback returns the last variant, but the logic is inconsistent

### Weight Validation Missing

We also discovered that weight validation is missing:

```python
# Test case that should fail but doesn't:
router.create_experiment("test", {
    "control": 0.40,
    "variant-A": 0.30,
    "variant-B": 0.20
    # Weights sum to 0.90, not 1.0 - but no error raised!
})
```

The router accepts any weights without validating they sum to 1.0.

---

## Secondary Issues Found

### First Request Cold Start

Users reported that the first prediction after model deployment is always slow:

| Request | Latency |
|---------|---------|
| First after deploy | 2,340 ms |
| Second | 45 ms |
| Third | 42 ms |
| Average steady-state | 44 ms |

The model warmup is missing. JIT compilation and cache priming happen on the first request instead of during deployment.

### Schema Drift

When we deployed variant-B (new model version), the input validation started rejecting valid requests:

```
ERROR: Input validation failed
Expected schema: {"features": ["age", "income", "score"]}
Got: {"features": ["age", "income", "score", "segment"]}
```

The validation schema wasn't updated when the model was swapped. It still references the old model's schema even though the new model accepts an additional "segment" feature.

---

## Symptoms Summary

1. **Traffic split drift**: 50/25/25 split drifts to 51.2/24.1/24.7 over time
2. **Float precision loss**: Cumulative weight addition loses precision at boundaries
3. **Missing weight validation**: Experiment creation accepts weights that don't sum to 1.0
4. **Cold start latency**: First request 50x slower than steady-state
5. **Stale schema validation**: Input schema doesn't update when model version changes

---

## Business Impact

- Revenue attribution unreliable for 2-week test period
- A/B test statistical significance questionable
- Marketing team made decisions based on flawed data
- Re-run of test required (2 more weeks, opportunity cost)
- Customer complaints about slow first predictions

---

## Acceptance Criteria

1. Traffic splits must be accurate within 0.1% of configured weights
2. Experiment creation must reject weights that don't sum to 1.0
3. Model warmup must run before serving traffic
4. Input validation schema must update with model version

---

## Related Tickets

- ML-2652: Model warmup not working (duplicate)
- ML-2701: Schema validation using wrong version
- ML-2533: A/B test weight precision issues (related)
