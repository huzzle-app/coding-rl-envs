# TaskForge - Alternative Tasks

This document contains alternative development tasks for the TaskForge project management platform. Each task represents a realistic feature request, refactoring effort, or improvement that a development team might undertake.

---

## Task 1: Feature Development - Recurring Tasks

### Description

TaskForge users have requested the ability to create recurring tasks that automatically generate new task instances on a schedule. This feature is critical for teams that have regular maintenance work, weekly standups, monthly reports, or other periodic activities that need tracking.

The recurring task system should support multiple recurrence patterns including daily, weekly, monthly, and custom intervals. When a recurring task is completed, the system should automatically create the next instance based on the recurrence rules. Users should be able to set an end date for the recurrence or specify a maximum number of occurrences.

The feature must integrate with the existing task workflow, including notifications, assignments, and project statistics. Care must be taken to ensure that bulk operations and task dependencies work correctly with recurring tasks.

### Acceptance Criteria

- Tasks can be marked as recurring with configurable frequency (daily, weekly, monthly, yearly, custom)
- When a recurring task is completed, the next instance is automatically created with the appropriate due date
- Recurring tasks support week-day patterns (e.g., "every Monday and Wednesday")
- Users can set an optional end date or maximum occurrence count for the recurrence
- The original recurring task serves as a template; modifications to the template affect future instances
- Recurring task series can be viewed together and edited/cancelled as a group
- Project statistics correctly account for recurring tasks without double-counting
- Task search returns both the template and generated instances appropriately

### Test Command

```bash
bundle exec rspec spec/models/recurring_task_spec.rb spec/services/recurring_task_service_spec.rb
```

---

## Task 2: Refactoring - Extract Task State Machine to Service Object

### Description

The current Task model has grown too large and handles multiple responsibilities including state management, callbacks, notifications, and business logic. The state machine implementation using AASM is tightly coupled with ActiveRecord callbacks, making it difficult to test state transitions in isolation and leading to unexpected side effects during bulk operations.

The goal is to extract the task state machine logic into a dedicated service object that encapsulates all state transition rules, guards, and side effects. This will make the codebase more maintainable, improve testability, and provide a clear boundary between persistence and business logic.

The refactoring should preserve all existing functionality while making it easier to add new states or transitions in the future. The service should handle all notifications and activity logging currently scattered across callbacks.

### Acceptance Criteria

- Task state transitions are managed through a dedicated TaskStateMachine service
- All state guards (can_start?, may_complete?, etc.) are centralized in the service
- Notifications triggered by state changes are handled by the service, not callbacks
- Activity logging for state changes happens in one place
- The Task model no longer has state-related callbacks (only data validation callbacks remain)
- Bulk state transitions work correctly without triggering N+1 notifications
- All existing state machine tests pass with the new implementation
- Service object is easy to mock in controller and integration tests

### Test Command

```bash
bundle exec rspec spec/services/task_state_machine_spec.rb spec/models/task_spec.rb
```

---

## Task 3: Performance Optimization - Project Dashboard Query Optimization

### Description

The project dashboard is experiencing severe performance degradation as projects grow beyond 500 tasks. Users report page load times exceeding 10 seconds for large projects. Analysis shows that the dashboard makes numerous database queries to calculate statistics, load recent activity, and display task breakdowns by status and assignee.

The optimization effort should focus on reducing database round trips, implementing efficient aggregation queries, and adding appropriate caching strategies. The solution must balance query efficiency with data freshness requirements - some statistics can be cached for minutes while others need to be real-time.

Special attention should be paid to the team performance calculations, milestone progress tracking, and overdue task alerts, which currently iterate through collections in Ruby rather than using database aggregations.

### Acceptance Criteria

- Project dashboard loads in under 2 seconds for projects with up to 5,000 tasks
- Total database queries for dashboard load reduced to under 10 (from current 50+)
- Task counts by status use a single GROUP BY query instead of multiple COUNT queries
- Team performance metrics are calculated using SQL aggregations, not Ruby iteration
- Milestone progress percentages are cached with automatic invalidation on task updates
- Overdue task counts update in real-time without loading full task records
- No N+1 queries when displaying project members with their task counts
- Cache invalidation strategy documented and tested for race conditions

### Test Command

```bash
bundle exec rspec spec/services/project_dashboard_spec.rb spec/performance/
```

---

## Task 4: API Extension - Task Templates API

### Description

Enterprise customers need the ability to create and manage task templates that can be instantiated into actual tasks. Templates are pre-configured task definitions with standard titles, descriptions, checklists, estimated hours, and default assignments. Teams use templates for onboarding new employees, sprint planning, release checklists, and other standardized workflows.

The API should support full CRUD operations on templates, template instantiation into projects, and template sharing across organizations. Templates should support variable substitution (e.g., "Onboard {{employee_name}}") that gets replaced when the template is instantiated.

The implementation must include proper authorization - only project admins can create templates, and templates can be scoped to organizations or made globally available. Template usage should be tracked for analytics purposes.

### Acceptance Criteria

- RESTful API endpoints for template CRUD: GET/POST/PUT/DELETE /api/v1/templates
- Templates can include: title, description, priority, estimated_hours, tags, checklist items
- POST /api/v1/templates/:id/instantiate creates a task from a template in a specified project
- Templates support variable placeholders ({{variable}}) with validation of required variables
- Template instantiation accepts a variables hash to populate placeholders
- Templates can be scoped to organization or marked as global (admin only)
- Template usage is tracked: instantiation count, last used date, created_by
- Authorization: only org admins can create/edit templates, members can instantiate
- API returns appropriate error messages for invalid template variables

### Test Command

```bash
bundle exec rspec spec/requests/api/v1/templates_spec.rb spec/services/template_service_spec.rb
```

---

## Task 5: Migration - Move from Synchronous to Event-Driven Notifications

### Description

The current notification system sends notifications synchronously within the request cycle or through directly-enqueued background jobs. This tight coupling creates several problems: notification logic is scattered across models and services, adding new notification channels requires code changes in multiple places, and the system cannot easily support notification batching or digests.

The migration involves implementing an event-driven architecture where domain events (task_created, task_assigned, comment_added, etc.) are published and notification handlers subscribe to relevant events. This decouples the core business logic from notification delivery and enables features like notification preferences, channel routing, and digest emails.

The migration must be backward compatible during the transition period, allowing the old and new systems to run in parallel until the migration is complete.

### Acceptance Criteria

- Domain events are published for all notification-worthy actions (task lifecycle, comments, mentions)
- Event handlers subscribe to events and create appropriate notifications
- Notification preferences are respected at the event handler level, not the publisher level
- Events include sufficient context to generate notifications without additional database queries
- Email notifications can be batched into hourly/daily digests based on user preferences
- In-app notifications remain real-time while emails follow digest schedule
- Failed notification deliveries can be retried without replaying the original event
- Monitoring dashboards show event throughput and handler success rates
- Old synchronous notification calls are logged for identification and removal

### Test Command

```bash
bundle exec rspec spec/events/ spec/services/notification_event_handler_spec.rb
```
