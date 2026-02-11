# GeneForge Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, compliance audits, and operational issues you might encounter as an engineer on the GeneForge genomics platform team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Read the scenario to understand the reported issues
2. Investigate the codebase to identify root causes
3. Locate the buggy code
4. Implement fixes
5. Verify fixes don't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-qc-batch-rejections.md](./01-qc-batch-rejections.md) | PagerDuty Alert | High | QC rejecting valid samples, boundary threshold issues |
| [02-consent-compliance-audit.md](./02-consent-compliance-audit.md) | Compliance Audit | Critical | Expired consent accepted, revocation incomplete, audit trail gaps |
| [03-statistical-analysis-errors.md](./03-statistical-analysis-errors.md) | Customer Escalation | Urgent | Wrong mean/variance/F1 calculations, statistical formula errors |
| [04-pipeline-failures.md](./04-pipeline-failures.md) | Slack Discussion | P1 | Retry storms, stage transition failures, samples stuck |
| [05-resilience-circuit-breaker.md](./05-resilience-circuit-breaker.md) | P0 Incident | Critical | Circuit breaker malfunction, cascading failures, backoff issues |

## Difficulty Progression

These scenarios are ordered by investigation complexity:

- **Scenario 1-2**: Domain-specific bugs (QC thresholds, consent logic) with clear symptoms
- **Scenario 3**: Mathematical/formula bugs requiring careful code review
- **Scenario 4-5**: Complex interaction bugs across multiple functions

## Investigation Tips

1. **Run tests first**: `cargo test` to see which tests are failing
2. **Search for patterns**: Use `grep -rn "keyword" src/` to find relevant code
3. **Check boundary conditions**: Many bugs involve `>` vs `>=` or off-by-one errors
4. **Validate formulas**: Compare against textbook definitions for statistical functions
5. **Trace data flow**: For pipeline issues, follow the execution path

## Bug Categories Covered

| Category | Scenarios |
|----------|-----------|
| Data Integrity | 01, 03 |
| Security/Privacy | 02 |
| Numerical/Statistical | 01, 03 |
| Pipeline Ordering | 04 |
| Resilience | 05 |
| Observability | 02 |

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation and test instructions
- Source files in `src/` directory contain the implementation
- Test files in `tests/` directory contain assertions that exercise these bugs
