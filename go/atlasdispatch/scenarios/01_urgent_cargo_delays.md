# Incident Report: Priority Cargo Processing Failures

**Incident ID:** INC-2024-0847
**Severity:** P1 - Critical
**Status:** Open
**Reported By:** Maria Chen, Port Operations Manager
**Date:** 2024-11-15 06:42 UTC

---

## Summary

High-urgency cargo shipments are consistently being processed after lower-priority orders, causing SLA violations and contractual penalties with premium shipping partners.

## Timeline

- **05:30 UTC**: Night shift reports that PRIORITY-1 medical supply shipment (ORD-88421) still waiting in queue despite being submitted 2 hours ago
- **05:45 UTC**: ORD-88421 finally dispatched, but only after 6 lower-urgency bulk cargo orders were processed
- **06:00 UTC**: Pattern confirmed across multiple berths - urgent orders are consistently processed last within their batch
- **06:15 UTC**: Premium partner MedLogistics Global escalates - third SLA violation this week
- **06:42 UTC**: Incident opened

## Observed Symptoms

1. **Priority Inversion**: Orders with urgency=10 (highest) are being dispatched after urgency=1 (lowest) orders
2. **Batch Ordering**: When capacity allows for 5 orders from a batch of 10, the 5 selected are consistently the LEAST urgent
3. **Queue Behavior**: The priority queue appears to be returning items in wrong order - peeking shows lowest priority item at head
4. **Comparator Confusion**: Manual log analysis shows the urgency comparator returning positive values when order A is more urgent than B, but sorted results show A coming after B

## Impact

- 47 SLA violations in past 72 hours
- $2.3M potential penalty exposure
- 3 premium partners considering contract termination
- Perishable goods (vaccines, produce) spoiling during extended wait times

## Affected Systems

- `/internal/allocator/` - Dispatch planning and cost estimation
- `/internal/queue/` - Priority queue management

## Additional Observations from Operations

### From Berth Coordinator (via radio log):

> "The turnaround time estimates are also off. We planned for 30-minute turnarounds but vessels are only getting 15 minutes of setup time. Crane operators are rushing and nearly had two accidents this week."

### From Capacity Monitoring Dashboard:

The dashboard shows berths at "100% capacity" still accepting new vessels. When berth B7 showed exactly 50/50 load, the system allowed a 51st vessel to dock, causing physical congestion.

### From Cost Accounting:

Cost estimates for Route APAC-7 came back negative (-$4,200). The operations team assumed this was a display error but the invoice was actually generated as a credit. Finance is investigating whether this is related to a data entry issue with rates or a calculation bug.

## Steps to Reproduce

1. Submit 10 orders with varying urgency levels (1-10)
2. Set dispatch capacity to 5
3. Call `PlanDispatch` and observe which 5 orders are selected
4. Expected: Orders with urgency 10, 9, 8, 7, 6 selected
5. Actual: Orders with urgency 1, 2, 3, 4, 5 selected

## Requested Actions

- Engineering team to investigate priority sorting logic
- Review queue dequeue behavior
- Verify comparator implementations are returning correct values
- Check turnaround time calculation parameters
- Audit capacity checking logic for off-by-one errors

---

**Last Updated:** 2024-11-15 07:30 UTC
**Assigned To:** Platform Team
**Next Review:** 2024-11-15 10:00 UTC
