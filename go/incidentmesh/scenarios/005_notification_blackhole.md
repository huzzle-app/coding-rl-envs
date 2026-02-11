# Scenario 005: Notification Blackhole

## Slack Discussion Thread: #platform-alerts

---

**@dispatch-supervisor** (09:15 UTC):
Anyone else seeing notification issues? Three hospitals say they never got our incoming patient alerts this morning.

**@comms-oncall** (09:17 UTC):
Looking into it. Which channels were supposed to be used?

**@dispatch-supervisor** (09:18 UTC):
SMS primary, with email and push as backups.

**@comms-oncall** (09:22 UTC):
Found something weird. The channel health check shows SMS as "healthy" even though it has a 45% error rate. That should definitely be "unhealthy" or at least "degraded".

**@backend-eng-2** (09:25 UTC):
Checked the ChannelHealth function. It only marks unhealthy if error rate > 90%. That's way too permissive. A channel with 45% errors should not be considered healthy.

**@comms-oncall** (09:28 UTC):
That explains why we didn't fail over. But wait - even when failover triggers, there's another problem.

**@backend-eng-2** (09:30 UTC):
What's that?

**@comms-oncall** (09:32 UTC):
The FailoverChain function. It's supposed to return the first non-failed channel. But it's returning the first channel in the list regardless of whether it's in the failed map. It doesn't actually check if the channel has failed.

**@dispatch-supervisor** (09:35 UTC):
So if SMS is failed, it still tries SMS instead of moving to email?

**@comms-oncall** (09:36 UTC):
Exactly. The failover logic is broken.

---

**@backend-eng-3** (09:45 UTC):
I'm seeing retry issues too. RetryDelay is returning 0 or negative numbers after the first attempt. Here's what I got:

```
Attempt 0: 1000ms (correct)
Attempt 1: 0ms (should be 2000ms)
Attempt 2: -1000ms (???)
Attempt 3: -2000ms (???)
```

The exponential backoff is going backwards somehow.

**@sre-lead** (09:48 UTC):
Negative retry delays would cause immediate retry storms. Is that what's happening?

**@backend-eng-3** (09:50 UTC):
Probably. But there's a clamp to 0, so it just retries immediately with no delay instead of backing off.

---

**@comms-oncall** (10:02 UTC):
More problems found:

1. **Circuit Breaker**: There's no "half-open" state. It only knows "open" and "closed". When a circuit opens, there's no way to probe if the channel recovered.

2. **Max Retries Inverted**: For severity 4-5 (critical), MaxRetries returns 0. For low severity, it returns 3. That's backwards - critical notifications should get MORE retries, not zero.

3. **Broadcast Channels**: When we broadcast to all channels EXCEPT one (like excluding a failed channel), the exclude parameter is ignored. All channels still receive the broadcast.

---

**@dispatch-supervisor** (10:15 UTC):
This explains a lot. What about the notification priority issue we saw last week?

**@backend-eng-2** (10:18 UTC):
Oh yeah. NotificationPriority in the notifications service returns `10 - priority`. So a priority-9 (critical) notification gets assigned priority 1 (low), and priority-1 (informational) gets assigned priority 9 (urgent).

**@dispatch-supervisor** (10:20 UTC):
That's why our critical patient alerts were being delivered after routine updates!

---

**@comms-oncall** (10:30 UTC):
Found more in the communications package:

1. **Unknown Channel Priority**: ChannelPriority returns -1 for any channel not in the hardcoded list. Negative priorities break our sorting.

2. **Message Dedup Broken**: MessageDedup is supposed to remove duplicate message keys before sending. It just returns the input unchanged. We're sending duplicate notifications.

**@backend-eng-3** (10:35 UTC):
Also in the notifications service - SendNotification swallows all errors. It returns nil even when the underlying send fails. So we think notifications succeeded when they didn't.

---

**@sre-lead** (10:45 UTC):
Let me summarize what's broken in the notification/communication path:

1. Channel health threshold too permissive (>90% required for unhealthy)
2. Retry delay subtracts instead of multiplies (exponential underflow)
3. Circuit breaker missing half-open state
4. Failover chain doesn't actually check failed channels
5. Max retries inverted (critical gets 0, low gets 3)
6. Broadcast doesn't exclude specified channel
7. Unknown channels get -1 priority
8. Message dedup doesn't deduplicate
9. Notification priority formula inverted (10 - priority)
10. SendNotification swallows errors

**@dispatch-supervisor** (10:48 UTC):
How did ANY notifications ever get delivered?

**@backend-eng-2** (10:50 UTC):
Luck, mostly. When channels work perfectly on first try, none of these bugs matter.

**@sre-lead** (10:52 UTC):
Assigning P2 incident. Communications and notification modules need comprehensive review.

---

## Impact Assessment

- **Missed Notifications**: ~340 notifications failed to deliver over 72 hours
- **Duplicate Sends**: ~890 duplicate notifications sent (user complaints)
- **Priority Inversion**: Critical alerts delayed behind routine messages
- **Retry Storms**: Excessive API calls to notification providers (potential rate limiting)

## Systems Affected

- `internal/communications` - failover, retry, circuit breaker
- `services/notifications` - priority calculation, error handling

---

*Incident Status: Open - Engineering investigation in progress*
