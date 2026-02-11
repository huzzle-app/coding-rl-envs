# MercuryLedger - Greenfield Tasks

## Overview

Three greenfield implementation tasks that build new modules from scratch for the MercuryLedger settlement platform. These tasks test ability to design and implement new services following existing architectural patterns, with provided Ruby interface contracts.

## Environment

- **Language**: Ruby 3.2
- **Infrastructure**: Docker Compose, Minitest, 8 interconnected services, 9 core modules
- **Difficulty**: Hyper-Principal (50-80 hours estimated for all three tasks)

## Tasks

### Task 1: Balance Snapshot Service (Greenfield Implementation)

Implement a new Balance Snapshot Service that captures point-in-time balance snapshots across ledger accounts. The service must support scheduled snapshots, on-demand captures, differential comparisons between snapshots, and rollback capabilities for auditing. Includes snapshot storage with retention policies, digest computation for integrity verification, and batch operations.

**Core Modules**:
- `Snapshot` — Struct for point-in-time balance capture with timestamp, account_id, balance, currency, metadata
- `SnapshotDiff` — Struct for computed differences between snapshots with percentage_change
- `SnapshotEngine` — Stateless module for capture, batch operations, validation, digest computation
- `SnapshotStore` — Thread-safe storage with latest/range/count/prune operations and retention limits
- `SnapshotComparator` — Comparison logic for single/batch diffs and significant change detection

**Service Layer**:
- `Services::Snapshot` — Service module with schedule_capture, history_summary, balance_trend

**Integration Points**:
- Use `Statistics.mean` and `Statistics.variance` for trend volatility
- Use `Security` module digest pattern for SHA-256 checksums
- Register in `Contracts::SERVICE_DEFS` with port 8118

**Test Requirements**: Minimum 15 unit tests + 4 service tests covering single/batch operations, validation, diffs, significant changes

### Task 2: Transaction Categorization Engine (Greenfield Implementation)

Implement a Transaction Categorization Engine that automatically classifies ledger transactions into configurable categories. The engine must support rule-based matching with configurable operators (eq, neq, gt, gte, lt, lte, contains, starts_with, ends_with, regex), category hierarchies, bulk categorization, and conflict resolution strategies.

**Core Modules**:
- `CategoryRule` — Struct for rule definition with conditions, priority, enabled flag
- `CategoryResult` — Struct for categorization result with confidence score and matched rule
- `CategorizationEngine` — Stateless module for condition evaluation, rule matching, single/batch categorization, validation
- `CategoryHierarchy` — Tree structure for category relationships with ancestors/descendants/depth operations
- `RuleStore` — Thread-safe rule storage with priority ordering and category filtering
- `ConflictResolver` — Module for handling multi-rule matches with strategy selection (highest_priority, highest_confidence, first)

**Service Layer**:
- `Services::Categorization` — Service module with categorize_transaction, bulk_categorize, suggest_category, accuracy_report

**Integration Points**:
- Use operator constant definitions similar to `Resilience` module
- Follow `Policy` module escalation patterns for rule evaluation
- Use `Statistics.mean` for confidence averaging
- Register in `Contracts::SERVICE_DEFS` with port 8119

**Test Requirements**: Minimum 20 unit tests (all operators, multi-condition rules, hierarchy operations, conflict resolution) + 4 service tests

### Task 3: Ledger Export Service (Greenfield Implementation)

Implement a Ledger Export Service that generates exports of ledger data in multiple formats (CSV, JSON, XML). The service must support filtering, field selection, streaming for large exports, checksums for integrity verification, and configurable scheduling.

**Core Modules**:
- `ExportFormat` — Module with CSV/JSON/XML constants and valid? validation
- `ExportJob` — Struct for job configuration with format, filters, fields, status tracking
- `ExportResult` — Struct for export metadata with row_count, byte_size, checksum, duration_ms
- `ExportEngine` — Stateless module for filtering, field selection, format conversion (CSV/JSON/XML), checksum computation
- `ExportJobQueue` — Thread-safe queue for job management with enqueue/dequeue/find/update_status/stats/cleanup
- `StreamingExporter` — Chunked export handler for write_header/write_chunk/write_footer with byte/record counters

**Service Layer**:
- `Services::Export` — Service module with create_export, job_status, cancel_export, list_exports, preview_export

**Integration Points**:
- Use `Security` module SHA-256 pattern for checksums
- Follow `Queue` module patterns for job queue with mutex protection
- Use symbol states similar to `CircuitBreaker` for FSM
- Register in `Contracts::SERVICE_DEFS` with port 8120

**Test Requirements**: Minimum 18 unit tests (filtering, field selection, format generation, checksums, queue operations, streaming) + 5 service tests

## Getting Started

```bash
cd ruby/mercuryledger
bundle exec rspec
```

Or using the standard test runner:

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Success Criteria

Implementation of all three greenfield tasks meets the acceptance criteria and interface contracts defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). Each implementation:
- Follows the provided Ruby interface contract exactly
- Uses existing architectural patterns (Mutex for thread safety, module_function for stateless operations, Struct.new with keyword_init for data objects)
- Includes comprehensive unit and service test coverage
- Integrates with existing core modules (Statistics, Security, Queue patterns)
- Registers in the service contracts system
