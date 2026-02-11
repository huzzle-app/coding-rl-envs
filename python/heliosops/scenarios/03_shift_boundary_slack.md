# Slack Thread: #heliosops-dispatch-support

---

**@dispatch-supervisor-garcia** [Today at 6:02 AM]
Hey team, weird issue this morning. Engine 22 shows as "unavailable" even though their shift officially starts at 0600. They're standing by at the station ready to roll but the system won't let me dispatch them.

---

**@sre-oncall-pat** [Today at 6:05 AM]
Looking at this now. Can you confirm the exact shift times configured for Engine 22?

---

**@dispatch-supervisor-garcia** [Today at 6:07 AM]
Yeah, checked the admin panel:
- Shift Start: 06:00:00 UTC
- Shift End: 18:00:00 UTC
- Current Time: 06:02:14 UTC

They should be on shift right now.

---

**@sre-oncall-pat** [Today at 6:09 AM]
Interesting. Let me check the `nearest_units` query response...

```json
{
  "query_time": "2024-03-19T06:02:14Z",
  "units_checked": 24,
  "units_returned": 0,
  "reason": "no units passed shift filter"
}
```

It's filtering out all units. That seems wrong.

---

**@dispatch-supervisor-garcia** [Today at 6:11 AM]
Same thing happened yesterday at exactly 1800. Ambulance 7 was still showing available even though their shift ended. I dispatched them and they were angry because they were supposed to be off duty.

---

**@platform-eng-alex** [Today at 6:14 AM]
Joining thread. So we have two symptoms:
1. Units not showing available at shift START time (0600 today)
2. Units incorrectly showing available at shift END time (1800 yesterday)

That sounds like a boundary condition issue.

---

**@sre-oncall-pat** [Today at 6:16 AM]
Checked the shift validation logic. It's doing something like `shift_start < now < shift_end`. But at exactly 06:00:00, `now` equals `shift_start`, so the condition is false.

---

**@dispatch-supervisor-garcia** [Today at 6:18 AM]
Wait, so if their shift starts at 6:00 they're not considered on shift until 6:00:01?

---

**@platform-eng-alex** [Today at 6:19 AM]
Exactly. And at 18:00:00 they're still showing because `now < shift_end` is true until 18:00:01.

---

**@dispatch-supervisor-garcia** [Today at 6:21 AM]
That's causing real problems. We have crews checking in at shift start and they can't be dispatched for the first minute. And crews staying "available" for a minute past their shift end.

---

**@sre-oncall-pat** [Today at 6:23 AM]
Looking at `geo.py` where `_is_on_shift()` is defined. Let me trace through...

---

**@platform-eng-alex** [Today at 6:26 AM]
@dispatch-supervisor-garcia - as a workaround, can you set shifts to start 1 minute early and end 1 minute late in the admin panel? That should cover the boundary.

---

**@dispatch-supervisor-garcia** [Today at 6:28 AM]
I can try that but it's going to confuse the crews. Their official schedules say 0600-1800, not 0559-1801. HR is going to have questions about the discrepancy.

---

**@ops-manager-chen** [Today at 6:32 AM]
Joining late. This has been an intermittent complaint for weeks but we couldn't reproduce it reliably. Makes sense now that it only happens at exact shift boundaries. Most queries land somewhere in the middle of a shift.

---

**@sre-oncall-pat** [Today at 6:35 AM]
Found the code. In `heliosops/geo.py`:

```python
def _is_on_shift(unit: Unit, now: datetime) -> bool:
    ...
    return unit.shift_start < now < unit.shift_end
```

Should probably be `<=` on at least one side.

---

**@platform-eng-alex** [Today at 6:38 AM]
Created ticket ENG-4521 to track. This is a business logic bug, not just a "nice to have" fix -- it's causing real dispatch failures at shift changeover times which are our busiest periods.

---

**@dispatch-supervisor-garcia** [Today at 6:40 AM]
Thanks team. Let me know when there's a fix. For now I'll use the workaround.

---

*Thread archived for incident tracking*
