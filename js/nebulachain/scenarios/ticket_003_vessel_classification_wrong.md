# Support Ticket SUP-2024-11892

## Ticket Details
- **Customer**: Maersk Line Global Operations
- **Priority**: High
- **Category**: Data Classification Error
- **Created**: 2024-11-20T09:15:00Z
- **Agent**: Jennifer Walsh

---

## Customer Message

**From**: Hans Petersen <h.petersen@maersk.com>
**Subject**: Vessel Classification Errors - Urgent

Hello Support Team,

We are experiencing classification errors with our vessel manifests in NebulaChain. Several of our Panamax-class vessels are being incorrectly classified, which is causing downstream problems with berth allocation and special handling flags.

### Specific Issues:

**1. Vessel Size Classification**

Our vessel MV Emma Maersk (tonnage: 23,500 DWT) is being classified as "small" when it should be "medium". According to our contract, the boundary between small and medium should be 20,000 tonnes, but your system appears to use 25,000.

Output from your API:
```json
{
  "vesselId": "EMMA-MAE-001",
  "tonnage": 23500,
  "classification": "small",
  "berth_eligible": ["berth-7", "berth-8"]
}
```

This is causing our medium-sized vessels to be allocated to small-vessel berths that cannot handle their draft requirements.

**2. Special Handling Flag Not Triggering**

We have shipments with tonnage exceeding 45,000 DWT that should trigger special handling protocols. However, the system only flags shipments above 50,000 DWT.

Example - MV Sovereign Maersk (tonnage: 47,200 DWT):
```json
{
  "vesselId": "SOV-MAE-002",
  "tonnage": 47200,
  "hazardClass": null,
  "requiresSpecialHandling": false
}
```

Our contract specifies special handling for any vessel above 40,000 DWT. Vessels in the 40,000-50,000 range are not getting pilot escort and tug assistance as required.

**3. Urgency Score Calculation**

The urgency scoring for dispatch tickets seems off. We've noticed that severity is not being weighted heavily enough in the calculation. For two tickets with similar SLA windows, the higher-severity ticket is not being prioritized appropriately.

Example comparison:
- Ticket A: severity=5, SLA=60min, urgencyScore=100
- Ticket B: severity=7, SLA=60min, urgencyScore=116

The difference of only 16 points between severity 5 and 7 seems too small. We expected the severity coefficient to be 10 per level (70 vs 50 = 20 point difference), but it appears to be 8.

### Impact

- 4 vessels misallocated to wrong berth class this week
- 2 large vessels proceeded without required pilot escort (safety violation)
- Dispatch priorities not aligning with actual severity of shipments

Please investigate urgently.

Best regards,
Hans Petersen
Senior Operations Manager, Maersk Line

---

## Internal Notes

**Agent Note (Jennifer Walsh, 09:45):**
Checked with product team. Customer is correct about documented thresholds:
- Small/medium boundary: 20,000 tonnes (Section 3.1.2 of Product Spec)
- Special handling: 40,000 tonnes (Section 5.2.1)
- Severity coefficient: 10 (Section 4.1.3)

Tests showing failures:
- `hyper-matrix-*` tests with tonnage between 20,000-25,000 failing classification
- `models.test.js` - urgency score calculations
- `service-mesh-matrix` tests involving vessel manifests

Escalating to engineering.

**Engineering Note (David Kim, 10:30):**
Looking at `src/models/dispatch-ticket.js`. Will investigate:
1. `vesselClass()` method - boundary checks
2. `requiresSpecialHandling()` method - tonnage threshold
3. `urgencyScore()` method - severity coefficient

---

## Status
- [x] Received
- [x] Triaged
- [ ] Engineering Investigation
- [ ] Fix Deployed
- [ ] Customer Verified

## Related Tests
- `models.test.js` - DispatchTicket unit tests
- `hyper-matrix-00200` through `hyper-matrix-00400` - tonnage/classification matrix
- `service-mesh-matrix` vessel manifest scenarios
