# FleetPulse Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, compliance audits, and operational alerts you might encounter as an engineer on the FleetPulse team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user/regulator reports. Your task is to:

1. Understand the reported problem
2. Reproduce the issue using tests
3. Investigate root cause in the codebase
4. Identify the buggy code
5. Implement a fix
6. Verify the fix passes all related tests

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-startup-failure-incident.md](./01-startup-failure-incident.md) | PagerDuty Incident | Critical | Services won't start, circular dependencies, missing Kafka topics |
| [02-financial-discrepancy-alert.md](./02-financial-discrepancy-alert.md) | Finance Escalation | High | Invoice calculation errors, floating-point precision issues |
| [03-memory-cpu-saturation.md](./03-memory-cpu-saturation.md) | PagerDuty Incident | Critical | OOM kills, thread pool exhaustion, ForkJoinPool starvation |
| [04-security-audit-findings.md](./04-security-audit-findings.md) | Security Audit | Critical | SQL injection, JWT bypass, path traversal, XXE vulnerabilities |
| [05-compliance-audit-failures.md](./05-compliance-audit-failures.md) | Regulatory Audit | High | HOS calculation errors, timezone issues, integer overflow |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Setup/configuration issues - clear error messages pointing to specific problems
- **Scenario 2**: Numerical precision issues - requires understanding of float vs BigDecimal
- **Scenario 3**: Concurrency and memory issues - requires understanding of Java threading model
- **Scenario 4**: Security vulnerabilities - requires knowledge of common attack patterns
- **Scenario 5**: Business logic and data type issues - requires domain knowledge

## Bug Categories Covered

| Scenario | Bug Categories | Bug IDs |
|----------|----------------|---------|
| 01 | Setup/Config | L1-L5 |
| 02 | Financial/Numerical | F1-F10 |
| 03 | Concurrency, Memory/Collections, Spring | A1-A12, B1-B8, C1-C5 |
| 04 | Security | I1-I8 |
| 05 | Business Logic, Modern Java | G5-G6, F9-F10, K4 |

## Tips for Investigation

1. **Run tests first**: `mvn test` to see which tests are failing
2. **Target specific modules**: `mvn test -pl vehicles` to run tests for one service
3. **Check for patterns**: Many bugs share common Java anti-patterns
4. **Follow dependency chains**: Some bugs cannot be fixed until prerequisites are resolved
5. **Watch for Java pitfalls**:
   - `BigDecimal.equals()` considers scale
   - `@Transactional` on private methods doesn't work
   - `Collectors.toMap()` throws on duplicate keys
   - Virtual threads get pinned on `synchronized` blocks

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation and dependency chains
- Test files in each module's `src/test/java/` directory
- Surefire reports in `target/surefire-reports/` after running tests

## Scenario-Specific Commands

```bash
# Scenario 1: Check if services can start
mvn spring-boot:run -pl gateway  # Will fail with circular dependency

# Scenario 2: Run billing tests
mvn test -pl billing -Dtest=InvoiceServiceTest

# Scenario 3: Run with race detection (limited in Java, but check thread dumps)
mvn test -pl dispatch,tracking,notifications

# Scenario 4: Run security tests
mvn test -pl gateway,auth -Dtest="*Security*"

# Scenario 5: Run compliance tests
mvn test -pl compliance -Dtest=HoursOfServiceTest
```
