# FluxRail Greenfield Tasks

These tasks require implementing NEW modules from scratch within the FluxRail rail/transit dispatch system. Each task builds upon the existing architecture patterns found in `src/core/` and `src/models/`.

## Test Command

```bash
npm test
```

---

## Task 1: Passenger Flow Predictor

### Overview

Implement a passenger flow prediction module that forecasts demand across stations and time windows. This module integrates with the existing capacity management (`src/core/capacity.js`) and economics (`src/core/economics.js`) systems to enable proactive resource allocation.

### Files to Create

- `src/core/passenger-flow.js` - Core prediction logic
- `src/models/flow-forecast.js` - Data model for forecasts
- `tests/unit/passenger-flow.test.js` - Unit tests
- `tests/integration/flow-capacity.test.js` - Integration with capacity module

### Interface Contract

```javascript
// src/core/passenger-flow.js

/**
 * Predicts passenger volume for a given station and time window.
 * Uses historical patterns and current conditions.
 *
 * @param {string} stationId - Unique station identifier
 * @param {Object} historicalData - Map of hourOfDay -> average passenger count
 * @param {number} currentHour - Current hour (0-23)
 * @param {number} weatherFactor - Multiplier for weather impact (0.5-1.5)
 * @param {number} eventFactor - Multiplier for special events (1.0-3.0)
 * @returns {number} Predicted passenger count (rounded integer, minimum 0)
 */
function predictVolume(stationId, historicalData, currentHour, weatherFactor, eventFactor) {}

/**
 * Calculates load distribution across connected stations.
 * Returns proportional load for each station based on connectivity and capacity.
 *
 * @param {Object} stationLoads - Map of stationId -> current passenger load
 * @param {Object} connections - Map of stationId -> array of connected station IDs
 * @param {Object} capacities - Map of stationId -> max capacity
 * @returns {Object} Map of stationId -> load ratio (0.0 to 1.0+, can exceed 1.0 for overflow)
 */
function loadDistribution(stationLoads, connections, capacities) {}

/**
 * Identifies stations at risk of overcrowding within the prediction window.
 *
 * @param {Object} predictedLoads - Map of stationId -> predicted passenger count
 * @param {Object} capacities - Map of stationId -> max capacity
 * @param {number} thresholdRatio - Alert threshold as ratio of capacity (e.g., 0.85)
 * @returns {Array<{stationId: string, ratio: number, severity: string}>} Stations exceeding threshold, sorted by ratio descending
 */
function identifyBottlenecks(predictedLoads, capacities, thresholdRatio) {}

/**
 * Computes optimal time window for maintenance based on predicted low-traffic periods.
 *
 * @param {Object} hourlyPredictions - Map of hour (0-23) -> predicted passenger count
 * @param {number} durationHours - Required maintenance window duration
 * @param {number} maxLoadThreshold - Maximum acceptable load during maintenance
 * @returns {{startHour: number, endHour: number, avgLoad: number} | null} Best window or null if none available
 */
function maintenanceWindow(hourlyPredictions, durationHours, maxLoadThreshold) {}

module.exports = { predictVolume, loadDistribution, identifyBottlenecks, maintenanceWindow };
```

```javascript
// src/models/flow-forecast.js

/**
 * Represents a passenger flow forecast for planning and capacity allocation.
 */
class FlowForecast {
  /**
   * @param {Object} params
   * @param {string} params.forecastId - Unique forecast identifier
   * @param {string} params.stationId - Station this forecast applies to
   * @param {Date} params.windowStart - Start of forecast window
   * @param {Date} params.windowEnd - End of forecast window
   * @param {number} params.predictedVolume - Predicted passenger count
   * @param {number} params.confidenceScore - Prediction confidence (0.0-1.0)
   * @param {string} params.createdBy - Creator identifier
   */
  constructor({ forecastId, stationId, windowStart, windowEnd, predictedVolume, confidenceScore, createdBy }) {}

  /**
   * Returns true if forecast confidence is above acceptable threshold (0.7).
   * @returns {boolean}
   */
  isReliable() {}

  /**
   * Returns forecast duration in minutes.
   * @returns {number}
   */
  durationMinutes() {}

  /**
   * Validates forecast has required fields and sensible values.
   * @returns {boolean}
   */
  validate() {}

  /**
   * Converts to audit-safe record format.
   * @returns {Object}
   */
  toAuditRecord() {}
}

module.exports = { FlowForecast };
```

### Required Models/Data Structures

| Structure | Description |
|-----------|-------------|
| `historicalData` | `Object<hourOfDay: number, avgCount: number>` - Historical averages by hour |
| `stationLoads` | `Object<stationId: string, load: number>` - Current passenger counts |
| `connections` | `Object<stationId: string, connectedIds: string[]>` - Station connectivity graph |
| `capacities` | `Object<stationId: string, capacity: number>` - Station max capacities |
| `FlowForecast` | Model class for forecast records |

### Architectural Patterns to Follow

1. **Function exports** - Use `module.exports = { fn1, fn2 }` pattern (see `src/core/dispatch.js`)
2. **Input coercion** - Convert inputs with `Number()`, `String()` for type safety
3. **Defensive defaults** - Handle `null`/`undefined` inputs with `|| {}` or `|| []`
4. **Sorting with tie-breakers** - Use lexical tie-break for deterministic ordering (see `chooseRoute()`)
5. **Class models** - Follow `DispatchPlan` pattern for model classes with validation

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/passenger-flow.test.js`)
   - `predictVolume` correctly applies weather and event factors
   - `predictVolume` handles missing historical data gracefully
   - `loadDistribution` returns valid ratios for all stations
   - `loadDistribution` handles isolated stations (no connections)
   - `identifyBottlenecks` returns stations sorted by ratio descending
   - `identifyBottlenecks` filters by threshold correctly
   - `maintenanceWindow` finds optimal low-traffic window
   - `maintenanceWindow` returns null when no valid window exists
   - `FlowForecast.isReliable()` returns correct boolean for confidence thresholds
   - `FlowForecast.validate()` rejects invalid forecasts

2. **Integration Tests** (`tests/integration/flow-capacity.test.js`)
   - Bottleneck identification triggers `shedRequired()` from capacity module
   - Predicted loads integrate with `rebalance()` for proactive capacity management
   - Flow forecasts work with existing `DispatchPlan` assignments

3. **Code Coverage**
   - Minimum 90% line coverage for new modules

---

## Task 2: Delay Propagation Simulator

### Overview

Implement a delay propagation simulation module that models how delays cascade through the rail network. This module helps operators understand the downstream impact of incidents and enables better recovery planning. Integrates with SLA (`src/core/sla.js`) and workflow (`src/core/workflow.js`) modules.

### Files to Create

- `src/core/delay-propagation.js` - Core simulation logic
- `src/models/delay-event.js` - Data model for delay events
- `tests/unit/delay-propagation.test.js` - Unit tests
- `tests/integration/delay-sla.test.js` - Integration with SLA module

### Interface Contract

```javascript
// src/core/delay-propagation.js

/**
 * Calculates the propagated delay for a downstream service based on upstream delay.
 * Applies dampening factor based on buffer time between services.
 *
 * @param {number} upstreamDelaySec - Delay in seconds at upstream station
 * @param {number} bufferTimeSec - Scheduled buffer between services
 * @param {number} dampeningFactor - How much delay is absorbed (0.0-1.0, where 1.0 = full absorption)
 * @returns {number} Propagated delay in seconds (minimum 0)
 */
function propagateDelay(upstreamDelaySec, bufferTimeSec, dampeningFactor) {}

/**
 * Simulates delay cascade through a network of connected services.
 * Returns final delay state for all affected services.
 *
 * @param {string} originServiceId - Service where delay originated
 * @param {number} initialDelaySec - Initial delay in seconds
 * @param {Object} networkGraph - Map of serviceId -> {downstream: string[], bufferSec: number}
 * @param {number} maxHops - Maximum propagation depth
 * @returns {Object} Map of serviceId -> {delaySec: number, hopCount: number}
 */
function simulateCascade(originServiceId, initialDelaySec, networkGraph, maxHops) {}

/**
 * Estimates total passenger-minutes of delay across affected services.
 *
 * @param {Object} delaysByService - Map of serviceId -> delay in seconds
 * @param {Object} passengersByService - Map of serviceId -> passenger count
 * @returns {number} Total passenger-minutes (rounded to 2 decimal places)
 */
function totalImpactMinutes(delaysByService, passengersByService) {}

/**
 * Identifies critical path services whose delays would cause maximum cascade impact.
 *
 * @param {Object} networkGraph - Map of serviceId -> {downstream: string[], bufferSec: number}
 * @param {Object} passengersByService - Map of serviceId -> passenger count
 * @param {number} testDelaySec - Hypothetical delay to simulate
 * @returns {Array<{serviceId: string, impactMinutes: number}>} Top services sorted by impact descending
 */
function identifyCriticalPaths(networkGraph, passengersByService, testDelaySec) {}

/**
 * Recommends recovery actions based on current delay state.
 *
 * @param {Object} delaysByService - Map of serviceId -> delay in seconds
 * @param {Object} capacityByService - Map of serviceId -> available recovery capacity (trains/hour)
 * @param {number} targetRecoveryMinutes - Target time to full recovery
 * @returns {Array<{serviceId: string, action: string, priority: number}>} Recovery actions sorted by priority
 */
function recommendRecovery(delaysByService, capacityByService, targetRecoveryMinutes) {}

module.exports = { propagateDelay, simulateCascade, totalImpactMinutes, identifyCriticalPaths, recommendRecovery };
```

```javascript
// src/models/delay-event.js

/**
 * Represents a delay event for tracking and analysis.
 */
class DelayEvent {
  /**
   * @param {Object} params
   * @param {string} params.eventId - Unique event identifier
   * @param {string} params.serviceId - Affected service
   * @param {number} params.delaySec - Delay duration in seconds
   * @param {string} params.cause - Delay cause category (signal|rolling_stock|passenger|weather|other)
   * @param {Date} params.occurredAt - When delay occurred
   * @param {string|null} params.upstreamEventId - ID of upstream event that caused this (null if origin)
   */
  constructor({ eventId, serviceId, delaySec, cause, occurredAt, upstreamEventId }) {}

  /**
   * Returns true if this is the origin event (no upstream cause).
   * @returns {boolean}
   */
  isOrigin() {}

  /**
   * Returns severity level based on delay duration.
   * - < 5 min: 'minor'
   * - 5-15 min: 'moderate'
   * - 15-30 min: 'major'
   * - > 30 min: 'severe'
   * @returns {string}
   */
  severityLevel() {}

  /**
   * Returns delay in human-readable format.
   * @returns {string} e.g., "5m 30s" or "1h 15m"
   */
  formatDelay() {}

  /**
   * Validates event has required fields and valid cause.
   * @returns {boolean}
   */
  validate() {}

  /**
   * Converts to audit-safe record format.
   * @returns {Object}
   */
  toAuditRecord() {}
}

module.exports = { DelayEvent };
```

### Required Models/Data Structures

| Structure | Description |
|-----------|-------------|
| `networkGraph` | `Object<serviceId: string, {downstream: string[], bufferSec: number}>` - Network topology |
| `delaysByService` | `Object<serviceId: string, delaySec: number>` - Current delay state |
| `passengersByService` | `Object<serviceId: string, count: number>` - Passenger counts |
| `DelayEvent` | Model class for delay event records |

### Architectural Patterns to Follow

1. **Graph traversal** - Use BFS/DFS with visited tracking (see `replayState()` pattern)
2. **Numeric precision** - Use `toFixed()` for financial/time calculations
3. **Severity thresholds** - Use clear numeric boundaries (see `breachSeverity()`)
4. **Sorting with comparators** - Descending sort for priority ordering

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/delay-propagation.test.js`)
   - `propagateDelay` correctly applies buffer and dampening
   - `propagateDelay` returns 0 when buffer exceeds delay
   - `simulateCascade` respects maxHops limit
   - `simulateCascade` handles circular references without infinite loops
   - `totalImpactMinutes` correctly aggregates across services
   - `identifyCriticalPaths` returns services sorted by impact
   - `recommendRecovery` prioritizes high-delay, high-capacity services
   - `DelayEvent.severityLevel()` returns correct levels for boundary values
   - `DelayEvent.isOrigin()` correctly identifies origin events

2. **Integration Tests** (`tests/integration/delay-sla.test.js`)
   - Cascaded delays trigger `breachRisk()` from SLA module
   - Delay severity maps to `breachSeverity()` levels
   - Recovery recommendations align with workflow state transitions

3. **Code Coverage**
   - Minimum 90% line coverage for new modules

---

## Task 3: Crew Scheduling Optimizer

### Overview

Implement a crew scheduling optimization module that manages train crew assignments, shift constraints, and rest requirements. This module integrates with the dispatch (`src/core/dispatch.js`), authorization (`src/core/authorization.js`), and policy (`src/core/policy.js`) systems.

### Files to Create

- `src/core/crew-scheduling.js` - Core scheduling logic
- `src/models/crew-assignment.js` - Data model for crew assignments
- `tests/unit/crew-scheduling.test.js` - Unit tests
- `tests/integration/crew-dispatch.test.js` - Integration with dispatch module

### Interface Contract

```javascript
// src/core/crew-scheduling.js

/**
 * Checks if a crew member is eligible for assignment based on rest requirements.
 *
 * @param {number} lastShiftEndEpochSec - When last shift ended (epoch seconds)
 * @param {number} proposedStartEpochSec - When proposed shift starts (epoch seconds)
 * @param {number} minRestHours - Minimum required rest between shifts
 * @returns {boolean} True if crew member has had sufficient rest
 */
function isRestCompliant(lastShiftEndEpochSec, proposedStartEpochSec, minRestHours) {}

/**
 * Calculates crew utilization rate for a given time period.
 *
 * @param {number} workedMinutes - Minutes actually worked
 * @param {number} availableMinutes - Total available minutes in period
 * @param {number} targetUtilization - Target utilization rate (0.0-1.0)
 * @returns {{rate: number, status: string}} Rate (0.0-1.0) and status ('under'|'optimal'|'over')
 */
function utilizationRate(workedMinutes, availableMinutes, targetUtilization) {}

/**
 * Finds optimal crew assignment for a service based on qualifications and availability.
 *
 * @param {string} serviceId - Service requiring crew
 * @param {Array<string>} requiredCertifications - Required certifications for service
 * @param {Array<{crewId: string, certifications: string[], available: boolean, fatigueScore: number}>} crewPool
 * @returns {{crewId: string, score: number} | null} Best matching crew or null if none available
 */
function findOptimalCrew(serviceId, requiredCertifications, crewPool) {}

/**
 * Detects scheduling conflicts across proposed assignments.
 *
 * @param {Array<{crewId: string, serviceId: string, startEpoch: number, endEpoch: number}>} assignments
 * @returns {Array<{crewId: string, conflicts: Array<{service1: string, service2: string}>}>} Detected conflicts
 */
function detectConflicts(assignments) {}

/**
 * Calculates overtime cost for a set of assignments.
 *
 * @param {Array<{crewId: string, workedMinutes: number, baseRatePerHour: number}>} assignments
 * @param {number} standardShiftMinutes - Standard shift length before overtime
 * @param {number} overtimeMultiplier - Overtime rate multiplier (e.g., 1.5)
 * @returns {{totalCost: number, overtimeMinutes: number, crewWithOvertime: string[]}}
 */
function calculateOvertimeCost(assignments, standardShiftMinutes, overtimeMultiplier) {}

/**
 * Generates shift handoff report for crew rotation.
 *
 * @param {string} outgoingCrewId - Crew ending shift
 * @param {string} incomingCrewId - Crew starting shift
 * @param {Object} currentState - Current service state to transfer
 * @param {number} handoffTimeEpochSec - When handoff occurs
 * @returns {{handoffId: string, outgoing: string, incoming: string, stateSnapshot: Object, timestamp: string}}
 */
function generateHandoff(outgoingCrewId, incomingCrewId, currentState, handoffTimeEpochSec) {}

module.exports = { isRestCompliant, utilizationRate, findOptimalCrew, detectConflicts, calculateOvertimeCost, generateHandoff };
```

```javascript
// src/models/crew-assignment.js

/**
 * Represents a crew assignment to a service.
 */
class CrewAssignment {
  /**
   * @param {Object} params
   * @param {string} params.assignmentId - Unique assignment identifier
   * @param {string} params.crewId - Assigned crew member ID
   * @param {string} params.serviceId - Service being worked
   * @param {Date} params.shiftStart - Shift start time
   * @param {Date} params.shiftEnd - Shift end time
   * @param {string} params.role - Crew role (driver|conductor|engineer)
   * @param {string} params.assignedBy - Who created assignment
   */
  constructor({ assignmentId, crewId, serviceId, shiftStart, shiftEnd, role, assignedBy }) {}

  /**
   * Returns shift duration in hours.
   * @returns {number}
   */
  durationHours() {}

  /**
   * Returns true if shift exceeds legal maximum (12 hours).
   * @returns {boolean}
   */
  exceedsMaxShift() {}

  /**
   * Returns true if this assignment overlaps with another.
   * @param {CrewAssignment} other
   * @returns {boolean}
   */
  overlapsWith(other) {}

  /**
   * Validates assignment has required fields and valid role.
   * @returns {boolean}
   */
  validate() {}

  /**
   * Converts to audit-safe record format.
   * @returns {Object}
   */
  toAuditRecord() {}
}

module.exports = { CrewAssignment };
```

### Required Models/Data Structures

| Structure | Description |
|-----------|-------------|
| `crewPool` | `Array<{crewId, certifications, available, fatigueScore}>` - Available crew |
| `assignments` | `Array<{crewId, serviceId, startEpoch, endEpoch}>` - Proposed assignments |
| `CrewAssignment` | Model class for assignment records |

### Architectural Patterns to Follow

1. **Authorization integration** - Use `allowed()` pattern for role-based assignment approval
2. **Time calculations** - Use epoch seconds for consistency (see `tokenFresh()`)
3. **Threshold-based categorization** - Use clear boundaries for status levels
4. **Conflict detection** - Use interval overlap detection algorithm
5. **Audit records** - Follow `toAuditRecord()` pattern with ISO timestamps

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/crew-scheduling.test.js`)
   - `isRestCompliant` correctly enforces minimum rest hours
   - `isRestCompliant` handles boundary cases (exactly minimum rest)
   - `utilizationRate` returns correct status for under/optimal/over
   - `findOptimalCrew` returns null when no qualified crew available
   - `findOptimalCrew` prefers lower fatigue scores among qualified crew
   - `detectConflicts` identifies overlapping assignments for same crew
   - `detectConflicts` returns empty array when no conflicts
   - `calculateOvertimeCost` correctly applies overtime multiplier
   - `CrewAssignment.overlapsWith()` detects partial overlaps
   - `CrewAssignment.exceedsMaxShift()` enforces 12-hour limit

2. **Integration Tests** (`tests/integration/crew-dispatch.test.js`)
   - Crew assignments integrate with `assignPriority()` from dispatch
   - Authorization checks via `allowed()` for assignment creation
   - Policy overrides via `overrideAllowed()` for emergency staffing

3. **Code Coverage**
   - Minimum 90% line coverage for new modules

---

## General Guidelines

### Testing Patterns

Follow the existing test patterns using Node.js built-in test runner:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');

test('descriptive test name', () => {
  // Arrange
  const input = { ... };

  // Act
  const result = functionUnderTest(input);

  // Assert
  assert.equal(result, expected);
});
```

### Code Style

- Use `function` declarations (not arrow functions) for exported functions
- Use `class` for model definitions
- Apply defensive programming with null checks and type coercion
- Include JSDoc comments for all public functions
- Use descriptive error messages for validation failures

### Integration Points

All new modules should integrate with existing modules where appropriate:

| New Module | Integrates With |
|------------|-----------------|
| `passenger-flow.js` | `capacity.js`, `economics.js`, `statistics.js` |
| `delay-propagation.js` | `sla.js`, `workflow.js`, `resilience.js` |
| `crew-scheduling.js` | `dispatch.js`, `authorization.js`, `policy.js` |

### Contracts

Ensure new modules export their interfaces and register with `shared/contracts/contracts.js`:

```javascript
// Add to shared/contracts/contracts.js
const PASSENGER_FLOW_FUNCTIONS = ['predictVolume', 'loadDistribution', 'identifyBottlenecks', 'maintenanceWindow'];
const DELAY_PROPAGATION_FUNCTIONS = ['propagateDelay', 'simulateCascade', 'totalImpactMinutes', 'identifyCriticalPaths', 'recommendRecovery'];
const CREW_SCHEDULING_FUNCTIONS = ['isRestCompliant', 'utilizationRate', 'findOptimalCrew', 'detectConflicts', 'calculateOvertimeCost', 'generateHandoff'];
```
