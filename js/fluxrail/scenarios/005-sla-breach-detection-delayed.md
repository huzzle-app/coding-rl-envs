# JIRA Ticket: FLUX-4892

## SLA Breach Detection Triggering Too Late

**Type:** Bug
**Priority:** High
**Component:** sla, economics
**Affects Version:** 4.7.2
**Reporter:** Operations Analytics Team
**Assignee:** Unassigned

---

### Description

The SLA monitoring subsystem is failing to detect impending breaches in time for corrective action. By the time breach alerts fire, we've already missed the customer SLA window. Additionally, the economic modeling functions are producing incorrect projections, leading to budget miscalculations.

### SLA Detection Issues

**Issue 1: Buffer Direction Inverted**

The `breachRisk` function should flag shipments that are within `bufferSec` of the SLA deadline. Instead, it's adding the buffer to the deadline, effectively detecting risk *after* the breach has occurred.

Example:
```
etaSec: 980, slaSec: 1000, bufferSec: 30
Expected: breachRisk = true (we're within 30s buffer of breach)
Actual: breachRisk = false (not detected until eta > 1030)
```

**Issue 2: Severity Boundaries Miscalibrated**

The `breachSeverity` function has incorrect thresholds:
- Exactly meeting SLA (delta=0) returns 'minor' instead of 'none'
- Minor->Major escalation happens at 300s instead of 180s
- Major->Critical escalation happens at 900s instead of 600s

This means we're under-reporting severity to customers and missing escalation windows.

### Economic Calculation Issues

**Issue 3: Projected Cost Formula Wrong**

The `projectedCost` function is adding the surge multiplier instead of multiplying:

```javascript
// With units=100, baseRate=50, surgeMultiplier=1.5
// Expected: 100 * 50 * 1.5 = 7500
// Actual: 100 * 50 + 1.5 = 5001.5
```

**Issue 4: Margin Ratio Denominator Incorrect**

The margin ratio is dividing by cost instead of revenue:

```javascript
// revenue=1000, cost=800
// Expected margin: (1000-800)/1000 = 0.20 (20%)
// Actual: (1000-800)/800 = 0.25 (wrong ratio)
```

**Issue 5: Budget Pressure Underestimated**

The `budgetPressure` function is subtracting backlog instead of adding it:

```javascript
// allocated=80, capacity=100, backlog=30
// Expected pressure: (80+30)/100 = 1.1 (over capacity)
// Actual: (80-30)/100 = 0.5 (looks fine, but we're drowning)
```

Also returns 0 instead of 1.0 when capacity is zero (division by zero edge case).

### Steps to Reproduce

Run the affected test suites:

```bash
npm test -- tests/unit/sla.test.js
npm test -- tests/unit/economics.test.js
npm test -- tests/integration/economic-risk.test.js
```

### Affected Files

- `src/core/sla.js` - `breachRisk()`, `breachSeverity()`
- `src/core/economics.js` - `projectedCost()`, `marginRatio()`, `budgetPressure()`

### Business Impact

1. **SLA Penalties:** $1.2M in SLA credits issued last month due to late detection
2. **Budget Overruns:** 23% variance between projected and actual costs
3. **Capacity Planning:** Pressure metrics showing "green" when we're actually overloaded
4. **Customer Trust:** Enterprise customers receiving incorrect severity classifications

### Acceptance Criteria

- [ ] `breachRisk` detects risk when ETA is within buffer of SLA
- [ ] `breachSeverity` returns 'none' for zero delta
- [ ] `breachSeverity` escalates to major at 180s, critical at 600s
- [ ] `projectedCost` multiplies by surge factor
- [ ] `marginRatio` divides by revenue, not cost
- [ ] `budgetPressure` adds backlog, not subtracts
- [ ] All related unit and integration tests pass

---

**Labels:** sla, economics, regression, customer-impact
**Sprint:** Current
**Story Points:** 5
