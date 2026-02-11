# TaskForge - Alternative Tasks

## Overview

TaskForge supports five alternative task types that test different software engineering skills: feature development, refactoring, performance optimization, API design, and architectural migration. Each task uses the same codebase but focuses on different aspects of professional development.

## Environment

- **Language**: Ruby (Rails 7.1)
- **Infrastructure**: PostgreSQL, Redis, Sidekiq, Docker Compose
- **Difficulty**: Senior

## Tasks

### Task 1: Feature Development - Recurring Tasks (Feature)

Implement a recurring task system that automatically generates new task instances on a schedule. Users can configure daily, weekly, monthly, or custom recurrence patterns. When a recurring task is completed, the system automatically creates the next instance with the appropriate due date. The feature must support week-day patterns (e.g., "every Monday and Wednesday"), end dates, maximum occurrence counts, and maintain statistics without double-counting.

**Key Challenges**: Integrating with existing task workflow, handling bulk operations, dependency chains, and notification integration.

### Task 2: Refactoring - Extract Task State Machine to Service Object (Refactor)

Extract the task state machine logic from the bloated Task model into a dedicated service object. The current implementation uses AASM callbacks tightly coupled to ActiveRecord, making it difficult to test state transitions in isolation and causing unexpected side effects during bulk operations. The refactoring should centralize all state guards, notifications, and activity logging while preserving all existing functionality.

**Key Challenges**: Preserving functionality during refactoring, eliminating N+1 notifications, maintaining backward compatibility, decoupling persistence from business logic.

### Task 3: Performance Optimization - Project Dashboard Query Optimization (Optimize)

Optimize the project dashboard which experiences severe performance degradation for projects with 500+ tasks. Current page load times exceed 10 seconds due to numerous database round trips and inefficient aggregations. The solution must reduce database queries to under 10 (from 50+), implement efficient GROUP BY queries for task counts, use SQL aggregations for team metrics, and add intelligent caching with automatic invalidation.

**Key Challenges**: Query optimization, N+1 detection, caching strategies, race condition handling, balancing freshness with performance.

### Task 4: API Extension - Task Templates API (API)

Build a RESTful API for managing task templates that can be instantiated into projects. Enterprise customers need pre-configured task definitions with standard titles, descriptions, checklists, and default assignments. The API must support full CRUD operations, template instantiation with variable substitution (e.g., "Onboard {{employee_name}}"), organization/global scoping, and usage tracking for analytics.

**Key Challenges**: API design, authorization scoping, variable substitution, usage tracking, error handling for invalid templates.

### Task 5: Migration - Move from Synchronous to Event-Driven Notifications (Migration)

Migrate from synchronous and directly-enqueued notifications to an event-driven architecture where domain events are published and handlers subscribe to relevant events. This decouples business logic from notification delivery, enables notification preferences, channel routing, and digest emails. The migration must run old and new systems in parallel during transition and handle backward compatibility.

**Key Challenges**: Event sourcing patterns, handler orchestration, backward compatibility, failure recovery, monitoring, batch processing for digests.

## Getting Started

```bash
# Start all services
docker compose up -d

# Set up the database
docker compose exec web rails db:create db:migrate db:seed

# Run tests for alternative tasks
docker compose exec web bundle exec rspec spec/models/recurring_task_spec.rb
docker compose exec web bundle exec rspec spec/services/task_state_machine_spec.rb
docker compose exec web bundle exec rspec spec/services/project_dashboard_spec.rb
docker compose exec web bundle exec rspec spec/requests/api/v1/templates_spec.rb
docker compose exec web bundle exec rspec spec/events/
```

## Success Criteria

Implementation meets the detailed acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Each task includes specific requirements for functionality, testing, integration points, and architectural patterns to follow.
