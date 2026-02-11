# TaskForge - Greenfield Implementation Tasks

## Overview

TaskForge supports three greenfield implementation tasks that require building new modules from scratch while following existing architectural patterns. Each task includes complete interface contracts, model definitions, and database migrations. These tasks test system design, service architecture, and integration capabilities.

## Environment

- **Language**: Ruby (Rails 7.1)
- **Infrastructure**: PostgreSQL, Redis, Sidekiq, Docker Compose
- **Difficulty**: Senior

## Tasks

### Task 1: Time Tracking Service (Greenfield)

Build a comprehensive time tracking system allowing users to log hours worked on tasks, view time entries, and generate time-based reports. The service must integrate with existing Task, Project, and User models with support for active timers (start/stop), manual time logging, and permission-based entry management.

**Key Components**:
- `TimeEntry` model with state tracking (in-progress vs completed)
- `TimeTrackingService` with methods for starting timers, stopping timers, logging time, and generating summaries
- Database migration with proper indexes for user/project/task queries
- Per-user and per-project summary calculations

**Interface Contract**: The service initializer takes a User, and provides `start_timer(task, description)`, `stop_timer()`, `log_time(task, duration_minutes, worked_on, description)`, `update_entry()`, `delete_entry()`, `entries_for_task()`, `user_summary(date_range)`, and `project_summary(date_range)`.

**Architectural Patterns**: Follows `TaskService` pattern with Pundit authorization, Paper Trail audit logging, and proper exception raising on errors.

### Task 2: Gantt Chart Data Generator (Greenfield)

Implement a service that generates structured data for Gantt chart visualization, including task timeline calculations, dependency handling, critical path identification, and scheduling conflict detection. The service must handle complex dependency graphs and provide scheduling suggestions.

**Key Components**:
- `GanttChartService` for generating complete Gantt data with project metadata, date ranges, tasks, milestones, critical path, and conflicts
- `CriticalPathCalculator` implementing the Critical Path Method algorithm for project duration and bottleneck identification
- Support for task dependencies, subtasks, and milestones
- Conflict detection for dependency violations, resource overallocation, and past-due tasks

**Interface Contract**: The service takes a Project and optional configuration hash. `generate()` returns complete Gantt data structure, `task_timeline(task)` generates per-task data, `detect_conflicts()` returns conflict array, and `scheduling_suggestions()` recommends optimal dates.

**Architectural Patterns**: Uses eager loading to avoid N+1 queries, returns plain JSON-serializable hashes, handles missing data gracefully, and follows immutable options pattern.

### Task 3: Workload Balancer (Greenfield)

Build a workload balancing service analyzing team member capacity, identifying over/under-allocated users, and suggesting task reassignments to optimize productivity. The service must account for configured hours per week, holidays, time off, and task estimated hours.

**Key Components**:
- `UserCapacity` model storing per-user capacity settings with hours per week, weekly schedule, skills, and effective date ranges
- `WorkloadBalancerService` for analyzing workload distribution, generating rebalancing suggestions with multiple strategies (minimize moves, optimize skills, level utilization)
- `CapacityCalculator` computing available hours, committed hours, remaining capacity, and utilization percentage
- Database migration with indexes for organization/user lookups and capacity date ranges

**Interface Contract**: Service takes Organization and optional date range/user/project filters. `analyze()` returns overall workload summary with over/under-allocated lists, `user_workload(user)` returns per-user breakdown, `suggest_rebalancing(strategy)` generates assignment suggestions, `apply_suggestions()` applies approved recommendations, and `simulate_assignment(task, candidates)` models what-if scenarios.

**Architectural Patterns**: Follows organization-scoped service pattern like `ReportService`, uses batch loading to handle 100+ users efficiently, wraps bulk operations in transactions, integrates with NotificationService for user notifications.

## Getting Started

```bash
# Start all services
docker compose up -d

# Set up the database
docker compose exec web rails db:create db:migrate db:seed

# Run tests for greenfield tasks
docker compose exec web bundle exec rspec \
  spec/models/time_entry_spec.rb \
  spec/services/time_tracking_service_spec.rb \
  spec/services/gantt_chart_service_spec.rb \
  spec/services/critical_path_calculator_spec.rb \
  spec/models/user_capacity_spec.rb \
  spec/services/workload_balancer_service_spec.rb \
  spec/services/capacity_calculator_spec.rb
```

## Success Criteria

Each task requires:
1. **Models and Services**: Implement all classes and methods matching provided interface contracts
2. **Testing**: Achieve 30+ test examples for simple services, 40+ for complex ones with edge cases
3. **Integration**: Add proper associations to existing models (has_many, belongs_to, etc.)
4. **Architecture**: Use frozen_string_literal pragma, YARD documentation, guard clauses, Pundit authorization, Paper Trail
5. **Performance**: Complete analysis operations within 2 seconds for realistic data volumes (100+ users, 1000+ tasks)

Implementation details and complete acceptance criteria are in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
