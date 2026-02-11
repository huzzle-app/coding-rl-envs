# FleetPulse Greenfield Tasks

This document contains greenfield implementation tasks for the FleetPulse fleet management platform. Each task requires implementing a new module from scratch while following the existing architectural patterns established in the codebase.

## Existing Architecture Patterns

Before implementing, study the existing patterns:

- **Entities**: Extend `BaseEntity` (provides id, createdAt, updatedAt, version)
- **Services**: Use `@Service` annotation, inject dependencies via `@Autowired`
- **Repositories**: Extend `JpaRepository<Entity, Long>`
- **BigDecimal**: Use for all monetary and precision-sensitive calculations
- **Logging**: Use SLF4J (`LoggerFactory.getLogger(Class.class)`)
- **Transactions**: Annotate service methods with `@Transactional` as needed

**Test command**: `mvn test`

---

## Task 1: Driver Safety Scoring Service

### Overview

Implement a comprehensive driver safety scoring system that analyzes driver behavior, calculates safety scores, and manages safety events. The service integrates with the tracking module for telemetry data and the compliance module for violation history.

### Module Location

Create a new `safety` module at `safety/src/main/java/com/fleetpulse/safety/`

### Interface Contract

```java
package com.fleetpulse.safety.service;

import com.fleetpulse.safety.model.DriverSafetyScore;
import com.fleetpulse.safety.model.SafetyEvent;
import com.fleetpulse.safety.model.SafetyEventType;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * Service for calculating and managing driver safety scores.
 *
 * Safety scores range from 0-100 where:
 *   - 90-100: Excellent (eligible for safety bonuses)
 *   - 75-89:  Good (standard operations)
 *   - 60-74:  Fair (monitoring required)
 *   - Below 60: Poor (intervention required)
 *
 * Scores are calculated based on weighted factors:
 *   - Hard braking events: -3 points each
 *   - Rapid acceleration: -2 points each
 *   - Speeding violations: -5 points each
 *   - Hours of Service violations: -10 points each
 *   - Accident involvement: -25 points each
 *   - Safe driving days: +1 point per day (max 30)
 */
public interface DriverSafetyService {

    /**
     * Calculates the current safety score for a driver based on events
     * from the past 30 days.
     *
     * @param driverId the driver's unique identifier
     * @return the calculated safety score (0-100), or empty if driver not found
     */
    Optional<DriverSafetyScore> calculateSafetyScore(Long driverId);

    /**
     * Recalculates safety scores for all active drivers.
     * Should be called as a scheduled job (e.g., nightly).
     *
     * @return the number of drivers whose scores were updated
     */
    int recalculateAllScores();

    /**
     * Records a new safety event for a driver.
     *
     * @param driverId the driver involved
     * @param eventType the type of safety event
     * @param severity severity level (1-5, where 5 is most severe)
     * @param latitude GPS latitude where event occurred
     * @param longitude GPS longitude where event occurred
     * @param description detailed description of the event
     * @return the created SafetyEvent
     * @throws IllegalArgumentException if driverId is invalid or severity out of range
     */
    SafetyEvent recordSafetyEvent(Long driverId, SafetyEventType eventType,
                                   int severity, double latitude, double longitude,
                                   String description);

    /**
     * Retrieves all safety events for a driver within a date range.
     *
     * @param driverId the driver's identifier
     * @param startDate start of the date range (inclusive)
     * @param endDate end of the date range (inclusive)
     * @return list of safety events, ordered by timestamp descending
     */
    List<SafetyEvent> getDriverSafetyEvents(Long driverId, LocalDate startDate, LocalDate endDate);

    /**
     * Gets drivers with scores below the threshold requiring intervention.
     *
     * @param threshold the score threshold (drivers below this need attention)
     * @return list of driver safety scores below the threshold
     */
    List<DriverSafetyScore> getDriversRequiringIntervention(int threshold);

    /**
     * Calculates the fleet-wide average safety score.
     *
     * @return the average score across all active drivers
     */
    BigDecimal calculateFleetAverageScore();

    /**
     * Determines if a driver is eligible for the safety bonus program.
     * Requires score >= 90 for the past 90 consecutive days.
     *
     * @param driverId the driver's identifier
     * @return true if eligible for safety bonus
     */
    boolean isEligibleForSafetyBonus(Long driverId);

    /**
     * Gets the historical trend of a driver's safety score.
     *
     * @param driverId the driver's identifier
     * @param months number of months of history to retrieve
     * @return list of monthly average scores, most recent first
     */
    List<BigDecimal> getSafetyScoreTrend(Long driverId, int months);
}
```

### Required Classes/Models

1. **`SafetyEvent`** (Entity)
   - Extends `BaseEntity`
   - Fields: `driverId` (Long), `vehicleId` (Long), `eventType` (SafetyEventType), `severity` (int 1-5), `latitude` (double), `longitude` (double), `description` (String), `occurredAt` (LocalDateTime), `resolved` (boolean)

2. **`DriverSafetyScore`** (Entity)
   - Extends `BaseEntity`
   - Fields: `driverId` (Long), `score` (BigDecimal), `hardBrakingCount` (int), `rapidAccelerationCount` (int), `speedingCount` (int), `hosViolationCount` (int), `accidentCount` (int), `safeDrivingDays` (int), `calculatedAt` (LocalDateTime), `scoreCategory` (String: EXCELLENT/GOOD/FAIR/POOR)

3. **`SafetyEventType`** (Enum)
   - Values: `HARD_BRAKING`, `RAPID_ACCELERATION`, `SPEEDING`, `HOS_VIOLATION`, `ACCIDENT`, `DISTRACTED_DRIVING`, `LANE_DEPARTURE`, `FOLLOWING_TOO_CLOSE`

4. **`SafetyEventRepository`** (Repository)
   - Extend `JpaRepository<SafetyEvent, Long>`
   - Custom queries for date range, driver, and event type filters

5. **`DriverSafetyScoreRepository`** (Repository)
   - Extend `JpaRepository<DriverSafetyScore, Long>`
   - Query for latest score by driver, scores below threshold

6. **`SafetyController`** (REST Controller)
   - Endpoints for retrieving scores, recording events, intervention list

### Acceptance Criteria

- [ ] All entity classes extend `BaseEntity` and use proper JPA annotations
- [ ] Safety scores calculated using `BigDecimal` with proper rounding (`RoundingMode.HALF_UP`)
- [ ] Service methods are properly annotated with `@Transactional`
- [ ] Repository uses `@Query` with JOIN FETCH to avoid N+1 queries
- [ ] Unit tests achieve >= 80% code coverage
- [ ] Integration tests verify score calculation accuracy
- [ ] Controller endpoints return proper HTTP status codes
- [ ] Service integrates with existing `ComplianceService` for HOS violations

### Integration Points

- **TrackingService**: Subscribe to position updates for speed/acceleration analysis
- **ComplianceService**: Query HOS violation history
- **NotificationService**: Trigger alerts when scores drop below threshold
- **AnalyticsService**: Provide data for fleet safety dashboards

---

## Task 2: Fuel Card Integration Service

### Overview

Implement a fuel card management system that tracks fuel transactions, detects anomalies (potential fraud), calculates fuel efficiency metrics, and integrates with external fuel card provider APIs.

### Module Location

Create a new `fuelcard` module at `fuelcard/src/main/java/com/fleetpulse/fuelcard/`

### Interface Contract

```java
package com.fleetpulse.fuelcard.service;

import com.fleetpulse.fuelcard.model.FuelCard;
import com.fleetpulse.fuelcard.model.FuelTransaction;
import com.fleetpulse.fuelcard.model.FuelAnomalyAlert;
import com.fleetpulse.fuelcard.model.FuelEfficiencyReport;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * Service for managing fuel cards, processing transactions, and detecting anomalies.
 *
 * Fuel card system handles:
 *   - Card issuance and lifecycle management
 *   - Transaction processing and validation
 *   - Anomaly detection (fraud, misuse, unusual patterns)
 *   - Fuel efficiency metrics per vehicle/driver
 *   - Integration with external fuel card provider APIs
 *
 * Anomaly detection rules:
 *   - Transaction > 150% of vehicle tank capacity
 *   - Transaction location > 50 miles from last known vehicle position
 *   - Multiple transactions within 2 hours
 *   - Transaction amount > $500 single purchase
 *   - Fuel grade mismatch (diesel in gasoline vehicle)
 */
public interface FuelCardService {

    /**
     * Issues a new fuel card for a driver/vehicle combination.
     *
     * @param driverId the driver who will use the card
     * @param vehicleId the vehicle associated with the card
     * @param dailyLimit maximum daily spend limit
     * @param monthlyLimit maximum monthly spend limit
     * @return the newly created FuelCard
     * @throws IllegalStateException if driver or vehicle already has an active card
     */
    FuelCard issueCard(Long driverId, Long vehicleId, BigDecimal dailyLimit, BigDecimal monthlyLimit);

    /**
     * Deactivates a fuel card (lost, stolen, or end of assignment).
     *
     * @param cardId the card to deactivate
     * @param reason the reason for deactivation
     * @return the updated FuelCard
     * @throws IllegalArgumentException if card not found
     */
    FuelCard deactivateCard(Long cardId, String reason);

    /**
     * Processes an incoming fuel transaction from the card provider.
     *
     * @param cardNumber the fuel card number used
     * @param amount the transaction amount in USD
     * @param gallons the number of gallons purchased
     * @param fuelGrade the fuel type (REGULAR, PREMIUM, DIESEL)
     * @param merchantName the gas station name
     * @param merchantLatitude station GPS latitude
     * @param merchantLongitude station GPS longitude
     * @param transactionId external transaction reference
     * @return the processed FuelTransaction
     * @throws IllegalArgumentException if card not found or inactive
     */
    FuelTransaction processTransaction(String cardNumber, BigDecimal amount, BigDecimal gallons,
                                        String fuelGrade, String merchantName,
                                        double merchantLatitude, double merchantLongitude,
                                        String transactionId);

    /**
     * Validates a transaction and returns any detected anomalies.
     * Does not persist - used for real-time authorization decisions.
     *
     * @param transaction the transaction to validate
     * @return list of detected anomalies (empty if transaction is normal)
     */
    List<FuelAnomalyAlert> validateTransaction(FuelTransaction transaction);

    /**
     * Retrieves all transactions for a vehicle within a date range.
     *
     * @param vehicleId the vehicle identifier
     * @param startDate start of the date range (inclusive)
     * @param endDate end of the date range (inclusive)
     * @return list of transactions ordered by timestamp descending
     */
    List<FuelTransaction> getVehicleTransactions(Long vehicleId, LocalDate startDate, LocalDate endDate);

    /**
     * Calculates fuel efficiency metrics for a vehicle.
     *
     * @param vehicleId the vehicle to analyze
     * @param startDate start of the analysis period
     * @param endDate end of the analysis period
     * @return the fuel efficiency report
     */
    FuelEfficiencyReport calculateFuelEfficiency(Long vehicleId, LocalDate startDate, LocalDate endDate);

    /**
     * Gets unresolved anomaly alerts requiring investigation.
     *
     * @return list of open anomaly alerts, ordered by severity descending
     */
    List<FuelAnomalyAlert> getUnresolvedAlerts();

    /**
     * Resolves an anomaly alert after investigation.
     *
     * @param alertId the alert to resolve
     * @param resolution the investigation outcome (CONFIRMED_FRAUD, FALSE_POSITIVE, POLICY_VIOLATION)
     * @param notes investigation notes
     * @return the updated alert
     */
    FuelAnomalyAlert resolveAlert(Long alertId, String resolution, String notes);

    /**
     * Calculates the total fuel spend for a fleet within a period.
     *
     * @param startDate start of the period
     * @param endDate end of the period
     * @return total spend as BigDecimal
     */
    BigDecimal calculateFleetFuelSpend(LocalDate startDate, LocalDate endDate);

    /**
     * Gets cards approaching their monthly limit (>= 80% used).
     *
     * @return list of cards nearing their monthly limit
     */
    List<FuelCard> getCardsNearingLimit();

    /**
     * Syncs transactions from the external fuel card provider API.
     * Should be called periodically to import new transactions.
     *
     * @param sinceTimestamp only fetch transactions after this time
     * @return number of new transactions imported
     */
    int syncTransactionsFromProvider(java.time.Instant sinceTimestamp);
}
```

### Required Classes/Models

1. **`FuelCard`** (Entity)
   - Extends `BaseEntity`
   - Fields: `cardNumber` (String, encrypted), `driverId` (Long), `vehicleId` (Long), `status` (FuelCardStatus), `dailyLimit` (BigDecimal), `monthlyLimit` (BigDecimal), `currentMonthSpend` (BigDecimal), `issuedAt` (LocalDateTime), `expiresAt` (LocalDate), `deactivationReason` (String)

2. **`FuelTransaction`** (Entity)
   - Extends `BaseEntity`
   - Fields: `fuelCardId` (Long), `vehicleId` (Long), `driverId` (Long), `amount` (BigDecimal), `gallons` (BigDecimal), `pricePerGallon` (BigDecimal), `fuelGrade` (String), `merchantName` (String), `merchantLatitude` (double), `merchantLongitude` (double), `externalTransactionId` (String), `transactionTime` (LocalDateTime), `odometer` (Long)

3. **`FuelAnomalyAlert`** (Entity)
   - Extends `BaseEntity`
   - Fields: `transactionId` (Long), `alertType` (FuelAnomalyType), `severity` (int 1-5), `description` (String), `vehicleLocationAtTime` (String), `distanceFromVehicle` (BigDecimal), `resolved` (boolean), `resolution` (String), `resolvedBy` (Long), `resolvedAt` (LocalDateTime)

4. **`FuelEfficiencyReport`** (DTO - not entity)
   - Fields: `vehicleId` (Long), `periodStart` (LocalDate), `periodEnd` (LocalDate), `totalGallons` (BigDecimal), `totalMiles` (BigDecimal), `milesPerGallon` (BigDecimal), `totalCost` (BigDecimal), `costPerMile` (BigDecimal), `comparedToFleetAverage` (BigDecimal, percentage)

5. **`FuelCardStatus`** (Enum)
   - Values: `ACTIVE`, `SUSPENDED`, `DEACTIVATED`, `EXPIRED`, `LOST`, `STOLEN`

6. **`FuelAnomalyType`** (Enum)
   - Values: `OVER_CAPACITY`, `LOCATION_MISMATCH`, `RAPID_TRANSACTIONS`, `EXCESSIVE_AMOUNT`, `FUEL_GRADE_MISMATCH`, `AFTER_HOURS`, `UNUSUAL_MERCHANT`

7. **`FuelCardRepository`**, **`FuelTransactionRepository`**, **`FuelAnomalyAlertRepository`** (Repositories)

8. **`FuelCardController`** (REST Controller)

### Acceptance Criteria

- [ ] All monetary calculations use `BigDecimal` with scale 2 and `RoundingMode.HALF_UP`
- [ ] Anomaly detection triggers for all defined rules
- [ ] Card number stored with encryption (use existing security patterns)
- [ ] Repository queries use pagination for large result sets
- [ ] Fuel efficiency calculations handle edge cases (zero miles, zero gallons)
- [ ] Unit tests for all anomaly detection rules
- [ ] Integration tests for transaction processing flow
- [ ] Controller endpoints follow REST conventions

### Integration Points

- **TrackingService**: Get vehicle location for distance anomaly detection
- **VehicleService**: Get vehicle specifications (tank capacity, fuel type)
- **BillingService**: Include fuel costs in customer invoices
- **NotificationService**: Alert on high-severity anomalies
- **AnalyticsService**: Fuel cost trends and efficiency reports

---

## Task 3: Route Optimization Engine

### Overview

Implement an advanced route optimization engine that calculates optimal routes considering multiple constraints: traffic, vehicle capacity, driver hours, time windows, and fuel efficiency. The engine supports both single-route optimization and multi-vehicle fleet-wide scheduling.

### Module Location

Create a new `optimization` module at `optimization/src/main/java/com/fleetpulse/optimization/`

### Interface Contract

```java
package com.fleetpulse.optimization.service;

import com.fleetpulse.optimization.model.*;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * Service for optimizing routes and fleet scheduling.
 *
 * Optimization considers multiple factors:
 *   - Distance minimization
 *   - Time window constraints (delivery windows)
 *   - Vehicle capacity (weight, volume, pallet count)
 *   - Driver hours of service limits
 *   - Traffic patterns (time-of-day adjustments)
 *   - Fuel efficiency (avoid stop-and-go routes)
 *   - Priority stops (must-visit first)
 *
 * Uses a combination of algorithms:
 *   - Nearest neighbor heuristic for initial solution
 *   - 2-opt improvement for local optimization
 *   - Simulated annealing for escaping local minima
 */
public interface RouteOptimizationService {

    /**
     * Optimizes a single route given a set of stops.
     *
     * @param request the optimization request containing stops and constraints
     * @return the optimized route with ordered stops and metrics
     * @throws IllegalArgumentException if request is invalid or stops are empty
     */
    OptimizedRoute optimizeRoute(RouteOptimizationRequest request);

    /**
     * Optimizes routes across multiple vehicles for fleet-wide scheduling.
     * Assigns stops to vehicles and orders each vehicle's route optimally.
     *
     * @param request the fleet optimization request
     * @return assignment of optimized routes per vehicle
     */
    FleetOptimizationResult optimizeFleet(FleetOptimizationRequest request);

    /**
     * Calculates the estimated time of arrival for each stop in a route.
     *
     * @param route the route with ordered stops
     * @param departureTime when the vehicle departs from origin
     * @param includeTraffic whether to adjust for historical traffic patterns
     * @return map of stop ID to estimated arrival time
     */
    Map<Long, LocalDateTime> calculateETAs(OptimizedRoute route, LocalDateTime departureTime, boolean includeTraffic);

    /**
     * Re-optimizes a route after a new stop is added mid-route.
     *
     * @param currentRoute the existing route being executed
     * @param newStop the stop to insert
     * @param currentVehiclePosition current GPS position of the vehicle
     * @param completedStopIds IDs of stops already completed
     * @return the updated optimized route
     */
    OptimizedRoute insertStopAndReoptimize(OptimizedRoute currentRoute, Stop newStop,
                                            GeoPoint currentVehiclePosition,
                                            List<Long> completedStopIds);

    /**
     * Calculates the cost savings from route optimization compared to naive ordering.
     *
     * @param originalStops stops in their original order
     * @param optimizedRoute the optimized route
     * @return savings breakdown (distance, time, fuel cost)
     */
    OptimizationSavings calculateSavings(List<Stop> originalStops, OptimizedRoute optimizedRoute);

    /**
     * Validates that a proposed route satisfies all constraints.
     *
     * @param route the route to validate
     * @param vehicleId the vehicle that would execute this route
     * @param driverId the driver assigned
     * @return validation result with any constraint violations
     */
    RouteValidationResult validateRoute(OptimizedRoute route, Long vehicleId, Long driverId);

    /**
     * Gets traffic-adjusted travel time between two points.
     *
     * @param origin starting point
     * @param destination ending point
     * @param departureTime when travel begins
     * @return estimated travel duration considering traffic
     */
    Duration getTrafficAdjustedTravelTime(GeoPoint origin, GeoPoint destination, LocalDateTime departureTime);

    /**
     * Calculates fuel consumption for a route based on distance, vehicle type, and conditions.
     *
     * @param route the route to analyze
     * @param vehicleId the vehicle that would execute this route
     * @return estimated fuel consumption in gallons
     */
    BigDecimal estimateFuelConsumption(OptimizedRoute route, Long vehicleId);

    /**
     * Finds the optimal vehicle for a set of stops based on proximity, capacity, and availability.
     *
     * @param stops the stops that need to be served
     * @param availableVehicleIds vehicles available for assignment
     * @param requiredCapacity minimum capacity requirements
     * @return the optimal vehicle ID and reasoning
     */
    VehicleRecommendation recommendVehicle(List<Stop> stops, List<Long> availableVehicleIds,
                                            CapacityRequirements requiredCapacity);

    /**
     * Generates alternative routes with different optimization priorities.
     *
     * @param request the base optimization request
     * @param priorities list of priority orderings (e.g., FASTEST, SHORTEST, FUEL_EFFICIENT)
     * @return list of alternative routes, one per priority
     */
    List<OptimizedRoute> generateAlternatives(RouteOptimizationRequest request, List<OptimizationPriority> priorities);
}
```

### Required Classes/Models

1. **`Stop`** (Entity)
   - Extends `BaseEntity`
   - Fields: `name` (String), `address` (String), `latitude` (double), `longitude` (double), `timeWindowStart` (LocalDateTime), `timeWindowEnd` (LocalDateTime), `serviceDurationMinutes` (int), `priority` (int), `weightKg` (BigDecimal), `volumeCubicMeters` (BigDecimal), `specialInstructions` (String)

2. **`OptimizedRoute`** (Entity)
   - Extends `BaseEntity`
   - Fields: `vehicleId` (Long), `driverId` (Long), `orderedStopIds` (List<Long>), `totalDistanceKm` (BigDecimal), `estimatedDurationMinutes` (int), `estimatedFuelGallons` (BigDecimal), `optimizationScore` (BigDecimal), `algorithmUsed` (String), `optimizedAt` (LocalDateTime)

3. **`RouteOptimizationRequest`** (DTO)
   - Fields: `stops` (List<Stop>), `originLatitude` (double), `originLongitude` (double), `vehicleId` (Long), `maxRouteTimeMinutes` (int), `priority` (OptimizationPriority), `respectTimeWindows` (boolean), `avoidTolls` (boolean), `avoidHighways` (boolean)

4. **`FleetOptimizationRequest`** (DTO)
   - Fields: `allStops` (List<Stop>), `availableVehicles` (List<Long>), `depotLatitude` (double), `depotLongitude` (double), `balanceWorkload` (boolean), `maxStopsPerVehicle` (int)

5. **`FleetOptimizationResult`** (DTO)
   - Fields: `vehicleRoutes` (Map<Long, OptimizedRoute>), `unassignedStops` (List<Stop>), `totalFleetDistance` (BigDecimal), `totalFleetTime` (int), `optimizationDurationMs` (long)

6. **`OptimizationSavings`** (DTO)
   - Fields: `distanceSavedKm` (BigDecimal), `timeSavedMinutes` (int), `fuelSavedGallons` (BigDecimal), `estimatedCostSavings` (BigDecimal), `percentageImprovement` (BigDecimal)

7. **`RouteValidationResult`** (DTO)
   - Fields: `valid` (boolean), `violations` (List<ConstraintViolation>), `warnings` (List<String>)

8. **`ConstraintViolation`** (DTO)
   - Fields: `constraintType` (String: TIME_WINDOW, CAPACITY, HOS, etc.), `stopId` (Long), `message` (String), `severity` (int)

9. **`GeoPoint`** (Record)
   - Fields: `latitude` (double), `longitude` (double)

10. **`CapacityRequirements`** (DTO)
    - Fields: `weightKg` (BigDecimal), `volumeCubicMeters` (BigDecimal), `palletCount` (int)

11. **`VehicleRecommendation`** (DTO)
    - Fields: `vehicleId` (Long), `score` (BigDecimal), `reasons` (List<String>), `alternativeVehicleIds` (List<Long>)

12. **`OptimizationPriority`** (Enum)
    - Values: `FASTEST`, `SHORTEST`, `FUEL_EFFICIENT`, `BALANCED`, `MINIMIZE_STOPS`

13. **`StopRepository`**, **`OptimizedRouteRepository`** (Repositories)

14. **`RouteOptimizationController`** (REST Controller)

### Acceptance Criteria

- [ ] Optimization algorithm terminates within configurable time limit (default 30 seconds)
- [ ] All distance calculations use proper geospatial formulas (Haversine)
- [ ] Fuel estimates use `BigDecimal` with proper precision
- [ ] Time window constraints are strictly enforced unless flagged otherwise
- [ ] HOS validation integrates with `ComplianceService`
- [ ] Fleet optimization distributes workload fairly when `balanceWorkload=true`
- [ ] Unit tests verify optimization improves over naive ordering in 95%+ of test cases
- [ ] Performance tests confirm < 5 second optimization for up to 50 stops
- [ ] Integration tests verify constraint validation
- [ ] Algorithm handles edge cases: single stop, two stops, circular routes

### Integration Points

- **VehicleService**: Get vehicle specifications (capacity, fuel efficiency)
- **TrackingService**: Get current vehicle positions for dynamic re-optimization
- **ComplianceService**: Validate driver HOS for route duration
- **RouteService**: Get existing route waypoints
- **DispatchService**: Assign optimized routes to drivers
- **BillingService**: Calculate route cost estimates for customer quotes

---

## Implementation Guidelines

### Getting Started

1. Create the new module directory structure:
   ```
   <module>/
   ├── src/
   │   ├── main/java/com/fleetpulse/<module>/
   │   │   ├── model/
   │   │   ├── repository/
   │   │   ├── service/
   │   │   └── controller/
   │   └── test/java/com/fleetpulse/<module>/
   └── pom.xml
   ```

2. Add module to parent `pom.xml`:
   ```xml
   <module><module-name></module>
   ```

3. Create module `pom.xml` with dependencies on `shared` module

### Testing Requirements

Each module must include:

- **Unit tests**: Test service logic in isolation using Mockito
- **Integration tests**: Test repository queries with `@DataJpaTest`
- **Controller tests**: Test REST endpoints with `@WebMvcTest`
- **Edge case tests**: Empty inputs, null handling, boundary conditions

### Code Quality

- Follow existing code style (see `VehicleService`, `InvoiceService` for examples)
- Use SLF4J for logging with appropriate log levels
- Document public methods with Javadoc
- Handle exceptions gracefully with meaningful error messages
- Use `Optional` for nullable return values
