# Scenario 001: Low-Priority Vessels Getting Berth Allocation Over Emergency Traffic

## Type: Incident Report

## Severity: P1 - Critical

## Reported By: Port Operations Manager (Rotterdam Hub)

## Summary

Emergency vessels are being delayed by 4-6 hours while routine cargo traffic gets priority berth allocation. This is causing dangerous anchorage congestion and regulatory violations.

---

## Timeline

**08:15 UTC** - Tanker "Pacific Guardian" declares mechanical emergency, requests priority berthing with urgency score 95.

**08:17 UTC** - SignalDock `planWindow()` allocates berths for the next cycle. Pacific Guardian is NOT in the allocated set.

**08:20 UTC** - Berth B-7 is allocated to container vessel "Nordic Star" (urgency score 12, routine cargo).

**08:45 UTC** - Port control notices Pacific Guardian still in anchorage queue. Manual override issued.

**09:30 UTC** - Second emergency vessel "Horizon Rescue" (urgency 88) also skipped in favor of low-priority traffic.

**10:00 UTC** - Incident escalated to engineering.

---

## Observed Behavior

When we query the scheduling system, vessels are returned in what appears to be reverse priority order. The vessel list after `planWindow()` consistently shows:

```
Allocated vessels (berth capacity = 3):
1. MV Langley (urgency: 5)
2. Nordic Star (urgency: 12)
3. Coastal Runner (urgency: 18)

Skipped vessels:
- Pacific Guardian (urgency: 95) - EMERGENCY
- Horizon Rescue (urgency: 88) - EMERGENCY
- Express Carrier (urgency: 72)
```

The vessels with the LOWEST urgency scores are being selected first.

---

## Impact

- 2 emergency vessels delayed beyond safe anchorage time
- Potential regulatory fines from maritime authority
- Insurance liability exposure
- Port congestion cascading to 12+ vessels

---

## Environment

- SignalDock version: 2.4.1
- Node.js: 20.x
- Module: `src/core/scheduling.js`

---

## Reproduction

Call `planWindow()` with a mixed-urgency vessel list. Observe that results are ordered by ascending urgency instead of descending.

---

## Questions for Engineering

1. How is the urgency-based sorting implemented in `planWindow()`?
2. Was there a recent change to the sort comparator?
3. Why would low-urgency vessels consistently win allocation?
