# DataNexus - Greenfield Implementation Tasks

This document defines greenfield tasks for implementing **new modules from scratch** in the DataNexus data pipeline platform. Each task requires following existing architectural patterns while building entirely new functionality.

---

## Task 1: Data Quality Monitor

### Overview

Implement a Data Quality Monitor service that validates data integrity across pipelines, detects schema violations, tracks data freshness, and generates quality scorecards.

### Module Location

```
services/quality/
├── src/
│   ├── index.js           # Express app setup
│   ├── config.js          # Service configuration
│   ├── routes/
│   │   └── index.js       # REST API routes
│   └── services/
│       └── monitor.js     # Core quality monitoring logic
```

### Interface Contract

```javascript
/**
 * Data Quality Monitor
 *
 * Validates data integrity, detects anomalies, and generates quality scores.
 */

class DataQualityMonitor {
  /**
   * @param {Object} options - Configuration options
   * @param {number} options.freshnessThresholdMs - Max age for data to be considered fresh (default: 300000)
   * @param {number} options.completenessThreshold - Min percentage of non-null fields (default: 0.95)
   * @param {number} options.windowSizeMs - Time window for quality calculations (default: 60000)
   */
  constructor(options = {}) {}

  /**
   * Register a schema for a data source
   * @param {string} sourceId - Unique identifier for the data source
   * @param {Object} schema - JSON Schema definition
   * @param {Object} schema.properties - Field definitions with types and constraints
   * @param {string[]} schema.required - Required field names
   * @returns {void}
   */
  registerSchema(sourceId, schema) {}

  /**
   * Validate a single record against its registered schema
   * @param {string} sourceId - Data source identifier
   * @param {Object} record - Data record to validate
   * @returns {ValidationResult}
   */
  validateRecord(sourceId, record) {}

  /**
   * Validate a batch of records and return aggregate results
   * @param {string} sourceId - Data source identifier
   * @param {Object[]} records - Array of data records
   * @returns {BatchValidationResult}
   */
  validateBatch(sourceId, records) {}

  /**
   * Calculate completeness score for a record (non-null field ratio)
   * @param {Object} record - Data record
   * @param {string[]} requiredFields - Fields that must be present
   * @returns {number} Score between 0.0 and 1.0
   */
  calculateCompleteness(record, requiredFields) {}

  /**
   * Check data freshness based on timestamp field
   * @param {Object} record - Data record with timestamp
   * @param {string} timestampField - Name of the timestamp field
   * @returns {FreshnessResult}
   */
  checkFreshness(record, timestampField) {}

  /**
   * Detect statistical anomalies in numeric fields
   * @param {string} sourceId - Data source identifier
   * @param {string} fieldName - Numeric field to analyze
   * @param {number} value - Current value to check
   * @returns {AnomalyResult}
   */
  detectAnomaly(sourceId, fieldName, value) {}

  /**
   * Generate a quality scorecard for a data source
   * @param {string} sourceId - Data source identifier
   * @returns {QualityScorecard}
   */
  generateScorecard(sourceId) {}

  /**
   * Register a custom validation rule
   * @param {string} ruleId - Unique rule identifier
   * @param {string} sourceId - Data source to apply rule to
   * @param {Function} validator - Function(record) => boolean
   * @param {string} description - Human-readable rule description
   * @returns {void}
   */
  addCustomRule(ruleId, sourceId, validator, description) {}

  /**
   * Get historical quality metrics for a source
   * @param {string} sourceId - Data source identifier
   * @param {number} fromTimestamp - Start of time range
   * @param {number} toTimestamp - End of time range
   * @returns {QualityMetrics[]}
   */
  getHistoricalMetrics(sourceId, fromTimestamp, toTimestamp) {}

  /**
   * Clear all state for testing
   * @returns {void}
   */
  clearState() {}
}

module.exports = { DataQualityMonitor };
```

### Data Structures

```javascript
/**
 * @typedef {Object} ValidationResult
 * @property {boolean} valid - Whether the record passed validation
 * @property {ValidationError[]} errors - List of validation errors
 * @property {number} timestamp - Validation timestamp
 */

/**
 * @typedef {Object} ValidationError
 * @property {string} field - Field that failed validation
 * @property {string} rule - Rule that was violated
 * @property {string} message - Human-readable error message
 * @property {*} actualValue - The value that failed
 * @property {*} expectedValue - What was expected (if applicable)
 */

/**
 * @typedef {Object} BatchValidationResult
 * @property {number} totalRecords - Total records in batch
 * @property {number} validRecords - Number of valid records
 * @property {number} invalidRecords - Number of invalid records
 * @property {number} validationRate - Percentage of valid records (0.0-1.0)
 * @property {Object.<string, number>} errorsByField - Error count per field
 * @property {Object.<string, number>} errorsByRule - Error count per rule
 */

/**
 * @typedef {Object} FreshnessResult
 * @property {boolean} isFresh - Whether data is within freshness threshold
 * @property {number} ageMs - Age of the data in milliseconds
 * @property {number} thresholdMs - Configured freshness threshold
 */

/**
 * @typedef {Object} AnomalyResult
 * @property {boolean} isAnomaly - Whether the value is anomalous
 * @property {number} zScore - Standard deviations from mean
 * @property {number} mean - Historical mean
 * @property {number} stddev - Historical standard deviation
 * @property {string} severity - 'low' | 'medium' | 'high' based on z-score
 */

/**
 * @typedef {Object} QualityScorecard
 * @property {string} sourceId - Data source identifier
 * @property {number} timestamp - Scorecard generation time
 * @property {number} overallScore - Weighted quality score (0.0-1.0)
 * @property {Object} dimensions - Quality dimension scores
 * @property {number} dimensions.completeness - Non-null field ratio
 * @property {number} dimensions.validity - Schema conformance rate
 * @property {number} dimensions.freshness - Data freshness score
 * @property {number} dimensions.consistency - Cross-field consistency
 * @property {number} recordsEvaluated - Number of records in evaluation window
 * @property {string[]} topIssues - Most common quality issues
 */

/**
 * @typedef {Object} QualityMetrics
 * @property {number} timestamp - Metric timestamp
 * @property {number} completeness - Completeness score
 * @property {number} validity - Validity score
 * @property {number} freshness - Freshness score
 * @property {number} recordCount - Records evaluated
 */
```

### Architectural Requirements

1. **Follow existing service patterns**: Use Express.js app structure matching `services/alerts/`
2. **Integrate with shared modules**: Use `shared/events` for publishing quality events
3. **State management**: Use Map-based state storage like `AlertDetector`
4. **Configuration**: Use environment-based config like `services/*/src/config.js`

### Acceptance Criteria

1. **Unit Tests** (30+ tests in `tests/unit/quality/monitor.test.js`):
   - Schema registration and validation
   - Completeness calculation with edge cases (null, undefined, empty string)
   - Freshness checks with timezone handling
   - Anomaly detection with statistical accuracy
   - Custom rule registration and execution
   - Scorecard generation with weighted dimensions

2. **Integration Tests** (10+ tests in `tests/integration/quality.test.js`):
   - End-to-end pipeline quality monitoring
   - Integration with ingestion service
   - Quality event publishing

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - All public methods tested
   - Edge cases for numeric overflow, empty inputs, missing fields

4. **Test Command**: `npm test`

---

## Task 2: Schema Evolution Manager

### Overview

Implement a Schema Evolution Manager that handles schema versioning, backward/forward compatibility checking, automatic migration generation, and schema registry synchronization.

### Module Location

```
services/schema/
├── src/
│   ├── index.js           # Express app setup
│   ├── config.js          # Service configuration
│   ├── routes/
│   │   └── index.js       # REST API routes
│   └── services/
│       └── evolution.js   # Core schema evolution logic
```

### Interface Contract

```javascript
/**
 * Schema Evolution Manager
 *
 * Manages schema versions, compatibility, and migrations.
 */

class SchemaEvolutionManager {
  /**
   * @param {Object} options - Configuration options
   * @param {string} options.compatibilityMode - 'BACKWARD' | 'FORWARD' | 'FULL' | 'NONE'
   * @param {number} options.maxVersions - Maximum versions to retain per subject (default: 100)
   */
  constructor(options = {}) {}

  /**
   * Register a new schema version
   * @param {string} subject - Schema subject (e.g., 'user-events')
   * @param {Object} schema - JSON Schema definition
   * @returns {SchemaRegistration}
   * @throws {CompatibilityError} If schema violates compatibility mode
   */
  registerSchema(subject, schema) {}

  /**
   * Get schema by subject and version
   * @param {string} subject - Schema subject
   * @param {number} version - Schema version (use -1 for latest)
   * @returns {Schema|null}
   */
  getSchema(subject, version) {}

  /**
   * Get all versions for a subject
   * @param {string} subject - Schema subject
   * @returns {number[]} Array of version numbers
   */
  getVersions(subject) {}

  /**
   * Check if a new schema is compatible with existing versions
   * @param {string} subject - Schema subject
   * @param {Object} newSchema - Proposed new schema
   * @returns {CompatibilityResult}
   */
  checkCompatibility(subject, newSchema) {}

  /**
   * Check backward compatibility (new schema can read old data)
   * @param {Object} oldSchema - Previous schema version
   * @param {Object} newSchema - New schema version
   * @returns {CompatibilityCheckResult}
   */
  isBackwardCompatible(oldSchema, newSchema) {}

  /**
   * Check forward compatibility (old schema can read new data)
   * @param {Object} oldSchema - Previous schema version
   * @param {Object} newSchema - New schema version
   * @returns {CompatibilityCheckResult}
   */
  isForwardCompatible(oldSchema, newSchema) {}

  /**
   * Generate migration function between schema versions
   * @param {string} subject - Schema subject
   * @param {number} fromVersion - Source version
   * @param {number} toVersion - Target version
   * @returns {MigrationPlan}
   */
  generateMigration(subject, fromVersion, toVersion) {}

  /**
   * Apply migration to a record
   * @param {Object} record - Data record to migrate
   * @param {MigrationPlan} migration - Migration plan to apply
   * @returns {Object} Migrated record
   */
  applyMigration(record, migration) {}

  /**
   * Detect schema from sample data
   * @param {Object[]} samples - Sample records
   * @returns {Object} Inferred JSON Schema
   */
  inferSchema(samples) {}

  /**
   * Compute diff between two schemas
   * @param {Object} schemaA - First schema
   * @param {Object} schemaB - Second schema
   * @returns {SchemaDiff}
   */
  diffSchemas(schemaA, schemaB) {}

  /**
   * Delete a specific schema version
   * @param {string} subject - Schema subject
   * @param {number} version - Version to delete
   * @returns {boolean} Success status
   */
  deleteVersion(subject, version) {}

  /**
   * Clear all schemas for testing
   * @returns {void}
   */
  clearAll() {}
}

module.exports = { SchemaEvolutionManager };
```

### Data Structures

```javascript
/**
 * @typedef {Object} SchemaRegistration
 * @property {string} subject - Schema subject
 * @property {number} version - Assigned version number
 * @property {string} schemaId - Unique schema identifier
 * @property {string} fingerprint - Schema content hash
 * @property {number} registeredAt - Registration timestamp
 */

/**
 * @typedef {Object} Schema
 * @property {string} subject - Schema subject
 * @property {number} version - Schema version
 * @property {Object} definition - JSON Schema definition
 * @property {string} fingerprint - Content hash
 * @property {number} createdAt - Creation timestamp
 */

/**
 * @typedef {Object} CompatibilityResult
 * @property {boolean} compatible - Whether schema is compatible
 * @property {string} mode - Compatibility mode used
 * @property {CompatibilityViolation[]} violations - List of violations
 */

/**
 * @typedef {Object} CompatibilityViolation
 * @property {string} type - 'FIELD_REMOVED' | 'TYPE_CHANGED' | 'REQUIRED_ADDED' | etc.
 * @property {string} field - Affected field path (e.g., 'user.address.zip')
 * @property {string} message - Human-readable description
 * @property {string} severity - 'ERROR' | 'WARNING'
 */

/**
 * @typedef {Object} CompatibilityCheckResult
 * @property {boolean} compatible - Whether schemas are compatible
 * @property {string[]} addedFields - New optional fields
 * @property {string[]} removedFields - Removed fields
 * @property {Object.<string, TypeChange>} typeChanges - Field type changes
 */

/**
 * @typedef {Object} TypeChange
 * @property {string} from - Original type
 * @property {string} to - New type
 * @property {boolean} compatible - Whether change is compatible
 */

/**
 * @typedef {Object} MigrationPlan
 * @property {string} subject - Schema subject
 * @property {number} fromVersion - Source version
 * @property {number} toVersion - Target version
 * @property {MigrationStep[]} steps - Ordered migration steps
 * @property {boolean} reversible - Whether migration can be reversed
 */

/**
 * @typedef {Object} MigrationStep
 * @property {string} operation - 'ADD_FIELD' | 'REMOVE_FIELD' | 'RENAME_FIELD' | 'CAST_TYPE' | 'SET_DEFAULT'
 * @property {string} field - Target field path
 * @property {*} value - Value for operation (default value, new name, etc.)
 * @property {Function} transform - Transformation function if needed
 */

/**
 * @typedef {Object} SchemaDiff
 * @property {string[]} addedFields - Fields in B but not A
 * @property {string[]} removedFields - Fields in A but not B
 * @property {string[]} modifiedFields - Fields with type/constraint changes
 * @property {Object.<string, FieldDiff>} fieldDiffs - Detailed per-field diffs
 */

/**
 * @typedef {Object} FieldDiff
 * @property {string} path - Field path
 * @property {*} oldValue - Value in schema A
 * @property {*} newValue - Value in schema B
 * @property {string} changeType - 'TYPE' | 'CONSTRAINT' | 'DEFAULT' | 'REQUIRED'
 */
```

### Architectural Requirements

1. **Follow connector registry patterns**: Reference `ConnectorSchemaRegistry` in `services/connectors/`
2. **Version management**: Implement proper version numbering with fingerprinting
3. **Compatibility modes**: Support Kafka-style compatibility (BACKWARD, FORWARD, FULL, NONE)
4. **Event integration**: Publish schema change events via `shared/events`

### Acceptance Criteria

1. **Unit Tests** (35+ tests in `tests/unit/schema/evolution.test.js`):
   - Schema registration with version auto-increment
   - Backward compatibility: adding optional fields, widening types
   - Forward compatibility: removing optional fields, narrowing types
   - Full compatibility: bidirectional checks
   - Migration generation for field additions, removals, renames
   - Schema inference from sample data
   - Diff computation accuracy

2. **Integration Tests** (10+ tests in `tests/integration/schema.test.js`):
   - Integration with connectors service
   - Schema evolution during live pipeline
   - Migration application to streaming data

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - All compatibility rules tested
   - Edge cases for nested schemas, arrays, unions

4. **Test Command**: `npm test`

---

## Task 3: Pipeline Orchestration Engine

### Overview

Implement a Pipeline Orchestration Engine that manages complex multi-stage data pipelines, handles branching and merging flows, provides retry/recovery mechanisms, and tracks pipeline execution state.

### Module Location

```
services/orchestrator/
├── src/
│   ├── index.js           # Express app setup
│   ├── config.js          # Service configuration
│   ├── routes/
│   │   └── index.js       # REST API routes
│   └── services/
│       └── orchestrator.js # Core orchestration logic
```

### Interface Contract

```javascript
/**
 * Pipeline Orchestration Engine
 *
 * Manages multi-stage pipeline execution with branching, merging, and recovery.
 */

class PipelineOrchestrator {
  /**
   * @param {Object} options - Configuration options
   * @param {number} options.maxConcurrentPipelines - Max parallel pipeline executions (default: 10)
   * @param {number} options.defaultTimeoutMs - Default stage timeout (default: 300000)
   * @param {Object} options.retryPolicy - Default retry configuration
   */
  constructor(options = {}) {}

  /**
   * Register a pipeline definition
   * @param {string} pipelineId - Unique pipeline identifier
   * @param {PipelineDefinition} definition - Pipeline structure
   * @returns {void}
   */
  registerPipeline(pipelineId, definition) {}

  /**
   * Start a pipeline execution
   * @param {string} pipelineId - Pipeline to execute
   * @param {Object} context - Initial context/input data
   * @returns {PipelineExecution}
   */
  async startPipeline(pipelineId, context) {}

  /**
   * Get current execution state
   * @param {string} executionId - Execution identifier
   * @returns {ExecutionState|null}
   */
  getExecutionState(executionId) {}

  /**
   * Pause a running pipeline
   * @param {string} executionId - Execution to pause
   * @returns {boolean} Success status
   */
  async pausePipeline(executionId) {}

  /**
   * Resume a paused pipeline
   * @param {string} executionId - Execution to resume
   * @returns {boolean} Success status
   */
  async resumePipeline(executionId) {}

  /**
   * Cancel a pipeline execution
   * @param {string} executionId - Execution to cancel
   * @param {string} reason - Cancellation reason
   * @returns {boolean} Success status
   */
  async cancelPipeline(executionId, reason) {}

  /**
   * Retry a failed stage
   * @param {string} executionId - Execution identifier
   * @param {string} stageId - Stage to retry
   * @returns {StageResult}
   */
  async retryStage(executionId, stageId) {}

  /**
   * Execute a single stage (internal)
   * @param {Stage} stage - Stage definition
   * @param {Object} context - Execution context
   * @returns {StageResult}
   */
  async executeStage(stage, context) {}

  /**
   * Handle branching logic (fan-out)
   * @param {BranchStage} branchStage - Branch definition
   * @param {Object} context - Current context
   * @returns {BranchResult[]}
   */
  async executeBranch(branchStage, context) {}

  /**
   * Handle merging logic (fan-in)
   * @param {MergeStage} mergeStage - Merge definition
   * @param {Object[]} branchResults - Results from branches
   * @returns {Object} Merged context
   */
  async executeMerge(mergeStage, branchResults) {}

  /**
   * Apply checkpoint for recovery
   * @param {string} executionId - Execution identifier
   * @param {string} stageId - Stage identifier
   * @param {Object} state - State to checkpoint
   * @returns {void}
   */
  checkpoint(executionId, stageId, state) {}

  /**
   * Recover from last checkpoint
   * @param {string} executionId - Execution to recover
   * @returns {ExecutionState|null}
   */
  recoverFromCheckpoint(executionId) {}

  /**
   * Get execution history for a pipeline
   * @param {string} pipelineId - Pipeline identifier
   * @param {number} limit - Max results (default: 100)
   * @returns {ExecutionSummary[]}
   */
  getExecutionHistory(pipelineId, limit) {}

  /**
   * Get metrics for a pipeline
   * @param {string} pipelineId - Pipeline identifier
   * @returns {PipelineMetrics}
   */
  getPipelineMetrics(pipelineId) {}

  /**
   * Clear all state for testing
   * @returns {void}
   */
  clearAll() {}
}

module.exports = { PipelineOrchestrator };
```

### Data Structures

```javascript
/**
 * @typedef {Object} PipelineDefinition
 * @property {string} id - Pipeline identifier
 * @property {string} name - Human-readable name
 * @property {Stage[]} stages - Ordered list of stages
 * @property {Object} defaultContext - Default context values
 * @property {RetryPolicy} retryPolicy - Default retry configuration
 * @property {number} timeoutMs - Overall pipeline timeout
 */

/**
 * @typedef {Object} Stage
 * @property {string} id - Stage identifier
 * @property {string} type - 'TRANSFORM' | 'BRANCH' | 'MERGE' | 'CONNECTOR' | 'AGGREGATE'
 * @property {Function} handler - Stage execution function
 * @property {string[]} dependsOn - IDs of stages that must complete first
 * @property {number} timeoutMs - Stage-specific timeout
 * @property {RetryPolicy} retryPolicy - Stage-specific retry config
 * @property {Object} config - Stage-specific configuration
 */

/**
 * @typedef {Object} BranchStage
 * @property {string} id - Branch stage identifier
 * @property {string} type - Always 'BRANCH'
 * @property {Function} condition - Function(context) => string[] (branch IDs to execute)
 * @property {Object.<string, Stage[]>} branches - Map of branch ID to stages
 * @property {boolean} parallel - Execute branches in parallel (default: true)
 */

/**
 * @typedef {Object} MergeStage
 * @property {string} id - Merge stage identifier
 * @property {string} type - Always 'MERGE'
 * @property {string} strategy - 'CONCAT' | 'REDUCE' | 'FIRST' | 'CUSTOM'
 * @property {Function} reducer - Custom merge function (for CUSTOM strategy)
 * @property {string[]} awaitBranches - Branch IDs to wait for
 */

/**
 * @typedef {Object} RetryPolicy
 * @property {number} maxRetries - Maximum retry attempts
 * @property {number} baseDelayMs - Initial delay between retries
 * @property {number} maxDelayMs - Maximum delay (for exponential backoff)
 * @property {string} backoffType - 'FIXED' | 'LINEAR' | 'EXPONENTIAL'
 * @property {string[]} retryableErrors - Error types that trigger retry
 */

/**
 * @typedef {Object} PipelineExecution
 * @property {string} executionId - Unique execution identifier
 * @property {string} pipelineId - Pipeline being executed
 * @property {string} status - 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
 * @property {number} startedAt - Execution start timestamp
 * @property {number} completedAt - Execution completion timestamp (if done)
 * @property {Object} context - Current execution context
 */

/**
 * @typedef {Object} ExecutionState
 * @property {string} executionId - Execution identifier
 * @property {string} pipelineId - Pipeline identifier
 * @property {string} status - Current status
 * @property {string} currentStageId - Currently executing stage
 * @property {Object.<string, StageState>} stageStates - Per-stage state
 * @property {Object} context - Current context
 * @property {number} startedAt - Start timestamp
 * @property {number} updatedAt - Last update timestamp
 */

/**
 * @typedef {Object} StageState
 * @property {string} stageId - Stage identifier
 * @property {string} status - 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED'
 * @property {number} attempts - Number of execution attempts
 * @property {number} startedAt - Stage start timestamp
 * @property {number} completedAt - Stage completion timestamp
 * @property {*} result - Stage output (if completed)
 * @property {string} error - Error message (if failed)
 */

/**
 * @typedef {Object} StageResult
 * @property {boolean} success - Whether stage completed successfully
 * @property {*} output - Stage output data
 * @property {string} error - Error message if failed
 * @property {number} durationMs - Execution duration
 * @property {number} attempts - Number of attempts made
 */

/**
 * @typedef {Object} BranchResult
 * @property {string} branchId - Branch identifier
 * @property {boolean} success - Whether branch completed
 * @property {Object} context - Branch output context
 * @property {StageResult[]} stageResults - Results from branch stages
 */

/**
 * @typedef {Object} ExecutionSummary
 * @property {string} executionId - Execution identifier
 * @property {string} status - Final status
 * @property {number} startedAt - Start timestamp
 * @property {number} completedAt - Completion timestamp
 * @property {number} durationMs - Total duration
 * @property {number} stagesCompleted - Number of stages completed
 * @property {number} stagesFailed - Number of stages that failed
 */

/**
 * @typedef {Object} PipelineMetrics
 * @property {string} pipelineId - Pipeline identifier
 * @property {number} totalExecutions - Total execution count
 * @property {number} successfulExecutions - Successful execution count
 * @property {number} failedExecutions - Failed execution count
 * @property {number} averageDurationMs - Average execution duration
 * @property {number} p95DurationMs - 95th percentile duration
 * @property {Object.<string, StageMetrics>} stageMetrics - Per-stage metrics
 */

/**
 * @typedef {Object} StageMetrics
 * @property {string} stageId - Stage identifier
 * @property {number} executionCount - Total executions
 * @property {number} successRate - Success rate (0.0-1.0)
 * @property {number} averageDurationMs - Average duration
 * @property {number} retryRate - Percentage requiring retry
 */
```

### Architectural Requirements

1. **Follow DAG executor patterns**: Reference `DAGExecutor` in `services/scheduler/src/services/dag.js`
2. **Integrate with existing services**: Use transform, aggregate, and connector services as stage handlers
3. **State persistence**: Implement checkpointing using Map-based storage (can be extended to Redis)
4. **Event-driven**: Publish execution events via `shared/events`
5. **Concurrency control**: Respect `maxConcurrentPipelines` limit

### Acceptance Criteria

1. **Unit Tests** (40+ tests in `tests/unit/orchestrator/pipeline.test.js`):
   - Pipeline registration and validation
   - Linear pipeline execution (A -> B -> C)
   - Branching execution (fan-out to parallel branches)
   - Merging execution (fan-in with different strategies)
   - Retry logic with exponential backoff
   - Pause/resume functionality
   - Cancellation with cleanup
   - Checkpoint creation and recovery
   - Timeout handling per stage and overall
   - Concurrent execution limits

2. **Integration Tests** (15+ tests in `tests/integration/orchestrator.test.js`):
   - End-to-end pipeline with transform stages
   - Integration with connector service
   - Integration with aggregate service
   - Recovery after simulated failure

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - All execution paths tested (success, failure, timeout, cancel)
   - Edge cases for empty pipelines, circular dependencies, max retries

4. **Test Command**: `npm test`

---

## General Requirements for All Tasks

### Code Style

- Use ES6+ features (async/await, destructuring, arrow functions)
- Follow existing JSDoc documentation patterns
- Use descriptive variable names
- Handle errors with try/catch and appropriate error types

### Testing Standards

- Use Jest test framework (existing `jest.config.js`)
- Test file naming: `*.test.js`
- Group tests with `describe()` blocks by feature
- Use `beforeEach`/`afterEach` for setup/teardown
- Mock external dependencies (Redis, RabbitMQ, Postgres)

### Integration Points

All new services must integrate with:
- `shared/events` - Event bus for inter-service communication
- `shared/clients` - Service client utilities
- `shared/stream` - Stream processing utilities (where applicable)

### Environment Configuration

Follow existing pattern in `services/*/src/config.js`:
```javascript
module.exports = {
  port: parseInt(process.env.PORT || '3015', 10),
  serviceName: 'quality', // or 'schema', 'orchestrator'
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
  },
  // ... service-specific config
};
```

### Running Tests

```bash
# Install dependencies
npm install

# Run all tests
npm test

# Run specific test file
npm test -- tests/unit/quality/monitor.test.js

# Run with coverage
npm test -- --coverage
```
