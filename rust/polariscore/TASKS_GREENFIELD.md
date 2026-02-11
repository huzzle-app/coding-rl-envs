# PolarisCore Greenfield Tasks

This document defines greenfield implementation tasks for PolarisCore - a cold-chain logistics control plane. Each task requires implementing a new module from scratch following the existing architectural patterns.

**Test Command:** `cargo test`

---

## Task 1: Weather Impact Assessor

### Overview

Implement a weather impact assessment module that evaluates how current and forecasted weather conditions affect polar logistics operations. This module integrates with routing decisions and risk calculations to adjust shipment priorities and route selections based on environmental factors.

### Module Location

Create: `src/weather.rs`

Update `src/lib.rs` to include:
```rust
pub mod weather;
```

### Trait Contract

```rust
use crate::models::Shipment;

/// Represents a weather observation at a specific location.
#[derive(Clone, Debug, PartialEq)]
pub struct WeatherObservation {
    /// Location identifier (hub ID or route segment)
    pub location: String,
    /// Temperature in Celsius
    pub temperature_c: f64,
    /// Wind speed in km/h
    pub wind_speed_kmh: f64,
    /// Visibility in meters
    pub visibility_m: u32,
    /// Precipitation type: "none", "snow", "ice", "rain"
    pub precipitation: String,
    /// Hours until conditions expire (0 = current conditions only)
    pub forecast_hours: u32,
}

/// Severity level for weather-related disruptions.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum WeatherSeverity {
    /// Normal operations
    Clear,
    /// Minor delays expected (10-20% slower)
    Advisory,
    /// Significant delays, alternate routing recommended
    Warning,
    /// Operations suspended for affected routes
    Severe,
}

/// Impact assessment result for a specific route or hub.
#[derive(Clone, Debug, PartialEq)]
pub struct WeatherImpact {
    pub location: String,
    pub severity: WeatherSeverity,
    /// Estimated delay multiplier (1.0 = no delay, 1.5 = 50% longer)
    pub delay_factor: f64,
    /// Whether cold-chain integrity is at risk
    pub cold_chain_risk: bool,
    /// Recommended action: "proceed", "delay", "reroute", "hold"
    pub recommendation: String,
}

/// Calculates weather severity based on observation parameters.
///
/// Severity thresholds:
/// - Severe: temp < -40C OR wind > 80 km/h OR visibility < 100m OR precipitation == "ice"
/// - Warning: temp < -25C OR wind > 50 km/h OR visibility < 500m OR precipitation == "snow"
/// - Advisory: temp < -15C OR wind > 30 km/h OR visibility < 1000m
/// - Clear: otherwise
///
/// Returns the highest severity triggered by any condition.
pub fn assess_severity(observation: &WeatherObservation) -> WeatherSeverity;

/// Calculates the delay factor for a given weather observation.
///
/// Base delay factors by severity:
/// - Clear: 1.0
/// - Advisory: 1.15
/// - Warning: 1.4
/// - Severe: 2.5
///
/// Additional modifiers:
/// - Multiply by 1.1 if wind_speed > 40 km/h
/// - Multiply by 1.2 if visibility < 300m
/// - Cap at 3.0 maximum
pub fn calculate_delay_factor(observation: &WeatherObservation) -> f64;

/// Determines if cold-chain integrity is at risk.
///
/// Cold chain is at risk when:
/// - Temperature is below -45C (freezing damage to some goods)
/// - Temperature is above 5C (thawing risk)
/// - Delay factor exceeds 2.0 (extended exposure)
/// - Severity is Severe and precipitation is "ice" (access issues)
pub fn cold_chain_at_risk(observation: &WeatherObservation, delay_factor: f64) -> bool;

/// Generates a complete weather impact assessment for a location.
///
/// Recommendation logic:
/// - "hold" if severity is Severe
/// - "reroute" if cold_chain_risk is true
/// - "delay" if severity is Warning
/// - "proceed" otherwise
pub fn assess_impact(observation: &WeatherObservation) -> WeatherImpact;

/// Evaluates weather impact across multiple hubs and returns the worst-affected hub.
///
/// Returns None if observations is empty.
/// If multiple hubs have the same severity, return the one with highest delay_factor.
/// Ties on delay_factor are broken by alphabetical location name.
pub fn worst_hub_impact(observations: &[WeatherObservation]) -> Option<WeatherImpact>;

/// Calculates a route viability score (0.0 to 1.0) based on weather along route segments.
///
/// Score calculation:
/// - Start with 1.0
/// - For each segment, multiply by (1.0 / delay_factor)
/// - Subtract 0.3 for each Severe segment
/// - Subtract 0.15 for each Warning segment with cold_chain_risk
/// - Clamp result to [0.0, 1.0]
pub fn route_viability_score(segment_observations: &[WeatherObservation]) -> f64;
```

### Required Structs/Enums

1. `WeatherObservation` - Weather data for a location
2. `WeatherSeverity` - Enum with `Clear`, `Advisory`, `Warning`, `Severe` variants
3. `WeatherImpact` - Assessment result with severity, delay factor, and recommendations

### Architectural Patterns to Follow

- Use standalone public functions (like `src/routing.rs`, `src/policy.rs`)
- Return owned types, accept references where appropriate
- Use `.min()` and `.max()` for clamping values
- Sort tie-breakers should use lexicographic ordering (see `select_hub` pattern)
- Keep functions pure (no side effects)

### Acceptance Criteria

1. All functions implemented as specified in the trait contract
2. Create `tests/weather_tests.rs` with at least 15 tests covering:
   - Each severity threshold boundary
   - Delay factor calculations with modifiers
   - Cold chain risk detection for each condition
   - Impact assessment recommendation logic
   - Worst hub selection with ties
   - Route viability score edge cases (empty, single, multiple segments)
3. All tests pass with `cargo test`
4. Module properly exported in `src/lib.rs`

### Example Test Cases

```rust
#[test]
fn assess_severity_extreme_cold_is_severe() {
    let obs = WeatherObservation {
        location: "hub-arctic".to_string(),
        temperature_c: -42.0,
        wind_speed_kmh: 20.0,
        visibility_m: 2000,
        precipitation: "none".to_string(),
        forecast_hours: 6,
    };
    assert_eq!(assess_severity(&obs), WeatherSeverity::Severe);
}

#[test]
fn route_viability_all_clear() {
    let segments = vec![
        WeatherObservation { location: "a".to_string(), temperature_c: -5.0, wind_speed_kmh: 10.0, visibility_m: 5000, precipitation: "none".to_string(), forecast_hours: 0 },
        WeatherObservation { location: "b".to_string(), temperature_c: -8.0, wind_speed_kmh: 15.0, visibility_m: 4000, precipitation: "none".to_string(), forecast_hours: 0 },
    ];
    let score = route_viability_score(&segments);
    assert!((score - 1.0).abs() < 0.01);
}
```

---

## Task 2: Cold Chain Monitor

### Overview

Implement a cold chain monitoring module that tracks temperature and environmental conditions throughout the logistics pipeline. This module detects anomalies, calculates exposure times, and determines whether shipments remain within acceptable parameters.

### Module Location

Create: `src/coldchain.rs`

Update `src/lib.rs` to include:
```rust
pub mod coldchain;
```

### Trait Contract

```rust
use crate::models::Shipment;

/// A temperature reading at a specific timestamp.
#[derive(Clone, Debug, PartialEq)]
pub struct TemperatureReading {
    /// Shipment ID this reading belongs to
    pub shipment_id: String,
    /// Timestamp in seconds since shipment departure
    pub timestamp_secs: u64,
    /// Temperature in Celsius
    pub temperature_c: f64,
    /// Sensor location: "internal", "external", "ambient"
    pub sensor_type: String,
}

/// Classification of a cold chain violation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ViolationType {
    /// Temperature exceeded upper bound
    TooWarm,
    /// Temperature dropped below lower bound
    TooCold,
    /// Temperature fluctuated excessively
    Fluctuation,
    /// Sensor gap exceeded maximum allowed
    SensorGap,
}

/// A detected cold chain violation event.
#[derive(Clone, Debug, PartialEq)]
pub struct Violation {
    pub shipment_id: String,
    pub violation_type: ViolationType,
    /// Timestamp when violation started
    pub start_secs: u64,
    /// Duration of violation in seconds
    pub duration_secs: u64,
    /// Severity score (0.0 to 1.0)
    pub severity: f64,
}

/// Cold chain compliance summary for a shipment.
#[derive(Clone, Debug, PartialEq)]
pub struct ComplianceReport {
    pub shipment_id: String,
    /// Percentage of time within acceptable range [0.0, 1.0]
    pub compliance_ratio: f64,
    /// Total time outside acceptable range in seconds
    pub violation_seconds: u64,
    /// List of detected violations
    pub violations: Vec<Violation>,
    /// Overall status: "compliant", "minor-deviation", "major-deviation", "rejected"
    pub status: String,
}

/// Temperature bounds for different cargo classifications.
#[derive(Clone, Debug, PartialEq)]
pub struct TemperatureBounds {
    /// Cargo classification: "frozen", "chilled", "controlled", "ambient"
    pub classification: String,
    /// Minimum acceptable temperature (Celsius)
    pub min_c: f64,
    /// Maximum acceptable temperature (Celsius)
    pub max_c: f64,
    /// Maximum allowed fluctuation per hour (Celsius)
    pub max_fluctuation_per_hour: f64,
    /// Maximum allowed sensor gap (seconds)
    pub max_sensor_gap_secs: u64,
}

/// Returns default temperature bounds for a cargo classification.
///
/// Classifications:
/// - "frozen": -25C to -18C, max fluctuation 2C/hr, max gap 300s
/// - "chilled": 0C to 5C, max fluctuation 3C/hr, max gap 600s
/// - "controlled": 15C to 25C, max fluctuation 5C/hr, max gap 900s
/// - "ambient": -10C to 35C, max fluctuation 10C/hr, max gap 1800s
///
/// Unknown classifications return "controlled" bounds.
pub fn default_bounds(classification: &str) -> TemperatureBounds;

/// Checks if a single reading is within bounds.
///
/// Returns None if compliant, Some(ViolationType) if violation detected.
pub fn check_reading(reading: &TemperatureReading, bounds: &TemperatureBounds) -> Option<ViolationType>;

/// Detects sensor gaps in a sequence of readings.
///
/// Readings must be sorted by timestamp. Returns violations for gaps
/// exceeding bounds.max_sensor_gap_secs. Gap duration is measured
/// between consecutive readings.
pub fn detect_sensor_gaps(readings: &[TemperatureReading], bounds: &TemperatureBounds) -> Vec<Violation>;

/// Detects temperature fluctuations exceeding the allowed rate.
///
/// Calculates rate of change between consecutive readings.
/// Fluctuation = |delta_temp| / (delta_time / 3600.0) for per-hour rate.
/// Returns a violation if any fluctuation exceeds max_fluctuation_per_hour.
/// Violation duration is the time span of the fluctuation.
/// Severity is (actual_rate / max_rate).min(1.0).
pub fn detect_fluctuations(readings: &[TemperatureReading], bounds: &TemperatureBounds) -> Vec<Violation>;

/// Calculates cumulative exposure time outside acceptable temperature range.
///
/// For each reading outside [min_c, max_c], add the time until the next reading
/// (or until the last reading for the final one).
/// Returns total seconds of exposure.
pub fn cumulative_exposure_secs(readings: &[TemperatureReading], bounds: &TemperatureBounds) -> u64;

/// Generates a complete compliance report for a shipment's readings.
///
/// Status determination:
/// - "rejected" if compliance_ratio < 0.85 OR any violation severity >= 0.9
/// - "major-deviation" if compliance_ratio < 0.95 OR any violation severity >= 0.7
/// - "minor-deviation" if compliance_ratio < 0.99 OR violations is non-empty
/// - "compliant" otherwise
pub fn generate_compliance_report(
    shipment_id: &str,
    readings: &[TemperatureReading],
    bounds: &TemperatureBounds,
) -> ComplianceReport;

/// Estimates remaining safe transit time based on current conditions.
///
/// If current_temp is within bounds, returns u64::MAX (unlimited).
/// If outside bounds, calculates based on deviation severity:
/// - For TooWarm: safe_hours = 4.0 / (current_temp - max_c).max(0.1)
/// - For TooCold: safe_hours = 4.0 / (min_c - current_temp).max(0.1)
/// Returns hours as seconds, capped at 86400 (24 hours).
pub fn estimate_safe_transit_secs(current_temp: f64, bounds: &TemperatureBounds) -> u64;
```

### Required Structs/Enums

1. `TemperatureReading` - Sensor reading with timestamp and location
2. `ViolationType` - Enum for violation classifications
3. `Violation` - Detected violation with timing and severity
4. `ComplianceReport` - Complete compliance summary
5. `TemperatureBounds` - Configurable temperature limits

### Architectural Patterns to Follow

- Use `Option<T>` for potentially absent results (see `check_reading`)
- Use `Vec<T>` for collecting multiple violations
- Implement pure functions without side effects
- Follow the numeric precision patterns (see `margin_ratio` in economics.rs)
- Use saturating arithmetic for duration calculations

### Acceptance Criteria

1. All functions implemented as specified
2. Create `tests/coldchain_tests.rs` with at least 20 tests covering:
   - Default bounds for all classifications
   - Reading checks for all violation types
   - Sensor gap detection edge cases
   - Fluctuation detection with various rates
   - Cumulative exposure calculations
   - Compliance report generation for all status levels
   - Safe transit estimation at boundaries
3. All tests pass with `cargo test`
4. Module properly exported in `src/lib.rs`

### Example Test Cases

```rust
#[test]
fn frozen_cargo_too_warm_violation() {
    let bounds = default_bounds("frozen");
    let reading = TemperatureReading {
        shipment_id: "ship-1".to_string(),
        timestamp_secs: 1000,
        temperature_c: -15.0, // Above -18C max
        sensor_type: "internal".to_string(),
    };
    assert_eq!(check_reading(&reading, &bounds), Some(ViolationType::TooWarm));
}

#[test]
fn compliance_ratio_calculation() {
    let bounds = default_bounds("chilled");
    let readings = vec![
        TemperatureReading { shipment_id: "s1".to_string(), timestamp_secs: 0, temperature_c: 3.0, sensor_type: "internal".to_string() },
        TemperatureReading { shipment_id: "s1".to_string(), timestamp_secs: 100, temperature_c: 7.0, sensor_type: "internal".to_string() }, // violation
        TemperatureReading { shipment_id: "s1".to_string(), timestamp_secs: 200, temperature_c: 2.0, sensor_type: "internal".to_string() },
    ];
    let report = generate_compliance_report("s1", &readings, &bounds);
    assert!(report.compliance_ratio < 1.0);
    assert!(!report.violations.is_empty());
}
```

---

## Task 3: Expedition Cost Estimator

### Overview

Implement an expedition cost estimation module that calculates comprehensive logistics costs for polar expeditions. This module accounts for fuel, equipment, personnel, insurance, and contingency costs based on route complexity, weather conditions, and cargo specifications.

### Module Location

Create: `src/expedition.rs`

Update `src/lib.rs` to include:
```rust
pub mod expedition;
```

### Trait Contract

```rust
use crate::models::Shipment;
use std::collections::HashMap;

/// Configuration for an expedition.
#[derive(Clone, Debug, PartialEq)]
pub struct ExpeditionConfig {
    /// Unique expedition identifier
    pub expedition_id: String,
    /// Route distance in kilometers
    pub distance_km: f64,
    /// Number of route segments requiring special handling
    pub hazardous_segments: u32,
    /// Expected duration in hours
    pub duration_hours: u32,
    /// Number of personnel required
    pub crew_size: u32,
    /// Cargo classification: "frozen", "chilled", "hazmat", "standard"
    pub cargo_class: String,
    /// Vehicle type: "tracked", "wheeled", "aerial", "marine"
    pub vehicle_type: String,
}

/// Breakdown of expedition costs.
#[derive(Clone, Debug, PartialEq)]
pub struct CostBreakdown {
    pub expedition_id: String,
    /// Fuel cost in cents
    pub fuel_cents: u64,
    /// Equipment rental/depreciation in cents
    pub equipment_cents: u64,
    /// Personnel wages in cents
    pub personnel_cents: u64,
    /// Insurance premium in cents
    pub insurance_cents: u64,
    /// Contingency reserve in cents
    pub contingency_cents: u64,
    /// Total cost in cents
    pub total_cents: u64,
}

/// Risk multipliers affecting cost calculations.
#[derive(Clone, Debug, PartialEq)]
pub struct RiskFactors {
    /// Weather risk multiplier (1.0 = normal, higher = worse)
    pub weather_multiplier: f64,
    /// Geopolitical risk for region (1.0 = stable)
    pub geopolitical_multiplier: f64,
    /// Seasonal difficulty (1.0 = optimal season)
    pub seasonal_multiplier: f64,
}

/// Fuel consumption rates by vehicle type (liters per km).
///
/// Returns base consumption rate:
/// - "tracked": 4.5 L/km
/// - "wheeled": 2.8 L/km
/// - "aerial": 15.0 L/km
/// - "marine": 8.0 L/km
/// - default: 3.5 L/km
pub fn fuel_rate_per_km(vehicle_type: &str) -> f64;

/// Calculates fuel cost for an expedition.
///
/// Formula: distance_km * fuel_rate * fuel_price_cents_per_liter
/// Apply 1.15x multiplier for hazardous segments (adds 15% per hazardous segment, multiplicative)
/// Cap the hazardous multiplier at 2.5x
/// Round to nearest cent.
pub fn calculate_fuel_cost(config: &ExpeditionConfig, fuel_price_cents_per_liter: u64) -> u64;

/// Calculates equipment costs.
///
/// Base daily rates in cents:
/// - "tracked": 45000 (450.00/day)
/// - "wheeled": 18000 (180.00/day)
/// - "aerial": 125000 (1250.00/day)
/// - "marine": 75000 (750.00/day)
/// - default: 25000 (250.00/day)
///
/// Calculate days as (duration_hours / 24).ceil()
/// Add 20% for "hazmat" cargo class
/// Add 10% for "frozen" cargo class (refrigeration equipment)
pub fn calculate_equipment_cost(config: &ExpeditionConfig) -> u64;

/// Calculates personnel costs.
///
/// Base hourly rate: 5500 cents (55.00/hour) per crew member
/// Apply overtime multiplier: 1.5x for hours beyond 8 per day
/// Add hazard pay: 25% for hazmat cargo, 15% for frozen cargo
/// Add skill premium: 20% for aerial vehicle type (pilots), 10% for marine (mariners)
pub fn calculate_personnel_cost(config: &ExpeditionConfig) -> u64;

/// Calculates insurance premium.
///
/// Base rate: 0.5% of (fuel + equipment + personnel) costs
/// Multiply by cargo risk factor:
/// - "hazmat": 3.0
/// - "frozen": 1.5
/// - "chilled": 1.2
/// - "standard": 1.0
/// Multiply by vehicle risk factor:
/// - "aerial": 2.5
/// - "marine": 2.0
/// - "tracked": 1.3
/// - "wheeled": 1.0
/// Add hazardous segment surcharge: 1000 cents per hazardous segment
pub fn calculate_insurance_cost(
    config: &ExpeditionConfig,
    fuel_cost: u64,
    equipment_cost: u64,
    personnel_cost: u64,
) -> u64;

/// Calculates contingency reserve.
///
/// Base contingency: 10% of subtotal (fuel + equipment + personnel + insurance)
/// Apply risk factors: multiply base by (weather * geopolitical * seasonal)
/// Minimum contingency: 5% of subtotal
/// Maximum contingency: 50% of subtotal
pub fn calculate_contingency(
    subtotal_cents: u64,
    risk_factors: &RiskFactors,
) -> u64;

/// Generates a complete cost breakdown for an expedition.
///
/// Uses standard fuel price of 250 cents/liter (2.50/L) if not specified.
/// Uses default risk factors (all 1.0) if not specified.
pub fn estimate_expedition_cost(
    config: &ExpeditionConfig,
    fuel_price_cents_per_liter: Option<u64>,
    risk_factors: Option<&RiskFactors>,
) -> CostBreakdown;

/// Compares costs across multiple vehicle types for the same expedition.
///
/// Returns a HashMap of vehicle_type -> CostBreakdown
/// Preserves original expedition_id but varies vehicle_type
pub fn compare_vehicle_costs(
    config: &ExpeditionConfig,
    fuel_price_cents_per_liter: u64,
    risk_factors: &RiskFactors,
) -> HashMap<String, CostBreakdown>;

/// Finds the most economical route configuration.
///
/// Given multiple expedition configs (different routes), returns the one
/// with the lowest total cost. Ties are broken by expedition_id alphabetically.
/// Returns None if configs is empty.
pub fn most_economical_route(
    configs: &[ExpeditionConfig],
    fuel_price_cents_per_liter: u64,
    risk_factors: &RiskFactors,
) -> Option<CostBreakdown>;

/// Calculates break-even cargo value for an expedition.
///
/// Returns the minimum cargo value in cents that would make the expedition
/// profitable given a target margin ratio (e.g., 0.15 for 15% margin).
/// Formula: total_cost / (1.0 - margin_ratio)
pub fn break_even_cargo_value(cost_breakdown: &CostBreakdown, target_margin_ratio: f64) -> u64;
```

### Required Structs/Enums

1. `ExpeditionConfig` - Complete expedition configuration
2. `CostBreakdown` - Itemized cost breakdown
3. `RiskFactors` - Environmental and operational risk multipliers

### Architectural Patterns to Follow

- Follow `projected_cost_cents` and `margin_ratio` patterns from `economics.rs`
- Use `HashMap` for vehicle comparisons (like `route_segments` in routing.rs)
- Apply rounding consistently (use `.round() as u64`)
- Use `Option<T>` for optional parameters with sensible defaults
- Keep computation pure and deterministic

### Acceptance Criteria

1. All functions implemented as specified
2. Create `tests/expedition_tests.rs` with at least 18 tests covering:
   - Fuel rates for all vehicle types
   - Fuel cost with hazardous segment multipliers
   - Equipment costs for all cargo/vehicle combinations
   - Personnel costs with overtime and hazard pay
   - Insurance calculations with all multipliers
   - Contingency calculations within bounds
   - Complete cost breakdown generation
   - Vehicle comparison across all types
   - Most economical route selection
   - Break-even calculations
3. All tests pass with `cargo test`
4. Module properly exported in `src/lib.rs`

### Example Test Cases

```rust
#[test]
fn fuel_cost_with_hazardous_segments() {
    let config = ExpeditionConfig {
        expedition_id: "exp-1".to_string(),
        distance_km: 500.0,
        hazardous_segments: 3,
        duration_hours: 48,
        crew_size: 4,
        cargo_class: "frozen".to_string(),
        vehicle_type: "tracked".to_string(),
    };
    // 500km * 4.5L/km * 250 cents/L = 562500 base
    // 3 hazardous segments: 1.15^3 = 1.52 multiplier (capped at 2.5)
    let cost = calculate_fuel_cost(&config, 250);
    assert!(cost > 562500); // Should be higher due to hazard multiplier
}

#[test]
fn compare_vehicle_costs_returns_all_types() {
    let config = ExpeditionConfig {
        expedition_id: "exp-compare".to_string(),
        distance_km: 200.0,
        hazardous_segments: 0,
        duration_hours: 24,
        crew_size: 2,
        cargo_class: "standard".to_string(),
        vehicle_type: "wheeled".to_string(),
    };
    let risk = RiskFactors { weather_multiplier: 1.0, geopolitical_multiplier: 1.0, seasonal_multiplier: 1.0 };
    let comparisons = compare_vehicle_costs(&config, 250, &risk);
    assert_eq!(comparisons.len(), 4);
    assert!(comparisons.contains_key("tracked"));
    assert!(comparisons.contains_key("wheeled"));
    assert!(comparisons.contains_key("aerial"));
    assert!(comparisons.contains_key("marine"));
}
```

---

## Integration Notes

After implementing all three modules, consider these integration points with existing PolarisCore modules:

1. **Weather + Routing**: `worst_hub_impact` results can inform `select_hub` decisions
2. **ColdChain + Policy**: `ComplianceReport.status` can feed into `risk_score` calculations
3. **Expedition + Economics**: `break_even_cargo_value` aligns with `margin_ratio` profitability analysis

These integrations are optional extensions beyond the core greenfield tasks.
