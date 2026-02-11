# Scenario 01: Hub Selection Routing to Blocked Nodes

## Incident Type
PagerDuty Alert / P1 Production Incident

---

## Alert Details

```
[PAGERDUTY] P1 - Cold Chain Routing Violation
Triggered: 2024-03-15 03:42:17 UTC
Service: polaris-routing-svc
Team: Platform Logistics

ALERT: Shipments routed to blocked hub during maintenance window
Affected: 847 shipments in last 2 hours
```

---

## Slack Thread

**#incident-response** at 03:45 UTC

**@oncall-logistics**: Getting paged about routing violations. Seeing shipments going to HUB-ATL-02 which should be blocked for scheduled maintenance.

**@platform-lead**: That hub was added to the blocked list at 02:00 UTC. The maintenance window runs until 08:00.

**@oncall-logistics**: Looking at the logs... the `select_hub` function is definitely being called with the blocked list populated correctly. But it's still returning HUB-ATL-02 as the selected destination.

**@platform-lead**: Is it ignoring the blocked list entirely?

**@oncall-logistics**: Looks like it. The candidate list includes the blocked hub and it's selecting based on lowest latency without filtering first. HUB-ATL-02 has 42ms latency vs 63ms for HUB-ATL-03.

**@sre-team**: We're seeing cold-chain temperature excursions on 12 shipments. The blocked hub's refrigeration is offline for maintenance. This is now a product quality incident.

---

## Business Impact

- **847 shipments** misrouted to a blocked hub during 2-hour window
- **12 shipments** with temperature excursions, requiring quality inspection
- **$156K** estimated product at risk (pharmaceutical cold-chain)
- **SLA breach** for 4 enterprise customers with guaranteed routing controls
- Maintenance windows are now unreliable, blocking future planned work

---

## Observed Symptoms

1. Shipments being routed to hubs explicitly in the blocked list
2. System appears to select purely by lowest latency, ignoring availability constraints
3. Failover logic in downstream services not being triggered (they trust routing decisions)
4. Load routing also appears affected - seeing traffic go to high-load segments instead of low-load

---

## Affected Test Files

Tests in the following files are failing and may provide clues:

- `tests/routing_tests.rs` - Hub selection and segment routing tests
- `tests/workflow_integration_tests.rs` - End-to-end routing workflow tests

---

## Relevant Modules

- `src/routing.rs` - Hub selection and segment routing logic

---

## Investigation Questions

1. Why is the blocked list being ignored in hub selection?
2. Is there a similar issue with segment routing load balancing?
3. Are there boundary conditions where filtering behaves unexpectedly?

---

## Resolution Criteria

- Blocked hubs must never be selected regardless of latency
- Segment routing should prefer lower-load paths
- All routing tests must pass
