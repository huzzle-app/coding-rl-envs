# Slack Thread: Failover Region Selection Issue

**Channel:** #platform-incidents
**Date:** 2024-03-25

---

**@sarah.ops** [10:23 AM]
Hey team, we're seeing weird behavior with region failovers. When us-east-1 went degraded this morning, traffic failed over to us-west-2 which was also showing issues. us-central-1 was perfectly healthy but got skipped.

---

**@mike.sre** [10:25 AM]
That's odd. Can you share the resilience logs from around that time?

---

**@sarah.ops** [10:27 AM]
```
10:15:32 INFO  resilience: initiating failover from primary=us-east-1
10:15:32 DEBUG resilience: candidates=['us-west-2', 'us-central-1', 'eu-west-1']
10:15:32 DEBUG resilience: degraded_regions=['us-west-2']
10:15:32 INFO  resilience: selected failover_region=us-west-2
```
Why would it pick us-west-2 when it's in the degraded list? 🤔

---

**@mike.sre** [10:31 AM]
Looking at the code now. The `choose_failover_region` function in resilience module is supposed to skip degraded regions...

---

**@alex.dev** [10:35 AM]
Found it. Check the ordering logic. It's iterating through candidates but I think there's something off with how it's filtering or selecting.

---

**@sarah.ops** [10:38 AM]
We've had 3 customers report elevated error rates during the failover. Whatever this is, it's causing real impact.

---

**@mike.sre** [10:42 AM]
Can someone check what tests are failing for this? Should be something like `test_plan_avoids_degraded_failover_region`

---

**@alex.dev** [10:45 AM]
Confirmed, that test is failing. Also seeing failures in:
- `test_degraded_comms_triggers_hold_at_lower_threshold`
- `test_choose_failover_region_skips_degraded`

---

**@sarah.ops** [10:48 AM]
Is this related to that routing issue we saw last week? The ground station thing?

---

**@mike.sre** [10:52 AM]
Could be the same pattern. Both seem like they're selecting the wrong option from a list. Let me dig into the selection logic...

---

**@alex.dev** [11:05 AM]
Creating a ticket. This needs to be fixed before the next maintenance window.

**Created:** PLAT-2847 - Failover region selection ignores degraded status

---

**@sarah.ops** [11:08 AM]
Thanks team. I'll set up monitoring to catch this earlier next time. 🙏
