# TaskForge - Project Management SaaS

Fix bugs in a Rails 7.1 project management platform. TaskForge allows teams to manage projects, tasks, and collaborate on work items.

## Stack

- **Rails 7.1** - API-only application
- **PostgreSQL** - Primary database
- **Redis** - Caching, Sidekiq queues
- **Sidekiq** - Background job processing

## Known Issues

Tests are failing across several modules. Previous maintainer mentioned problems with async operations and data handling.

**Total: issues across tests**

## Getting Started

```bash
# Start all services
docker compose up -d

# Set up the database
docker compose exec web rails db:create db:migrate db:seed

# Run tests
docker compose exec web bundle exec rspec

# Run specific test categories
docker compose exec web bundle exec rspec spec/models/
docker compose exec web bundle exec rspec spec/services/
docker compose exec web bundle exec rspec spec/requests/
docker compose exec web bundle exec rspec spec/jobs/
```

## Key Notes

1. **Start with Setup bugs (L1-L5)** - The application may not start correctly until these are fixed
2. **Ruby-specific patterns** - Watch for mutable default arguments, symbol vs string key confusion, thread-unsafe memoization
3. **Thread safety** - Many bugs involve instance/class variables accessed from multiple threads
4. **Callbacks** - Look for infinite loops with `touch`, premature side effects, missing error handling
5. **N+1 queries** - Use the `bullet` gem to detect query inefficiencies
6. **Security** - SQL injection, timing attacks, weak JWT secrets, missing authentication

## Common Ruby Bug Patterns

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
# Should be: where(status: params[:status])
```

## Success Criteria

- All tests pass
- No N+1 queries
- No SQL injection vulnerabilities
- No timing attacks
- Thread-safe code
- Proper error handling in callbacks and jobs

## Difficulty

**Senior (2-4 hours)** - Requires understanding of Rails internals, Ruby concurrency patterns, and common security vulnerabilities.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Recurring Tasks, State Machine Refactor, Dashboard Optimization, Task Templates API, Event-Driven Notifications |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Time Tracking Service, Gantt Chart Generator, Workload Balancer |

These tasks test different software engineering skills while using the same codebase.
