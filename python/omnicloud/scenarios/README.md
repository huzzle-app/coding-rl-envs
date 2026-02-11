# OmniCloud Debugging Scenarios

This directory contains realistic debugging scenarios for the OmniCloud multi-cloud infrastructure orchestration platform. Each scenario describes symptoms observed in production, not the underlying causes.

## Scenarios Overview

| # | Scenario | Primary Services | Difficulty |
|---|----------|------------------|------------|
| 1 | Billing Discrepancies | billing, tenants | Medium |
| 2 | Deployment Failures | deploy, compute, gateway | High |
| 3 | Network Connectivity Issues | network, loadbalancer, dns | High |
| 4 | Resource Scheduling Problems | compute, tenants | Medium |
| 5 | Distributed Consensus Failure | shared/distributed, shared/state | High |

## How to Use These Scenarios

1. Read the scenario description to understand the reported symptoms
2. Use the test suite to reproduce the failures: `python -m pytest tests/ -v -k <relevant_test>`
3. Investigate the codebase to identify root causes
4. Fix the bugs and verify with tests

## Scenario Format

Each scenario includes:
- **Source**: How the issue was reported (incident, ticket, alert, etc.)
- **Severity**: Impact level (P1-P4)
- **Symptoms**: What users/operators observed
- **Timeline**: When the issue was first noticed
- **Affected Components**: Services and modules involved
- **Diagnostic Data**: Logs, metrics, or other evidence

## Tips for Investigation

- Start with the test files to understand expected behavior
- Check `# BUG` comments in source files for hints
- Multiple bugs often interact to cause symptoms
- Consider timing, concurrency, and edge cases
