# Slack Discussion: Pipeline Stage Failures and Retry Storms

## #genomics-platform - March 22, 2024

---

**@sre.alex** (08:15):
> We had another pipeline incident overnight. 47 samples stuck in failed state, and I'm seeing weird retry behavior. Anyone from the genomics team available?

**@sre.alex** (08:17):
> Dashboard screenshot:
```
Pipeline Status (Last 24h)
--------------------------
Started: 312
Completed: 218
Failed (retries exhausted): 47
Stuck (retry loop): 47

Retry Distribution:
  Intake: 12 retries avg (budget: 2)
  QC: 8 retries avg (budget: 2)
  Align: 23 retries avg (budget: 5)
  CallVariants: 6 retries avg (budget: 3)
```

**@dev.priya** (08:25):
> Those retry counts look way off. How is Intake hitting 12 retries if the budget is 2?

**@sre.alex** (08:28):
> That's what I'm trying to figure out. Also, samples are failing at the Align stage after only 4 retries, but the budget should be 5.

**@dev.priya** (08:32):
> Let me check the `can_retry` function... oh no. It's checking `retries > budget` instead of `retries < budget`. That's completely inverted logic!

**@dev.marcus** (08:35):
> Wait, so samples that HAVE retries left are being marked as exhausted, and samples that are OUT of retries keep going?

**@dev.priya** (08:38):
> Exactly. And I found another issue - when a pipeline advances to the next stage, it's not resetting the retry counter. So if Intake used 2 retries, QC starts with 2 already used.

---

**@sre.alex** (09:00):
> There's more weirdness. Look at these stage transitions:

```
Run ID: RUN-2024-08847
Timeline:
  08:00:00 - Stage: Intake
  08:05:00 - Stage: QC
  08:20:00 - Stage: Align
  08:22:00 - ERROR: "Invalid stage transition: Align -> Align"
  08:22:01 - Pipeline marked FAILED
```

**@dev.priya** (09:05):
> I see it. The `can_transition` function returns `false` for same-stage transitions. But staying in the same stage should be a valid no-op, especially for retry scenarios.

**@dev.marcus** (09:08):
> Also found that the stage index calculation is wrong:
```
stage_index(CallVariants) = 4  // should be 3
stage_index(Annotate) = 3      // should be 4
```

**@dev.priya** (09:12):
> That would cause all sorts of havoc with transition validation.

---

**@sre.alex** (09:30):
> Pipeline duration estimates are also way off. Our capacity planning is showing we can handle 500 samples/day, but we're bottlenecking at 350.

```
Expected Duration: 260 minutes
Actual Duration: 270 minutes
Discrepancy: 10 minutes

Individual Stage Estimates:
  Intake: 5m (correct)
  QC: 15m (correct)
  Align: 120m (correct)
  CallVariants: 90m (correct)
  Annotate: 30m (correct)
  Report: shows 10m (should be 5m)
```

**@dev.priya** (09:35):
> There's also something wrong with the total pipeline duration calculation. It's not including the Report stage at all!

```rust
// This is what I'm seeing in the code:
total_pipeline_duration = Intake + QC + Align + CallVariants + Annotate
// Missing: + Report
```

**@sre.alex** (09:40):
> That explains the capacity planning mismatch. We're underestimating by 5-10 minutes per sample.

---

**@qa.jennifer** (10:00):
> I ran the pipeline validation tests and got failures:

```
test pipeline::test_valid_stage_order ... FAILED
  Assertion: valid_stage_order should verify actual stage sequence
  Any 6-element array passes, even wrong order!

test pipeline::test_stage_transitions ... FAILED
  Assertion: same-stage transition should be allowed
  can_transition(Align, Align) returned false, expected true

test pipeline::test_critical_stages ... FAILED
  Assertion: Annotate should be marked as critical
  is_critical_stage(Annotate) returned false, expected true

test pipeline::test_parallel_factor ... FAILED
  Assertion: QC parallel factor should be 4
  parallel_factor(QC) returned 2, expected 4
```

**@dev.priya** (10:10):
> The `valid_stage_order` function only checks length, not actual order! Any array with 6 elements passes.

**@dev.marcus** (10:15):
> And the Annotate stage is missing from `is_critical_stage`. That's important for scheduling priority.

---

**@ops.david** (10:30):
> Operations here. We're getting complaints from the clinical lab about sample turnaround times. Can someone give me an ETA on fixes?

**@dev.priya** (10:35):
> We've identified at least 10 issues in the pipeline logic:
1. Retry check logic inverted
2. Retry counter not reset on stage advance
3. Stage indices swapped for CallVariants/Annotate
4. Same-stage transitions rejected
5. Total duration missing Report stage
6. Stage order validation only checks length
7. Annotate not marked as critical stage
8. Report duration estimate wrong (10m vs 5m)
9. Align retry budget wrong (4 vs 5)
10. QC parallel factor wrong (2 vs 4)

**@ops.david** (10:40):
> That's a lot. What's the customer impact?

**@sre.alex** (10:45):
> - 47 samples stuck in failed state need manual intervention
- 23% reduction in throughput due to wrong parallel factors
- Retry storms consuming compute resources
- Incorrect ETA calculations frustrating lab staff

---

**Status**: INVESTIGATING
**Severity**: P1
**Assigned**: @genomics-pipeline-team
**Customer Impact**: Clinical sample processing delayed by 4-6 hours
