# VertexGrid - Greenfield Implementation Tasks

## Overview
Three greenfield modules requiring implementation from scratch while following existing architectural patterns. Each module integrates with the VertexGrid platform and requires comprehensive testing.

## Environment
- **Language**: Java
- **Infrastructure**: Spring Boot microservices, JPA entities, EventBus integration, concurrent collections
- **Difficulty**: Apex-Principal
- **Estimated Hours**: 120-168 hours (5-7 days)

## Tasks

### Task 1: Energy Consumption Analyzer (Greenfield Implementation)
Implement a new `energy` module analyzing vehicle energy consumption patterns and providing efficiency metrics and consumption forecasting. The module records energy readings (kWh consumed, distance traveled, battery level) and calculates efficiency in kWh per kilometer over time ranges. Generate consumption reports with daily breakdowns, peak/minimum readings, and trend analysis. Compare fleet efficiency across multiple vehicles with rankings and grades. Forecast energy consumption using historical patterns and detect anomalies through statistical outlier identification. Calculate fleet energy costs using variable electricity rates.

**Required Interface**:
```java
public interface EnergyAnalysisService {
    void recordReading(String vehicleId, EnergyReading reading);
    BigDecimal calculateEfficiency(String vehicleId, Instant from, Instant to);
    ConsumptionReport generateConsumptionReport(String vehicleId, Instant from, Instant to);
    Map<String, EfficiencyMetric> compareFleetEfficiency(List<String> vehicleIds, Instant from, Instant to);
    BigDecimal forecastConsumption(String vehicleId, int forecastHours);
    List<EnergyReading> detectAnomalies(String vehicleId, double sensitivityThreshold);
    BigDecimal calculateFleetEnergyCost(List<String> vehicleIds, Instant from, Instant to, BigDecimal ratePerKwh);
}
```

**Models**: EnergyReading, ConsumptionReport (with DailyConsumption breakdown), EfficiencyMetric

**Acceptance Criteria**:
- Minimum 50 unit tests covering edge cases, BigDecimal precision, concurrency, anomaly detection, and forecasting
- Thread-safe reading storage with concurrent collections
- Integration with TrackingData events and VehicleService
- Test command: `mvn test -pl energy`

---

### Task 2: Demand Response Coordinator (Greenfield Implementation)
Implement a new `demand` module coordinating vehicle charging schedules based on grid demand signals, electricity pricing, and fleet requirements. Register grid demand signals specifying time windows, demand levels, pricing, and available capacity. Create optimized charging plans minimizing cost while respecting constraints (deadline, target battery level, max charge rate). Optimize fleet-wide charging considering grid capacity limits. Retrieve available charging slots sorted by cost. Handle curtailment events by reducing or shifting charging load. Calculate potential cost savings from demand response participation.

**Required Interface**:
```java
public interface DemandResponseService {
    void registerGridSignal(GridSignal signal);
    ChargingPlan createChargingPlan(String vehicleId, ScheduleConstraint constraints);
    Map<String, ChargingPlan> createFleetChargingPlan(Map<String, ScheduleConstraint> vehicleConstraints);
    List<ChargingSlot> getAvailableSlots(Instant from, Instant to);
    BigDecimal calculatePlanCost(ChargingPlan plan);
    CompletableFuture<Map<String, ChargingPlan>> handleCurtailmentEvent(int curtailmentPercent, Duration duration);
    GridSignal getActiveSignal(Instant timestamp);
    BigDecimal calculatePotentialSavings(String vehicleId, BigDecimal energyNeededKwh, Instant deadline);
}
```

**Models**: GridSignal (with DemandLevel enum), ChargingSlot, ScheduleConstraint (with TimeWindow), ChargingPlan

**Acceptance Criteria**:
- Minimum 60 unit tests covering scheduling algorithm, cost optimization, curtailment, edge cases, and concurrency
- Constraint satisfaction validation (impossible constraints detection)
- Integration with VehicleService, EnergyAnalysisService, DispatchJob events
- Publish ChargingScheduledEvent and CurtailmentEvent via EventBus
- Test command: `mvn test -pl demand`

---

### Task 3: Carbon Footprint Calculator (Greenfield Implementation)
Implement a new `carbon` module tracking and reporting carbon emissions across the fleet. Calculate vehicle and fleet carbon footprints using energy consumption data and regional emission factors. Register emission factors for specific regions and energy sources with time-based validity. Record carbon offset purchases and calculate net emissions after offset application. Generate sustainability reports for regulatory compliance including emissions by source/region, offset tracking, trend analysis, and baseline comparisons. Calculate carbon intensity (emissions per kilometer), project future emissions, and rank vehicles by emissions.

**Required Interface**:
```java
public interface CarbonCalculatorService {
    CarbonFootprint calculateVehicleFootprint(String vehicleId, Instant from, Instant to);
    CarbonFootprint calculateFleetFootprint(List<String> vehicleIds, Instant from, Instant to);
    void registerEmissionFactor(EmissionFactor factor);
    BigDecimal getEmissionFactor(double lat, double lng, Instant timestamp);
    void recordOffset(OffsetRecord record);
    BigDecimal calculateNetFootprint(List<String> vehicleIds, Instant from, Instant to);
    SustainabilityReport generateSustainabilityReport(LocalDate reportPeriodStart, LocalDate reportPeriodEnd, int baselineYear);
    BigDecimal calculateCarbonIntensity(String vehicleId, Instant from, Instant to);
    Map<LocalDate, BigDecimal> projectEmissions(List<String> vehicleIds, int projectionMonths);
    List<CarbonFootprint> rankVehiclesByEmissions(List<String> vehicleIds, Instant from, Instant to);
    BigDecimal calculateOffsetCost(List<String> vehicleIds, Instant from, Instant to, BigDecimal offsetPricePerTon);
}
```

**Models**: CarbonFootprint (with Scope 1/2 breakdown), EmissionFactor (with time validity), OffsetRecord, SustainabilityReport (with MonthlyEmission trend)

**Acceptance Criteria**:
- Minimum 55 unit tests covering calculation precision, emission factor lookup, offset accounting, report generation, and edge cases
- BigDecimal precision with 6+ decimal places internally, rounded to 2 for output
- Region-based and time-based emission factor lookup with fallback defaults
- Net calculations handling expiration and negative offsets
- Integration with EnergyAnalysisService, TrackingService, BillingService
- Publish EmissionsAlertEvent when thresholds exceeded
- Test command: `mvn test -pl carbon`

---

## General Implementation Guidelines

### Module Structure
Each module requires:
- `pom.xml` inheriting from parent, depending on `shared`
- `<ModuleName>Application.java` Spring Boot entry point
- Controller and Service layers with proper annotations
- Model classes with getters/setters
- Comprehensive test suite in `src/test/java/com/vertexgrid/<module>/`

### Coding Standards
- Use `Objects.requireNonNull()` for parameter validation
- Return `Optional<>` or empty collections (never null)
- Use SLF4J with MDC for traceability
- Complete Javadoc on all public methods
- Use `BigDecimal` for all financial/scientific calculations
- Thread-safety with concurrent collections where needed

### Testing Command
```bash
mvn test
```

Runs all tests including new modules.
