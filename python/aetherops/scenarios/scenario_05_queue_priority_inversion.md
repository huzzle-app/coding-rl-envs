# Scenario 05: Mission Command Queue Processing Low-Priority First

## Incident Post-Mortem: INC-2026-0201

**Incident Commander:** Alex Petrov
**Date of Incident:** 2026-01-25
**Duration:** 3 hours 17 minutes
**Severity:** SEV-1

---

### Executive Summary

A priority inversion bug in the command queue processor caused low-priority housekeeping commands to be processed before high-priority orbital correction commands. This resulted in delayed execution of a critical attitude adjustment for GEOSAT-4, leading to a temporary loss of antenna pointing accuracy.

### Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:02 | Attitude drift detected on GEOSAT-4 |
| 14:05 | Priority-5 correction command queued |
| 14:08 | Priority-1 telemetry poll command queued |
| 14:12 | Queue processor dequeues priority-1 command first |
| 14:15 | Operators notice wrong command executed |
| 14:18 | Manual override initiated |
| 14:45 | Correction command finally processed |
| 17:19 | Antenna pointing restored to nominal |

### Root Cause

The `PriorityQueue.dequeue()` method in `aetherops/queue.py` is returning the item with the **lowest** priority value instead of the **highest**. In our system, priority 5 is critical and priority 1 is routine, but the queue is treating priority 1 as more urgent.

### Evidence

When debugging, we observed:
```python
queue = PriorityQueue()
queue.enqueue("urgent", priority=5)    # Should be first
queue.enqueue("routine", priority=1)   # Should be last
item = queue.dequeue()
# Returns "routine" instead of "urgent"
```

### Additional Queue Issues Found

During investigation, the team also identified related problems:

1. **Queue health utilization calculation** - The utilization formula appears inverted, showing utilization > 1.0 for nearly empty queues and < 1.0 for full queues.

2. **Wait time estimation** - Estimated wait times are impossibly high. A queue of 10 items with a processing rate of 2/second shows 20 seconds wait instead of 5 seconds.

### Test Failures

```
tests/unit/queue_test.py::QueueTest::test_priority_queue_ordering
tests/unit/queue_test.py::QueueTest::test_queue_health_metrics
tests/unit/queue_test.py::QueueTest::test_wait_time_estimation
tests/stress/hyper_matrix_test.py::test_queue_priority_*
tests/stress/service_mesh_matrix_test.py::test_command_ordering_*
```

### Impact Assessment

- GEOSAT-4 pointing accuracy degraded for 2.5 hours
- 12 downlink sessions missed (estimated data loss: 840 MB)
- Customer SLA breach (99.9% availability target)
- Estimated revenue impact: $45,000 in service credits

### Corrective Actions

1. Fix priority queue ordering logic (high priority = dequeue first)
2. Fix queue health utilization calculation
3. Fix wait time estimation formula
4. Add integration tests for priority ordering
5. Implement priority queue invariant monitoring

---

### Lessons Learned

Priority semantics must be clearly documented and tested. The current implementation assumes "lower number = higher priority" (like Unix nice values) but our domain uses "higher number = higher priority" (like severity levels).

---

**Post-Mortem Owner:** Alex Petrov
**Review Date:** 2026-01-27
**Status:** Pending Fix
