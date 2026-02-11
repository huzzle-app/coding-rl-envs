# PolarisCore - Greenfield Implementation Tasks

## Overview
Three greenfield module implementations for the PolarisCore platform. Each task requires building a complete new module from scratch following established architectural patterns while integrating seamlessly with existing services.

## Environment
- **Language**: Rust
- **Infrastructure**: Cold-chain logistics control plane with 13 microservices
- **Difficulty**: Hyper-Principal (70-140h expected)

## Tasks

### Task 1: Weather Impact Assessor (Greenfield Module)
Implement a weather impact assessment module (`src/weather.rs`) that evaluates how current and forecasted weather conditions affect polar logistics operations. The module must assess weather severity based on temperature, wind speed, visibility, and precipitation type using defined thresholds. Calculate delay factors accounting for both base severity and environmental modifiers. Determine cold-chain integrity risk and generate operation recommendations (proceed, delay, reroute, hold). Support route viability scoring across multiple segments for comprehensive route planning integration.

**Key Interfaces**: `WeatherObservation` (location, temperature, wind, visibility, precipitation), `WeatherSeverity` (Clear, Advisory, Warning, Severe), `WeatherImpact` (severity, delay_factor, cold_chain_risk, recommendation)

**Core Functions**: `assess_severity()`, `calculate_delay_factor()`, `cold_chain_at_risk()`, `assess_impact()`, `worst_hub_impact()`, `route_viability_score()`

### Task 2: Cold Chain Monitor (Greenfield Module)
Implement a cold chain monitoring module (`src/coldchain.rs`) that tracks temperature and environmental conditions throughout the logistics pipeline. Detect anomalies including temperature excursions, excessive fluctuations, and sensor gaps. Calculate cumulative exposure time outside acceptable ranges and generate compliance reports determining shipment status (compliant, minor-deviation, major-deviation, rejected). Estimate remaining safe transit time based on current conditions and deviation severity.

**Key Interfaces**: `TemperatureReading` (shipment_id, timestamp_secs, temperature_c, sensor_type), `ViolationType` (TooWarm, TooCold, Fluctuation, SensorGap), `Violation` (shipment_id, type, timing, severity), `ComplianceReport` (shipment_id, compliance_ratio, violations, status), `TemperatureBounds` (classification, min/max temps, fluctuation limits)

**Core Functions**: `default_bounds()`, `check_reading()`, `detect_sensor_gaps()`, `detect_fluctuations()`, `cumulative_exposure_secs()`, `generate_compliance_report()`, `estimate_safe_transit_secs()`

### Task 3: Expedition Cost Estimator (Greenfield Module)
Implement an expedition cost estimation module (`src/expedition.rs`) that calculates comprehensive logistics costs for polar expeditions. Break down fuel costs based on vehicle type and distance with hazardous segment multipliers. Calculate equipment rental costs accounting for cargo classification and duration. Compute personnel costs with overtime, hazard pay, and skill premiums. Determine insurance premiums based on cargo and vehicle risk factors. Estimate contingency reserves based on weather, geopolitical, and seasonal risk multipliers. Support vehicle comparison and route optimization for economical decision-making.

**Key Interfaces**: `ExpeditionConfig` (expedition_id, distance_km, hazardous_segments, duration_hours, crew_size, cargo_class, vehicle_type), `CostBreakdown` (fuel, equipment, personnel, insurance, contingency, total in cents), `RiskFactors` (weather_multiplier, geopolitical_multiplier, seasonal_multiplier)

**Core Functions**: `fuel_rate_per_km()`, `calculate_fuel_cost()`, `calculate_equipment_cost()`, `calculate_personnel_cost()`, `calculate_insurance_cost()`, `calculate_contingency()`, `estimate_expedition_cost()`, `compare_vehicle_costs()`, `most_economical_route()`, `break_even_cargo_value()`

## Getting Started
```bash
docker compose up -d
cargo test
```

## Success Criteria
- All functions implemented as specified in the module contracts
- Comprehensive test suites covering boundary conditions, edge cases, and integration scenarios
- All tests pass with `cargo test`
- Modules properly exported in `src/lib.rs`
- Implementation follows existing architectural patterns from routing.rs, policy.rs, and economics.rs
- New tests verify correctness of calculations and integration with existing services

## Integration Points
After implementing all three modules, consider these integration opportunities:
1. Weather + Routing: `worst_hub_impact` results inform `select_hub` decisions
2. ColdChain + Policy: `ComplianceReport.status` feeds into risk_score calculations
3. Expedition + Economics: `break_even_cargo_value` aligns with margin_ratio profitability analysis
