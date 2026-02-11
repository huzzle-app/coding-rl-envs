# DataNexus - Greenfield Implementation Tasks

## Overview

DataNexus includes 3 greenfield implementation tasks that require building entirely new services from scratch. These tasks test the ability to design and implement complex systems following established architectural patterns while maintaining integration with the existing 15-service ecosystem.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: RabbitMQ, PostgreSQL, Redis, Consul, MinIO, TimescaleDB
- **Difficulty**: Distinguished
- **Architecture Pattern**: Distributed microservices with event-driven communication

## Tasks

### Task 1: Data Quality Monitor (Greenfield Service)

Implement a Data Quality Monitor service that validates data integrity across pipelines, detects schema violations, tracks data freshness, and generates quality scorecards.

**Service Location**: `services/quality/`

**Key Interface**: `DataQualityMonitor` class with methods for:
- Schema registration and validation
- Record validation against registered schemas
- Batch validation with aggregate results
- Completeness scoring (non-null field ratio)
- Data freshness checking based on timestamps
- Statistical anomaly detection for numeric fields
- Quality scorecard generation with multiple dimensions
- Custom validation rule registration
- Historical metrics tracking

**Integration Points**:
- Validate data from ingestion service
- Publish quality events via shared/events
- Store metrics in PostgreSQL
- Cache scoring data in Redis
- Follow Express.js service pattern from existing services

**Acceptance Criteria**: 30+ unit tests covering schema validation, completeness calculation, freshness checks, anomaly detection, custom rules, and scorecard generation. Minimum 85% code coverage with integration tests.

### Task 2: Schema Evolution Manager (Greenfield Service)

Implement a Schema Evolution Manager that handles schema versioning, backward/forward compatibility checking, automatic migration generation, and schema registry synchronization.

**Service Location**: `services/schema/`

**Key Interface**: `SchemaEvolutionManager` class with methods for:
- Schema registration with version auto-increment
- Schema retrieval by subject and version
- Backward/forward compatibility checking
- Migration plan generation between versions
- Migration application to records
- Schema inference from sample data
- Schema diff computation
- Version management and deletion

**Compatibility Modes**: Support Kafka-style compatibility (BACKWARD, FORWARD, FULL, NONE)

**Integration Points**:
- Synchronize with connector service
- Publish schema change events
- Store schema definitions in PostgreSQL
- Reference connector framework patterns
- Fingerprint schemas for efficient storage

**Acceptance Criteria**: 35+ unit tests covering schema registration, compatibility checking, migration generation, schema inference, and diff computation. Tests must validate edge cases for nested schemas, arrays, and unions. Minimum 85% code coverage with integration tests.

### Task 3: Pipeline Orchestration Engine (Greenfield Service)

Implement a Pipeline Orchestration Engine that manages complex multi-stage data pipelines, handles branching and merging flows, provides retry/recovery mechanisms, and tracks pipeline execution state.

**Service Location**: `services/orchestrator/`

**Key Interface**: `PipelineOrchestrator` class with methods for:
- Pipeline definition registration
- Pipeline execution startup with initial context
- Execution state tracking and retrieval
- Pause/resume functionality for running pipelines
- Cancellation with cleanup
- Stage retry with configurable backoff
- Branching logic (fan-out to parallel branches)
- Merging logic (fan-in with configurable strategies)
- Checkpoint creation and recovery
- Execution history and metrics

**Pipeline Features**:
- Linear stage sequences (A -> B -> C)
- Branching with parallel execution
- Merging with different strategies (CONCAT, REDUCE, FIRST, CUSTOM)
- Configurable retry policies (FIXED, LINEAR, EXPONENTIAL backoff)
- Timeout handling per stage and overall pipeline
- Concurrent execution limits

**Integration Points**:
- Reference DAGExecutor patterns from scheduler service
- Use transform, aggregate, and connector services as stage handlers
- Implement checkpointing using Map-based storage
- Publish execution events via shared/events
- Respect concurrency control limits

**Acceptance Criteria**: 40+ unit tests covering linear execution, branching/merging, retry logic, pause/resume, cancellation, checkpointing, and timeout handling. Tests must validate concurrent execution limits and edge cases. Minimum 85% code coverage with integration tests covering end-to-end pipelines with transform and connector stages.

## Getting Started

```bash
cd js/datanexus

# Start infrastructure and services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run tests
npm test

# Run tests with coverage
npm test -- --coverage
```

## Service Implementation Guidelines

### Code Structure

Each service should follow this pattern:
```
services/<service-name>/
├── src/
│   ├── index.js           # Express app setup
│   ├── config.js          # Service configuration (environment-based)
│   ├── routes/
│   │   └── index.js       # REST API routes
│   └── services/
│       └── <core>.js      # Core business logic
├── tests/
│   ├── unit/              # Unit tests with mocks
│   └── integration/       # Integration tests
└── package.json           # Service dependencies
```

### Configuration Pattern

Follow environment-based configuration:
```javascript
module.exports = {
  port: parseInt(process.env.PORT || '3015', 10),
  serviceName: 'quality',
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
  },
  postgres: {
    host: process.env.PG_HOST || 'localhost',
    port: parseInt(process.env.PG_PORT || '5432', 10),
  },
};
```

### Integration Points

All services must integrate with:
- `shared/events` - Event bus for inter-service communication
- `shared/clients` - Service client utilities
- `shared/stream` - Stream processing utilities (where applicable)

### Testing Standards

- Use Jest test framework (existing `jest.config.js`)
- Test file naming: `*.test.js`
- Group tests with `describe()` blocks by feature
- Use `beforeEach`/`afterEach` for setup/teardown
- Mock external dependencies (Redis, RabbitMQ, Postgres)
- Target 85% minimum code coverage

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).

Each service:
1. Implements all required interface methods with proper JSDoc documentation
2. Includes 30-40+ unit tests with 85%+ coverage
3. Includes 10-15+ integration tests
4. Follows existing service architecture patterns
5. Integrates properly with shared modules and existing services
6. Handles all specified edge cases and error conditions
7. Maintains backward compatibility (where applicable)
