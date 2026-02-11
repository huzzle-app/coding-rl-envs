# TransitCore - Greenfield Tasks

## Overview

These greenfield tasks require implementing NEW modules from scratch for the TransitCore public transit platform. Each task builds on the existing architecture patterns and integrates with existing services to extend the platform with user-facing or operational capabilities.

## Environment

- **Language**: Java 21
- **Build**: Maven + JUnit 5
- **Infrastructure**: PostgreSQL, Redis, NATS
- **Difficulty**: Principal

## Tasks

### Task 1: Passenger Information Display Service (User-Facing)

Implement a service that computes real-time passenger information for display at transit stops and stations. Aggregate arrival predictions, service alerts, and capacity indicators to produce display-ready content for various screen formats. The service must handle capacity level computation (available/crowded/full), alert prioritization by severity, and scroll message generation for critical disruptions.

**Interface**: `PassengerInfoDisplay` with methods for content generation, capacity level calculation, alert filtering, and message generation.

### Task 2: Accessibility Routing Engine (Accessibility Feature)

Develop a routing engine that finds accessible routes for passengers with mobility requirements, considering elevator availability, platform gaps, step-free access, and real-time accessibility equipment status. Compute accessibility scores based on equipment status and generate warnings for accessibility concerns. The engine must handle edge cases like broken elevators and platform gaps exceeding safe thresholds.

**Interface**: `AccessibilityRouter` with methods for route finding, accessibility validation, scoring, and warning generation.

### Task 3: Real-Time Arrival Predictor (Prediction Engine)

Build a prediction engine that estimates vehicle arrival times using historical patterns, current traffic conditions, and real-time GPS positions. Implement GPS-based and historical-based prediction methods with intelligent fallback to hybrid approaches. Compute confidence intervals based on data quality and apply corrections for known delay patterns.

**Interface**: `ArrivalPredictor` with methods for arrival prediction, GPS-based calculation, historical-based calculation, traffic delay application, and quality scoring.

## Getting Started

```bash
cd java/transitcore
mvn test -q
```

## Success Criteria

- All public methods have comprehensive test coverage (minimum 6-10 tests per greenfield task)
- Unit tests verify boundary conditions and edge cases (e.g., capacity level thresholds, platform gap limits)
- Integration points with existing services (CapacityBalancer, RoutingHeuristics, SlaModel) work correctly
- Code follows existing architectural patterns (final classes, static utilities, records, immutable data structures)
- All tests pass: `mvn test`

## Interface Documentation

Detailed interface contracts for each greenfield task are available in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md), including:
- Record definitions for data structures
- Method signatures with parameter descriptions
- Acceptance criteria and test requirements
- Integration points with existing components
