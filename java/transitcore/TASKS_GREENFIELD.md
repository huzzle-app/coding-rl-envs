# TransitCore Greenfield Tasks

These tasks require implementing NEW modules from scratch for the TransitCore public transit platform. Each task builds on the existing architecture patterns (final classes, static utility methods, record types, JUnit 5 tests) and integrates with existing services.

---

## Task 1: Passenger Information Display Service

### Overview
Implement a service that computes real-time passenger information for display at transit stops and stations. The service aggregates arrival predictions, service alerts, and capacity indicators to produce display-ready content for various screen formats.

### Interface Contract

```java
package com.terminalbench.transitcore;

import java.util.List;
import java.util.Map;

/**
 * Computes passenger information for transit stop displays.
 * Supports multiple display formats and accessibility requirements.
 */
public interface PassengerInfoDisplay {

    /**
     * Represents a single arrival entry for display.
     *
     * @param routeId       unique route identifier
     * @param destination   human-readable destination name
     * @param etaMinutes    estimated minutes until arrival (0 = arriving now)
     * @param capacityLevel capacity indicator: "available", "crowded", "full"
     * @param accessible    whether vehicle has accessibility features
     */
    record ArrivalEntry(
        String routeId,
        String destination,
        int etaMinutes,
        String capacityLevel,
        boolean accessible
    ) {}

    /**
     * Represents a service alert affecting a stop or route.
     *
     * @param alertId    unique alert identifier
     * @param severity   "info", "warning", "critical"
     * @param headline   short summary (max 80 chars)
     * @param affectedRoutes list of affected route IDs
     * @param expiresAt  epoch seconds when alert expires
     */
    record ServiceAlert(
        String alertId,
        String severity,
        String headline,
        List<String> affectedRoutes,
        long expiresAt
    ) {}

    /**
     * Represents display content ready for rendering.
     *
     * @param stopId         the stop this content is for
     * @param generatedAt    epoch seconds when content was generated
     * @param arrivals       sorted list of upcoming arrivals
     * @param alerts         active alerts affecting this stop
     * @param scrollMessage  optional scrolling message (may be null)
     */
    record DisplayContent(
        String stopId,
        long generatedAt,
        List<ArrivalEntry> arrivals,
        List<ServiceAlert> alerts,
        String scrollMessage
    ) {}

    /**
     * Generates display content for a stop.
     *
     * @param stopId           the stop to generate content for
     * @param predictions      map of routeId to predicted ETA in seconds
     * @param capacities       map of routeId to current passenger count
     * @param vehicleCapacities map of routeId to max passenger capacity
     * @param alerts           all active alerts (filter by stop/routes)
     * @param nowEpochSec      current timestamp in epoch seconds
     * @param maxArrivals      maximum arrivals to include (typically 4-6)
     * @return display content ready for rendering
     */
    DisplayContent generateContent(
        String stopId,
        Map<String, Long> predictions,
        Map<String, Integer> capacities,
        Map<String, Integer> vehicleCapacities,
        List<ServiceAlert> alerts,
        long nowEpochSec,
        int maxArrivals
    );

    /**
     * Computes capacity level label from passenger count and vehicle capacity.
     *
     * @param currentPassengers current passenger count
     * @param maxCapacity       vehicle maximum capacity
     * @return "available" if <70%, "crowded" if 70-90%, "full" if >=90%
     */
    String capacityLevel(int currentPassengers, int maxCapacity);

    /**
     * Filters and prioritizes alerts for a specific stop.
     * Critical alerts first, then warning, then info.
     * Expired alerts are excluded.
     *
     * @param allAlerts       all active alerts in the system
     * @param stopRoutes      routes that serve this stop
     * @param nowEpochSec     current timestamp
     * @param maxAlerts       maximum alerts to return
     * @return filtered and sorted alerts
     */
    List<ServiceAlert> filterAlerts(
        List<ServiceAlert> allAlerts,
        List<String> stopRoutes,
        long nowEpochSec,
        int maxAlerts
    );

    /**
     * Generates a scroll message summarizing disruptions.
     * Returns null if no disruptions warrant a scroll message.
     *
     * @param alerts    active alerts for this stop
     * @return scroll message or null
     */
    String generateScrollMessage(List<ServiceAlert> alerts);
}
```

### Required Classes

1. **`PassengerInfoDisplayService.java`** - Implementation of the interface
2. **Records are defined in the interface** - `ArrivalEntry`, `ServiceAlert`, `DisplayContent`

### Architectural Patterns to Follow

- Use `final class` with private constructor for utility methods if needed
- Sort arrivals by ETA ascending, then by routeId for stable ordering
- Use `Comparator` chains similar to `RoutingHeuristics.selectHub()`
- Threshold logic should use `>=` correctly (learn from existing bugs)
- Handle edge cases: empty predictions, all alerts expired, zero capacity

### Acceptance Criteria

1. **Unit Tests** (create `PassengerInfoDisplayTest.java`):
   - `capacityLevelBoundaries()` - Test 69%, 70%, 89%, 90% thresholds
   - `arrivalsSortedByEtaThenRouteId()` - Verify correct ordering
   - `filterAlertsExcludesExpired()` - Expired alerts not included
   - `filterAlertsPrioritizesBySeverity()` - Critical > Warning > Info
   - `generateContentIntegration()` - Full flow test
   - `scrollMessageOnlyForCritical()` - Null when no critical alerts

2. **Integration Points**:
   - `CapacityBalancer` - Use capacity thresholds consistently
   - `SlaModel` - ETA calculations align with SLA concepts
   - `WatermarkWindow` - Timestamp handling patterns

3. **Test Command**: `mvn test`

4. **Coverage**: All public methods must have test coverage

---

## Task 2: Accessibility Routing Engine

### Overview
Implement a routing engine that finds accessible routes for passengers with mobility requirements. The engine considers elevator availability, platform gaps, step-free access, and real-time accessibility equipment status.

### Interface Contract

```java
package com.terminalbench.transitcore;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Computes accessible routes considering mobility requirements and
 * real-time accessibility equipment status.
 */
public interface AccessibilityRouter {

    /**
     * Accessibility requirements for a passenger.
     *
     * @param wheelchairAccess   requires wheelchair-accessible vehicle
     * @param stepFreeAccess     requires step-free boarding
     * @param elevatorRequired   cannot use stairs
     * @param maxWalkingMeters   maximum walking distance between stops
     * @param audioAnnouncements requires audio announcements
     */
    record AccessibilityNeeds(
        boolean wheelchairAccess,
        boolean stepFreeAccess,
        boolean elevatorRequired,
        int maxWalkingMeters,
        boolean audioAnnouncements
    ) {}

    /**
     * Status of accessibility equipment at a stop.
     *
     * @param stopId             stop identifier
     * @param elevatorWorking    elevator operational status
     * @param rampAvailable      boarding ramp available
     * @param tactilePaving      tactile paving present
     * @param audioSystem        audio announcement system working
     * @param platformGapCm      gap between platform and vehicle in cm
     */
    record StopAccessibility(
        String stopId,
        boolean elevatorWorking,
        boolean rampAvailable,
        boolean tactilePaving,
        boolean audioSystem,
        int platformGapCm
    ) {}

    /**
     * A route segment between two stops.
     *
     * @param fromStop        origin stop ID
     * @param toStop          destination stop ID
     * @param routeId         route to take
     * @param walkingMeters   walking distance if transfer (0 if same platform)
     * @param vehicleAccessible whether vehicle on this route is accessible
     */
    record RouteSegment(
        String fromStop,
        String toStop,
        String routeId,
        int walkingMeters,
        boolean vehicleAccessible
    ) {}

    /**
     * Result of an accessibility route search.
     *
     * @param segments          ordered list of route segments
     * @param totalTimeMinutes  estimated total journey time
     * @param accessibilityScore score from 0-100 (higher = more accessible)
     * @param warnings          list of accessibility concerns
     */
    record AccessibleRoute(
        List<RouteSegment> segments,
        int totalTimeMinutes,
        int accessibilityScore,
        List<String> warnings
    ) {}

    /**
     * Finds accessible routes between origin and destination.
     *
     * @param origin          origin stop ID
     * @param destination     destination stop ID
     * @param needs           passenger accessibility requirements
     * @param stopStatus      current accessibility status of all stops
     * @param routeTimes      map of "fromStop:toStop:routeId" to travel minutes
     * @param maxTransfers    maximum number of transfers allowed
     * @return list of accessible routes, sorted by accessibility score descending
     */
    List<AccessibleRoute> findAccessibleRoutes(
        String origin,
        String destination,
        AccessibilityNeeds needs,
        Map<String, StopAccessibility> stopStatus,
        Map<String, Integer> routeTimes,
        int maxTransfers
    );

    /**
     * Checks if a stop meets accessibility requirements.
     *
     * @param status  stop accessibility status
     * @param needs   passenger requirements
     * @return true if stop is accessible for these needs
     */
    boolean stopMeetsNeeds(StopAccessibility status, AccessibilityNeeds needs);

    /**
     * Computes accessibility score for a route.
     * Considers: working elevators, platform gaps, walking distances.
     *
     * @param segments    route segments
     * @param stopStatus  accessibility status of stops
     * @param needs       passenger requirements
     * @return score from 0-100
     */
    int computeAccessibilityScore(
        List<RouteSegment> segments,
        Map<String, StopAccessibility> stopStatus,
        AccessibilityNeeds needs
    );

    /**
     * Generates warnings for accessibility concerns on a route.
     * Examples: "Elevator at StopX reported out of service",
     *           "Platform gap of 8cm at StopY exceeds recommended 5cm"
     *
     * @param segments    route segments
     * @param stopStatus  accessibility status
     * @param needs       passenger requirements
     * @return list of warning messages
     */
    List<String> generateWarnings(
        List<RouteSegment> segments,
        Map<String, StopAccessibility> stopStatus,
        AccessibilityNeeds needs
    );

    /**
     * Checks if a platform gap is acceptable for wheelchair users.
     * Gap must be <= 5cm for wheelchairs, <= 8cm for step-free.
     *
     * @param gapCm           platform gap in centimeters
     * @param wheelchairUser  whether user is a wheelchair user
     * @return true if gap is acceptable
     */
    boolean platformGapAcceptable(int gapCm, boolean wheelchairUser);
}
```

### Required Classes

1. **`AccessibilityRouterService.java`** - Implementation of the interface
2. **Records are defined in the interface** - `AccessibilityNeeds`, `StopAccessibility`, `RouteSegment`, `AccessibleRoute`

### Architectural Patterns to Follow

- Use `final class` pattern consistent with existing codebase
- Threshold comparisons: Be careful with `>` vs `>=` (reference `PolicyEngine` patterns)
- Scoring should use bounded ratios similar to `StatisticsReducer.boundedRatio()`
- Route sorting: Use `Comparator` chains for stable ordering
- Handle edge cases: No accessible routes, all elevators down, origin equals destination

### Acceptance Criteria

1. **Unit Tests** (create `AccessibilityRouterTest.java`):
   - `stopMeetsNeedsElevatorRequired()` - Elevator check
   - `stopMeetsNeedsWheelchairAccess()` - Ramp requirement
   - `platformGapBoundariesWheelchair()` - 5cm threshold for wheelchair
   - `platformGapBoundariesStepFree()` - 8cm threshold for step-free
   - `computeScoreDeductsForBrokenElevator()` - Score reduction
   - `generateWarningsForPlatformGap()` - Warning generation
   - `findAccessibleRoutesRespectsMaxTransfers()` - Transfer limit
   - `routesSortedByAccessibilityScore()` - Descending order

2. **Integration Points**:
   - `RoutingHeuristics` - Follow hub selection patterns for stop selection
   - `PolicyEngine` - Threshold logic patterns
   - `CapacityBalancer` - Boundary condition handling

3. **Test Command**: `mvn test`

4. **Coverage**: All public methods must have test coverage

---

## Task 3: Real-Time Arrival Predictor

### Overview
Implement a prediction engine that estimates vehicle arrival times using historical patterns, current traffic conditions, and real-time GPS positions. The predictor adjusts confidence intervals based on data quality and applies corrections for known delay patterns.

### Interface Contract

```java
package com.terminalbench.transitcore;

import java.util.List;
import java.util.Map;

/**
 * Predicts vehicle arrival times using historical patterns,
 * real-time positions, and traffic conditions.
 */
public interface ArrivalPredictor {

    /**
     * Real-time vehicle position and status.
     *
     * @param vehicleId        unique vehicle identifier
     * @param routeId          route the vehicle is serving
     * @param lastStopId       most recent stop visited
     * @param distanceToNextM  meters to next stop
     * @param currentSpeedKph  current speed in km/h
     * @param timestampEpoch   position timestamp in epoch seconds
     * @param passengerLoad    current passenger count
     */
    record VehiclePosition(
        String vehicleId,
        String routeId,
        String lastStopId,
        int distanceToNextM,
        double currentSpeedKph,
        long timestampEpoch,
        int passengerLoad
    ) {}

    /**
     * Historical travel time statistics between stops.
     *
     * @param fromStop         origin stop
     * @param toStop           destination stop
     * @param routeId          route ID
     * @param hourOfDay        hour (0-23) this data is for
     * @param dayType          "weekday", "saturday", "sunday"
     * @param medianSeconds    median travel time
     * @param p90Seconds       90th percentile travel time
     * @param sampleCount      number of observations
     */
    record HistoricalTravelTime(
        String fromStop,
        String toStop,
        String routeId,
        int hourOfDay,
        String dayType,
        int medianSeconds,
        int p90Seconds,
        int sampleCount
    ) {}

    /**
     * Arrival prediction with confidence interval.
     *
     * @param vehicleId        vehicle being predicted
     * @param stopId           stop arrival is predicted for
     * @param predictedEpoch   predicted arrival in epoch seconds
     * @param confidenceLow    lower bound (seconds earlier than predicted)
     * @param confidenceHigh   upper bound (seconds later than predicted)
     * @param qualityScore     prediction quality 0-100 (higher = more confident)
     * @param method           prediction method used: "gps", "historical", "hybrid"
     */
    record ArrivalPrediction(
        String vehicleId,
        String stopId,
        long predictedEpoch,
        int confidenceLow,
        int confidenceHigh,
        int qualityScore,
        String method
    ) {}

    /**
     * Traffic condition affecting a route segment.
     *
     * @param fromStop         segment start
     * @param toStop           segment end
     * @param delayFactor      multiplier for normal travel time (1.0 = normal, 2.0 = double delay)
     * @param reason           "congestion", "incident", "weather", "event"
     * @param confidence       confidence in delay factor 0-100
     */
    record TrafficCondition(
        String fromStop,
        String toStop,
        double delayFactor,
        String reason,
        int confidence
    ) {}

    /**
     * Predicts arrival time for a vehicle at a target stop.
     *
     * @param vehicle          current vehicle position
     * @param targetStop       stop to predict arrival for
     * @param stopsEnRoute     ordered list of stops between current position and target
     * @param historical       historical travel times for relevant segments
     * @param traffic          current traffic conditions
     * @param nowEpochSec      current timestamp
     * @return arrival prediction with confidence interval
     */
    ArrivalPrediction predictArrival(
        VehiclePosition vehicle,
        String targetStop,
        List<String> stopsEnRoute,
        List<HistoricalTravelTime> historical,
        List<TrafficCondition> traffic,
        long nowEpochSec
    );

    /**
     * Computes GPS-based prediction when vehicle position is fresh.
     * Uses current speed and distance to estimate arrival.
     *
     * @param distanceMeters   distance to target stop
     * @param currentSpeedKph  current vehicle speed
     * @param dwellTimeSeconds expected dwell time at intermediate stops
     * @param stopCount        number of intermediate stops
     * @return predicted travel time in seconds
     */
    int gpsBasedPrediction(
        int distanceMeters,
        double currentSpeedKph,
        int dwellTimeSeconds,
        int stopCount
    );

    /**
     * Computes historical-based prediction using past patterns.
     *
     * @param historical       historical data for relevant segments
     * @param hourOfDay        current hour (0-23)
     * @param dayType          "weekday", "saturday", or "sunday"
     * @param useP90           use 90th percentile instead of median
     * @return predicted travel time in seconds
     */
    int historicalBasedPrediction(
        List<HistoricalTravelTime> historical,
        int hourOfDay,
        String dayType,
        boolean useP90
    );

    /**
     * Applies traffic delay factor to base prediction.
     *
     * @param basePredictionSec base prediction in seconds
     * @param delayFactor       delay multiplier (1.0 = no delay)
     * @return adjusted prediction in seconds
     */
    int applyTrafficDelay(int basePredictionSec, double delayFactor);

    /**
     * Computes confidence interval width based on data quality.
     * Factors: position age, sample count, traffic confidence.
     *
     * @param positionAgeSec   age of GPS position in seconds
     * @param sampleCount      historical sample count
     * @param trafficConfidence traffic data confidence 0-100
     * @return confidence interval half-width in seconds
     */
    int computeConfidenceWidth(
        long positionAgeSec,
        int sampleCount,
        int trafficConfidence
    );

    /**
     * Determines prediction quality score.
     * Score decreases with stale GPS, low sample count, uncertain traffic.
     *
     * @param positionAgeSec     GPS position age
     * @param historicalSamples  number of historical observations
     * @param trafficConfidence  traffic data confidence
     * @return quality score 0-100
     */
    int qualityScore(
        long positionAgeSec,
        int historicalSamples,
        int trafficConfidence
    );

    /**
     * Selects prediction method based on available data quality.
     * GPS if position fresh (<60s) and speed > 0, historical if stale,
     * hybrid if both available with reasonable quality.
     *
     * @param positionAgeSec   GPS position age in seconds
     * @param currentSpeedKph  current vehicle speed
     * @param historicalSamples number of historical samples
     * @return "gps", "historical", or "hybrid"
     */
    String selectMethod(
        long positionAgeSec,
        double currentSpeedKph,
        int historicalSamples
    );
}
```

### Required Classes

1. **`ArrivalPredictorService.java`** - Implementation of the interface
2. **Records are defined in the interface** - `VehiclePosition`, `HistoricalTravelTime`, `ArrivalPrediction`, `TrafficCondition`

### Architectural Patterns to Follow

- Use `final class` consistent with codebase style
- Percentile calculations: Reference `StatisticsReducer.percentile()` patterns
- Time calculations: Use epoch seconds consistently like `WatermarkWindow`
- Threshold logic: Learn from existing `<` vs `<=` patterns in bugs
- Bounded values: Use `Math.min(Math.max(...))` pattern from existing code
- Handle edge cases: Zero speed, stale GPS, no historical data, empty stops list

### Acceptance Criteria

1. **Unit Tests** (create `ArrivalPredictorTest.java`):
   - `gpsBasedPredictionCalculation()` - Speed/distance formula
   - `gpsBasedPredictionWithDwellTime()` - Intermediate stops
   - `historicalPredictionMedianVsP90()` - Percentile selection
   - `applyTrafficDelayMultiplier()` - Delay factor application
   - `confidenceWidthIncreasesWithStaleGps()` - Staleness impact
   - `qualityScoreDegradesWithAge()` - Age impact on quality
   - `selectMethodGpsWhenFresh()` - Method selection < 60s
   - `selectMethodHistoricalWhenStale()` - Method selection >= 60s
   - `selectMethodHybridBothAvailable()` - Hybrid selection
   - `predictArrivalIntegration()` - Full prediction flow

2. **Integration Points**:
   - `StatisticsReducer` - Percentile calculation patterns
   - `WatermarkWindow` - Timestamp and lag calculations
   - `SlaModel` - ETA and threshold patterns
   - `RetryBudget` - Score/penalty calculation patterns

3. **Test Command**: `mvn test`

4. **Coverage**: All public methods must have test coverage

---

## General Guidelines

### Package Structure
All new classes should be in `com.terminalbench.transitcore` package:
```
src/main/java/com/terminalbench/transitcore/
    PassengerInfoDisplay.java (interface)
    PassengerInfoDisplayService.java (implementation)
    AccessibilityRouter.java (interface)
    AccessibilityRouterService.java (implementation)
    ArrivalPredictor.java (interface)
    ArrivalPredictorService.java (implementation)

src/test/java/com/terminalbench/transitcore/
    PassengerInfoDisplayTest.java
    AccessibilityRouterTest.java
    ArrivalPredictorTest.java
```

### Testing Patterns
Follow existing test patterns:
```java
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertFalse;

import org.junit.jupiter.api.Test;

class ExampleTest {
    @Test
    void methodNameDescribesScenario() {
        // Arrange
        Service service = new ServiceImpl();

        // Act
        Result result = service.method(input);

        // Assert
        assertEquals(expected, result);
    }
}
```

### Code Quality
- Use Java 21 features (records, switch expressions, pattern matching)
- Immutable data structures preferred
- Null-safe operations with proper validation
- Clear Javadoc on all public methods
- Consistent threshold handling (be explicit about `<` vs `<=`)
