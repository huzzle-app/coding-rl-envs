# Scenario 01: Production Model Serving Memory Crisis

## PagerDuty Incident #INC-4892

**Severity**: P1 - Critical
**Status**: Investigating
**Created**: 2024-03-15 03:42 UTC
**Assigned**: ML Platform On-Call

---

## Alert Details

```
CRITICAL: inference-service-prod Memory Usage > 95%
Service: inference (8005)
Instance: inference-prod-3.us-east-1
Memory: 31.2 GB / 32 GB (97.5%)
Trend: Increasing 2.3 GB/hour for past 6 hours
```

---

## Incident Timeline

**03:42 UTC** - PagerDuty alert triggered: inference-service memory critical
**03:45 UTC** - On-call acknowledged, began investigation
**03:52 UTC** - Checked metrics dashboard, confirmed memory climbing steadily
**04:15 UTC** - Restarted inference-prod-3, memory dropped to 8 GB
**04:47 UTC** - Memory climbed back to 18 GB
**05:30 UTC** - Pattern confirmed on inference-prod-1 and inference-prod-2

---

## Symptoms Observed

1. **Memory Growth Pattern**
   - Memory usage increases approximately 500 MB every time a model version is deployed
   - Memory does NOT decrease when old model versions are unloaded
   - `gc.collect()` calls have minimal effect

2. **Model Deployment Correlation**
   - Issue accelerates during peak hours (12:00-16:00 UTC) when data science team deploys frequently
   - Today: 47 model version deployments between 00:00-03:42 UTC
   - Each deployment appears to leave orphaned memory

3. **Cache Metrics Anomaly**
   - ModelCache reports `max_size=10` models
   - But memory profiler shows data structures for 47+ model versions still resident
   - Cache "eviction" logs appear, but memory not actually freed

4. **Inference Latency Degradation**
   - P99 latency increased from 45ms to 180ms as memory pressure increased
   - Swap usage starting to appear: 1.2 GB swapped

---

## Investigation Notes

### What We Checked

- **Heap dumps**: Show multiple copies of model weights for the same model_id but different versions
- **GC logs**: Objects are being dereferenced but not collected (possible reference leak)
- **Model registry**: Confirms only 10 unique models should be loaded at any time
- **Inference logs**: Normal request patterns, no unusual payloads

### Suspicious Observations

- When `load_model()` is called for a new version of an existing model, the old version's weights appear to remain in memory
- The ModelCache `put()` method logs "Evicted model X from cache" but memory profiler shows the data still exists
- Reference count for evicted model objects stays > 0

### Red Herrings Ruled Out

- NOT a memory leak in numpy (same numpy version for 6 months without issues)
- NOT a kernel issue (other services on same hosts are fine)
- NOT request volume (traffic is actually lower than last week)

---

## Business Impact

- Inference service requires restart every 4-6 hours to prevent OOM
- Each restart causes 2-3 minutes of degraded service (requests timeout)
- SLA violations: 3 customers reported prediction failures during restarts
- Data science team blocked from deploying new model versions

---

## Environment Details

```
Service: inference
Port: 8005
Container Memory Limit: 32 GB
Python Version: 3.11
Key Dependencies: numpy, FastAPI
Model Cache Max Size: 10 models
Average Model Size: ~500 MB weights
```

---

## Questions for Investigation

1. Why doesn't the ModelCache eviction actually free memory?
2. Where are the dangling references to old model versions coming from?
3. Is there a cleanup step missing when replacing a model version?
4. How does `_current_models` dict interact with the cache during version updates?

---

## Attachments

- Memory profile: `memory_profile_inference_03_42.json`
- Heap dump: `heap_dump_inference_prod_3.hprof`
- Model deployment log: `model_deployments_20240315.log`
