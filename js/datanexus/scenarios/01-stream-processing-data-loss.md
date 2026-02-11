# Incident Report: Data Loss in Real-Time Stream Processing

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-18 02:15 UTC
**Acknowledged**: 2024-01-18 02:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: datanexus-ingestion-prod-1 data loss detected
Host: datanexus-ingestion-prod-1.us-west-2.internal
Metric: stream.events.dropped
Threshold: >0 for 1 minute
Current Value: 4,287 events dropped in last minute
```

## Timeline

**02:15 UTC** - Initial alert fired for stream event drops

**02:22 UTC** - Second alert: Memory usage on stream processor exceeding 85%
```
CRITICAL: Memory usage 87.3%
Host: datanexus-transform-prod-2
Metric: container_memory_usage_bytes
```

**02:35 UTC** - Customer reported missing data in their hourly aggregations

**02:48 UTC** - Third pod OOM-killed, goroutine-equivalent leak suspected
```
Container killed due to OOM
exitCode: 137
restartCount: 2
```

**03:15 UTC** - After restart, same patterns immediately recurring

## Grafana Dashboard Observations

### Event Processing Metrics
```
Time Window: 02:00 - 03:00 UTC
Events Ingested: 2,847,293
Events Processed: 2,831,106
Events Dropped (late): 12,891
Events Rejected (window closed): 3,296
Gap: 16,187 events unaccounted for
```

### Window State Metrics
```
Open Windows: 847 (and growing)
Closed Windows: 12,493
Window Memory Usage: 2.1GB (up from 400MB baseline)
Window Cleanup Rate: 0/min (should be ~100/min)
```

### Watermark Progression
```
Source A watermark: 1705544400000 (02:00:00)
Source B watermark: 1705544520000 (02:02:00)
Source C watermark: 1705544100000 (01:55:00)
Min watermark: 1705544100000

Note: Events with timestamp > min_watermark but < source_watermark
are being dropped even when within allowed lateness
```

## Customer Impact

### FinServe Corp (Enterprise Customer)
> "Our 1-minute trading aggregations are showing gaps. We're missing roughly 5% of events in certain windows. This is unacceptable for our compliance reporting."

### DataFlow Inc (Mid-Market)
> "The hourly rollups for our IoT sensors don't match the raw event counts. We're seeing duplicates at window boundaries - the same event appears in two consecutive windows."

## Error Logs

```
2024-01-18T02:15:23Z WARN  Stream processor: event dropped, reason=late
  event_time=1705544150000 watermark=1705544160000 allowed_lateness=5000
  Note: event was only 10 seconds late but within 5-second allowed lateness

2024-01-18T02:18:45Z ERROR Window manager: rejecting event for closed window
  window_key=tumbling:1705543800000 event_time=1705543860000
  Note: event timestamp is clearly WITHIN window bounds

2024-01-18T02:22:12Z WARN  Memory pressure detected
  open_windows=623 closed_windows=8491
  Note: closed window count keeps growing, never cleaned up

2024-01-18T02:25:33Z INFO  Processing event
  window_start=1705544400000 window_end=1705544460000 inclusive=true
  Note: "inclusive=true" for end boundary seems suspicious
```

## Investigation Notes from On-Call

**@oncall.maya** (02:45):
> Looking at the window boundaries. An event at exactly 02:01:00.000 is being assigned to BOTH the 02:00-02:01 window AND the 02:01-02:02 window. That's definitely wrong.

**@oncall.maya** (02:52):
> The watermark tracker seems to be using processing time instead of event time. Source C has old events but its watermark is advancing based on when we receive events, not their timestamps.

**@oncall.alex** (03:05):
> Memory dump shows the `closedWindows` Set keeps growing but `windows` Map never shrinks. We're tracking that windows are closed but never actually freeing the event data.

**@oncall.alex** (03:12):
> Also found something odd in the late event handling. The `isLate()` check doesn't factor in `allowedLateness` at all. It just checks if event time is less than watermark.

## Reproduction Steps

1. Start stream processing with tumbling windows (1-minute size)
2. Ingest events with timestamps spread across window boundaries
3. Observe:
   - Events at exact boundary appearing in multiple windows
   - Late events within allowed lateness being dropped
   - Memory growing as windows are "closed" but not cleaned up
4. After ~30 minutes, memory exhaustion occurs

## Key Questions

1. Why are events at window boundaries appearing in two windows?
2. Why isn't the allowed lateness window being respected?
3. Why are closed windows never being garbage collected?
4. Why is the watermark using processing time instead of event time?

## Files to Investigate

Based on error patterns and stack traces:
- `shared/stream/index.js` - WindowManager and WatermarkTracker
- `services/ingestion/src/services/ingest.js` - Event ingestion
- `services/transform/src/services/pipeline.js` - Stream processing

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Follow-up**: Post-incident review scheduled for 2024-01-19 10:00 UTC
