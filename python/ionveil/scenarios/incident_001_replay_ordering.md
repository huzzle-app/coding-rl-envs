# INC-2024-0847: Event Replay System Returning Stale State During Disaster Recovery

## Severity: P1 - Critical
## Status: Open
## Reported: 2024-03-15 14:22 UTC
## Service: ionveil-resilience / replay-service

---

### Executive Summary

During scheduled disaster recovery testing at the Pacific Northwest Emergency Operations Center, the event replay system failed to reconstruct the correct state for 3 active wildfire incidents. First responders received outdated dispatch assignments after failover, resulting in duplicate resource deployments and a 47-minute coordination gap.

---

### Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:00 | DR drill initiated - primary datacenter marked offline |
| 14:08 | Secondary datacenter promoted to active |
| 14:12 | Event replay triggered for active incidents |
| 14:15 | Dispatch console shows outdated unit assignments |
| 14:22 | Field supervisor reports receiving conflicting dispatch orders |
| 14:47 | Manual reconciliation completed |
| 15:03 | Incident escalated to engineering |

---

### Symptoms Observed

1. **Stale Event State**: After replaying event streams, the system shows older event versions instead of the most recent updates
2. **Incorrect Sequence Processing**: Events with sequence numbers `[1, 4, 2]` for the same incident ID appear to keep sequence 1 instead of 4
3. **Test Failures**: `test_replay_prefers_latest_sequence` consistently fails in unit test suite
4. **Convergence Issues**: `replay_converges()` returns False when comparing replayed streams from different nodes

### Affected Tests

```
FAIL: tests/unit/resilience_test.py::ResilienceTests::test_replay_prefers_latest_sequence
FAIL: tests/stress/hyper_matrix_test.py::test_case_00001 (idx % 4 == 1 path)
FAIL: tests/stress/hyper_matrix_test.py::test_case_00005
... (approximately 3100 similar failures)
```

---

### Reproduction Steps

```python
from ionveil.resilience import replay_events

events = [
    {"id": "incident-wildfire-001", "sequence": 1, "status": "dispatched", "units": ["E41"]},
    {"id": "incident-wildfire-001", "sequence": 4, "status": "on_scene", "units": ["E41", "E42", "T12"]},
    {"id": "incident-flood-002", "sequence": 2, "status": "en_route", "units": ["R7"]},
]

result = replay_events(events)
# Expected: Returns events with highest sequence per ID
# Actual: Returns events with LOWEST sequence per ID
```

---

### Log Excerpts

```
2024-03-15 14:12:33.441 [ionveil.resilience] DEBUG: Replay processing 847 events
2024-03-15 14:12:33.512 [ionveil.resilience] DEBUG: Dedup complete: 312 unique incident IDs
2024-03-15 14:12:33.589 [ionveil.dispatch] WARN: Incident INC-WF-2847 shows 1 assigned units, expected 4
2024-03-15 14:12:33.601 [ionveil.dispatch] WARN: Incident INC-WF-2849 shows status=dispatched, expected on_scene
2024-03-15 14:15:01.223 [ionveil.gateway] ERROR: Consistency check failed - replay state differs from checkpoint
```

---

### Business Impact

- **Field Operations**: 3 fire crews received duplicate dispatch orders
- **Resource Waste**: Estimated $24,000 in unnecessary deployments
- **Response Time**: 47-minute gap in coordinated response
- **Compliance**: Potential NIMS/ICS audit finding for command inconsistency
- **Trust**: Operations team expressing concern about DR reliability

---

### Technical Context

The `replay_events()` function in `ionveil/resilience.py` is responsible for reconstructing state from an event stream. It should:
1. Group events by their entity ID
2. For each entity, retain only the event with the HIGHEST sequence number
3. Return events sorted by (sequence, id) for deterministic ordering

The CheckpointManager records periodic snapshots, and replay is used to bring state forward from the last checkpoint.

---

### Investigation Notes

- Problem appears to be in the event deduplication logic
- The sequence comparison might be inverted
- All instances in the cluster show identical behavior (not a node-specific issue)
- Problem is 100% reproducible in test suite

---

### Stakeholders

- **Incident Commander**: Deputy Chief M. Rodriguez (Pacific NW EOC)
- **Platform Lead**: @dispatch-team
- **On-Call**: @resilience-oncall

---

### Related Incidents

- INC-2024-0312: Similar replay issues reported during Q1 DR drill (marked "could not reproduce")
- INC-2023-1847: Checkpoint corruption - may be masking this underlying bug
