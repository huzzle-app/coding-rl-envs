# NimbusFlow Greenfield Tasks

This document defines greenfield implementation tasks for extending NimbusFlow's cloud workflow platform. Each task requires implementing a new module from scratch while following existing architectural patterns.

**Test Command:** `mvn test`

---

## Task 1: Workflow Debugger Service

### Overview

Implement a `WorkflowDebugger` service that provides runtime inspection and debugging capabilities for workflow executions. This service enables operators to trace workflow state, identify bottlenecks, and diagnose failed transitions in the dispatch pipeline.

### Interface Contract

Create `src/main/kotlin/com/terminalbench/nimbusflow/Debugger.kt`:

```kotlin
package com.terminalbench.nimbusflow

/**
 * Represents a single step in a workflow execution trace.
 *
 * @property stepId Unique identifier for this trace step
 * @property entityId The entity being traced (vessel, order, etc.)
 * @property fromState State before the transition
 * @property toState State after the transition
 * @property timestamp Unix timestamp in milliseconds
 * @property durationMs Time spent in the fromState before transition
 * @property metadata Optional key-value pairs with additional context
 */
data class TraceStep(
    val stepId: String,
    val entityId: String,
    val fromState: String,
    val toState: String,
    val timestamp: Long,
    val durationMs: Long,
    val metadata: Map<String, String>
)

/**
 * Aggregated trace for a complete workflow execution.
 *
 * @property traceId Unique trace identifier
 * @property entityId The entity this trace belongs to
 * @property steps Ordered list of trace steps
 * @property startTimestamp When the trace began
 * @property endTimestamp When the trace ended (null if still active)
 * @property isComplete Whether the workflow reached a terminal state
 */
data class WorkflowTrace(
    val traceId: String,
    val entityId: String,
    val steps: List<TraceStep>,
    val startTimestamp: Long,
    val endTimestamp: Long?,
    val isComplete: Boolean
)

/**
 * Result of a bottleneck analysis.
 *
 * @property state The state identified as a bottleneck
 * @property avgDurationMs Average time entities spend in this state
 * @property maxDurationMs Maximum observed duration in this state
 * @property entityCount Number of entities that passed through this state
 * @property percentageOfTotal Percentage of total workflow time spent here
 */
data class BottleneckAnalysis(
    val state: String,
    val avgDurationMs: Double,
    val maxDurationMs: Long,
    val entityCount: Int,
    val percentageOfTotal: Double
)

/**
 * Diagnostic report for a failed transition.
 *
 * @property entityId Entity that failed to transition
 * @property attemptedTransition The transition that was attempted (from -> to)
 * @property failureReason Human-readable explanation of the failure
 * @property timestamp When the failure occurred
 * @property suggestedResolution Recommended action to resolve the issue
 */
data class TransitionFailure(
    val entityId: String,
    val attemptedTransition: Pair<String, String>,
    val failureReason: String,
    val timestamp: Long,
    val suggestedResolution: String
)

/**
 * Service for debugging and tracing workflow executions.
 *
 * Thread-safe implementation required using ReentrantLock.
 */
interface WorkflowDebuggerService {
    /**
     * Starts tracing a workflow entity.
     *
     * @param entityId The entity to trace
     * @return The trace ID for this trace session
     */
    fun startTrace(entityId: String): String

    /**
     * Records a transition step in an active trace.
     *
     * @param traceId The active trace ID
     * @param step The trace step to record
     * @return true if recorded successfully, false if trace not found
     */
    fun recordStep(traceId: String, step: TraceStep): Boolean

    /**
     * Ends a trace session and marks it complete.
     *
     * @param traceId The trace to end
     * @param endTimestamp The completion timestamp
     * @return The completed trace, or null if not found
     */
    fun endTrace(traceId: String, endTimestamp: Long): WorkflowTrace?

    /**
     * Retrieves a trace by its ID.
     *
     * @param traceId The trace ID to look up
     * @return The trace, or null if not found
     */
    fun getTrace(traceId: String): WorkflowTrace?

    /**
     * Gets all traces for a specific entity.
     *
     * @param entityId The entity ID to look up
     * @return List of traces for this entity, ordered by start time descending
     */
    fun getTracesForEntity(entityId: String): List<WorkflowTrace>

    /**
     * Analyzes traces to identify bottleneck states.
     *
     * @param traces List of traces to analyze
     * @param topN Number of top bottlenecks to return
     * @return List of bottleneck analyses, ordered by avgDurationMs descending
     */
    fun analyzeBottlenecks(traces: List<WorkflowTrace>, topN: Int): List<BottleneckAnalysis>

    /**
     * Records a failed transition attempt for diagnostics.
     *
     * @param failure The failure to record
     */
    fun recordFailure(failure: TransitionFailure)

    /**
     * Gets all recorded failures within a time window.
     *
     * @param sinceTimestamp Only return failures after this timestamp
     * @return List of failures, ordered by timestamp descending
     */
    fun getFailures(sinceTimestamp: Long): List<TransitionFailure>

    /**
     * Clears all traces and failures older than the given timestamp.
     *
     * @param olderThan Timestamp threshold for cleanup
     * @return Number of traces and failures removed
     */
    fun cleanup(olderThan: Long): Int
}
```

### Required Data Classes

- `TraceStep` - Individual transition record with timing metadata
- `WorkflowTrace` - Complete trace aggregation for an entity
- `BottleneckAnalysis` - Aggregated bottleneck metrics per state
- `TransitionFailure` - Diagnostic record for failed transitions

### Architectural Requirements

1. Follow the `ReentrantLock` + `withLock` pattern used in `WorkflowEngine`, `RouteTable`, etc.
2. Use companion object or `object` for singleton services similar to `Workflow`, `Allocator`
3. Generate trace IDs using a deterministic scheme (e.g., `"trace-${entityId}-${timestamp}"`)
4. Integrate with the existing `Workflow.canTransition()` and `Workflow.isTerminalState()` methods
5. Sort results consistently using `sortedWith(compareBy<T> { ... }.thenBy { ... })` pattern

### Acceptance Criteria

1. **Unit Tests** (`src/test/kotlin/com/terminalbench/nimbusflow/DebuggerTest.kt`):
   - Test trace lifecycle (start, record steps, end)
   - Test bottleneck analysis with known durations
   - Test failure recording and retrieval
   - Test cleanup removes old data correctly
   - Test thread safety with concurrent trace operations
   - Minimum 15 test cases

2. **Integration Points**:
   - `WorkflowDebuggerService.recordStep()` should validate state transitions against `Workflow.canTransition()`
   - `analyzeBottlenecks()` should recognize terminal states via `Workflow.isTerminalState()`

3. **Coverage**: All public methods must have at least one test

---

## Task 2: Cost Attribution Engine

### Overview

Implement a `CostAttribution` engine that tracks, allocates, and reports operational costs across dispatch orders, routes, and berth allocations. This enables finance teams to understand cost drivers and charge back costs to appropriate cost centers.

### Interface Contract

Create `src/main/kotlin/com/terminalbench/nimbusflow/CostAttribution.kt`:

```kotlin
package com.terminalbench.nimbusflow

/**
 * Represents a cost line item for attribution.
 *
 * @property lineId Unique identifier for this cost line
 * @property category Cost category (FUEL, PORT_FEE, BERTH, HANDLING, DELAY_PENALTY)
 * @property amount Cost amount in USD
 * @property orderId Associated dispatch order ID
 * @property timestamp When this cost was incurred
 * @property description Human-readable description
 */
data class CostLineItem(
    val lineId: String,
    val category: CostCategory,
    val amount: Double,
    val orderId: String,
    val timestamp: Long,
    val description: String
)

/**
 * Enumeration of cost categories for classification.
 */
enum class CostCategory {
    FUEL,
    PORT_FEE,
    BERTH,
    HANDLING,
    DELAY_PENALTY,
    OVERHEAD
}

/**
 * Cost allocation result for a single order.
 *
 * @property orderId The order ID
 * @property totalCost Sum of all attributed costs
 * @property breakdown Costs broken down by category
 * @property costCenter Assigned cost center for chargeback
 */
data class OrderCostAllocation(
    val orderId: String,
    val totalCost: Double,
    val breakdown: Map<CostCategory, Double>,
    val costCenter: String
)

/**
 * Cost attribution report for a time period.
 *
 * @property reportId Unique report identifier
 * @property periodStart Start of the reporting period
 * @property periodEnd End of the reporting period
 * @property totalCost Total costs in the period
 * @property byCategory Costs aggregated by category
 * @property byOrder Costs aggregated by order
 * @property topCostDrivers Top N orders by total cost
 */
data class CostAttributionReport(
    val reportId: String,
    val periodStart: Long,
    val periodEnd: Long,
    val totalCost: Double,
    val byCategory: Map<CostCategory, Double>,
    val byOrder: Map<String, Double>,
    val topCostDrivers: List<String>
)

/**
 * Cost center definition for chargeback routing.
 *
 * @property centerId Unique cost center ID
 * @property name Human-readable name
 * @property orderPattern Regex pattern to match order IDs
 * @property defaultAllocation Default percentage allocation (0.0 to 1.0)
 */
data class CostCenter(
    val centerId: String,
    val name: String,
    val orderPattern: String,
    val defaultAllocation: Double
)

/**
 * Engine for cost tracking, attribution, and reporting.
 *
 * Thread-safe implementation required.
 */
interface CostAttributionEngine {
    /**
     * Records a cost line item.
     *
     * @param item The cost item to record
     * @return true if recorded, false if duplicate lineId
     */
    fun recordCost(item: CostLineItem): Boolean

    /**
     * Records multiple cost items in a batch.
     *
     * @param items List of cost items to record
     * @return Number of items successfully recorded (excludes duplicates)
     */
    fun recordCostBatch(items: List<CostLineItem>): Int

    /**
     * Calculates fuel cost for a route segment.
     *
     * Uses: distanceNm * fuelRatePerNm (from Routing.estimateRouteCost pattern)
     *
     * @param distanceNm Distance in nautical miles
     * @param fuelRatePerNm Fuel cost per nautical mile
     * @return Calculated fuel cost
     */
    fun calculateFuelCost(distanceNm: Double, fuelRatePerNm: Double): Double

    /**
     * Calculates delay penalty based on SLA breach.
     *
     * Penalty = baseRate * severity * (minutesOverSla / 60.0)
     * No penalty if within SLA.
     *
     * @param order The dispatch order
     * @param actualMinutes Actual processing time in minutes
     * @param baseRate Base penalty rate per severity-hour
     * @return Calculated penalty (0.0 if within SLA)
     */
    fun calculateDelayPenalty(order: DispatchOrder, actualMinutes: Int, baseRate: Double): Double

    /**
     * Gets all costs for a specific order.
     *
     * @param orderId The order ID
     * @return List of cost items, ordered by timestamp ascending
     */
    fun getCostsForOrder(orderId: String): List<CostLineItem>

    /**
     * Gets costs within a time window, optionally filtered by category.
     *
     * @param startTimestamp Start of the window (inclusive)
     * @param endTimestamp End of the window (exclusive)
     * @param category Optional category filter
     * @return List of matching cost items
     */
    fun getCostsInWindow(
        startTimestamp: Long,
        endTimestamp: Long,
        category: CostCategory? = null
    ): List<CostLineItem>

    /**
     * Allocates costs to orders and assigns cost centers.
     *
     * @param orderIds Orders to allocate costs for
     * @param costCenters Available cost centers for assignment
     * @return List of allocations, one per order
     */
    fun allocateCosts(
        orderIds: List<String>,
        costCenters: List<CostCenter>
    ): List<OrderCostAllocation>

    /**
     * Generates a cost attribution report for a time period.
     *
     * @param periodStart Start of period
     * @param periodEnd End of period
     * @param topN Number of top cost drivers to include
     * @return The generated report
     */
    fun generateReport(periodStart: Long, periodEnd: Long, topN: Int): CostAttributionReport

    /**
     * Returns the total costs attributed to a category.
     *
     * @param category The category to sum
     * @return Total cost for that category
     */
    fun totalByCategory(category: CostCategory): Double

    /**
     * Clears all cost records older than the specified timestamp.
     *
     * @param olderThan Timestamp threshold
     * @return Number of records removed
     */
    fun purgeOldRecords(olderThan: Long): Int
}
```

### Required Data Classes

- `CostLineItem` - Individual cost record with category and attribution
- `CostCategory` - Enum of cost classification categories
- `OrderCostAllocation` - Aggregated cost allocation for an order
- `CostAttributionReport` - Period-based cost report
- `CostCenter` - Cost center definition for chargeback routing

### Architectural Requirements

1. Use `ReentrantLock` for thread-safe cost recording and retrieval
2. Follow `Allocator.estimateCost()` pattern for cost calculations
3. Use `Allocator.allocateCosts()` pattern for proportional cost distribution
4. Integrate with `DispatchOrder` for SLA and urgency information
5. Round monetary values to 2 decimal places using `Math.round(value * 100.0) / 100.0`
6. Use `Regex.matches()` for cost center pattern matching

### Acceptance Criteria

1. **Unit Tests** (`src/test/kotlin/com/terminalbench/nimbusflow/CostAttributionTest.kt`):
   - Test cost recording (single and batch)
   - Test duplicate line ID rejection
   - Test fuel cost calculation
   - Test delay penalty calculation (within SLA and breached)
   - Test cost retrieval by order and time window
   - Test cost allocation to cost centers
   - Test report generation with correct aggregations
   - Test concurrent cost recording
   - Minimum 20 test cases

2. **Integration Points**:
   - `calculateDelayPenalty()` must use `DispatchOrder.slaMinutes` and `urgency`
   - `calculateFuelCost()` should align with `Routing.estimateRouteCost()` logic

3. **Coverage**: All public methods and enum values must have tests

---

## Task 3: Deployment Rollback Manager

### Overview

Implement a `RollbackManager` service that manages deployment versions, tracks rollback history, and enables safe rollback operations for NimbusFlow services. This supports the platform's resilience requirements by providing a mechanism to revert to known-good configurations.

### Interface Contract

Create `src/main/kotlin/com/terminalbench/nimbusflow/RollbackManager.kt`:

```kotlin
package com.terminalbench.nimbusflow

/**
 * Represents a deployed version of a service.
 *
 * @property versionId Unique version identifier (semantic versioning)
 * @property serviceId The service this version belongs to
 * @property deployedAt Deployment timestamp
 * @property configHash SHA-256 hash of the configuration
 * @property isActive Whether this version is currently active
 * @property healthScore Health score at deployment (0.0 to 1.0)
 */
data class DeploymentVersion(
    val versionId: String,
    val serviceId: String,
    val deployedAt: Long,
    val configHash: String,
    val isActive: Boolean,
    val healthScore: Double
)

/**
 * Record of a rollback operation.
 *
 * @property rollbackId Unique rollback identifier
 * @property serviceId The service that was rolled back
 * @property fromVersion Version rolled back from
 * @property toVersion Version rolled back to
 * @property initiatedAt When the rollback started
 * @property completedAt When the rollback finished (null if in progress)
 * @property status Rollback status (PENDING, IN_PROGRESS, COMPLETED, FAILED)
 * @property reason Human-readable reason for the rollback
 */
data class RollbackRecord(
    val rollbackId: String,
    val serviceId: String,
    val fromVersion: String,
    val toVersion: String,
    val initiatedAt: Long,
    val completedAt: Long?,
    val status: RollbackStatus,
    val reason: String
)

/**
 * Status of a rollback operation.
 */
enum class RollbackStatus {
    PENDING,
    IN_PROGRESS,
    COMPLETED,
    FAILED
}

/**
 * Result of a rollback eligibility check.
 *
 * @property eligible Whether rollback is allowed
 * @property targetVersion The version that would be rolled back to
 * @property blockers List of reasons preventing rollback (empty if eligible)
 * @property estimatedDowntimeSeconds Estimated downtime for the rollback
 */
data class RollbackEligibility(
    val eligible: Boolean,
    val targetVersion: String?,
    val blockers: List<String>,
    val estimatedDowntimeSeconds: Int
)

/**
 * Health check result for a deployment.
 *
 * @property serviceId The service checked
 * @property versionId The version checked
 * @property healthy Whether the deployment is healthy
 * @property checkTimestamp When the check was performed
 * @property metrics Health metrics (latencyP99, errorRate, etc.)
 */
data class HealthCheckResult(
    val serviceId: String,
    val versionId: String,
    val healthy: Boolean,
    val checkTimestamp: Long,
    val metrics: Map<String, Double>
)

/**
 * Manager for deployment versions and rollback operations.
 *
 * Thread-safe implementation required.
 */
interface RollbackManagerService {
    /**
     * Registers a new deployment version.
     *
     * Automatically deactivates previous active version for the service.
     *
     * @param version The version to register
     * @return true if registered, false if version ID already exists
     */
    fun registerVersion(version: DeploymentVersion): Boolean

    /**
     * Gets the currently active version for a service.
     *
     * @param serviceId The service ID
     * @return The active version, or null if no active version
     */
    fun getActiveVersion(serviceId: String): DeploymentVersion?

    /**
     * Gets version history for a service.
     *
     * @param serviceId The service ID
     * @param limit Maximum number of versions to return
     * @return List of versions, ordered by deployedAt descending
     */
    fun getVersionHistory(serviceId: String, limit: Int): List<DeploymentVersion>

    /**
     * Checks if a rollback is possible for a service.
     *
     * Rollback is blocked if:
     * - No previous version exists
     * - A rollback is already in progress
     * - The previous version has healthScore < 0.5
     * - The service is in the protected list
     *
     * @param serviceId The service to check
     * @return Eligibility result with blockers if not eligible
     */
    fun checkRollbackEligibility(serviceId: String): RollbackEligibility

    /**
     * Initiates a rollback operation.
     *
     * @param serviceId The service to roll back
     * @param reason Reason for the rollback
     * @param timestamp Current timestamp
     * @return The rollback record if initiated, null if not eligible
     */
    fun initiateRollback(serviceId: String, reason: String, timestamp: Long): RollbackRecord?

    /**
     * Completes a rollback operation (marks it as finished).
     *
     * @param rollbackId The rollback to complete
     * @param success Whether the rollback succeeded
     * @param timestamp Completion timestamp
     * @return Updated rollback record, or null if not found
     */
    fun completeRollback(rollbackId: String, success: Boolean, timestamp: Long): RollbackRecord?

    /**
     * Gets all rollback records for a service.
     *
     * @param serviceId The service ID
     * @return List of rollback records, ordered by initiatedAt descending
     */
    fun getRollbackHistory(serviceId: String): List<RollbackRecord>

    /**
     * Records a health check result.
     *
     * @param result The health check result
     */
    fun recordHealthCheck(result: HealthCheckResult)

    /**
     * Gets recent health checks for a version.
     *
     * @param serviceId The service ID
     * @param versionId The version ID
     * @param limit Maximum results to return
     * @return List of health checks, ordered by checkTimestamp descending
     */
    fun getHealthChecks(serviceId: String, versionId: String, limit: Int): List<HealthCheckResult>

    /**
     * Calculates the health score for a version based on recent checks.
     *
     * Score = (healthy checks / total checks) weighted by recency.
     * More recent checks have higher weight.
     *
     * @param serviceId The service ID
     * @param versionId The version ID
     * @param windowMs Time window to consider
     * @return Health score between 0.0 and 1.0
     */
    fun calculateHealthScore(serviceId: String, versionId: String, windowMs: Long): Double

    /**
     * Adds a service to the protected list (cannot be rolled back).
     *
     * @param serviceId The service to protect
     */
    fun protectService(serviceId: String)

    /**
     * Removes a service from the protected list.
     *
     * @param serviceId The service to unprotect
     */
    fun unprotectService(serviceId: String)

    /**
     * Lists all protected services.
     *
     * @return Set of protected service IDs
     */
    fun getProtectedServices(): Set<String>

    /**
     * Clears old version records beyond retention limit.
     *
     * Keeps the N most recent versions per service.
     *
     * @param retentionCount Number of versions to retain per service
     * @return Number of versions removed
     */
    fun pruneVersions(retentionCount: Int): Int
}
```

### Required Data Classes

- `DeploymentVersion` - Version metadata with health and configuration info
- `RollbackRecord` - Audit trail of rollback operations
- `RollbackStatus` - Enum of rollback lifecycle states
- `RollbackEligibility` - Result of rollback possibility check
- `HealthCheckResult` - Health metrics for deployments

### Architectural Requirements

1. Use `ReentrantLock` for thread-safe version and rollback management
2. Follow `ServiceRegistry` pattern for service lookups and validation
3. Use `Security.sha256Digest()` pattern for config hash generation (or create similar)
4. Integrate with `Contracts.servicePorts` to validate known services
5. Follow `CircuitBreaker` FSM pattern for rollback status transitions
6. Use deterministic ID generation: `"rollback-${serviceId}-${timestamp}"`
7. Sort lists consistently using `sortedByDescending { }` for timestamps

### Acceptance Criteria

1. **Unit Tests** (`src/test/kotlin/com/terminalbench/nimbusflow/RollbackManagerTest.kt`):
   - Test version registration and automatic deactivation
   - Test active version retrieval
   - Test version history ordering
   - Test rollback eligibility (all blocker scenarios)
   - Test rollback lifecycle (initiate, complete success, complete failure)
   - Test health check recording and retrieval
   - Test health score calculation with recency weighting
   - Test protected services functionality
   - Test version pruning
   - Test concurrent version registration
   - Minimum 25 test cases

2. **Integration Points**:
   - `registerVersion()` should validate serviceId against `ServiceRegistry.all()`
   - Rollback eligibility should check `Contracts.servicePorts` for valid services

3. **Coverage**: All public methods, enum values, and edge cases must have tests

---

## General Guidelines

### Code Style

- Use Kotlin idioms: `data class`, `object`, `?.let { }`, `when` expressions
- Prefer immutable collections in return types (`List`, `Set`, `Map`)
- Use internal mutable collections for state (`mutableMapOf`, `mutableListOf`)
- Add KDoc comments to all public types and methods
- Use `require()` and `check()` for precondition validation

### Testing Pattern

Follow the existing test structure in `CoreTest.kt`:

```kotlin
@Test
fun `descriptive test name with backticks`() {
    // Arrange
    val input = ...

    // Act
    val result = serviceUnderTest.methodToTest(input)

    // Assert
    assertEquals(expected, result)
}
```

### Thread Safety

All stateful services must use `ReentrantLock`:

```kotlin
class MyService {
    private val lock = ReentrantLock()
    private val data = mutableMapOf<String, Value>()

    fun get(key: String): Value? = lock.withLock { data[key] }

    fun put(key: String, value: Value) {
        lock.withLock { data[key] = value }
    }
}
```

### File Locations

- Source: `src/main/kotlin/com/terminalbench/nimbusflow/<Module>.kt`
- Tests: `src/test/kotlin/com/terminalbench/nimbusflow/<Module>Test.kt`
- Package: `com.terminalbench.nimbusflow`
