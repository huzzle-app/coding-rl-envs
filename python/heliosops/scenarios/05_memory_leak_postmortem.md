# POSTMORTEM DRAFT: Gradual Memory Growth Leading to OOM Kills

**Incident Date**: 2024-03-14 through 2024-03-17
**Author**: Platform Engineering
**Status**: DRAFT - Root Cause Analysis Incomplete
**Review Date**: Pending

---

## Incident Summary

Over a 72-hour period, HeliosOps worker nodes exhibited steadily increasing memory usage, eventually triggering OOM (Out of Memory) kills. The pattern repeated on multiple nodes, each time approximately 18-24 hours after restart. No obvious memory spike or trigger event was identified.

## Impact

- 7 worker node restarts due to OOM kills
- 3 periods of degraded availability (5-15 minutes each)
- Increased infrastructure costs from over-provisioned memory (temporary mitigation)

## Timeline

```
Day 1, 00:00 UTC: Fresh deployment, baseline memory ~1.2 GB per worker
Day 1, 12:00 UTC: Memory at ~2.1 GB per worker
Day 2, 00:00 UTC: Memory at ~3.4 GB per worker
Day 2, 08:47 UTC: First OOM kill on worker-3
Day 2, 09:02 UTC: worker-3 restarted, memory back to 1.2 GB
Day 2, 18:00 UTC: worker-3 memory at 2.0 GB (growing again)
Day 3, 03:15 UTC: Second OOM kill on worker-1
Day 3, 14:22 UTC: Third OOM kill on worker-5
...pattern continues...
```

## Memory Profile Analysis

### Heap Dumps

We captured heap dumps at multiple points. The largest growth categories:

| Object Type | Count Growth (24h) | Memory Growth |
|-------------|-------------------|---------------|
| `socket` objects | +47,000 | +180 MB |
| `dict` objects | +125,000 | +340 MB |
| `file` objects | +8,200 | +65 MB |
| `weakref` objects | +12,000 | +25 MB |

### Correlation with Traffic

Memory growth does NOT correlate with request volume:
- Low traffic periods (2-6 AM): Memory still grows
- High traffic periods (9 AM - 6 PM): Growth rate similar

This suggests the leak is not directly tied to request handling but to some background process or cleanup failure.

## Hypotheses Under Investigation

### Hypothesis 1: WebSocket Connection Leak

The unit tracking WebSocket handler manages a global connection set. When clients disconnect, connections may not be removed properly.

**Evidence**:
- `socket` object count grows continuously
- WebSocket connection count in metrics diverges from actual active connections
- `_ws_connections` set size only grows, never shrinks

**Affected Code**: `heliosops/geo.py` - `UnitTrackingWSHandler`

### Hypothesis 2: File Descriptor Leak in Geofence Loading

The geofence data loader opens files but may not close them if an exception occurs during parsing.

**Evidence**:
- `lsof` shows hundreds of open file handles to geofence data files
- File descriptor count grows over time
- Pattern matches geofence reload frequency

**Affected Code**: `heliosops/geo.py` - `load_geofence_data()`

### Hypothesis 3: Unclosed Statistics File Handles

The statistics module opens files for heatmap generation but there's a suspicious pattern in the code.

**Evidence**:
- Heatmap files remain locked after generation
- `file` object count correlates with heatmap generation runs

**Affected Code**: `heliosops/statistics.py` (file handling functions)

### Hypothesis 4: Metrics Cardinality Explosion

High-cardinality labels on metrics (like `incident_id` as a label) could cause the metrics library to retain memory for each unique label combination.

**Evidence**:
- Prometheus client memory footprint is unusually large
- Label cardinality for some metrics exceeds 100,000 unique values

**Affected Code**: `heliosops/statistics.py` - metric registration

## Preliminary Findings

### WebSocket Handler Review

```python
class UnitTrackingWSHandler:
    def on_disconnect(self) -> None:
        # Does this actually clean up?
        pass
```

The disconnect handler appears to be a no-op. Connections are added to the global set but never removed.

### Geofence Loader Review

```python
def load_geofence_data(filepath: str) -> List[...]:
    f = open(filepath, "r")
    # ... parsing logic ...
    f.close()  # Only reached on success
    return polygons
```

If parsing raises an exception, the file handle is never closed. With frequent reload attempts on malformed data, this could accumulate.

## Recommended Investigation Steps

1. Review `on_disconnect()` in `geo.py` for proper cleanup
2. Audit all `open()` calls for proper `with` statement or try/finally patterns
3. Check metrics label cardinality in `statistics.py`
4. Run memory profiler with object tracking enabled

## Temporary Mitigation

- Increased node memory from 4GB to 8GB
- Added cron job to restart workers every 12 hours
- Reduced geofence reload frequency

## Root Cause

**PENDING** - Awaiting code review completion

## Lessons Learned

**PENDING** - To be completed after root cause identified

---

*This postmortem is a draft. Do not distribute externally.*
