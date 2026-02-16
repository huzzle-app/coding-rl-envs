# TaskForge - Project Management SaaS

## Task Description

You are debugging a project management application built with Ruby on Rails. The application allows teams to manage projects, tasks, and collaborate on work items.

## Known Issues

Current state: most tests broken. Main concerns include API endpoints, background processing, and database operations.

The codebase contains issues across multiple categories that need to be identified and fixed. All tests must pass before the task is complete.

## Getting Started

```bash
# Start all services
docker compose up -d

# Set up the database
docker compose exec web rails db:create db:migrate db:seed

# Run all tests
docker compose exec web bundle exec rspec

# Run specific test files
docker compose exec web bundle exec rspec spec/models/
docker compose exec web bundle exec rspec spec/services/
docker compose exec web bundle exec rspec spec/requests/
```

## Architecture

TaskForge is a Rails 7 API-only application with the following components:

| Component | Purpose |
|-----------|---------|
| Rails API | REST API endpoints |
| PostgreSQL | Primary database |
| Redis | Caching, Sidekiq queues |
| Sidekiq | Background job processing |

### Key Models

- **User** - Authentication, preferences
- **Organization** - Multi-tenant container
- **Project** - Work containers with status
- **Task** - Work items with state machine
- **Comment** - Task discussions
- **Notification** - User notifications

- L1: Autoload paths configured incorrectly
- L2: Time zone not set for ActiveRecord
- L3: ActiveJob adapter not configured
- L4: Session store configured in API-only mode
- L5: User timezone not applied correctly

### Thread Safety/Concurrency
- A1: Thread-unsafe instance variable memoization
- A2: Race condition in counter increment (not atomic)
- A3: Thread-unsafe memoization in Project#stats
- A4: Race condition in Task position calculation
- A5: Job triggered on every save without debouncing
- A6: Thread-unsafe class variable in Notification
- A7: N+1 updates in bulk assign
- A8: Thread-unsafe singleton in NotificationService
- A9: No validation assignee is project member
- A10: Race condition - token valid after logout
- A11: Race condition with concurrent stats updates

### Ruby-Specific
- B1: Mutable default argument in search method
- B2: Symbol vs String key confusion in hash access
- B3: SQL injection through string interpolation
- B4: Modifying enumerable during iteration
- B5: Mutable default array argument
- B6: Using eval for parsing (security)
- B7: Mutable class instance variable shared across instances
- B8: Shallow copy of arrays/hashes in dup
- B9: Modifying frozen string

### Callback/Lifecycle
- C1: Missing error handling in callback
- C2: Callback causes infinite loop with touch
- C3: Recursive callback can cause stack overflow
- C4: Notification sent before save succeeds
- C5: Side effects inside transaction
- C6: Callbacks fire with incomplete data in duplicate
- C7: No error handling in async notification jobs
- C8: Error message exposes internal details
- C9: Sending email synchronously blocks response

### Database/Query
- D1: N+1 query in User#as_json
- D2: N+1 query in Organization#member_details
- D3: Two queries when one suffices in completion_percentage
- D4: N+1 query in Task#all_dependencies
- D5: Loading all records without pagination
- D6: Returning nil on error instead of raising
- D7: Authorization check inside loop
- D8: Memory leak - unbounded cache
- D9: Sequential queries instead of parallel
- D10: Loading all overdue tasks into memory
- D11: N+1 in team performance report
- D12: No pagination in task index
- D13: Eager loading too much data
- D14: Sorting without index

### Missing Index/Schema
- E1: Missing connection pool settings for production
- E2: Missing index on projects.status
- E3: Missing composite index on notifications
- E4: No transaction wrapping multiple updates
- E5: Queuing email without batching
- E6: Multiple queries that could be one
- E7: Cascading delete can timeout
- E8: Missing index on users.deactivated_at

### Calculation/Precision
- F1: Float precision issues in percentage calculation
- F2: Time calculation with timezone issues

### Security
- I1: No authentication on Sidekiq web UI
- I2: Authorization bypass in development
- I3: SQL injection through status parameter
- I4: User search exposes all users, not just org members
- I5: Mass assignment vulnerability
- I6: Filter bypass through params
- I7: Timing attack - different response times
- I8: Account enumeration through error messages
- I9: Token comparison without timing-safe check
- I10: Weak default JWT secret
- I11: JWT not verifying token type
- I12: Token blacklist not implemented

### Background Jobs
- J1: No retry limit on failed jobs
- J2: Silent failure without logging
- J3: No uniqueness check - duplicate jobs
- J4: Job cascade from broadcast
- J5: No timeout on external API calls

## Key Files to Examine

## Test Categories

| Category | Tests | Focus |
| Models | ~50 | Associations, validations, state machine |
| Services | ~35 | Business logic, edge cases |
| Requests | ~25 | API endpoints, authentication |
| Jobs | ~15 | Background processing |

## Success Criteria

- All 128 tests pass
- No N+1 queries (use Bullet gem)
- No SQL injection vulnerabilities
- No timing attacks
- Thread-safe code
- Proper error handling

## Hints

1. Start with L category bugs - the app may not start correctly
2. Use `rails console` to test model behavior
3. Run tests with `--format documentation` for detailed output
4. The `bullet` gem can help detect N+1 queries
5. Check symbol vs string key usage in hash access
6. Look for mutable default arguments in method definitions
7. Thread safety issues often involve instance/class variables
8. Callbacks with `touch` can cause infinite loops

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter:

| Scenario | Type | Description |
| [01-sidekiq-queue-explosion.md](./scenarios/01-sidekiq-queue-explosion.md) | PagerDuty Incident | Background job queue growing unbounded |
| [02-security-penetration-test.md](./scenarios/02-security-penetration-test.md) | Security Audit | SQL injection, timing attacks, auth bypasses |
| [03-task-ordering-race-condition.md](./scenarios/03-task-ordering-race-condition.md) | Customer Escalation | Duplicate task positions in Kanban boards |
| [04-memory-leak-production.md](./scenarios/04-memory-leak-production.md) | Datadog Alert | Web worker memory growing steadily |
| [05-data-corruption-callbacks.md](./scenarios/05-data-corruption-callbacks.md) | QA Bug Report | Silent failures and corrupted duplicates |

Each scenario describes **symptoms only** - use them to practice root cause analysis and debugging.

## Ruby-Specific Patterns to Watch

```ruby
# Mutable default argument (BUG)
def method(options = {})
 options[:key] = value # Modifies shared object
end

# Symbol vs String keys (BUG)
hash = { 'key' => 'value' }
hash[:key] # Returns nil!

# Thread-unsafe memoization (BUG)
def data
 @data ||= expensive_calculation
end

# SQL injection (BUG)
where("status = '#{params[:status]}'")

# Should be:
where(status: params[:status])
```

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Recurring Tasks, State Machine Refactor, Dashboard Optimization, Task Templates API, Event-Driven Notifications |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Time Tracking Service, Gantt Chart Generator, Workload Balancer |

These tasks test different software engineering skills while using the same codebase.
