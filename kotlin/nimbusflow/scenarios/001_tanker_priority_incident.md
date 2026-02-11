# Incident Report: Critical Tanker Dispatch Delays

**Incident ID:** NMB-INC-2024-0847
**Severity:** P1 - Critical
**Status:** Open
**Duration:** 4h 23m (ongoing)
**Affected Service:** NimbusFlow Dispatch Allocator

---

## Summary

Multiple critical-priority tanker dispatches are being delayed while lower-priority cargo vessels receive berth allocations first. Port operations are experiencing significant revenue loss and SLA breaches.

## Timeline

- **06:12 UTC** - Port dispatcher notices MV Valdez Star (CRITICAL, urgency=5) still in queue after 45 minutes
- **06:18 UTC** - Dispatcher manually checks allocation queue, sees routine cargo ships (urgency=2) being allocated first
- **06:34 UTC** - Harbor Master escalates to operations; 3 more critical vessels now waiting
- **06:52 UTC** - Engineering engaged; initial triage shows dispatch planning is running but priorities appear inverted
- **07:45 UTC** - Pattern confirmed: low-urgency orders consistently allocated before high-urgency ones

## Symptoms

1. **Queue ordering is backwards** - When 10 vessels queue simultaneously, urgency=1 vessels are processed before urgency=5
2. **SLA breaches accumulating** - 12 critical dispatches missed their 15-minute SLA window in the past 4 hours
3. **No errors in logs** - The allocator completes successfully; it just chooses the wrong vessels

## Sample Data

Dispatch queue snapshot at 07:30 UTC:

| Order ID | Vessel | Urgency | SLA (min) | Allocation Order |
|----------|--------|---------|-----------|------------------|
| ORD-4401 | MV Valdez Star | 5 (CRITICAL) | 15 | 8th |
| ORD-4402 | MV Ocean Pride | 2 (LOW) | 120 | 1st |
| ORD-4403 | MV Arctic Phoenix | 4 (HIGH) | 30 | 6th |
| ORD-4404 | MV Coastal Runner | 1 (INFO) | 240 | 2nd |
| ORD-4405 | MV Titan Horizon | 5 (CRITICAL) | 15 | 9th |

## Business Impact

- 12 SLA breaches (potential penalties: $45,000 per breach)
- 3 tankers rerouted to competitor port
- Harbor operations trust in automated dispatch system severely degraded
- Manual override queue growing

## Investigation Notes

- `planDispatch()` is being called correctly with accurate urgency values
- Capacity limits are not being exceeded
- The returned list consistently has low-urgency items first
- Sorting logic is suspect but no exceptions thrown

## Questions for Engineering

1. How is the dispatch priority queue sorted before allocation?
2. Is there a comparator or sort operation that might have inverted semantics?
3. When was the last change to allocation logic deployed?

---

**Next Steps:** Engineering to investigate dispatch planning sort order

**Assignee:** @platform-dispatch-team
**Labels:** `dispatch`, `priority`, `sla-breach`, `p1`
