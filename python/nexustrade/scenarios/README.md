# NexusTrade Debugging Scenarios

This directory contains realistic debugging scenarios for the NexusTrade distributed trading platform. Each scenario describes symptoms of real bugs without revealing the solutions.

## Scenario Format

Each scenario file presents:
- **Context**: Background on who reported the issue and when
- **Symptoms**: Observable behaviors, error messages, and conditions
- **Impact**: Business and user impact
- **Initial Investigation Notes**: What the on-call team has ruled out or observed
- **Reproduction**: How to trigger the issue (if known)

## Scenarios

| File | Title | Severity | Category |
|------|-------|----------|----------|
| `01-order-exposure-breach.md` | Customer Exceeds Risk Limits on Rapid-Fire Orders | P1 | Race Condition / Risk |
| `02-market-close-orders.md` | Orders Executed After Market Close | P2 | Edge Case / Time Handling |
| `03-penny-discrepancy.md` | Mysterious Penny Discrepancies in Trade Reports | P3 | Precision / Financial |
| `04-token-refresh-storm.md` | Mobile App Token Refresh Causes Auth Failures | P2 | Concurrency / Auth |
| `05-cache-stampede.md` | Market Data Service Overwhelmed on Cache Miss | P1 | Caching / Performance |

## How to Use

1. Read the scenario carefully
2. Identify which services and components are involved
3. Use the symptoms to narrow down where to look in the codebase
4. Run relevant tests to understand expected vs actual behavior
5. Find and fix the root cause(s)

## Severity Levels

- **P1 (Critical)**: Causes data corruption, financial loss, or complete service outage
- **P2 (High)**: Significant user impact, requires prompt attention
- **P3 (Medium)**: Noticeable issue but workarounds exist
- **P4 (Low)**: Minor inconvenience, cosmetic issues
