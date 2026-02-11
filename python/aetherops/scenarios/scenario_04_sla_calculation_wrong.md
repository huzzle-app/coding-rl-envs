# Scenario 04: SLA Compliance Metrics Showing 10x Lower Than Actual

## PagerDuty Alert: Mission Control Dashboard Anomaly

**Alert ID:** PD-2026-7742
**Severity:** High
**Service:** Policy / SLA Monitoring
**Time:** 2026-01-22 11:30 UTC

---

### Alert Details

The Mission Control dashboard is reporting impossibly low SLA compliance percentages. Operations team flagged that the displayed values appear to be exactly 10x lower than expected.

### Dashboard Reading vs Actual

| Metric | Dashboard Shows | Expected Value |
|--------|-----------------|----------------|
| Weekly SLA Compliance | 9.2% | ~92% |
| Monthly SLA Compliance | 9.7% | ~97% |
| Q4 2025 Compliance | 9.45% | ~94.5% |

### Investigation Timeline

**11:30 UTC** - NOC operator notices dashboard showing 9.2% weekly compliance
**11:35 UTC** - Manual audit of incident tickets shows ~92% actual compliance
**11:42 UTC** - Pattern identified: all readings are exactly 10x too low
**11:50 UTC** - Engineering engaged to investigate calculation logic

### Affected Code Path

The SLA percentage calculation originates in `aetherops/policy.py` in the `sla_percentage()` function. This function is called by:

- Reporting service for executive dashboards
- Analytics service for trend analysis
- Policy service for compliance gating

### Test Failures

```
tests/unit/policy_test.py::PolicyTest::test_sla_percentage_calculation
tests/services/policy_test.py::PolicyServiceTest::test_compliance_percentage
tests/stress/hyper_matrix_test.py::test_sla_boundary_*
```

### Business Impact

- Executive dashboard showing false SLA breach alerts
- Unnecessary escalations triggered to leadership
- Customer-facing SLA reports delayed pending fix
- Audit team questioning data integrity

### Related Issues

Additionally, the escalation band thresholds may have similar boundary issues. A risk score of 80 is being classified as "critical" when it should be "high". Review the `escalation_band()` function in the same file.

---

### Escalation Notes

**@policy-oncall** - This is blocking our monthly compliance report to the FAA. Need a fix ASAP.

**@data-integrity** - If SLA calculation is wrong here, verify it's not propagated to other metrics. Check the multiplier being used.
