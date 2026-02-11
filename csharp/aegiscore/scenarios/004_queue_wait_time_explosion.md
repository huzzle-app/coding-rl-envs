# Slack Thread: #aegiscore-oncall

---

**@sarah.ops** - 2024-11-12 16:42
Hey team, getting weird numbers from the dispatch queue dashboard. Wait time estimates are WAY off. System is showing 800+ minute wait times when we only have 20 orders in queue.

---

**@mike.sre** - 2024-11-12 16:44
That's bizarre. What's the processing rate showing?

---

**@sarah.ops** - 2024-11-12 16:45
Processing rate is 0.5 orders/minute which is normal. But with 20 orders and 0.5/min rate, wait time should be ~40 minutes, not 800.

---

**@chen.backend** - 2024-11-12 16:48
I think I see what's happening. Let me check the `EstimateWaitTime` function in QueueGuard...

Actually wait, the formula looks wrong. The code is doing `depth * processingRate` but that gives you something weird. If depth=20 and rate=0.5, you get 10, not 40.

But 800 minutes... that's like 20 * 40 or something. @sarah.ops what's the exact depth and rate values?

---

**@sarah.ops** - 2024-11-12 16:51
Depth: 20
Processing rate: 40 orders/minute (peak capacity)

So 20 * 40 = 800. The multiplication is backwards!

---

**@mike.sre** - 2024-11-12 16:53
Oh I see it now. The formula should be `depth / processingRate` (division), not multiplication. Classic inverted operation bug.

With depth=20 and rate=40, correct answer is 0.5 minutes. But we're getting 800 minutes instead.

---

**@chen.backend** - 2024-11-12 16:55
Yeah that's AGS0011. The `EstimateWaitTime` function has the operator inverted.

Also I noticed another issue in the same module - the emergency queue threshold (AGS0010). The `ShouldShed` function is using `>` instead of `>=` for the 80% emergency threshold. So if you're at exactly 80% capacity, it won't trigger emergency shedding when it should.

---

**@sarah.ops** - 2024-11-12 16:58
That would explain why we had that queue overflow last week. We were hovering right at the 80% line and no shedding kicked in.

---

**@mike.sre** - 2024-11-12 17:00
Let me file tickets for both:
1. Wait time calculation inverted (multiply vs divide)
2. Emergency threshold off-by-one (> vs >=)

Both in QueueGuard module.

---

**@chen.backend** - 2024-11-12 17:02
There are test failures for these:
```
QueueGuardUsesHardLimit (the emergency threshold case)
EstimateWaitTimeCalculation
```

---

**@sarah.ops** - 2024-11-12 17:05
Thanks team. This explains why operations has been complaining about the dashboard. They've been manually calculating wait times in Excel because they don't trust the system numbers.

---

**Thread resolved** - 2024-11-12 17:10
Action items assigned to Core Platform team.
