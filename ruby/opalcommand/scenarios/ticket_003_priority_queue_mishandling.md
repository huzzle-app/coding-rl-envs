# Support Ticket: CLAIMS-2024-44891

**Priority:** High
**Category:** Claims Processing - Queue Management
**Submitted By:** Jennifer Martinez (Claims Supervisor, Southeast Region)
**Date Opened:** 2024-11-19 10:15 EST
**Status:** Escalated to Engineering

---

## Issue Description

Our claims intake team has noticed that high-urgency catastrophe claims are not being processed in the correct order. Emergency claims from the recent hurricane should be handled before standard claims, but they seem to be processed last instead of first.

Additionally, we are seeing strange behavior with the queue load warnings. The system should warn us when we hit 65% capacity, but warnings only appear at 60% - this causes us to shed claims too early and delays policyholder notifications.

## Steps to Reproduce

1. Submit 100 claims with varying urgency levels (1-10 scale)
2. Observe the order claims appear in the processing queue
3. Claims with urgency=10 appear at the END of the queue, not the beginning

## Expected Behavior

- Claims sorted by urgency descending (urgency 10 first, urgency 1 last)
- Queue warning at 65% capacity
- Emergency shedding at 85% capacity

## Actual Behavior

- Claims sorted by urgency ASCENDING (urgency 1 first, urgency 10 last)
- Queue warning at 60% capacity (too early)
- Emergency shedding at 80% capacity (too early)

## Business Impact

Our team processed 47 low-priority windshield claims before getting to 12 emergency water damage claims from flooded homes. Three policyholders called to complain that their adjuster had not been dispatched within the 24-hour SLA.

We're also hitting our queue shed limit too early. Last Tuesday we rejected 230 claims because the system thought we were at emergency capacity, but we still had 15% headroom.

## Screenshots/Logs

```
[2024-11-19 09:47:12] Queue status: depth=680, capacity=800
[2024-11-19 09:47:12] WARNING: Queue approaching capacity (ratio=0.85)
[2024-11-19 09:47:12] Action: Shedding low-priority claims

Expected: Warning should not trigger until ratio >= 0.85 for emergency
Observed: Warning triggered at ratio = 0.80
```

Queue processing order log:
```
Processing order (first 10):
  1. CLM-991001 urgency=1 (glass breakage)
  2. CLM-991002 urgency=2 (minor fender)
  3. CLM-991003 urgency=2 (cosmetic damage)
  4. CLM-991004 urgency=3 (garage door)
  5. CLM-991005 urgency=4 (fence damage)
  ...
  95. CLM-991095 urgency=9 (roof collapse)
  96. CLM-991096 urgency=9 (structural)
  97. CLM-991097 urgency=10 (total loss - fire)
  98. CLM-991098 urgency=10 (flooding - evacuation)
  99. CLM-991099 urgency=10 (flooding - elderly resident)
  100. CLM-991100 urgency=10 (flooding - medical equipment)
```

## Environment

- OpalCommand Version: 2.4.1
- Region: Southeast Claims Center
- Queue Module: lib/opalcommand/core/queue.rb
- Intake Service: services/intake/service.rb

## Related Test Failures

IT sent me these test results when I asked them to check:

```
QueueTest#test_priority_sort_descending - FAILED
IntakeServiceTest#test_priority_sort_high_urgency_first - FAILED
ExtendedTest#test_queue_warning_threshold - FAILED
ExtendedTest#test_queue_emergency_threshold - FAILED
ExtendedTest#test_shed_boundary_inclusive - FAILED
```

## Workaround

Currently our team is manually reordering the queue every morning, which takes about 45 minutes. This is not sustainable during catastrophe season.

## Additional Notes

I also noticed that when I partition claims by urgency threshold (say, urgency >= 5 should go to senior adjusters), claims with urgency EXACTLY equal to 5 go to the regular queue instead of senior. This seems like a boundary issue.

Please prioritize - we have another storm system approaching the Gulf Coast this weekend.

---

**Update from IT (2024-11-19 14:30):**

Confirmed the test failures. The queue module appears to have several threshold and comparison issues. Escalating to Claims Platform Engineering for code review.

---

*Ticket escalated per SLA policy. Engineering team has 24 hours to provide initial assessment.*
