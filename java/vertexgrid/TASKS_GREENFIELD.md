# VertexGrid - Greenfield Implementation Tasks

This document defines greenfield implementation tasks for VertexGrid, a grid analytics platform with vehicle tracking and billing capabilities. Each task requires implementing a new module from scratch while following the existing architectural patterns.

## Architectural Guidelines

Before implementing any task, review the existing patterns:

- **Entity Pattern**: Extend `BaseEntity` from `shared/model/` for JPA entities (provides id, timestamps, version)
- **Service Pattern**: Use `@Service` annotation, inject dependencies via constructor, use SLF4J logging
- **Event Pattern**: Use `EventBus` from `shared/event/` for intra-service events
- **Concurrency**: Use `ConcurrentHashMap`, `CopyOnWriteArrayList`, `ReentrantReadWriteLock` as appropriate
- **Financial Calculations**: Use `BigDecimal` with explicit `RoundingMode` for all monetary values
- **Testing**: JUnit 5 with `@Tag("unit")`, comprehensive edge case coverage

---

## Task 1: Energy Consumption Analyzer

### Overview

Implement a new `energy` module that analyzes vehicle energy consumption patterns, calculates efficiency metrics, and provides consumption forecasting for fleet operations.

### Module Location

```
energy/
  src/main/java/com/vertexgrid/energy/
    EnergyApplication.java
    controller/EnergyController.java
    service/EnergyAnalysisService.java
    model/EnergyReading.java
    model/ConsumptionReport.java
    model/EfficiencyMetric.java
  src/test/java/com/vertexgrid/energy/
    EnergyAnalysisServiceTest.java
```

### Interface Contract

```java
package com.vertexgrid.energy.service;

import com.vertexgrid.energy.model.ConsumptionReport;
import com.vertexgrid.energy.model.EfficiencyMetric;
import com.vertexgrid.energy.model.EnergyReading;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Service for analyzing vehicle energy consumption and efficiency.
 *
 * Provides real-time consumption tracking, historical analysis, and
 * predictive forecasting for fleet energy management.
 */
public interface EnergyAnalysisService {

    /**
     * Records an energy reading for a vehicle.
     *
     * @param vehicleId the vehicle identifier
     * @param reading the energy reading data (kWh consumed, distance, timestamp)
     * @throws IllegalArgumentException if vehicleId is null/empty or reading is invalid
     */
    void recordReading(String vehicleId, EnergyReading reading);

    /**
     * Calculates energy efficiency (kWh per kilometer) for a vehicle
     * over a specified time range.
     *
     * @param vehicleId the vehicle identifier
     * @param from start of time range (inclusive)
     * @param to end of time range (inclusive)
     * @return efficiency in kWh/km, or null if insufficient data
     * @throws IllegalArgumentException if from is after to
     */
    BigDecimal calculateEfficiency(String vehicleId, Instant from, Instant to);

    /**
     * Generates a consumption report for a vehicle covering a time period.
     *
     * @param vehicleId the vehicle identifier
     * @param from start of reporting period
     * @param to end of reporting period
     * @return consumption report with totals, averages, and trends
     */
    ConsumptionReport generateConsumptionReport(String vehicleId, Instant from, Instant to);

    /**
     * Compares efficiency across multiple vehicles, returning ranked metrics.
     *
     * @param vehicleIds list of vehicle identifiers to compare
     * @param from start of comparison period
     * @param to end of comparison period
     * @return map of vehicleId to EfficiencyMetric, sorted by efficiency (best first)
     */
    Map<String, EfficiencyMetric> compareFleetEfficiency(
        List<String> vehicleIds, Instant from, Instant to);

    /**
     * Forecasts energy consumption for a vehicle based on historical patterns.
     *
     * @param vehicleId the vehicle identifier
     * @param forecastHours number of hours to forecast
     * @return predicted consumption in kWh
     * @throws IllegalStateException if insufficient historical data for forecasting
     */
    BigDecimal forecastConsumption(String vehicleId, int forecastHours);

    /**
     * Identifies anomalous energy consumption patterns (sudden spikes, unusual efficiency).
     *
     * @param vehicleId the vehicle identifier
     * @param sensitivityThreshold standard deviations from mean to flag as anomaly (e.g., 2.0)
     * @return list of readings flagged as anomalies
     */
    List<EnergyReading> detectAnomalies(String vehicleId, double sensitivityThreshold);

    /**
     * Calculates total fleet energy cost for a period.
     *
     * @param vehicleIds vehicles to include
     * @param from start of period
     * @param to end of period
     * @param ratePerKwh cost per kilowatt-hour
     * @return total energy cost with 2 decimal precision
     */
    BigDecimal calculateFleetEnergyCost(
        List<String> vehicleIds, Instant from, Instant to, BigDecimal ratePerKwh);
}
```

### Required Models

```java
// EnergyReading.java
package com.vertexgrid.energy.model;

import java.math.BigDecimal;
import java.time.Instant;

public class EnergyReading {
    private String vehicleId;
    private BigDecimal energyConsumedKwh;  // Energy consumed since last reading
    private BigDecimal distanceKm;          // Distance traveled since last reading
    private BigDecimal batteryLevelPercent; // Current battery level (0-100)
    private Instant timestamp;
    private double lat;
    private double lng;

    // Constructors, getters, setters
}

// ConsumptionReport.java
package com.vertexgrid.energy.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public class ConsumptionReport {
    private String vehicleId;
    private Instant periodStart;
    private Instant periodEnd;
    private BigDecimal totalEnergyKwh;
    private BigDecimal totalDistanceKm;
    private BigDecimal averageEfficiencyKwhPerKm;
    private BigDecimal peakConsumptionKwh;      // Highest single reading
    private BigDecimal minConsumptionKwh;       // Lowest single reading
    private int readingCount;
    private List<DailyConsumption> dailyBreakdown;

    // Constructors, getters, setters
}

// EfficiencyMetric.java
package com.vertexgrid.energy.model;

import java.math.BigDecimal;

public class EfficiencyMetric {
    private String vehicleId;
    private BigDecimal efficiencyKwhPerKm;
    private BigDecimal totalEnergyKwh;
    private BigDecimal totalDistanceKm;
    private int rank;                    // 1 = most efficient
    private String efficiencyGrade;      // A, B, C, D, F

    // Constructors, getters, setters
}
```

### Acceptance Criteria

1. **Unit Tests**: Minimum 50 test cases covering:
   - Edge cases: empty readings, single reading, division by zero guards
   - Precision: BigDecimal calculations maintain 4+ decimal places internally, round to 2 for output
   - Concurrency: Thread-safe reading storage using appropriate concurrent collections
   - Anomaly detection: Statistical outlier identification
   - Forecasting: Linear regression or moving average implementation

2. **Integration Points**:
   - Subscribe to `TrackingData` events from tracking module via EventBus
   - Publish `EnergyAlertEvent` when anomalies detected
   - Use `VehicleService` to validate vehicle existence

3. **Test Command**:
   ```bash
   mvn test -pl energy
   ```

---

## Task 2: Demand Response Coordinator

### Overview

Implement a `demand` module that coordinates vehicle charging schedules based on grid demand signals, electricity pricing, and fleet operational requirements.

### Module Location

```
demand/
  src/main/java/com/vertexgrid/demand/
    DemandApplication.java
    controller/DemandController.java
    service/DemandResponseService.java
    service/ChargingScheduler.java
    model/GridSignal.java
    model/ChargingSlot.java
    model/ScheduleConstraint.java
    model/ChargingPlan.java
  src/test/java/com/vertexgrid/demand/
    DemandResponseServiceTest.java
    ChargingSchedulerTest.java
```

### Interface Contract

```java
package com.vertexgrid.demand.service;

import com.vertexgrid.demand.model.ChargingPlan;
import com.vertexgrid.demand.model.ChargingSlot;
import com.vertexgrid.demand.model.GridSignal;
import com.vertexgrid.demand.model.ScheduleConstraint;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Coordinates demand response for vehicle charging across the fleet.
 *
 * Optimizes charging schedules based on grid signals, electricity pricing,
 * vehicle availability, and operational constraints to minimize costs and
 * support grid stability.
 */
public interface DemandResponseService {

    /**
     * Registers a grid demand signal for a time window.
     *
     * @param signal the grid signal containing demand level, pricing, and time window
     * @throws IllegalArgumentException if signal time window is invalid
     */
    void registerGridSignal(GridSignal signal);

    /**
     * Creates an optimized charging plan for a vehicle.
     *
     * The plan minimizes cost while respecting constraints (required charge level
     * by deadline, preferred charging windows, maximum charge rate).
     *
     * @param vehicleId the vehicle to schedule charging for
     * @param constraints scheduling constraints (deadline, target battery %, etc.)
     * @return optimal charging plan with time slots and expected cost
     * @throws IllegalStateException if no valid schedule exists within constraints
     */
    ChargingPlan createChargingPlan(String vehicleId, ScheduleConstraint constraints);

    /**
     * Creates charging plans for multiple vehicles, optimizing fleet-wide cost.
     *
     * Considers grid capacity limits and distributes load across time windows.
     *
     * @param vehicleConstraints map of vehicleId to their constraints
     * @return map of vehicleId to their charging plans
     */
    Map<String, ChargingPlan> createFleetChargingPlan(
        Map<String, ScheduleConstraint> vehicleConstraints);

    /**
     * Retrieves available charging slots for a time range, considering grid signals.
     *
     * @param from start of time range
     * @param to end of time range
     * @return available slots sorted by cost (cheapest first)
     */
    List<ChargingSlot> getAvailableSlots(Instant from, Instant to);

    /**
     * Calculates the estimated cost for a charging plan.
     *
     * @param plan the charging plan to cost
     * @return total cost in currency units with 2 decimal precision
     */
    BigDecimal calculatePlanCost(ChargingPlan plan);

    /**
     * Responds to a demand response event by curtailing or shifting charging load.
     *
     * @param curtailmentPercent percentage of current charging load to reduce (0-100)
     * @param duration how long to maintain curtailment
     * @return list of affected vehicle IDs and their modified plans
     */
    CompletableFuture<Map<String, ChargingPlan>> handleCurtailmentEvent(
        int curtailmentPercent, Duration duration);

    /**
     * Retrieves current grid signal for a specific time.
     *
     * @param timestamp the time to query
     * @return active grid signal, or null if none registered
     */
    GridSignal getActiveSignal(Instant timestamp);

    /**
     * Calculates potential cost savings from demand response participation.
     *
     * Compares optimized schedule cost vs. immediate charging cost.
     *
     * @param vehicleId the vehicle to analyze
     * @param energyNeededKwh energy required
     * @param deadline must complete by this time
     * @return potential savings amount
     */
    BigDecimal calculatePotentialSavings(
        String vehicleId, BigDecimal energyNeededKwh, Instant deadline);
}
```

### Required Models

```java
// GridSignal.java
package com.vertexgrid.demand.model;

import java.math.BigDecimal;
import java.time.Instant;

public class GridSignal {
    public enum DemandLevel { LOW, NORMAL, HIGH, CRITICAL }

    private String signalId;
    private Instant windowStart;
    private Instant windowEnd;
    private DemandLevel demandLevel;
    private BigDecimal pricePerKwh;          // Current electricity price
    private BigDecimal incentivePerKwh;       // Incentive for load shifting (can be negative)
    private int availableCapacityKw;          // Grid capacity available for charging

    // Constructors, getters, setters
}

// ChargingSlot.java
package com.vertexgrid.demand.model;

import java.math.BigDecimal;
import java.time.Instant;

public class ChargingSlot {
    private Instant startTime;
    private Instant endTime;
    private BigDecimal effectiveRatePerKwh;   // Price minus incentive
    private int maxChargeRateKw;
    private boolean curtailable;              // Can be interrupted for grid events

    // Constructors, getters, setters
}

// ScheduleConstraint.java
package com.vertexgrid.demand.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public class ScheduleConstraint {
    private String vehicleId;
    private BigDecimal currentBatteryPercent;
    private BigDecimal targetBatteryPercent;
    private BigDecimal batteryCapacityKwh;
    private Instant deadline;                  // Must reach target by this time
    private int maxChargeRateKw;
    private List<TimeWindow> preferredWindows; // Optional preferred charging times
    private boolean allowCurtailment;          // Can participate in demand response

    // Constructors, getters, setters
}

// ChargingPlan.java
package com.vertexgrid.demand.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public class ChargingPlan {
    private String planId;
    private String vehicleId;
    private Instant createdAt;
    private List<ChargingSlot> scheduledSlots;
    private BigDecimal totalEnergyKwh;
    private BigDecimal estimatedCost;
    private BigDecimal estimatedSavings;       // vs. immediate charging
    private PlanStatus status;                 // PENDING, ACTIVE, COMPLETED, CURTAILED

    // Constructors, getters, setters
}
```

### Acceptance Criteria

1. **Unit Tests**: Minimum 60 test cases covering:
   - Scheduling algorithm: Greedy slot selection, constraint satisfaction
   - Cost optimization: Verify cheapest slots selected when possible
   - Curtailment: Load reduction calculations, plan modifications
   - Edge cases: Impossible constraints, overlapping signals, zero capacity
   - Concurrency: Concurrent plan creation, signal updates

2. **Integration Points**:
   - Query `VehicleService` for current battery levels
   - Query `EnergyAnalysisService` for consumption forecasts
   - Publish `ChargingScheduledEvent` and `CurtailmentEvent` via EventBus
   - Subscribe to `DispatchJob` events to update charging feasibility

3. **Test Command**:
   ```bash
   mvn test -pl demand
   ```

---

## Task 3: Carbon Footprint Calculator

### Overview

Implement a `carbon` module that calculates, tracks, and reports carbon emissions across the fleet, supporting sustainability reporting and carbon offset calculations.

### Module Location

```
carbon/
  src/main/java/com/vertexgrid/carbon/
    CarbonApplication.java
    controller/CarbonController.java
    service/CarbonCalculatorService.java
    service/EmissionFactorService.java
    model/CarbonFootprint.java
    model/EmissionFactor.java
    model/OffsetRecord.java
    model/SustainabilityReport.java
  src/test/java/com/vertexgrid/carbon/
    CarbonCalculatorServiceTest.java
    EmissionFactorServiceTest.java
```

### Interface Contract

```java
package com.vertexgrid.carbon.service;

import com.vertexgrid.carbon.model.CarbonFootprint;
import com.vertexgrid.carbon.model.EmissionFactor;
import com.vertexgrid.carbon.model.OffsetRecord;
import com.vertexgrid.carbon.model.SustainabilityReport;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * Service for calculating and tracking carbon emissions across the fleet.
 *
 * Supports multiple emission factor sources (grid region, fuel type, vehicle class),
 * carbon offset tracking, and regulatory sustainability reporting.
 */
public interface CarbonCalculatorService {

    /**
     * Calculates carbon footprint for a vehicle over a time period.
     *
     * Uses energy consumption data and regional emission factors.
     *
     * @param vehicleId the vehicle identifier
     * @param from start of period
     * @param to end of period
     * @return carbon footprint in kg CO2e (CO2 equivalent)
     */
    CarbonFootprint calculateVehicleFootprint(String vehicleId, Instant from, Instant to);

    /**
     * Calculates total fleet carbon footprint.
     *
     * @param vehicleIds vehicles to include (null/empty = all vehicles)
     * @param from start of period
     * @param to end of period
     * @return aggregated carbon footprint
     */
    CarbonFootprint calculateFleetFootprint(List<String> vehicleIds, Instant from, Instant to);

    /**
     * Registers an emission factor for a specific region and energy source.
     *
     * @param factor the emission factor definition
     * @throws IllegalArgumentException if factor values are invalid
     */
    void registerEmissionFactor(EmissionFactor factor);

    /**
     * Retrieves the applicable emission factor for a location and time.
     *
     * Considers grid region, time-of-day variations, and energy source mix.
     *
     * @param lat latitude
     * @param lng longitude
     * @param timestamp time for which to get the factor
     * @return emission factor in kg CO2e per kWh
     */
    BigDecimal getEmissionFactor(double lat, double lng, Instant timestamp);

    /**
     * Records a carbon offset purchase or credit.
     *
     * @param record the offset record details
     */
    void recordOffset(OffsetRecord record);

    /**
     * Calculates net carbon footprint after applying offsets.
     *
     * @param vehicleIds vehicles to include
     * @param from start of period
     * @param to end of period
     * @return net footprint (can be negative if offsets exceed emissions)
     */
    BigDecimal calculateNetFootprint(List<String> vehicleIds, Instant from, Instant to);

    /**
     * Generates a sustainability report for regulatory compliance.
     *
     * Includes emissions by source, offset credits, trend analysis,
     * and comparison to baseline/targets.
     *
     * @param reportPeriodStart start date of reporting period
     * @param reportPeriodEnd end date of reporting period
     * @param baselineYear year to compare against for trend analysis
     * @return comprehensive sustainability report
     */
    SustainabilityReport generateSustainabilityReport(
        LocalDate reportPeriodStart, LocalDate reportPeriodEnd, int baselineYear);

    /**
     * Calculates carbon intensity (emissions per km or per delivery).
     *
     * @param vehicleId the vehicle identifier
     * @param from start of period
     * @param to end of period
     * @return carbon intensity in kg CO2e per km
     */
    BigDecimal calculateCarbonIntensity(String vehicleId, Instant from, Instant to);

    /**
     * Projects future emissions based on historical trends and planned operations.
     *
     * @param vehicleIds vehicles to include in projection
     * @param projectionMonths number of months to project
     * @return projected emissions map by month
     */
    Map<LocalDate, BigDecimal> projectEmissions(List<String> vehicleIds, int projectionMonths);

    /**
     * Compares emissions across vehicles, identifying high emitters.
     *
     * @param vehicleIds vehicles to compare
     * @param from start of period
     * @param to end of period
     * @return vehicles ranked by emissions (highest first)
     */
    List<CarbonFootprint> rankVehiclesByEmissions(
        List<String> vehicleIds, Instant from, Instant to);

    /**
     * Calculates the cost of carbon offsets needed to achieve carbon neutrality.
     *
     * @param vehicleIds vehicles to include
     * @param from start of period
     * @param to end of period
     * @param offsetPricePerTon price per metric ton of CO2e offset
     * @return total offset cost required
     */
    BigDecimal calculateOffsetCost(
        List<String> vehicleIds, Instant from, Instant to, BigDecimal offsetPricePerTon);
}
```

### Required Models

```java
// CarbonFootprint.java
package com.vertexgrid.carbon.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;

public class CarbonFootprint {
    private String entityId;              // Vehicle ID or "FLEET"
    private Instant periodStart;
    private Instant periodEnd;
    private BigDecimal totalEmissionsKgCO2e;
    private BigDecimal directEmissions;    // Scope 1: fuel combustion
    private BigDecimal indirectEmissions;  // Scope 2: electricity
    private BigDecimal totalDistanceKm;
    private BigDecimal intensityKgCO2ePerKm;
    private Map<String, BigDecimal> emissionsBySource;  // Breakdown by energy source

    // Constructors, getters, setters
}

// EmissionFactor.java
package com.vertexgrid.carbon.model;

import java.math.BigDecimal;
import java.time.Instant;

public class EmissionFactor {
    private String factorId;
    private String regionCode;             // e.g., "US-CA", "EU-DE"
    private String energySource;           // e.g., "GRID", "SOLAR", "DIESEL"
    private BigDecimal kgCO2ePerKwh;       // For electricity
    private BigDecimal kgCO2ePerLiter;     // For fuels
    private Instant validFrom;
    private Instant validTo;
    private String source;                 // Data source (EPA, IEA, etc.)

    // Constructors, getters, setters
}

// OffsetRecord.java
package com.vertexgrid.carbon.model;

import java.math.BigDecimal;
import java.time.LocalDate;

public class OffsetRecord {
    private String offsetId;
    private LocalDate purchaseDate;
    private BigDecimal amountTonsCO2e;
    private BigDecimal costPerTon;
    private String projectType;            // e.g., "REFORESTATION", "RENEWABLE_ENERGY"
    private String certificationStandard;  // e.g., "GOLD_STANDARD", "VCS"
    private String verificationId;
    private LocalDate expirationDate;

    // Constructors, getters, setters
}

// SustainabilityReport.java
package com.vertexgrid.carbon.model;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

public class SustainabilityReport {
    private String reportId;
    private LocalDate periodStart;
    private LocalDate periodEnd;
    private BigDecimal totalEmissions;
    private BigDecimal totalOffsets;
    private BigDecimal netEmissions;
    private BigDecimal baselineEmissions;
    private BigDecimal reductionPercent;
    private Map<String, BigDecimal> emissionsByVehicleClass;
    private Map<String, BigDecimal> emissionsByRegion;
    private List<MonthlyEmission> monthlyTrend;
    private String complianceStatus;       // COMPLIANT, NON_COMPLIANT, PENDING
    private List<String> recommendations;

    // Constructors, getters, setters
}
```

### Acceptance Criteria

1. **Unit Tests**: Minimum 55 test cases covering:
   - Calculation precision: BigDecimal with 6+ decimal places internally
   - Emission factors: Region lookup, time-based variations, fallback defaults
   - Offset accounting: Net calculations, expiration handling
   - Report generation: Aggregations, trend calculations, baseline comparisons
   - Edge cases: Zero emissions, negative offsets, missing factors

2. **Integration Points**:
   - Query `EnergyAnalysisService` for consumption data
   - Query `TrackingService` for vehicle locations (to determine grid region)
   - Query `BillingService` for regional billing zones
   - Publish `EmissionsAlertEvent` when thresholds exceeded
   - Subscribe to `EnergyReading` events for real-time tracking

3. **Test Command**:
   ```bash
   mvn test -pl carbon
   ```

---

## General Implementation Notes

### Build Configuration

Each new module needs a `pom.xml` that:
- Inherits from parent `vertexgrid` POM
- Declares dependencies on `shared` module
- Includes Spring Boot starter dependencies
- Configures JUnit 5 for testing

### Coding Standards

1. **Null Safety**: Use `Objects.requireNonNull()` for parameters, return `Optional<>` or empty collections (not null)
2. **Immutability**: Prefer immutable objects; use `List.of()`, `Map.of()` for returns
3. **Logging**: Use SLF4J with MDC for traceability; log at appropriate levels
4. **Documentation**: Javadoc on all public methods; include `@param`, `@return`, `@throws`

### Running All Tests

```bash
# Run tests for all modules including new ones
mvn test

# Run tests with coverage report
mvn test jacoco:report

# Run specific module tests
mvn test -pl energy,demand,carbon
```
