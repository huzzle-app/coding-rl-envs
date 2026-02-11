# Aerolith - Greenfield Tasks

## Overview

The Aerolith platform supports three greenfield implementation tasks that require building entirely new modules from scratch following existing architectural patterns. These tasks test your ability to design modular systems, implement complex algorithms, and integrate new services with existing subsystems while maintaining code quality and test coverage.

## Environment

- **Language**: Rust
- **Infrastructure**: Docker-based development environment with full test suite (1220 tests)
- **Difficulty**: Ultra-Principal

## Tasks

### Task 1: Debris Avoidance Planner (New Module: `src/debris_avoidance.rs`)

Implement a debris avoidance planning module that generates collision avoidance maneuvers for satellites in the constellation. The planner must predict debris trajectories using simplified circular orbit propagation, compute time-to-closest-approach (TCA), assess urgency levels (None/Watch/Yellow/Red), and generate optimal evasive burn plans while minimizing fuel consumption.

**Key Interfaces:**
- `DebrisObject`: Tracked debris with catalog ID, altitude, inclination, mean motion, RCS, and last observation timestamp
- `ConjunctionEvent`: Predicted conjunction with debris reference, TCA, miss distance, probability, and relative velocity
- `AvoidanceManeuver`: Burn plan with timing, delta-v, direction vectors, post-maneuver miss distance, and fuel cost
- `DebrisAvoidancePlanner` trait: `propagate_debris()`, `screen_conjunctions()`, `compute_collision_probability()`, `assess_urgency()`, `plan_avoidance_maneuver()`, `validate_maneuver()`

**Standalone Functions:** Orbital propagation, altitude threat detection, Tsiolkovsky fuel calculations, optimal burn timing, burn direction normalization, risk priority sorting, and conjunction window merging.

Minimum 15 unit tests covering propagation, screening, probability calculations, urgency assessment, maneuver planning, and validation. Integrate with `orbit::orbital_period_minutes()`, `safety::collision_probability()`, `power::battery_soc()`, and `scheduling::contact_window_end()`.

### Task 2: Solar Panel Orientation Optimizer (New Module: `src/panel_optimizer.rs`)

Implement a solar panel orientation optimization module that maximizes power generation while balancing thermal constraints, eclipse periods, and attitude control limitations. The optimizer must compute optimal panel angles based on sun position, predict power output at given orientations, estimate thermal states with heating/cooling rates, and generate time-sequenced orientation commands.

**Key Interfaces:**
- `PanelConfig`: Panel physical configuration with max power, area, temperature limits, and rotation rate constraints
- `SunVector`: Sun position with elevation, azimuth, and intensity parameters
- `OrientationCommand`: Target angle, timestamp, and expected power output
- `OptimizationConstraints`: Power requirements, thermal limits, pointing accuracy, and eclipse windows
- `PanelThermalState`: Temperature tracking with heating rate and time-to-max predictions
- `PanelOrientationOptimizer` trait: `compute_optimal_angle()`, `predict_power_output()`, `estimate_thermal_state()`, `optimize_orientation_plan()`, `should_feather_panel()`, `calculate_rotation_time()`

**Standalone Functions:** Incidence angle calculations, instantaneous power predictions, thermal state evolution, heating rates, angle normalization, shortest rotation paths, rate limiting checks, and energy integration.

Minimum 15 unit tests covering optimal angles, power predictions, thermal modeling, planning algorithms, feathering logic, and rotation timing. Integrate with `power::solar_panel_output_watts()`, `scheduling::eclipse_duration_s()`, `orbit::eclipse_fraction()`, and `telemetry::health_score()`.

### Task 3: Telemetry Compression Service (New Module: `src/telemetry_compression.rs`)

Implement a telemetry compression service that reduces downlink bandwidth while preserving data fidelity for critical measurements. The service must support multiple compression strategies (delta encoding, statistical summaries, exception encoding, raw passthrough), adapt strategy selection based on data characteristics and bandwidth constraints, detect compression-related anomalies, and validate packet integrity.

**Key Interfaces:**
- `TelemetrySample`: Raw samples with channel ID, timestamp (ms), value, and quality flag
- `CompressedPacket`: Compressed output with window boundaries, sample count, payload variant, and compression ratio
- `CompressionPayload` enum: Delta, Summary, Exception, Raw variants
- `CompressionStrategy` enum: MaxCompression, MaxFidelity, Balanced, Adaptive
- `ChannelConfig`: Per-channel strategy preference, error tolerance, batch sizing, critical flag
- `DecompressionResult`: Reconstructed samples, quality metrics (max/RMS error), and anomalies
- `CompressionAnomaly`: Timestamp, anomaly type (OutOfRange/PatternAnomaly/IntegrityError/TimestampGap), severity, description
- `TelemetryCompressor` trait: `compress()`, `decompress()`, `select_strategy()`, `estimate_compressed_size()`, `validate_packet()`, `detect_anomalies()`, `compression_statistics()`

**Standalone Functions:** Delta encoding/decoding, statistical summary computation, exception identification and reconstruction, compression ratio calculation, entropy estimation, CRC32 checksums, timestamp gap detection, and packet merging.

Minimum 15 unit tests covering delta encoding, summary statistics, exception handling, strategy selection, size estimation, packet validation, anomaly detection, and compression metrics. Integrate with `telemetry::TelemetrySample` patterns, `telemetry::error_rate()`, `routing::data_rate_mbps()`, and `resilience::circuit_open()`.

## Getting Started

```bash
cargo test
```

Run this command to execute the full test suite. Your implementations must integrate cleanly with the existing codebase and pass all tests.

## Success Criteria

Your implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md), which specifies detailed requirements for each module including required structs, trait contracts, standalone functions, minimum unit test coverage (15+ tests per module), integration points, and code quality expectations (80% line coverage minimum).

All modules must follow existing architectural patterns: public structs with `#[derive(Debug, Clone)]`, standalone functions for stateless operations, trait-based service interfaces, and descriptive error handling using `Option<T>`. Register new modules in `src/lib.rs` and create test files at `tests/<module>_tests.rs`.
