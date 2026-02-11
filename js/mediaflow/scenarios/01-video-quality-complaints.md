# Incident Report: Video Quality Degradation in High-Motion Content

## PagerDuty Alert

**Severity**: High (P2)
**Triggered**: 2024-02-12 18:30 UTC
**Team**: Media Engineering
**Service**: transcode-service

---

## Alert Details

```
WARNING: Video quality complaints spike detected
Dashboard: media-quality-metrics
Time Window: Last 2 hours
Affected Content: Sports streams, action movies, live events
Complaint Rate: 340% above baseline
```

## Customer Reports (Zendesk)

### Ticket #89421
> "I'm watching the Champions League final and the quality is terrible. Whenever there's fast action on the pitch, the video looks like it's from 2005. I'm paying for 4K Premium and this is unacceptable."

### Ticket #89445
> "Action movies look blocky during fight scenes. Dialogue scenes are fine but any movement causes artifacts. Something changed recently - this wasn't happening last week."

### Ticket #89467
> "Live concert stream is unwatchable. Audio is crystal clear but video turns into a pixelated mess whenever the camera pans across the crowd."

---

## Internal Slack Thread

**#video-platform** - February 12, 2024

**@content-ops** (18:45):
> We're getting hammered with quality complaints. Seems specific to high-motion content. Any ideas?

**@media-eng-sara** (18:52):
> Looking at transcoding logs. The bitrate calculations seem off. For 1080p60 content, we should be hitting around 8-12 Mbps for sports, but I'm seeing some videos encoded at way lower rates.

**@media-eng-raj** (19:03):
> Pulled up some samples. Here's what I'm seeing for a sports clip:
> ```
> Input: 1920x1080, 60fps, high motion
> Expected bitrate: ~10,000 kbps (motion factor 1.5)
> Actual bitrate: 8,068 kbps
> ```
> The motion factor doesn't seem to be scaling the bitrate properly.

**@media-eng-sara** (19:10):
> That's weird. Motion factor of 1.5 should increase bitrate by 50%. Let me check the bitrate calculator...

**@media-eng-raj** (19:18):
> Found something else - the adaptive tiers are also wrong. 720p tier is showing almost the same bitrate as 1080p for high-motion content. That can't be right.

**@qa-lead** (19:25):
> I ran some tests with known motion factors. The results don't match our specs at all. Motion factor seems to have minimal effect on final bitrate.

---

## Technical Investigation

### Test Results

```
Transcoding test with controlled inputs:
  Input: 1920x1080, 30fps, codec h264
  Motion Factor: 1.0 (low motion)
  Result: 207,360 kbps (base bitrate)

  Input: 1920x1080, 30fps, codec h264
  Motion Factor: 2.0 (high motion)
  Expected: 414,720 kbps (2x multiplier)
  Actual: 207,362 kbps (barely changed)
```

### Sample Encoder Output

```json
{
  "job_id": "enc-7834921",
  "input": {
    "resolution": "1920x1080",
    "frameRate": 60,
    "motionComplexity": "high"
  },
  "output": {
    "tiers": [
      {"label": "1080p", "bitrate": 233284},
      {"label": "810p", "bitrate": 131224},
      {"label": "540p", "bitrate": 58322},
      {"label": "270p", "bitrate": 14581}
    ]
  },
  "motionFactor": 1.5,
  "timestamp": "2024-02-12T18:00:00Z"
}
```

### Expected vs Actual Bitrates

| Resolution | Motion Factor | Expected Bitrate | Actual Bitrate | Difference |
|------------|---------------|------------------|----------------|------------|
| 1080p | 1.0 | 233,280 | 233,281 | ~0% |
| 1080p | 1.5 | 349,920 | 233,282 | -33% |
| 1080p | 2.0 | 466,560 | 233,282 | -50% |
| 720p | 1.5 | 156,060 | 104,041 | -33% |

---

## Grafana Observations

### Quality Metrics Dashboard
- VMAF scores dropped 15-20 points for high-motion content
- Buffering ratio increased 3x for sports category
- Re-encoding queue depth: normal (not a capacity issue)

### Bitrate Distribution
```
Before Feb 10:
  High motion content: 8-15 Mbps average
  Low motion content: 4-8 Mbps average

After Feb 10:
  High motion content: 5-8 Mbps average (dropped!)
  Low motion content: 4-8 Mbps average (unchanged)
```

---

## Recent Changes

- Feb 10: Deployed v2.3.1 of transcode-service
- Feb 10: Refactored adaptive tier calculation for efficiency
- Feb 11: No deployments

---

## Impact Assessment

- **Users Affected**: ~45% of concurrent viewers (sports/action content)
- **Revenue Impact**: 12 subscription cancellations citing quality issues
- **SLA Status**: Quality SLA at risk (target: VMAF > 85, current: 71 for affected content)

---

## Files to Investigate

Based on the symptoms:
- `services/transcode/src/services/bitrate.js` - Bitrate calculations
- Adaptive tier generation logic
- Motion factor application

---

**Status**: INVESTIGATING
**Assigned**: @media-eng-team
**Priority**: High - affects premium subscribers
