# FluxRail - Greenfield Implementation Tasks

## Overview

These greenfield tasks require implementing NEW modules from scratch within the FluxRail rail/transit dispatch system. Each task builds upon the existing architecture patterns found in `src/core/` and `src/models/`, and provides specific interface contracts, data structures, and integration points. You will create complete modules including core logic, data models, unit tests, and integration tests.

## Environment

- **Language**: JavaScript (Node)
- **Test Runner**: `node --test` (TAP format)
- **Infrastructure**: Docker Compose with 15 existing integrated modules
- **Difficulty**: Hyper-Principal
- **Constraint**: Do not edit files under `tests/`

## Tasks

### Task 1: Passenger Flow Predictor (Greenfield Implementation)

Implement a passenger flow prediction module that forecasts demand across stations and time windows. This module integrates with the existing capacity management (`src/core/capacity.js`) and economics (`src/core/economics.js`) systems to enable proactive resource allocation.

**Files to Create:**
- `src/core/passenger-flow.js` - Core prediction logic with functions for volume prediction, load distribution, bottleneck identification, and maintenance window optimization
- `src/models/flow-forecast.js` - Model class for forecast records with validation and audit support
- `tests/unit/passenger-flow.test.js` - Unit tests covering all prediction scenarios
- `tests/integration/flow-capacity.test.js` - Integration tests with capacity module

**Key Interfaces:**
- `predictVolume(stationId, historicalData, currentHour, weatherFactor, eventFactor)` - Predicts passenger volume applying weather and event factors
- `loadDistribution(stationLoads, connections, capacities)` - Calculates load distribution across connected stations
- `identifyBottlenecks(predictedLoads, capacities, thresholdRatio)` - Identifies stations at risk of overcrowding
- `maintenanceWindow(hourlyPredictions, durationHours, maxLoadThreshold)` - Finds optimal maintenance windows

**Integration Points:** Bottleneck identification triggers `shedRequired()` from capacity module; predicted loads integrate with `rebalance()` for proactive capacity management; flow forecasts work with existing `DispatchPlan` assignments.

---

### Task 2: Delay Propagation Simulator (Greenfield Implementation)

Implement a delay propagation simulation module that models how delays cascade through the rail network. This module helps operators understand the downstream impact of incidents and enables better recovery planning. Integrates with SLA (`src/core/sla.js`) and workflow (`src/core/workflow.js`) modules.

**Files to Create:**
- `src/core/delay-propagation.js` - Core simulation logic with cascade modeling, impact calculation, critical path analysis, and recovery recommendations
- `src/models/delay-event.js` - Model class for delay events with severity classification and formatting
- `tests/unit/delay-propagation.test.js` - Unit tests for propagation algorithms and edge cases
- `tests/integration/delay-sla.test.js` - Integration tests with SLA and workflow modules

**Key Interfaces:**
- `propagateDelay(upstreamDelaySec, bufferTimeSec, dampeningFactor)` - Calculates propagated delay with dampening based on buffer time
- `simulateCascade(originServiceId, initialDelaySec, networkGraph, maxHops)` - Simulates delay cascade through network
- `totalImpactMinutes(delaysByService, passengersByService)` - Estimates total passenger-minutes of delay
- `identifyCriticalPaths(networkGraph, passengersByService, testDelaySec)` - Identifies services with maximum cascade impact
- `recommendRecovery(delaysByService, capacityByService, targetRecoveryMinutes)` - Recommends recovery actions by priority

**Integration Points:** Cascaded delays trigger `breachRisk()` from SLA module; delay severity maps to `breachSeverity()` levels; recovery recommendations align with workflow state transitions.

---

### Task 3: Crew Scheduling Optimizer (Greenfield Implementation)

Implement a crew scheduling optimization module that manages train crew assignments, shift constraints, and rest requirements. This module integrates with the dispatch (`src/core/dispatch.js`), authorization (`src/core/authorization.js`), and policy (`src/core/policy.js`) systems.

**Files to Create:**
- `src/core/crew-scheduling.js` - Core scheduling logic with rest compliance, utilization tracking, crew selection, conflict detection, overtime calculation, and handoff generation
- `src/models/crew-assignment.js` - Model class for crew assignments with duration tracking, shift validation, and overlap detection
- `tests/unit/crew-scheduling.test.js` - Unit tests for all scheduling scenarios including rest rules and shift limits
- `tests/integration/crew-dispatch.test.js` - Integration tests with dispatch, authorization, and policy modules

**Key Interfaces:**
- `isRestCompliant(lastShiftEndEpochSec, proposedStartEpochSec, minRestHours)` - Checks rest requirement compliance
- `utilizationRate(workedMinutes, availableMinutes, targetUtilization)` - Calculates crew utilization with status
- `findOptimalCrew(serviceId, requiredCertifications, crewPool)` - Finds best crew match by qualifications and fatigue
- `detectConflicts(assignments)` - Detects overlapping time assignments for same crew
- `calculateOvertimeCost(assignments, standardShiftMinutes, overtimeMultiplier)` - Computes overtime costs
- `generateHandoff(outgoingCrewId, incomingCrewId, currentState, handoffTimeEpochSec)` - Generates shift handoff reports

**Integration Points:** Crew assignments integrate with `assignPriority()` from dispatch; authorization checks via `allowed()` for assignment creation; policy overrides via `overrideAllowed()` for emergency staffing.

## Getting Started

```bash
cd js/fluxrail
npm install
npm test
```

## Success Criteria

Implementation must:
1. Create all required files with complete, tested implementations
2. Follow existing architectural patterns from `src/core/` and `src/models/`
3. Achieve minimum 90% line coverage for new modules
4. Pass all 8,053 tests without modification to test files
5. Integrate correctly with existing modules per the documented integration points
6. Follow code style guidelines: use function declarations, classes for models, defensive programming, and JSDoc comments

All implementations must reference the detailed interface contracts and acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
