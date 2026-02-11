# Scenario 02: Compliance Review Backlog and Risk Underreporting

## Incident Type
Operations Ticket / Compliance Audit Finding

---

## Ticket Details

```
JIRA: POLARIS-4821
Title: Board-level reviews not being triggered for high-risk shipments
Priority: P2
Reporter: compliance-team
Assignee: platform-logistics

Created: 2024-03-12
Status: In Investigation
```

---

## Ticket Description

**Summary:**
During our quarterly compliance audit, we discovered that 23% fewer shipments were escalated to board-level review compared to the previous quarter, despite incident volumes increasing 18%. The risk scoring system appears to be underreporting actual risk levels.

**Audit Findings:**

1. Shipments with risk scores in the 75-85 range are being classified as "ops-review" instead of "board-review"
2. The risk score calculation appears to underweight both load factors and incident severity
3. Multiple high-severity incidents (severity 4-5) resulted in lower-than-expected composite scores

**Evidence:**
- Shipment S-2024-38291: 8 incidents with severity 4, temperature excursion, calculated score: 42.3 (should have triggered board review)
- Shipment S-2024-39104: Risk score of exactly 66.0 with degraded comms, no hold triggered
- Shipment S-2024-40012: 12 priority-5 items, scored as 14.2 (expected ~70+)

---

## Email Thread

**From:** Chief Compliance Officer
**To:** VP Engineering, Platform Lead
**Subject:** RE: Q1 Compliance Audit - Risk Scoring Anomalies

We've completed our analysis and the findings are concerning. The risk scoring subsystem is systematically underreporting risk by approximately 10x in some cases.

Specific issues:
- Load component of risk score is an order of magnitude too low
- Incident severity multiplier appears to be 0.42 instead of the documented 4.2
- Boundary conditions at score thresholds (66.0, 75.0) are not triggering correctly
- Compliance tier assignments are using shifted thresholds

This means shipments that should have been flagged for board review are being auto-approved or sent only to ops review. We need an immediate fix.

---

## Business Impact

- **Regulatory exposure**: 147 shipments approved without proper oversight
- **Audit finding**: Material weakness in risk controls
- **Remediation cost**: Manual review of all Q1 shipments ($340K labor)
- **Reputational risk**: If regulators discover the underreporting

---

## Observed Symptoms

1. Risk scores are approximately 10x lower than expected for shipment load
2. Incident severity contribution is ~10x lower than documented formula
3. Score of exactly 66.0 does not trigger hold (boundary issue)
4. Shipments scoring 75-84 going to "ops-review" instead of "board-review"
5. Score of exactly 50.0 with degraded comms not triggering hold

---

## Affected Test Files

- `tests/policy_tests.rs` - Risk scoring, hold rules, and compliance tier tests
- `tests/chaos_replay_tests.rs` - Integration tests involving policy holds

---

## Relevant Modules

- `src/policy.rs` - Risk scoring, hold determination, compliance tier assignment

---

## Investigation Questions

1. What is the actual divisor being used in the load component calculation?
2. What multiplier is being applied to incident severity?
3. Are the boundary checks using `>` vs `>=` correctly?
4. What thresholds are being used for compliance tier assignment?

---

## Resolution Criteria

- Risk scores must match documented formulas within 0.1% tolerance
- Score of exactly 66.0 must trigger hold
- Score of 75.0+ must route to board-review
- All policy tests must pass
