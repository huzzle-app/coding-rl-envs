# TaskForge Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, security audits, and support escalations you might encounter as an engineer on the TaskForge team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Analyze the symptoms and formulate hypotheses
2. Investigate the codebase to find root causes
3. Identify the buggy code paths
4. Implement fixes that address all related issues
5. Verify fixes don't introduce regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-sidekiq-queue-explosion.md](./01-sidekiq-queue-explosion.md) | PagerDuty Incident | Critical | Background job queue growing unbounded, Redis OOM |
| [02-security-penetration-test.md](./02-security-penetration-test.md) | Security Audit | Critical | SQL injection, timing attacks, authorization bypasses |
| [03-task-ordering-race-condition.md](./03-task-ordering-race-condition.md) | Customer Escalation | High | Duplicate task positions, Kanban board rendering issues |
| [04-memory-leak-production.md](./04-memory-leak-production.md) | Datadog Alert | High | Web worker memory growing steadily, eventual OOM |
| [05-data-corruption-callbacks.md](./05-data-corruption-callbacks.md) | QA Bug Report | High | Silent failures, corrupted duplicates, callback issues |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Background job issues with clear job class involvement
- **Scenario 2**: Security vulnerabilities identified by external auditor
- **Scenario 3**: Concurrency issues requiring thread safety analysis
- **Scenario 4**: Memory leaks requiring Ruby-specific knowledge
- **Scenario 5**: Cross-cutting callback and transaction issues

## Bug Categories Covered

| Scenario | Categories |
|----------|------------|
| 01 | A5 (job debouncing), C2 (infinite callback loops), J1-J2 (job retry/logging) |
| 02 | I3-I4 (SQL injection, user exposure), I7-I9 (timing attacks), I10-I11 (JWT issues) |
| 03 | A3-A4 (thread-unsafe memoization, race conditions) |
| 04 | B1, B5, B7 (mutable defaults, class variables), A8 (singleton), D8 (unbounded cache) |
| 05 | B8 (shallow copy), B9 (frozen string), C3-C5 (callbacks), D6 (silent errors), E4 (transactions) |

## Tips for Investigation

1. **Run tests with verbose output**: `bundle exec rspec --format documentation`
2. **Check for N+1 queries**: Use the Bullet gem in test mode
3. **Search for patterns**: `grep -rn "||=" app/` for memoization, `grep -rn "@@" app/` for class variables
4. **Review recent changes**: `git log --oneline -20`
5. **Test thread safety**: Use concurrent-ruby or threading tests
6. **Memory profiling**: Use memory_profiler gem for leak detection

## Ruby-Specific Patterns to Watch

```ruby
# Mutable default argument - shared across calls
def method(options = {})
  options[:key] = value  # Mutates shared object!
end

# Thread-unsafe memoization
def data
  @data ||= expensive_call  # Race condition!
end

# Shallow copy
new_obj = old_obj.dup
new_obj.tags = old_obj.tags  # Same array reference!

# Class variable mutation
@@config[:new_key] = value  # Affects all instances!
```

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `spec/` directory contain assertions that exercise these bugs
