# Slack Thread: Policy Engine Acting Strange

**Channel:** #nimbusflow-ops
**Date:** 2024-09-22

---

**@marina.chen** [09:14]
Anyone else seeing weird behavior from the policy engine today? We had 5 consecutive failures on the routing cluster and the system stayed in NORMAL mode.

**@derek.okonkwo** [09:16]
Wait what? 5 failures should definitely trigger escalation to WATCH at minimum

**@marina.chen** [09:17]
Right? I checked the logs and it's like the escalation logic is inverted. We need MORE failures for it to NOT escalate? Makes no sense.

**@sarah.tanaka** [09:21]
I noticed something similar yesterday. We had a single random timeout and suddenly we were in RESTRICTED mode. Like way too aggressive.

**@derek.okonkwo** [09:23]
Screenshot of the policy history?

**@marina.chen** [09:25]
```
[09:02:31] normal -> normal (failureBurst: 5)
[09:05:44] normal -> watch (failureBurst: 1)
[09:08:12] watch -> restricted (failureBurst: 1)
[09:10:33] restricted -> restricted (failureBurst: 8)
```
See that? 5 failures = stay normal. 1 failure = escalate. 8 failures = stay put.

**@priya.sharma** [09:28]
That's completely backwards from the design doc. The threshold is supposed to be >1 failure triggers escalation.

**@derek.okonkwo** [09:30]
And there's also de-escalation happening way too fast. I saw us go from HALTED to NORMAL in like 2 minutes yesterday.

**@marina.chen** [09:32]
Oh yeah the de-escalation thresholds are all wrong too. Check this out:
```
shouldDeescalate("halted", successStreak=5) -> true   // Should need 10
shouldDeescalate("restricted", successStreak=3) -> true  // Should need 6
shouldDeescalate("watch", successStreak=2) -> true  // Should need 4
```

**@sarah.tanaka** [09:35]
So it's de-escalating at half the required success streak?

**@marina.chen** [09:36]
Exactly. The thresholds are all halved from what they should be.

**@priya.sharma** [09:38]
This explains why we've been flip-flopping between modes all week. System escalates on a single failure, then de-escalates too quickly, then escalates again...

**@derek.okonkwo** [09:40]
Business impact check:
- 23 false escalations in the past 48h
- 4 unnecessary HALTED states blocking legitimate traffic
- Ops team has stopped trusting automated policy decisions

**@marina.chen** [09:42]
I'm going to open an incident. This is affecting production traffic routing.

**@sarah.tanaka** [09:44]
+1. The comparison logic in `nextPolicy` seems completely inverted. Like it escalates when it should stay and stays when it should escalate.

**@priya.sharma** [09:46]
And those de-escalation thresholds need to be doubled. HALTED should need 10 successes, not 5.

---

**Incident Link:** NMB-INC-2024-0912
**Status:** Investigating
**Assigned:** @platform-policy-team
