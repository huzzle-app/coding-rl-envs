# Slack Thread: Event Replay Returning Wrong Order

**Channel:** #tensorforge-platform
**Date:** 2024-03-25
**Participants:** @elena-k (SRE), @james-w (Backend), @priya-s (Data Eng), @tom-h (Tech Lead)

---

**@elena-k** [09:14 AM]
:rotating_light: anyone seeing issues with event replay? we're getting customer complaints that replayed inference results are coming back in reverse chronological order

**@james-w** [09:16 AM]
wait what? that would completely break deterministic replay guarantees

**@elena-k** [09:17 AM]
yeah exactly. customer tried to replay a batch from yesterday and the events came back newest-first instead of oldest-first. here's what they sent us:
```
Replay request: sequence_range=[1000, 1050]
Expected order: 1000, 1001, 1002, ... 1050
Actual order: 1050, 1049, 1048, ... 1000
```

**@priya-s** [09:19 AM]
oh no. we use that replay for model training data pipelines. if the ordering is wrong, all our training batches are corrupted :scream:

**@tom-h** [09:21 AM]
let me check the event ordering code. this should be a simple sort ascending by timestamp

**@tom-h** [09:24 AM]
found something suspicious in the logs:
```
[2024-03-25T09:15:22.117Z] events::sort DEBUG
  input_count=51
  first_event_ts=1711353600
  last_event_ts=1711357200
  output_first_ts=1711357200
  output_last_ts=1711353600
  ANOMALY: output is sorted descending, expected ascending
```

**@james-w** [09:26 AM]
the sort comparator is probably using `b.cmp(&a)` instead of `a.cmp(&b)`. classic rust gotcha

**@elena-k** [09:28 AM]
there's more. the dedup function is also behaving weird. when we have duplicate event IDs, it's keeping the latest version instead of the earliest:
```
Event ID: evt-12345
  Version 1 (timestamp: 1000): {"status": "pending"}
  Version 2 (timestamp: 2000): {"status": "completed"}

Expected to keep: Version 1 (earliest)
Actually keeping: Version 2 (latest)
```

**@priya-s** [09:31 AM]
that's really bad for audit compliance. we need to keep the original event, not the most recent update. the latest one could have been tampered with

**@tom-h** [09:33 AM]
pulling up the test failures from last night's CI run:
- `test_sort_events_ascending_by_timestamp` - FAILED
- `test_dedup_keeps_earliest_event` - FAILED
- `test_events_in_window_inclusive_bounds` - FAILED
- `test_replay_window_filters_correctly` - FAILED
- `test_event_ordering_for_replay` - FAILED

**@elena-k** [09:35 AM]
wait what's the window issue?

**@tom-h** [09:37 AM]
looks like the time window filter is excluding the start boundary. if you query for events between timestamp 1000 and 2000, it's returning events where `ts > 1000` instead of `ts >= 1000`
```
Window: [1000, 2000]
Event at ts=1000: EXCLUDED (should be INCLUDED)
Event at ts=1500: INCLUDED
Event at ts=2000: INCLUDED
```

**@james-w** [09:40 AM]
so we're losing the first event in every window. that's causing gaps in replay sequences

**@priya-s** [09:42 AM]
this explains the missing data our ML pipeline has been complaining about. we thought it was a kafka issue but it's the event processor

**@tom-h** [09:45 AM]
there's also something wrong with the resilience module's replay filtering. the `replay_window` function is supposed to keep events WITHIN the sequence range, but it's keeping events OUTSIDE the range instead:
```
[2024-03-25T09:40:15.223Z] resilience::replay DEBUG
  min_seq=100
  max_seq=200
  input_events=500
  filtered_events=400
  ANOMALY: keeping 400 events OUTSIDE [100,200] instead of ~100 events INSIDE
```

**@elena-k** [09:48 AM]
:facepalm: so the filter condition is inverted. instead of `seq >= min && seq <= max` it's doing `seq < min || seq > max`

**@james-w** [09:50 AM]
and the batch counting is wrong too. just checked - when we count events by kind, it's counting unique IDs per kind instead of total occurrences:
```
Events: [
  {id: 1, kind: "inference"},
  {id: 2, kind: "inference"},
  {id: 1, kind: "inference"}  // same ID, different occurrence
]
Expected count for "inference": 3
Actual count: 2 (only counting unique IDs)
```

**@tom-h** [09:53 AM]
alright, I'm creating a tracking issue. we have at least 6 bugs in the events and resilience modules:

1. Event sort direction inverted (descending vs ascending)
2. Dedup keeping latest instead of earliest
3. Window filter excluding start boundary
4. Gap detection missing boundary events
5. Replay window filter inverted
6. Event count using unique IDs instead of occurrences

**@priya-s** [09:55 AM]
can we get an ETA? our training pipeline is blocked and we're burning GPU hours with no usable output

**@tom-h** [09:57 AM]
@priya-s these look like straightforward fixes - comparator direction, boundary operators, filter logic. maybe a few hours for an engineer to work through them. the tricky part is they might have dependencies on each other

**@elena-k** [09:59 AM]
I'll add it to the incident board. marking as P1 given the customer impact and compliance risk

**@james-w** [10:01 AM]
:+1: I'll start looking at the events module. someone else want to take resilience?

**@tom-h** [10:03 AM]
I'll handle resilience. let's sync in 2 hours with findings

---

**Thread Summary:**
- Multiple bugs in event ordering, deduplication, and replay filtering
- Causing wrong order, missing events, and incorrect counts
- Blocking ML training pipeline and affecting audit compliance
- 6+ interconnected bugs identified across events and resilience modules
