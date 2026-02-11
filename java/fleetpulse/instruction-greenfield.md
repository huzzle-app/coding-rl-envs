# FleetPulse - Greenfield Implementation Tasks

## Overview

Three greenfield implementation tasks that require building new modules from scratch following FleetPulse architectural patterns. Each task provides detailed interface contracts, entity specifications, and integration points with existing services.

## Environment

- **Language**: Java 21
- **Framework**: Spring Boot 3.2
- **Infrastructure**: Docker Compose with Kafka 3.6, PostgreSQL 15, Redis 7, Consul 1.17
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Driver Safety Scoring Service (Greenfield Module)

Implement a comprehensive driver safety scoring system that analyzes driver behavior, calculates safety scores (0-100 scale), and manages safety events. The service calculates scores based on weighted factors: hard braking (-3 points), rapid acceleration (-2), speeding (-5), HOS violations (-10), accidents (-25), safe driving days (+1 per day, max 30). Provides REST endpoints for score retrieval, event recording, intervention list, and safety bonus eligibility determination. Integrates with TrackingService for telemetry, ComplianceService for HOS violations, and NotificationService for alerts. Module location: `safety/src/main/java/com/fleetpulse/safety/`

**Key Entities**: SafetyEvent, DriverSafetyScore, SafetyEventType (enum with 8 event types)

**Key Operations**: calculateSafetyScore(), recalculateAllScores(), recordSafetyEvent(), getDriverSafetyEvents(), getDriversRequiringIntervention(), calculateFleetAverageScore(), isEligibleForSafetyBonus(), getSafetyScoreTrend()

### Task 2: Fuel Card Integration Service (Greenfield Module)

Implement a fuel card management system tracking transactions, detecting anomalies, calculating fuel efficiency, and integrating with external fuel card provider APIs. Supports card issuance/lifecycle management, transaction processing with validation, and 7 anomaly detection rules (capacity mismatch, location discrepancy, rapid transactions, excessive amount, fuel grade mismatch, after-hours, unusual merchant). Provides REST endpoints for card management, transaction processing, anomaly resolution, and fuel efficiency reporting. Integrates with TrackingService for vehicle location, VehicleService for tank capacity, BillingService for invoicing, and AnalyticsService for reporting. Module location: `fuelcard/src/main/java/com/fleetpulse/fuelcard/`

**Key Entities**: FuelCard, FuelTransaction, FuelAnomalyAlert, FuelEfficiencyReport (DTO)

**Key Enums**: FuelCardStatus (6 states), FuelAnomalyType (7 types)

**Key Operations**: issueCard(), deactivateCard(), processTransaction(), validateTransaction(), getVehicleTransactions(), calculateFuelEfficiency(), getUnresolvedAlerts(), resolveAlert(), calculateFleetFuelSpend(), getCardsNearingLimit(), syncTransactionsFromProvider()

### Task 3: Route Optimization Engine (Greenfield Module)

Implement an advanced route optimization engine that calculates optimal routes considering traffic, vehicle capacity, driver hours, time windows, and fuel efficiency. Supports single-route optimization and multi-vehicle fleet-wide scheduling. Uses combination of algorithms: nearest neighbor heuristic for initial solution, 2-opt improvement for local optimization, simulated annealing for escaping local minima. Provides REST endpoints for route optimization, fleet scheduling, ETA calculation, route validation, and dynamic re-optimization during execution. Integrates with VehicleService for vehicle specs, TrackingService for positions, ComplianceService for HOS validation, RouteService for existing waypoints, DispatchService for assignment, and BillingService for cost estimates. Module location: `optimization/src/main/java/com/fleetpulse/optimization/`

**Key Entities**: Stop, OptimizedRoute (with ordered stop IDs)

**Key DTOs**: RouteOptimizationRequest, FleetOptimizationRequest, FleetOptimizationResult, OptimizationSavings, RouteValidationResult, ConstraintViolation, GeoPoint (record), CapacityRequirements, VehicleRecommendation

**Key Enums**: OptimizationPriority (FASTEST, SHORTEST, FUEL_EFFICIENT, BALANCED, MINIMIZE_STOPS)

**Key Operations**: optimizeRoute(), optimizeFleet(), calculateETAs(), insertStopAndReoptimize(), calculateSavings(), validateRoute(), getTrafficAdjustedTravelTime(), estimateFuelConsumption(), recommendVehicle(), generateAlternatives()

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/java/fleetpulse

# Start infrastructure
docker compose up -d

# Run tests
mvn test -B
```

## Architecture Patterns

All implementations must follow established patterns:

- **Entities**: Extend `BaseEntity` (provides id, createdAt, updatedAt, version)
- **Services**: Use `@Service` annotation with `@Autowired` dependency injection
- **Repositories**: Extend `JpaRepository<Entity, Long>` with custom `@Query` methods
- **Monetary Values**: Use `BigDecimal` with scale 2 and `RoundingMode.HALF_UP`
- **Logging**: Use SLF4J via `LoggerFactory.getLogger(Class.class)`
- **Transactions**: Annotate service methods with `@Transactional` as needed
- **Validation**: Proper exception handling with meaningful error messages

## Success Criteria

Implementation meets the acceptance criteria and architectural patterns defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
