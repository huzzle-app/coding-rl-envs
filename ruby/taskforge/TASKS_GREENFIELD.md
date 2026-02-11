# TaskForge - Greenfield Implementation Tasks

These tasks require implementing NEW modules from scratch while following the existing TaskForge architectural patterns. Each task builds upon the existing codebase's conventions for services, models, and testing.

---

## Task 1: Time Tracking Service

### Overview

Implement a time tracking system that allows users to log hours worked on tasks, view time entries, and generate time-based reports. This service must integrate with the existing Task, Project, and User models.

### New Files to Create

| File | Purpose |
|------|---------|
| `app/models/time_entry.rb` | ActiveRecord model for time entries |
| `app/services/time_tracking_service.rb` | Business logic for time operations |
| `db/migrate/YYYYMMDDHHMMSS_create_time_entries.rb` | Database migration |
| `spec/models/time_entry_spec.rb` | Model specs |
| `spec/services/time_tracking_service_spec.rb` | Service specs |
| `spec/factories/time_entries.rb` | Factory for test data |

### Interface Contract

```ruby
# frozen_string_literal: true

# app/services/time_tracking_service.rb
class TimeTrackingService
  # Initializes the time tracking service for a specific user
  #
  # @param user [User] the user performing time tracking operations
  def initialize(user)
    @user = user
  end

  # Starts a timer for the given task
  # Creates an in-progress time entry with start_time set to now
  #
  # @param task [Task] the task to track time against
  # @param description [String, nil] optional description of work being done
  # @return [TimeEntry] the created time entry
  # @raise [ActiveRecord::RecordInvalid] if validation fails
  # @raise [TimeTrackingError] if user already has an active timer
  def start_timer(task, description: nil)
    raise NotImplementedError
  end

  # Stops the active timer for the current user
  # Sets end_time to now and calculates duration_minutes
  #
  # @return [TimeEntry] the stopped time entry
  # @raise [TimeTrackingError] if no active timer exists
  def stop_timer
    raise NotImplementedError
  end

  # Logs a completed time entry manually
  #
  # @param task [Task] the task to log time against
  # @param duration_minutes [Integer] time spent in minutes
  # @param worked_on [Date] the date the work was performed
  # @param description [String, nil] optional description
  # @return [TimeEntry] the created time entry
  # @raise [ActiveRecord::RecordInvalid] if validation fails
  def log_time(task, duration_minutes:, worked_on:, description: nil)
    raise NotImplementedError
  end

  # Updates an existing time entry
  # Only allows editing own entries unless user is project admin
  #
  # @param time_entry [TimeEntry] the entry to update
  # @param attributes [Hash] attributes to update
  # @return [TimeEntry] the updated entry
  # @raise [Pundit::NotAuthorizedError] if not authorized
  def update_entry(time_entry, attributes)
    raise NotImplementedError
  end

  # Deletes a time entry
  # Only allows deleting own entries unless user is project admin
  #
  # @param time_entry [TimeEntry] the entry to delete
  # @return [Boolean] true if deleted
  # @raise [Pundit::NotAuthorizedError] if not authorized
  def delete_entry(time_entry)
    raise NotImplementedError
  end

  # Returns time entries for a task with optional date filtering
  #
  # @param task [Task] the task to get entries for
  # @param date_range [Range<Date>, nil] optional date filter
  # @return [ActiveRecord::Relation<TimeEntry>]
  def entries_for_task(task, date_range: nil)
    raise NotImplementedError
  end

  # Returns a summary of time logged by the user
  #
  # @param date_range [Range<Date>] the date range for the summary
  # @return [Hash] summary with keys: :total_minutes, :by_project, :by_day
  def user_summary(date_range)
    raise NotImplementedError
  end

  # Returns a summary of time logged on a project
  #
  # @param project [Project] the project to summarize
  # @param date_range [Range<Date>] the date range for the summary
  # @return [Hash] summary with keys: :total_minutes, :by_user, :by_task
  def project_summary(project, date_range)
    raise NotImplementedError
  end

  class TimeTrackingError < StandardError; end
end
```

### Required Model

```ruby
# frozen_string_literal: true

# app/models/time_entry.rb
class TimeEntry < ApplicationRecord
  # Associations
  belongs_to :task
  belongs_to :user
  belongs_to :project  # denormalized for easier querying

  # Validations
  validates :duration_minutes, numericality: { greater_than: 0 }, unless: :in_progress?
  validates :worked_on, presence: true, unless: :in_progress?
  validates :start_time, presence: true, if: :in_progress?

  # Scopes
  scope :in_progress, -> { where(end_time: nil).where.not(start_time: nil) }
  scope :completed, -> { where.not(duration_minutes: nil) }
  scope :for_date_range, ->(range) { where(worked_on: range) }
  scope :by_user, ->(user) { where(user: user) }

  # State helpers
  def in_progress?
    start_time.present? && end_time.nil?
  end

  def stop!
    return unless in_progress?

    self.end_time = Time.current
    self.duration_minutes = ((end_time - start_time) / 60).round
    self.worked_on = start_time.to_date
    save!
  end
end
```

### Database Migration

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_time_entries.rb
class CreateTimeEntries < ActiveRecord::Migration[7.1]
  def change
    create_table :time_entries, id: :uuid, default: -> { "gen_random_uuid()" } do |t|
      t.references :task, null: false, foreign_key: true, type: :uuid
      t.references :user, null: false, foreign_key: true, type: :uuid
      t.references :project, null: false, foreign_key: true, type: :uuid

      t.datetime :start_time
      t.datetime :end_time
      t.integer :duration_minutes
      t.date :worked_on
      t.text :description
      t.boolean :billable, default: true

      t.timestamps
    end

    add_index :time_entries, [:user_id, :worked_on]
    add_index :time_entries, [:project_id, :worked_on]
    add_index :time_entries, [:task_id, :worked_on]
    add_index :time_entries, [:user_id, :start_time], where: "end_time IS NULL"
  end
end
```

### Acceptance Criteria

1. **Unit Tests (30+ examples)**
   - Model validations and scopes
   - Service methods for all CRUD operations
   - Timer start/stop functionality
   - Summary calculations with edge cases

2. **Integration Points**
   - Task model has `has_many :time_entries`
   - Project model has `has_many :time_entries`
   - User model has `has_many :time_entries`
   - TimeEntry syncs `project_id` from task on create

3. **Architectural Compliance**
   - Follow `TaskService` pattern for service initialization
   - Use `Pundit` for authorization (reference `TaskPolicy`)
   - Handle errors with proper exceptions (not nil returns)
   - Add `has_paper_trail` for audit logging

4. **Test Command**
   ```bash
   bundle exec rspec spec/models/time_entry_spec.rb spec/services/time_tracking_service_spec.rb
   ```

---

## Task 2: Gantt Chart Data Generator

### Overview

Implement a service that generates structured data for Gantt chart visualization. The service must calculate task timelines, handle dependencies, identify the critical path, and detect scheduling conflicts.

### New Files to Create

| File | Purpose |
|------|---------|
| `app/services/gantt_chart_service.rb` | Core Gantt data generation |
| `app/services/critical_path_calculator.rb` | Critical path algorithm |
| `spec/services/gantt_chart_service_spec.rb` | Service specs |
| `spec/services/critical_path_calculator_spec.rb` | Calculator specs |

### Interface Contract

```ruby
# frozen_string_literal: true

# app/services/gantt_chart_service.rb
class GanttChartService
  # Initializes the Gantt chart service for a project
  #
  # @param project [Project] the project to generate Gantt data for
  # @param options [Hash] configuration options
  # @option options [Date] :start_date override project start date
  # @option options [Date] :end_date override project end date
  # @option options [Boolean] :include_completed include completed tasks (default: true)
  # @option options [Array<String>] :status_filter filter by task statuses
  def initialize(project, options = {})
    @project = project
    @options = options.freeze
  end

  # Generates the complete Gantt chart data structure
  #
  # @return [Hash] Gantt data with keys:
  #   - :project => project metadata
  #   - :date_range => { start: Date, end: Date }
  #   - :tasks => Array of task timeline data
  #   - :milestones => Array of milestone markers
  #   - :critical_path => Array of task IDs on critical path
  #   - :conflicts => Array of scheduling conflicts
  def generate
    raise NotImplementedError
  end

  # Generates timeline data for a single task
  #
  # @param task [Task] the task to process
  # @return [Hash] task timeline with keys:
  #   - :id, :title, :status, :priority
  #   - :start_date, :end_date, :duration_days
  #   - :progress_percentage (based on status or subtasks)
  #   - :dependencies => Array of dependent task IDs
  #   - :assignee => { id:, name:, avatar_url: }
  #   - :is_milestone => Boolean
  #   - :is_overdue => Boolean
  #   - :slack_days => Integer (buffer before affecting dependencies)
  def task_timeline(task)
    raise NotImplementedError
  end

  # Detects scheduling conflicts in the project
  #
  # @return [Array<Hash>] conflicts with keys:
  #   - :type => :dependency_violation | :resource_overallocation | :past_due
  #   - :task_ids => Array of affected task IDs
  #   - :message => Human-readable description
  #   - :severity => :warning | :error
  def detect_conflicts
    raise NotImplementedError
  end

  # Suggests optimal scheduling based on dependencies and resources
  #
  # @return [Array<Hash>] suggestions with keys:
  #   - :task_id
  #   - :suggested_start_date
  #   - :suggested_end_date
  #   - :reason
  def scheduling_suggestions
    raise NotImplementedError
  end
end
```

```ruby
# frozen_string_literal: true

# app/services/critical_path_calculator.rb
class CriticalPathCalculator
  # Initializes the calculator with tasks and their dependencies
  #
  # @param tasks [ActiveRecord::Relation<Task>] tasks to analyze
  def initialize(tasks)
    @tasks = tasks
  end

  # Calculates the critical path through the project
  # Uses the Critical Path Method (CPM) algorithm
  #
  # @return [Array<UUID>] ordered list of task IDs on the critical path
  def calculate
    raise NotImplementedError
  end

  # Calculates early start/finish and late start/finish for each task
  #
  # @return [Hash<UUID, Hash>] task_id => { es:, ef:, ls:, lf:, slack: }
  def task_schedule_data
    raise NotImplementedError
  end

  # Returns total project duration based on critical path
  #
  # @return [Integer] duration in days
  def project_duration
    raise NotImplementedError
  end

  # Identifies bottleneck tasks (zero slack on critical path)
  #
  # @return [Array<UUID>] task IDs that are bottlenecks
  def bottleneck_tasks
    raise NotImplementedError
  end
end
```

### Acceptance Criteria

1. **Unit Tests (40+ examples)**
   - Gantt data generation with various task configurations
   - Critical path calculation with complex dependency graphs
   - Conflict detection for all conflict types
   - Edge cases: circular dependencies, missing dates, orphan tasks

2. **Integration Points**
   - Uses existing `Task#dependencies` association
   - Uses existing `Task#subtasks` for rollup calculations
   - Integrates with `Milestone` model for milestone markers
   - Compatible with `ReportService` patterns

3. **Architectural Compliance**
   - Immutable options hash (use `.freeze`)
   - Eager load associations to avoid N+1 queries
   - Return plain Ruby hashes (serializable to JSON)
   - Handle missing data gracefully (nil dates, etc.)

4. **Test Command**
   ```bash
   bundle exec rspec spec/services/gantt_chart_service_spec.rb spec/services/critical_path_calculator_spec.rb
   ```

---

## Task 3: Workload Balancer

### Overview

Implement a workload balancing service that analyzes team member capacity, identifies over/under-allocated users, and suggests task reassignments to optimize team productivity.

### New Files to Create

| File | Purpose |
|------|---------|
| `app/models/user_capacity.rb` | Model for user capacity settings |
| `app/services/workload_balancer_service.rb` | Core balancing logic |
| `app/services/capacity_calculator.rb` | Capacity computation |
| `db/migrate/YYYYMMDDHHMMSS_create_user_capacities.rb` | Migration |
| `spec/models/user_capacity_spec.rb` | Model specs |
| `spec/services/workload_balancer_service_spec.rb` | Service specs |
| `spec/services/capacity_calculator_spec.rb` | Calculator specs |
| `spec/factories/user_capacities.rb` | Factory |

### Interface Contract

```ruby
# frozen_string_literal: true

# app/services/workload_balancer_service.rb
class WorkloadBalancerService
  # Initializes the workload balancer for an organization
  #
  # @param organization [Organization] the organization to balance
  # @param options [Hash] configuration options
  # @option options [Date] :start_date start of analysis window (default: today)
  # @option options [Date] :end_date end of analysis window (default: 2 weeks out)
  # @option options [Array<UUID>] :user_ids limit analysis to specific users
  # @option options [Array<UUID>] :project_ids limit analysis to specific projects
  def initialize(organization, options = {})
    @organization = organization
    @options = options
  end

  # Analyzes current workload distribution across team members
  #
  # @return [Hash] analysis with keys:
  #   - :summary => { total_tasks:, total_hours:, avg_utilization: }
  #   - :users => Array of user workload data
  #   - :overallocated => Array of user IDs over capacity
  #   - :underallocated => Array of user IDs under capacity
  #   - :balanced => Array of user IDs at optimal capacity
  def analyze
    raise NotImplementedError
  end

  # Returns detailed workload data for a specific user
  #
  # @param user [User] the user to analyze
  # @return [Hash] workload data with keys:
  #   - :user => { id:, name:, email: }
  #   - :capacity => { hours_per_week:, available_hours: }
  #   - :assigned => { task_count:, estimated_hours:, by_priority: }
  #   - :utilization_percentage
  #   - :status => :overallocated | :underallocated | :balanced
  #   - :tasks => Array of assigned task summaries
  def user_workload(user)
    raise NotImplementedError
  end

  # Generates task reassignment suggestions to balance workload
  #
  # @param strategy [Symbol] balancing strategy
  #   - :minimize_moves => fewest reassignments
  #   - :optimize_skills => match task requirements to user skills
  #   - :level_utilization => equalize utilization percentages
  # @return [Array<Hash>] suggestions with keys:
  #   - :task_id
  #   - :from_user_id
  #   - :to_user_id
  #   - :reason
  #   - :impact => { from_utilization_delta:, to_utilization_delta: }
  def suggest_rebalancing(strategy: :level_utilization)
    raise NotImplementedError
  end

  # Applies suggested reassignments
  # Only reassigns tasks where current user has permission
  #
  # @param suggestions [Array<Hash>] suggestions from suggest_rebalancing
  # @param notify [Boolean] whether to send notifications (default: true)
  # @return [Hash] result with keys:
  #   - :applied => Array of applied suggestion indices
  #   - :skipped => Array of { index:, reason: }
  #   - :errors => Array of { index:, error: }
  def apply_suggestions(suggestions, notify: true)
    raise NotImplementedError
  end

  # Simulates what-if scenarios for task assignment
  #
  # @param task [Task] the task being assigned
  # @param candidates [Array<User>] potential assignees
  # @return [Array<Hash>] impact analysis per candidate with keys:
  #   - :user_id
  #   - :current_utilization
  #   - :projected_utilization
  #   - :recommendation_score (0-100, higher is better fit)
  #   - :warnings => Array of potential issues
  def simulate_assignment(task, candidates)
    raise NotImplementedError
  end
end
```

```ruby
# frozen_string_literal: true

# app/services/capacity_calculator.rb
class CapacityCalculator
  # Initializes the calculator for a user
  #
  # @param user [User] the user to calculate capacity for
  # @param date_range [Range<Date>] the date range for calculation
  def initialize(user, date_range)
    @user = user
    @date_range = date_range
  end

  # Calculates available hours in the date range
  # Accounts for: configured hours/week, holidays, time off
  #
  # @return [Float] total available hours
  def available_hours
    raise NotImplementedError
  end

  # Calculates hours already committed to tasks
  # Uses task.estimated_hours, prorated by date overlap
  #
  # @return [Float] total committed hours
  def committed_hours
    raise NotImplementedError
  end

  # Calculates remaining capacity
  #
  # @return [Float] hours available for new work
  def remaining_capacity
    raise NotImplementedError
  end

  # Calculates utilization percentage
  #
  # @return [Float] percentage (can exceed 100 if overallocated)
  def utilization_percentage
    raise NotImplementedError
  end

  # Returns allocation status
  #
  # @return [Symbol] :overallocated | :underallocated | :balanced
  def status
    raise NotImplementedError
  end
end
```

### Required Model

```ruby
# frozen_string_literal: true

# app/models/user_capacity.rb
class UserCapacity < ApplicationRecord
  belongs_to :user
  belongs_to :organization

  validates :hours_per_week, presence: true,
            numericality: { greater_than: 0, less_than_or_equal_to: 168 }
  validates :user_id, uniqueness: { scope: :organization_id }

  # Default capacity thresholds
  UNDERALLOCATED_THRESHOLD = 70  # below 70% utilization
  OVERALLOCATED_THRESHOLD = 100  # at or above 100% utilization

  scope :for_organization, ->(org) { where(organization: org) }

  def self.for_user_in_org(user, organization)
    find_or_initialize_by(user: user, organization: organization) do |cap|
      cap.hours_per_week = 40  # default
    end
  end
end
```

### Database Migration

```ruby
# db/migrate/YYYYMMDDHHMMSS_create_user_capacities.rb
class CreateUserCapacities < ActiveRecord::Migration[7.1]
  def change
    create_table :user_capacities, id: :uuid, default: -> { "gen_random_uuid()" } do |t|
      t.references :user, null: false, foreign_key: true, type: :uuid
      t.references :organization, null: false, foreign_key: true, type: :uuid

      t.decimal :hours_per_week, precision: 5, scale: 2, null: false, default: 40
      t.jsonb :weekly_schedule, default: {}  # { mon: 8, tue: 8, ... }
      t.jsonb :skills, default: []           # ['ruby', 'frontend', ...]
      t.date :effective_from
      t.date :effective_until

      t.timestamps
    end

    add_index :user_capacities, [:user_id, :organization_id], unique: true
    add_index :user_capacities, [:organization_id, :effective_from]
  end
end
```

### Acceptance Criteria

1. **Unit Tests (50+ examples)**
   - Capacity calculation with various configurations
   - Workload analysis accuracy
   - Rebalancing suggestions for different strategies
   - Simulation accuracy for assignment scenarios
   - Edge cases: no capacity set, zero tasks, all overallocated

2. **Integration Points**
   - User model has `has_many :user_capacities`
   - Organization model has `has_many :user_capacities`
   - Uses `Task#estimated_hours` for workload calculation
   - Uses `ProjectMembership` to scope users per project

3. **Architectural Compliance**
   - Follow `ReportService` pattern for organization-scoped services
   - Eager load to avoid N+1 (tasks, users, capacities)
   - Transaction wrapping for `apply_suggestions`
   - Notification integration via `NotificationService`

4. **Performance Requirements**
   - Analysis should complete in < 2 seconds for 100 users, 1000 tasks
   - Use batch loading and avoid loading full task objects when possible

5. **Test Command**
   ```bash
   bundle exec rspec spec/models/user_capacity_spec.rb spec/services/workload_balancer_service_spec.rb spec/services/capacity_calculator_spec.rb
   ```

---

## General Guidelines

### Following Existing Patterns

1. **Service Initialization**: Services take primary entity in constructor (user, organization, project)
2. **Error Handling**: Raise exceptions, don't return nil on errors (unlike the buggy `TaskService#create`)
3. **Authorization**: Use Pundit policies, check permissions in service methods
4. **Testing**: Use FactoryBot, follow existing spec structure with `let` blocks
5. **Associations**: Add `has_many`/`belongs_to` to existing models
6. **Paper Trail**: Add `has_paper_trail` to new models for audit logging

### Code Style

- Use `frozen_string_literal: true` pragma
- YARD documentation for public methods
- Meaningful variable names
- Guard clauses for early returns
- Scopes for common queries

### Running All Greenfield Tests

```bash
# Run all new service and model tests
bundle exec rspec \
  spec/models/time_entry_spec.rb \
  spec/models/user_capacity_spec.rb \
  spec/services/time_tracking_service_spec.rb \
  spec/services/gantt_chart_service_spec.rb \
  spec/services/critical_path_calculator_spec.rb \
  spec/services/workload_balancer_service_spec.rb \
  spec/services/capacity_calculator_spec.rb
```
