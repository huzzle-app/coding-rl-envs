# LatticeForge Debugging Scenarios

This directory contains realistic debugging scenarios that describe symptoms and context without revealing the exact fixes. Use these to understand the system behavior and guide your investigation.

## Scenario Types

| Type | Format | Example |
|------|--------|---------|
| Incident Report | Formal ops ticket | `incident_*.md` |
| Support Ticket | User-reported issue | `ticket_*.md` |
| Production Alert | Monitoring system | `alert_*.md` |
| Slack Thread | Team discussion | `slack_*.md` |

## Available Scenarios

### 1. High Latency to Ground Stations
**File:** `incident_001_high_latency.md`
**Symptoms:** Communications routed through high-latency paths despite healthy low-latency stations available.
**Impact:** Mission-critical command delays, near-miss on maneuvers.

### 2. Missed Critical Alerts
**File:** `incident_002_missed_alerts.md`
**Symptoms:** Severity-5 incidents only trigger email, pager/SMS channels don't fire.
**Impact:** Delayed incident response, SLA breaches.

### 3. Reports in Wrong Order
**File:** `ticket_003_reports_wrong_order.md`
**Symptoms:** Daily reports list low-severity incidents before critical ones.
**Impact:** Operators miss important issues in briefings.

### 4. Gateway Degraded Node Selection
**File:** `alert_004_gateway_degraded.md`
**Symptoms:** Gateway routes to degraded nodes despite healthy alternatives.
**Impact:** Elevated latency, degraded user experience.

### 5. Failover Region Selection
**File:** `slack_005_failover_issue.md`
**Symptoms:** Failover selects degraded regions instead of healthy ones.
**Impact:** Extended outages during region failures.

## How to Use

1. Read the scenario to understand the symptoms
2. Identify which tests are failing (mentioned in each scenario)
3. Investigate the relevant code modules
4. Look for `# BUG:` comments that match the symptoms
5. Fix the underlying issue and verify tests pass

## Notes

- Scenarios may reference multiple related bugs
- Not all bugs have corresponding scenarios (some are discovered through test failures only)
- Scenarios describe symptoms, not solutions - investigation is required
