# Scenario 05: Distributed Training Cluster Hang

## Incident Report: IR-2024-0319-001

**Severity**: SEV-1
**Duration**: 4 hours 23 minutes
**Services Affected**: training, workers
**Customers Impacted**: All training jobs (47 jobs affected)

---

## Executive Summary

On March 19, 2024, the distributed training cluster experienced a complete hang affecting all active training jobs. The incident was caused by multiple interacting concurrency bugs in the parameter server and all-reduce coordination systems. Total business impact: ~$45,000 in GPU compute time wasted, 47 training jobs failed.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:00 | Spike in training jobs as data science team kicks off hyperparameter sweep |
| 14:12 | First worker timeout alert: "Worker w-12 failed to receive parameters" |
| 14:15 | 8 workers showing "waiting for lock" status |
| 14:18 | All-reduce operations timing out across cluster |
| 14:23 | Parameter server CPU at 100%, all 32 workers blocked |
| 14:30 | On-call declares SEV-1, pages distributed systems team |
| 14:45 | Initial diagnosis: deadlock in all-reduce coordinator |
| 15:30 | Attempted rolling restart of workers - made situation worse |
| 16:00 | Identified secondary issue: parameter server race condition |
| 17:15 | Force-killed all workers, restarted parameter server |
| 17:30 | Cluster restored, jobs re-queued |
| 18:23 | All re-queued jobs confirmed running |

---

## Symptoms Observed

### 1. Worker Deadlock Pattern

Thread dumps from worker processes showed classic ABBA deadlock:

```
Worker-12 Thread-7:
  waiting for: _aggregation_lock
  holding: _worker_lock

Worker-18 Thread-3:
  waiting for: _worker_lock
  holding: _aggregation_lock
```

All 32 workers eventually blocked waiting for one of these two locks.

### 2. Parameter Server Race Condition

Before the deadlock, we observed intermittent data corruption:

```
Worker-5: Received parameters version=142
Worker-5: Applied gradient, expected version=143
Worker-5: Received parameters version=142 (STALE!)
Worker-8: Received parameters version=144 (skipped 143?)
```

Workers were receiving inconsistent parameter versions. Some workers got stale parameters, others skipped versions entirely.

### 3. Staleness Bound Violation

Training logs showed stale gradients being applied:

```
WARNING: Worker w-23 gradient staleness=15, max_allowed=10
WARNING: Worker w-17 gradient staleness=12, max_allowed=10
WARNING: Worker w-09 gradient staleness=18, max_allowed=10
```

Despite warnings, stale gradients were still applied. The staleness check logs but doesn't reject.

### 4. All-Reduce Never Completes

```
DEBUG: AllReduceCoordinator: barrier_count=31/32, waiting...
DEBUG: AllReduceCoordinator: barrier_count=31/32, waiting... (60s)
DEBUG: AllReduceCoordinator: barrier_count=31/32, waiting... (120s)
DEBUG: AllReduceCoordinator: barrier_count=31/32, waiting... (180s)
TIMEOUT: AllReduceCoordinator: barrier never reached, 1 worker missing
```

One worker was blocked on a lock, preventing the barrier from completing. All other workers blocked waiting for the barrier.

---

## Root Cause Analysis

### Primary Cause: Lock Ordering Violation

The `AllReduceCoordinator` class has two locks: `_worker_lock` and `_aggregation_lock`.

**Path 1** (`submit_gradients`):
1. Acquire `_worker_lock`
2. Acquire `_aggregation_lock` (nested)
3. Release both

**Path 2** (`get_reduced_gradients`):
1. Acquire `_aggregation_lock`
2. Acquire `_worker_lock` (nested)
3. Release both

When Worker A calls `submit_gradients` while Worker B calls `get_reduced_gradients`:
- Worker A holds `_worker_lock`, waits for `_aggregation_lock`
- Worker B holds `_aggregation_lock`, waits for `_worker_lock`
- **DEADLOCK**

### Secondary Cause: Parameter Server Race

The `ParameterServer.apply_gradient()` and `get_parameters()` methods have no locking:

1. Worker A reads parameters (version=100)
2. Worker B applies gradient, version becomes 101
3. Worker A applies gradient based on version 100
4. Worker C reads parameters (gets version 101)
5. Worker A reads parameters (gets version 101, but its gradient was based on 100)

This caused inconsistent training state and likely contributed to workers falling behind.

### Tertiary Cause: Staleness Check Ineffective

```python
if staleness > self._max_staleness + 1:  # Off-by-one
    logger.warning(...)
    pass  # Does NOT return False!
```

The staleness check:
1. Has an off-by-one error (`> max + 1` instead of `>= max`)
2. Logs a warning but doesn't reject the gradient

---

## Symptoms Summary

1. **Complete cluster hang**: All 32 workers blocked, no training progress
2. **ABBA deadlock**: Two locks acquired in opposite order by different code paths
3. **Stale parameters**: Workers receive outdated parameter versions
4. **Version skipping**: Some parameter versions never delivered to some workers
5. **Staleness warnings ignored**: Stale gradients applied despite exceeding threshold
6. **Barrier timeout**: All-reduce barrier never completes due to blocked worker
7. **Inconsistent model state**: Different workers training with different parameter states

---

## Business Impact

| Metric | Value |
|--------|-------|
| Training jobs affected | 47 |
| GPU hours wasted | ~180 |
| Estimated cost | $45,000 |
| Data science productivity loss | 4 hours x 12 engineers |
| SLA violation | Yes (training availability < 99%) |

---

## Affected Components

- `shared/utils/distributed.py`: ParameterServer, AllReduceCoordinator
- `services/training/main.py`: TrainingOrchestrator
- `services/workers/tasks.py`: Worker task coordination

---

## Recommended Actions

1. Enforce consistent lock ordering across all code paths
2. Add proper locking to parameter server read/write operations
3. Fix staleness check to actually reject stale gradients
4. Add deadlock detection with timeout and recovery
5. Implement circuit breaker for distributed training operations
