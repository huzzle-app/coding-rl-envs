# Slack Thread: #ops-traffic-grid - Workflow Processing Issues

---

**@marina.chen** [09:15 AM]
Hey team, anyone else seeing weird behavior with the workflow engine this morning? I'm looking at the vessel throughput dashboard and the numbers don't add up.

---

**@david.okonkwo** [09:17 AM]
Yeah I noticed that too. The completion percentage for the morning batch shows 133%? That's... not possible.

---

**@marina.chen** [09:18 AM]
Wait what? Let me check

Screenshot: [workflow_metrics_anomaly.png]
```
Morning Batch Summary:
- Completed: 75
- Total: 100
- Completion: 133.33%

Throughput: 0.5 vessels/hour
(Completed: 10, Hours: 5)
```

---

**@sarah.goldberg** [09:19 AM]
That throughput also looks inverted. 10 completed in 5 hours should be 2/hr not 0.5/hr

---

**@david.okonkwo** [09:21 AM]
I just ran a test locally:
```cpp
completion_percentage(75, 100)  // expected: 75.0, got: 133.33
workflow_throughput(10, 5.0)    // expected: 2.0, got: 0.5
```

The completion calculation is dividing the wrong way: `total/completed` instead of `completed/total`

---

**@marina.chen** [09:23 AM]
Okay that explains the dashboard. But we have a bigger problem. Look at the bottleneck detection:

```
State Distribution:
- queued: 47
- allocated: 12
- departed: 3
- arrived: 2

Detected Bottleneck: "allocated"
```

Shouldn't it be "queued"? That has the most vessels waiting.

---

**@james.murphy** [09:25 AM]
Let me check the bottleneck_state function... yeah it's returning the first key from the map instead of the max. std::map iteration is alphabetical so "allocated" comes before "queued"

---

**@sarah.goldberg** [09:27 AM]
That's bad. We've been making staffing decisions based on this data. If we thought allocated was the bottleneck, we've been putting extra resources on berth crews instead of dispatch.

---

**@david.okonkwo** [09:28 AM]
Found another one. The parallel entity count is wrong too:

```cpp
entities = [{"v1", "queued"}, {"v2", "allocated"}, {"v3", "arrived"}]
parallel_entity_count(entities)  // expected: 2, got: 3
```

It's counting arrived vessels as "active" but arrived is a terminal state.

---

**@marina.chen** [09:30 AM]
And the transition count per vessel is broken. I'm debugging vessel V-8834:

```cpp
records = [
    {"v1", "queued", "allocated"},
    {"v2", "queued", "cancelled"},
    {"v1", "allocated", "departed"}
]
transition_count(records, "v1")  // expected: 2, got: 3
```

It's counting ALL transitions, not filtering by entity_id.

---

**@james.murphy** [09:32 AM]
Same thing with chain_length. No entity filtering.

---

**@sarah.goldberg** [09:34 AM]
Okay, let me compile what we've found so far for the incident report:

**Workflow bugs identified:**
1. `completion_percentage` - division inverted (total/completed vs completed/total)
2. `workflow_throughput` - same inversion issue
3. `bottleneck_state` - returns first map key, not max value
4. `parallel_entity_count` - doesn't exclude terminal states
5. `transition_count` - doesn't filter by entity_id
6. `chain_length` - same filtering issue

---

**@david.okonkwo** [09:36 AM]
Add time calculations to the list. `time_in_state_hours` returns milliseconds, not hours:

```cpp
time_in_state_hours(0, 3600000)  // expected: 1.0, got: 3600000.0
```

And `state_age_hours` returns minutes instead of hours.

---

**@marina.chen** [09:38 AM]
Found the path validation issue. This path should be invalid:
```cpp
is_valid_path({"queued", "arrived"})  // expected: false, got: true
```

You can't go directly from queued to arrived. The function only checks if each state is valid, not if the transitions between consecutive states are valid.

---

**@james.murphy** [09:40 AM]
Also `can_cancel` is too permissive:
```cpp
can_cancel("arrived")  // expected: false, got: true
```

You shouldn't be able to cancel a vessel that's already arrived.

---

**@sarah.goldberg** [09:42 AM]
@ops-leads FYI we have significant issues with workflow metrics. The data powering our operations dashboard has been incorrect. Key impacts:
- Bottleneck detection pointing to wrong stages
- Throughput numbers inverted
- Active vessel counts inflated
- Per-vessel analytics broken

Staffing and resource allocation decisions based on this data should be reviewed.

---

**@carlos.rodriguez** [09:45 AM]
Thanks for the heads up. @marina.chen can you open an incident? This affects our SLA reporting too.

---

**@marina.chen** [09:47 AM]
On it. Linking to the failing tests:
- `workflow_transition_count`
- `workflow_time_in_state`
- `workflow_parallel_count`
- `workflow_bottleneck`
- `workflow_completion_pct`
- `workflow_state_age`
- `workflow_valid_path`
- `workflow_cancel_from_any`
- `workflow_throughput`
- `workflow_chain_length`

All in `tests/test_main.cpp` lines 635-753.

---

**@david.okonkwo** [09:48 AM]
The source is `src/workflow.cpp`. All these functions have BUG markers. This looks like a bigger cleanup effort.

---

**@james.murphy** [09:50 AM]
Also noticed the merge_histories function doesn't sort after merging. If you merge two history streams, they should be ordered by timestamp but they're just concatenated.

---

**@sarah.goldberg** [09:52 AM]
Okay, I've updated the incident with all findings. @platform-oncall for visibility.

**Summary:**
- 14 bugs identified in workflow module
- Affects: bottleneck detection, throughput metrics, entity counts, time calculations, path validation, cancellation logic
- Business impact: incorrect operational dashboards, wrong resource allocation, invalid SLA reports

---

**@carlos.rodriguez** [09:55 AM]
Thanks everyone. Let's get this fixed before the afternoon shift review.

---

*Thread participants: @marina.chen, @david.okonkwo, @sarah.goldberg, @james.murphy, @carlos.rodriguez*
