# Slack Thread: Alerting System Not Working

## #incident-response - January 22, 2024

---

**@sarah.ops** (09:15):
> Hey team, we had a major production issue overnight but NONE of our alerts fired. The disk on storage-prod-3 hit 99% and we only found out when customers started complaining about failed writes. What's going on with the alerting service?

**@mike.sre** (09:18):
> That's weird. I was on-call and didn't get any pages. Let me check the alert service logs.

**@mike.sre** (09:25):
> Found something. The alert service is showing a lot of these errors:
> ```
> 2024-01-22T03:15:00Z [ERROR] Alert state update failed: check-then-act race
> 2024-01-22T03:15:00Z [ERROR] Alert already in FIRING state (was PENDING)
> 2024-01-22T03:15:01Z [ERROR] Skipping alert send due to state mismatch
> ```
> Looks like concurrent updates to alert state are conflicting.

**@sarah.ops** (09:28):
> But even if there's a race, shouldn't SOME alerts get through?

**@mike.sre** (09:32):
> Looking deeper... The distributed lock that guards alert state transitions keeps expiring:
> ```
> 2024-01-22T03:14:55Z [INFO] Acquired distributed lock for alert-123
> 2024-01-22T03:14:58Z [INFO] Processing alert evaluation (this takes 5s)...
> 2024-01-22T03:15:00Z [WARN] Lock lease expired during processing
> 2024-01-22T03:15:03Z [ERROR] Lost lock, aborting alert send
> ```
> The lock lease is 5 seconds but alert evaluation takes longer. We're not renewing the lease.

---

**@jennifer.dev** (09:45):
> I've seen related issues. The circuit breaker for external notification services (PagerDuty, Slack webhooks) seems stuck in a bad state:
> ```
> Circuit Breaker State Transitions:
> CLOSED -> OPEN (after 5 failures) - OK
> OPEN -> HALF_OPEN (after timeout) - OK
> HALF_OPEN -> OPEN (on failure) - OK
> HALF_OPEN -> CLOSED (on success) - NEVER HAPPENS!
> ```
> Even when the probe succeeds in HALF_OPEN, it transitions back to OPEN instead of CLOSED.

**@sarah.ops** (09:50):
> So the circuit breaker is broken? That would explain why we stopped getting Slack notifications last week even after the webhook endpoint was fixed.

**@jennifer.dev** (09:55):
> Exactly. I also see this pattern when our notification service was briefly unavailable:
> ```
> 2024-01-22T03:15:05Z [INFO] Sending alert notification (attempt 1)...
> 2024-01-22T03:15:05Z [ERROR] Notification failed, retrying immediately
> 2024-01-22T03:15:05Z [INFO] Sending alert notification (attempt 2)...
> 2024-01-22T03:15:05Z [ERROR] Notification failed, retrying immediately
> 2024-01-22T03:15:05Z [INFO] Sending alert notification (attempt 3)...
> [... 47 more attempts in the same second ...]
> ```
> We're retrying with no backoff. This caused a retry storm that probably overwhelmed the notification service.

---

**@david.backend** (10:15):
> I found another issue. Looking at why some rate calculations in alerts show "Infinity" or "NaN":
> ```
> 2024-01-22T02:00:00Z [DEBUG] Rate calculation: events=100, interval=0ms
> 2024-01-22T02:00:00Z [DEBUG] Rate result: inf (division by zero)
> 2024-01-22T02:00:01Z [WARN] Alert threshold comparison: inf > 50.0 = false (NaN propagation)
> ```
> When the time interval is zero (same timestamp for start/end), we get division by zero.

**@sarah.ops** (10:20):
> That explains the false negatives on our rate-based alerts. They evaluate to NaN and NaN comparisons always return false.

---

**@mike.sre** (10:30):
> Found yet another issue with the destructor in the AlertRule class:
> ```
> 2024-01-22T04:00:00Z [ERROR] Exception thrown in destructor during alert cleanup
> terminate called after throwing an instance of 'std::runtime_error'
> Aborted (core dumped)
> ```
> When alert rules are being cleaned up, an exception escapes the destructor and crashes the whole service.

**@jennifer.dev** (10:35):
> That's undefined behavior in C++. Destructors should be noexcept.

---

**@sarah.ops** (10:45):
> Let me summarize what we've found so far:

1. **Check-then-act race**: Alert state gets corrupted when multiple threads update simultaneously
2. **Lock lease expiry**: Distributed locks expire during processing because we don't renew them
3. **Broken circuit breaker FSM**: HALF_OPEN never transitions to CLOSED on success
4. **Retry storm**: No exponential backoff, immediate retries overwhelm downstream services
5. **Division by zero**: Rate calculations crash when interval is zero
6. **Destructor throws**: Exceptions in destructors crash the service

**@david.backend** (10:50):
> There's also a split-brain issue. When the leader changes, old leaders don't respect fencing tokens:
> ```
> 2024-01-22T03:00:00Z [INFO] Node-1 elected as leader (token=100)
> 2024-01-22T03:00:05Z [WARN] Network partition detected
> 2024-01-22T03:00:10Z [INFO] Node-2 elected as leader (token=101)
> 2024-01-22T03:00:15Z [WARN] Network healed
> 2024-01-22T03:00:16Z [ERROR] Node-1 still acting as leader (using stale token=100)
> 2024-01-22T03:00:17Z [ERROR] Duplicate alert sent from both nodes!
> ```
> The old leader doesn't check if its token is still valid.

---

**@sarah.ops** (11:00):
> This is a mess. We need to fix all of these before we can trust our alerting again. @david.backend @jennifer.dev can you create tickets for each issue?

**@jennifer.dev** (11:05):
> On it. I'll also add tests that reproduce each of these scenarios.

---

## Files to Investigate

Based on the discussion:
- `src/services/alert/alert.cpp` - Check-then-act race, rate calculation
- `src/services/alert/distributed_lock.cpp` - Lock lease renewal
- `src/services/alert/circuit_breaker.cpp` - FSM transitions
- `src/services/alert/notifier.cpp` - Retry logic
- `src/services/alert/alert_rule.cpp` - Destructor exception

---

**Thread Status**: Being triaged
**Priority**: P1
**Assigned**: @alert-team
