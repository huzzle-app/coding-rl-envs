# MercuryLedger Greenfield Tasks

This document defines greenfield implementation tasks for the MercuryLedger ledger platform. Each task requires building a new module from scratch while following existing architectural patterns.

---

## Task 1: Balance Snapshot Service

### Overview

Implement a **Balance Snapshot Service** that captures point-in-time snapshots of ledger balances across accounts. The service must support scheduled snapshots, on-demand captures, differential comparisons between snapshots, and rollback capabilities for auditing purposes.

### Module Location

- **Core Module**: `lib/mercuryledger/core/snapshot.rb`
- **Service Module**: `services/snapshot/service.rb`

### Ruby Interface Contract

```ruby
# frozen_string_literal: true

module MercuryLedger
  module Core
    # Represents a single balance snapshot at a point in time
    # @attr_reader id [String] Unique snapshot identifier
    # @attr_reader timestamp [Integer] Unix timestamp of snapshot creation
    # @attr_reader account_id [String] Account identifier
    # @attr_reader balance [Float] Balance value at snapshot time
    # @attr_reader currency [String] ISO 4217 currency code
    # @attr_reader metadata [Hash] Additional snapshot metadata
    Snapshot = Struct.new(:id, :timestamp, :account_id, :balance, :currency, :metadata, keyword_init: true)

    # Represents the difference between two snapshots
    # @attr_reader account_id [String] Account identifier
    # @attr_reader before_balance [Float] Balance in earlier snapshot
    # @attr_reader after_balance [Float] Balance in later snapshot
    # @attr_reader delta [Float] Calculated difference (after - before)
    # @attr_reader percentage_change [Float] Percentage change between snapshots
    SnapshotDiff = Struct.new(:account_id, :before_balance, :after_balance, :delta, :percentage_change, keyword_init: true)

    module SnapshotEngine
      module_function

      # Captures a snapshot for a single account
      # @param account_id [String] The account to snapshot
      # @param balance [Float] Current balance value
      # @param currency [String] Currency code (default: 'USD')
      # @param metadata [Hash] Optional metadata to attach
      # @return [Snapshot] The created snapshot
      def capture(account_id, balance, currency: 'USD', metadata: {})
        raise NotImplementedError
      end

      # Captures snapshots for multiple accounts in a batch
      # @param accounts [Array<Hash>] Array of {account_id:, balance:, currency:}
      # @return [Array<Snapshot>] Array of created snapshots
      def capture_batch(accounts)
        raise NotImplementedError
      end

      # Validates a snapshot has required fields and valid values
      # @param snapshot [Snapshot] The snapshot to validate
      # @return [Boolean] True if valid
      def valid?(snapshot)
        raise NotImplementedError
      end

      # Computes the hash digest of a snapshot for integrity verification
      # @param snapshot [Snapshot] The snapshot to hash
      # @return [String] SHA-256 hex digest
      def compute_digest(snapshot)
        raise NotImplementedError
      end
    end

    class SnapshotStore
      # Initializes a new snapshot store
      # @param max_snapshots_per_account [Integer] Maximum snapshots to retain per account
      def initialize(max_snapshots_per_account: 1000)
        raise NotImplementedError
      end

      # Stores a snapshot
      # @param snapshot [Snapshot] The snapshot to store
      # @return [Boolean] True if stored successfully
      def store(snapshot)
        raise NotImplementedError
      end

      # Retrieves the latest snapshot for an account
      # @param account_id [String] The account identifier
      # @return [Snapshot, nil] The latest snapshot or nil
      def latest(account_id)
        raise NotImplementedError
      end

      # Retrieves snapshots within a time range
      # @param account_id [String] The account identifier
      # @param from_ts [Integer] Start timestamp (inclusive)
      # @param to_ts [Integer] End timestamp (inclusive)
      # @return [Array<Snapshot>] Snapshots in range, ordered by timestamp
      def range(account_id, from_ts, to_ts)
        raise NotImplementedError
      end

      # Returns the count of stored snapshots for an account
      # @param account_id [String] The account identifier
      # @return [Integer] Number of snapshots
      def count(account_id)
        raise NotImplementedError
      end

      # Prunes snapshots older than the retention period
      # @param account_id [String] The account identifier
      # @param retention_seconds [Integer] Retention window in seconds
      # @return [Integer] Number of snapshots pruned
      def prune(account_id, retention_seconds)
        raise NotImplementedError
      end
    end

    class SnapshotComparator
      # Computes the difference between two snapshots
      # @param before [Snapshot] Earlier snapshot
      # @param after [Snapshot] Later snapshot
      # @return [SnapshotDiff] The computed difference
      def self.diff(before, after)
        raise NotImplementedError
      end

      # Computes differences for a batch of snapshot pairs
      # @param pairs [Array<Array<Snapshot, Snapshot>>] Array of [before, after] pairs
      # @return [Array<SnapshotDiff>] Array of diffs
      def self.diff_batch(pairs)
        raise NotImplementedError
      end

      # Identifies accounts with significant balance changes
      # @param diffs [Array<SnapshotDiff>] Computed diffs
      # @param threshold_pct [Float] Percentage threshold (e.g., 10.0 for 10%)
      # @return [Array<SnapshotDiff>] Diffs exceeding threshold
      def self.significant_changes(diffs, threshold_pct)
        raise NotImplementedError
      end
    end
  end

  module Services
    module Snapshot
      SERVICE = { name: 'snapshot', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Schedules a snapshot capture at a future time
      # @param account_ids [Array<String>] Accounts to snapshot
      # @param scheduled_at [Integer] Unix timestamp for capture
      # @return [Hash] Schedule confirmation with :schedule_id
      def schedule_capture(account_ids, scheduled_at)
        raise NotImplementedError
      end

      # Retrieves snapshot history summary for an account
      # @param account_id [String] The account identifier
      # @param limit [Integer] Maximum snapshots to return
      # @return [Hash] Summary with :snapshots, :oldest, :newest, :count
      def history_summary(account_id, limit: 100)
        raise NotImplementedError
      end

      # Generates a balance trend report from snapshots
      # @param account_id [String] The account identifier
      # @param window_size [Integer] Number of snapshots for trend calculation
      # @return [Hash] Trend data with :direction, :slope, :volatility
      def balance_trend(account_id, window_size: 10)
        raise NotImplementedError
      end
    end
  end
end
```

### Required Models/Classes

| Class/Module | Location | Purpose |
|--------------|----------|---------|
| `Snapshot` | `lib/mercuryledger/core/snapshot.rb` | Struct representing a point-in-time balance |
| `SnapshotDiff` | `lib/mercuryledger/core/snapshot.rb` | Struct for difference between snapshots |
| `SnapshotEngine` | `lib/mercuryledger/core/snapshot.rb` | Module for snapshot capture logic |
| `SnapshotStore` | `lib/mercuryledger/core/snapshot.rb` | Thread-safe storage with retention |
| `SnapshotComparator` | `lib/mercuryledger/core/snapshot.rb` | Comparison and diff calculations |
| `Services::Snapshot` | `services/snapshot/service.rb` | Service layer with scheduling |

### Architectural Patterns to Follow

1. **Thread Safety**: Use `Mutex` for all mutable state (see `BerthPlanner`, `RateLimiter`)
2. **Module Functions**: Use `module_function` for stateless operations (see `Dispatch`, `Statistics`)
3. **Struct Models**: Use `Struct.new(..., keyword_init: true)` for data objects (see `Checkpoint`, `QueueHealth`)
4. **Guard Clauses**: Return early for nil/empty/invalid inputs (see `Analytics.compute_fleet_health`)
5. **Digest Integration**: Use SHA-256 from `Security` module patterns for integrity
6. **Service Constants**: Define `SERVICE` hash with name, status, version (see `Analytics`)

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/snapshot_test.rb` with minimum 15 test cases covering:
   - Single and batch snapshot capture
   - Validation of snapshot fields
   - Digest computation consistency
   - Store operations (store, latest, range, count, prune)
   - Diff calculations including edge cases (zero balance, negative delta)
   - Significant change detection

2. **Service Tests**: Create `tests/services/snapshot_service_test.rb` with minimum 4 test cases:
   - Schedule capture validation
   - History summary retrieval
   - Balance trend calculation
   - Edge cases (empty history, single snapshot)

3. **Integration Points**:
   - Use `Statistics.mean` and `Statistics.variance` for trend volatility
   - Use `Security` module digest pattern for `compute_digest`
   - Register in `Contracts::SERVICE_DEFS` with port 8118

4. **Test Command**: `bundle exec rspec` or `ruby -Ilib -Itests tests/run_all.rb`

---

## Task 2: Transaction Categorization Engine

### Overview

Implement a **Transaction Categorization Engine** that automatically classifies ledger transactions into categories based on configurable rules. The engine must support rule-based matching, machine learning-style scoring, category hierarchies, and bulk categorization with conflict resolution.

### Module Location

- **Core Module**: `lib/mercuryledger/core/categorization.rb`
- **Service Module**: `services/categorization/service.rb`

### Ruby Interface Contract

```ruby
# frozen_string_literal: true

module MercuryLedger
  module Core
    # Represents a categorization rule
    # @attr_reader id [String] Rule identifier
    # @attr_reader name [String] Human-readable rule name
    # @attr_reader category [String] Target category for matching transactions
    # @attr_reader conditions [Array<Hash>] Match conditions [{field:, operator:, value:}]
    # @attr_reader priority [Integer] Rule priority (higher = checked first)
    # @attr_reader enabled [Boolean] Whether rule is active
    CategoryRule = Struct.new(:id, :name, :category, :conditions, :priority, :enabled, keyword_init: true)

    # Represents a categorized transaction result
    # @attr_reader transaction_id [String] Original transaction ID
    # @attr_reader category [String] Assigned category
    # @attr_reader confidence [Float] Confidence score 0.0-1.0
    # @attr_reader rule_id [String, nil] Rule that matched (nil for ML-based)
    # @attr_reader subcategory [String, nil] Optional subcategory
    CategoryResult = Struct.new(:transaction_id, :category, :confidence, :rule_id, :subcategory, keyword_init: true)

    module CategorizationEngine
      OPERATORS = %w[eq neq gt gte lt lte contains starts_with ends_with regex].freeze

      module_function

      # Evaluates a single condition against a transaction
      # @param transaction [Hash] Transaction data
      # @param condition [Hash] Condition with :field, :operator, :value
      # @return [Boolean] True if condition matches
      def evaluate_condition(transaction, condition)
        raise NotImplementedError
      end

      # Evaluates all conditions for a rule (AND logic)
      # @param transaction [Hash] Transaction data
      # @param rule [CategoryRule] Rule to evaluate
      # @return [Boolean] True if all conditions match
      def matches_rule?(transaction, rule)
        raise NotImplementedError
      end

      # Categorizes a transaction using rule-based matching
      # @param transaction [Hash] Transaction with :id, :amount, :description, :merchant, etc.
      # @param rules [Array<CategoryRule>] Ordered list of rules
      # @return [CategoryResult, nil] Result or nil if no match
      def categorize(transaction, rules)
        raise NotImplementedError
      end

      # Categorizes transactions in bulk with parallel rule evaluation
      # @param transactions [Array<Hash>] Transactions to categorize
      # @param rules [Array<CategoryRule>] Rules to apply
      # @return [Array<CategoryResult>] Results for all transactions
      def categorize_batch(transactions, rules)
        raise NotImplementedError
      end

      # Validates a rule has valid structure and operators
      # @param rule [CategoryRule] Rule to validate
      # @return [Boolean] True if valid
      def valid_rule?(rule)
        raise NotImplementedError
      end
    end

    class CategoryHierarchy
      # Initializes hierarchy with root categories
      # @param root_categories [Array<String>] Top-level category names
      def initialize(root_categories = [])
        raise NotImplementedError
      end

      # Adds a subcategory under a parent
      # @param parent [String] Parent category name
      # @param child [String] Child category name
      # @return [Boolean] True if added successfully
      def add_child(parent, child)
        raise NotImplementedError
      end

      # Returns all ancestors of a category
      # @param category [String] Category name
      # @return [Array<String>] Ancestor path from root
      def ancestors(category)
        raise NotImplementedError
      end

      # Returns all descendants of a category
      # @param category [String] Category name
      # @return [Array<String>] All child categories recursively
      def descendants(category)
        raise NotImplementedError
      end

      # Checks if a category is a descendant of another
      # @param category [String] Category to check
      # @param ancestor [String] Potential ancestor
      # @return [Boolean] True if descendant
      def descendant_of?(category, ancestor)
        raise NotImplementedError
      end

      # Returns depth of category in hierarchy
      # @param category [String] Category name
      # @return [Integer] Depth (0 for root)
      def depth(category)
        raise NotImplementedError
      end
    end

    class RuleStore
      # Initializes an empty rule store
      def initialize
        raise NotImplementedError
      end

      # Adds a rule to the store
      # @param rule [CategoryRule] Rule to add
      # @return [Boolean] True if added
      def add(rule)
        raise NotImplementedError
      end

      # Removes a rule by ID
      # @param rule_id [String] Rule identifier
      # @return [CategoryRule, nil] Removed rule or nil
      def remove(rule_id)
        raise NotImplementedError
      end

      # Returns all enabled rules sorted by priority descending
      # @return [Array<CategoryRule>] Enabled rules in priority order
      def enabled_rules
        raise NotImplementedError
      end

      # Returns rules matching a specific category
      # @param category [String] Category name
      # @return [Array<CategoryRule>] Rules for category
      def rules_for_category(category)
        raise NotImplementedError
      end

      # Returns total rule count
      # @return [Integer] Number of rules
      def count
        raise NotImplementedError
      end
    end

    module ConflictResolver
      module_function

      # Resolves conflicts when multiple rules match
      # @param results [Array<CategoryResult>] Conflicting results
      # @param strategy [Symbol] Resolution strategy (:highest_priority, :highest_confidence, :first)
      # @return [CategoryResult] Winning result
      def resolve(results, strategy: :highest_priority)
        raise NotImplementedError
      end
    end
  end

  module Services
    module Categorization
      SERVICE = { name: 'categorization', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Categorizes a single transaction using stored rules
      # @param transaction [Hash] Transaction data
      # @return [Hash] Result with :category, :confidence, :rule_id
      def categorize_transaction(transaction)
        raise NotImplementedError
      end

      # Bulk categorization with summary statistics
      # @param transactions [Array<Hash>] Transactions to process
      # @return [Hash] Summary with :results, :categorized_count, :uncategorized_count, :categories
      def bulk_categorize(transactions)
        raise NotImplementedError
      end

      # Suggests a category based on similar past transactions
      # @param transaction [Hash] Transaction to analyze
      # @param history [Array<Hash>] Past categorized transactions
      # @param k [Integer] Number of neighbors to consider
      # @return [Hash] Suggestion with :category, :confidence, :similar_count
      def suggest_category(transaction, history, k: 5)
        raise NotImplementedError
      end

      # Validates categorization accuracy against known labels
      # @param predictions [Array<CategoryResult>] Predicted categories
      # @param actuals [Array<String>] Actual category labels
      # @return [Hash] Metrics with :accuracy, :precision, :recall
      def accuracy_report(predictions, actuals)
        raise NotImplementedError
      end
    end
  end
end
```

### Required Models/Classes

| Class/Module | Location | Purpose |
|--------------|----------|---------|
| `CategoryRule` | `lib/mercuryledger/core/categorization.rb` | Rule definition struct |
| `CategoryResult` | `lib/mercuryledger/core/categorization.rb` | Categorization result struct |
| `CategorizationEngine` | `lib/mercuryledger/core/categorization.rb` | Rule evaluation logic |
| `CategoryHierarchy` | `lib/mercuryledger/core/categorization.rb` | Tree structure for categories |
| `RuleStore` | `lib/mercuryledger/core/categorization.rb` | Thread-safe rule storage |
| `ConflictResolver` | `lib/mercuryledger/core/categorization.rb` | Multi-match resolution |
| `Services::Categorization` | `services/categorization/service.rb` | Service API |

### Architectural Patterns to Follow

1. **Operator Pattern**: Define constants for valid operators (see `Resilience::CB_*`)
2. **Rule Evaluation**: Follow `Policy` module escalation/de-escalation patterns
3. **Hierarchy**: Use BFS/DFS like `Workflow` module for graph traversal
4. **Thread Safety**: Mutex for `RuleStore` mutable state
5. **Batch Processing**: Follow `dispatch_batch` pattern with planned/rejected splits
6. **Validation**: Use guard clauses and explicit nil checks throughout

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/categorization_test.rb` with minimum 20 test cases:
   - All operator types (eq, neq, gt, gte, lt, lte, contains, starts_with, ends_with, regex)
   - Multi-condition rules (all must match)
   - Priority ordering
   - Hierarchy operations (ancestors, descendants, depth)
   - Conflict resolution strategies
   - Edge cases (empty rules, invalid operators, missing fields)

2. **Service Tests**: Create `tests/services/categorization_service_test.rb` with minimum 4 test cases:
   - Single transaction categorization
   - Bulk categorization with summary
   - Category suggestion from history
   - Accuracy report calculation

3. **Integration Points**:
   - Use `Statistics.mean` for confidence averaging
   - Register in `Contracts::SERVICE_DEFS` with port 8119

4. **Test Command**: `bundle exec rspec` or `ruby -Ilib -Itests tests/run_all.rb`

---

## Task 3: Ledger Export Service

### Overview

Implement a **Ledger Export Service** that generates exports of ledger data in multiple formats (CSV, JSON, XML). The service must support filtering, field selection, streaming for large exports, checksums for integrity, and configurable scheduling.

### Module Location

- **Core Module**: `lib/mercuryledger/core/export.rb`
- **Service Module**: `services/export/service.rb`

### Ruby Interface Contract

```ruby
# frozen_string_literal: true

module MercuryLedger
  module Core
    # Export format enumeration
    module ExportFormat
      CSV  = 'csv'
      JSON = 'json'
      XML  = 'xml'

      ALL = [CSV, JSON, XML].freeze

      module_function

      def valid?(format)
        ALL.include?(format)
      end
    end

    # Represents an export job configuration
    # @attr_reader id [String] Export job identifier
    # @attr_reader format [String] Output format (csv, json, xml)
    # @attr_reader filters [Hash] Filter criteria {field: value}
    # @attr_reader fields [Array<String>] Fields to include (nil = all)
    # @attr_reader created_at [Integer] Job creation timestamp
    # @attr_reader status [Symbol] Job status (:pending, :running, :completed, :failed)
    ExportJob = Struct.new(:id, :format, :filters, :fields, :created_at, :status, keyword_init: true)

    # Represents export result metadata
    # @attr_reader job_id [String] Associated job ID
    # @attr_reader row_count [Integer] Number of records exported
    # @attr_reader byte_size [Integer] Size in bytes
    # @attr_reader checksum [String] SHA-256 of content
    # @attr_reader duration_ms [Integer] Export duration in milliseconds
    ExportResult = Struct.new(:job_id, :row_count, :byte_size, :checksum, :duration_ms, keyword_init: true)

    module ExportEngine
      module_function

      # Filters records based on criteria
      # @param records [Array<Hash>] Records to filter
      # @param filters [Hash] Filter criteria {field: value} or {field: {op: :gt, val: 100}}
      # @return [Array<Hash>] Filtered records
      def filter_records(records, filters)
        raise NotImplementedError
      end

      # Selects specific fields from records
      # @param records [Array<Hash>] Records to project
      # @param fields [Array<String>] Field names to keep
      # @return [Array<Hash>] Projected records
      def select_fields(records, fields)
        raise NotImplementedError
      end

      # Exports records to CSV format
      # @param records [Array<Hash>] Records to export
      # @param fields [Array<String>] Fields to include (determines column order)
      # @return [String] CSV content
      def to_csv(records, fields)
        raise NotImplementedError
      end

      # Exports records to JSON format
      # @param records [Array<Hash>] Records to export
      # @param pretty [Boolean] Pretty-print output
      # @return [String] JSON content
      def to_json(records, pretty: false)
        raise NotImplementedError
      end

      # Exports records to XML format
      # @param records [Array<Hash>] Records to export
      # @param root_element [String] Root XML element name
      # @param record_element [String] Each record's element name
      # @return [String] XML content
      def to_xml(records, root_element: 'records', record_element: 'record')
        raise NotImplementedError
      end

      # Computes SHA-256 checksum of content
      # @param content [String] Content to hash
      # @return [String] Hex digest
      def compute_checksum(content)
        raise NotImplementedError
      end

      # Validates export job configuration
      # @param job [ExportJob] Job to validate
      # @return [Boolean] True if valid
      def valid_job?(job)
        raise NotImplementedError
      end
    end

    class ExportJobQueue
      # Initializes a new job queue
      # @param max_concurrent [Integer] Maximum concurrent exports
      def initialize(max_concurrent: 3)
        raise NotImplementedError
      end

      # Enqueues an export job
      # @param job [ExportJob] Job to queue
      # @return [Boolean] True if queued
      def enqueue(job)
        raise NotImplementedError
      end

      # Dequeues the next pending job
      # @return [ExportJob, nil] Next job or nil
      def dequeue
        raise NotImplementedError
      end

      # Returns job by ID
      # @param job_id [String] Job identifier
      # @return [ExportJob, nil] Job or nil
      def find(job_id)
        raise NotImplementedError
      end

      # Updates job status
      # @param job_id [String] Job identifier
      # @param status [Symbol] New status
      # @return [Boolean] True if updated
      def update_status(job_id, status)
        raise NotImplementedError
      end

      # Returns queue statistics
      # @return [Hash] Stats with :pending, :running, :completed, :failed counts
      def stats
        raise NotImplementedError
      end

      # Clears completed and failed jobs older than retention
      # @param retention_seconds [Integer] Retention window
      # @return [Integer] Jobs cleared
      def cleanup(retention_seconds)
        raise NotImplementedError
      end
    end

    class StreamingExporter
      # Initializes streaming exporter
      # @param format [String] Export format
      # @param chunk_size [Integer] Records per chunk
      def initialize(format:, chunk_size: 1000)
        raise NotImplementedError
      end

      # Writes header (for CSV/XML)
      # @param fields [Array<String>] Field names
      # @return [String] Header content
      def write_header(fields)
        raise NotImplementedError
      end

      # Writes a chunk of records
      # @param records [Array<Hash>] Records to write
      # @return [String] Chunk content
      def write_chunk(records)
        raise NotImplementedError
      end

      # Writes footer (for XML)
      # @return [String] Footer content
      def write_footer
        raise NotImplementedError
      end

      # Returns total bytes written
      # @return [Integer] Byte count
      def bytes_written
        raise NotImplementedError
      end

      # Returns total records written
      # @return [Integer] Record count
      def records_written
        raise NotImplementedError
      end
    end
  end

  module Services
    module Export
      SERVICE = { name: 'export', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Creates and queues an export job
      # @param format [String] Export format
      # @param filters [Hash] Filter criteria
      # @param fields [Array<String>, nil] Fields to include
      # @return [Hash] Job info with :job_id, :status, :estimated_time
      def create_export(format:, filters: {}, fields: nil)
        raise NotImplementedError
      end

      # Retrieves export job status
      # @param job_id [String] Job identifier
      # @return [Hash] Status with :status, :progress, :result
      def job_status(job_id)
        raise NotImplementedError
      end

      # Cancels a pending or running export
      # @param job_id [String] Job identifier
      # @return [Boolean] True if cancelled
      def cancel_export(job_id)
        raise NotImplementedError
      end

      # Lists recent export jobs
      # @param limit [Integer] Maximum jobs to return
      # @param status_filter [Symbol, nil] Filter by status
      # @return [Array<Hash>] Job summaries
      def list_exports(limit: 20, status_filter: nil)
        raise NotImplementedError
      end

      # Generates export preview (first N records)
      # @param format [String] Export format
      # @param filters [Hash] Filter criteria
      # @param preview_count [Integer] Records to preview
      # @return [Hash] Preview with :content, :total_estimated
      def preview_export(format:, filters: {}, preview_count: 10)
        raise NotImplementedError
      end
    end
  end
end
```

### Required Models/Classes

| Class/Module | Location | Purpose |
|--------------|----------|---------|
| `ExportFormat` | `lib/mercuryledger/core/export.rb` | Format constants and validation |
| `ExportJob` | `lib/mercuryledger/core/export.rb` | Job configuration struct |
| `ExportResult` | `lib/mercuryledger/core/export.rb` | Export result metadata |
| `ExportEngine` | `lib/mercuryledger/core/export.rb` | Format conversion logic |
| `ExportJobQueue` | `lib/mercuryledger/core/export.rb` | Thread-safe job queue |
| `StreamingExporter` | `lib/mercuryledger/core/export.rb` | Chunked export handler |
| `Services::Export` | `services/export/service.rb` | Service API |

### Architectural Patterns to Follow

1. **Format Constants**: Use module with constants and `valid?` method (see `Severity`)
2. **Job Queue**: Follow `PriorityQueue` pattern with mutex-guarded operations
3. **Status FSM**: Use symbol states like `CircuitBreaker` states
4. **Streaming**: Chunk processing similar to `RollingWindowScheduler`
5. **Checksums**: Use `Security` module SHA-256 pattern
6. **Service Layer**: Match existing service patterns with `module_function`

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/export_test.rb` with minimum 18 test cases:
   - Filter operations (equality, comparison operators)
   - Field selection and projection
   - CSV generation (header, quoting, escaping)
   - JSON generation (pretty and compact)
   - XML generation (proper escaping, nesting)
   - Checksum computation
   - Job queue operations (enqueue, dequeue, find, update)
   - Streaming export (header, chunks, footer, counters)
   - Edge cases (empty records, special characters, nil values)

2. **Service Tests**: Create `tests/services/export_service_test.rb` with minimum 5 test cases:
   - Create export job
   - Job status retrieval
   - Cancel export
   - List exports with filtering
   - Preview generation

3. **Integration Points**:
   - Use `Security` module for checksum computation
   - Use `Queue` module patterns for job queue
   - Register in `Contracts::SERVICE_DEFS` with port 8120

4. **Test Command**: `bundle exec rspec` or `ruby -Ilib -Itests tests/run_all.rb`

---

## General Implementation Notes

### File Structure

After implementing all tasks, the following files should exist:

```
lib/mercuryledger/core/
  snapshot.rb          # Task 1
  categorization.rb    # Task 2
  export.rb            # Task 3

services/
  snapshot/service.rb      # Task 1
  categorization/service.rb # Task 2
  export/service.rb        # Task 3

tests/unit/
  snapshot_test.rb         # Task 1
  categorization_test.rb   # Task 2
  export_test.rb           # Task 3

tests/services/
  snapshot_service_test.rb      # Task 1
  categorization_service_test.rb # Task 2
  export_service_test.rb        # Task 3
```

### Require Updates

Update `lib/mercuryledger.rb` to require new modules:

```ruby
require_relative 'mercuryledger/core/snapshot'
require_relative 'mercuryledger/core/categorization'
require_relative 'mercuryledger/core/export'
```

### Contract Registration

Add to `shared/contracts/contracts.rb`:

```ruby
CONTRACTS = {
  # ... existing contracts ...
  snapshot:       { id: 'snapshot',       port: 8118 },
  categorization: { id: 'categorization', port: 8119 },
  export:         { id: 'export',         port: 8120 }
}.freeze

SERVICE_DEFS = {
  # ... existing service defs ...
  snapshot:       ServiceDefinition.new(id: 'snapshot',       port: 8118, dependencies: %i[audit analytics]),
  categorization: ServiceDefinition.new(id: 'categorization', port: 8119, dependencies: %i[audit]),
  export:         ServiceDefinition.new(id: 'export',         port: 8120, dependencies: %i[audit security])
}.freeze
```

### Testing

Run all tests with:

```bash
bundle exec rspec
```

Or using the existing test runner:

```bash
ruby -Ilib -Itests tests/run_all.rb
```
