# Aerolith Greenfield Tasks

This document defines new modules to implement from scratch for the Aerolith satellite operations platform. Each task requires creating a new service following existing architectural patterns.

**Test command:** `cargo test`

---

## Task 1: Debris Avoidance Planner

### Overview

Implement a debris avoidance planning module that generates collision avoidance maneuvers for satellites in the constellation. The planner must predict debris trajectories, compute time-to-closest-approach (TCA), and generate optimal evasive burn plans while minimizing fuel consumption.

### Module Location

Create `src/debris_avoidance.rs` and register in `src/lib.rs`.

### Required Structs

```rust
/// Tracked debris object in orbital space
#[derive(Debug, Clone)]
pub struct DebrisObject {
    /// Unique catalog identifier (e.g., NORAD ID)
    pub catalog_id: String,
    /// Current altitude in kilometers
    pub altitude_km: f64,
    /// Inclination in degrees
    pub inclination_deg: f64,
    /// Mean motion in revolutions per day
    pub mean_motion_rev_day: f64,
    /// Radar cross-section in square meters
    pub rcs_m2: f64,
    /// Last observation timestamp (Unix seconds)
    pub last_observed: u64,
}

/// Predicted conjunction event between satellite and debris
#[derive(Debug, Clone)]
pub struct ConjunctionEvent {
    /// Debris object involved
    pub debris: DebrisObject,
    /// Time of closest approach (Unix seconds)
    pub tca_s: u64,
    /// Predicted miss distance in meters
    pub miss_distance_m: f64,
    /// Collision probability (0.0 to 1.0)
    pub probability: f64,
    /// Relative velocity at TCA in m/s
    pub relative_velocity_mps: f64,
}

/// Avoidance maneuver plan
#[derive(Debug, Clone)]
pub struct AvoidanceManeuver {
    /// Target debris event being avoided
    pub conjunction: ConjunctionEvent,
    /// Recommended burn start time (Unix seconds)
    pub burn_start_s: u64,
    /// Delta-v required in m/s
    pub delta_v_mps: f64,
    /// Burn direction (radial, in-track, cross-track components)
    pub direction: BurnDirection,
    /// Post-maneuver predicted miss distance
    pub new_miss_distance_m: f64,
    /// Fuel cost in kg
    pub fuel_kg: f64,
}

/// Burn direction vector components
#[derive(Debug, Clone)]
pub struct BurnDirection {
    /// Radial component (toward/away from Earth center)
    pub radial: f64,
    /// In-track component (along velocity vector)
    pub in_track: f64,
    /// Cross-track component (perpendicular to orbital plane)
    pub cross_track: f64,
}

/// Risk assessment result
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AvoidanceUrgency {
    /// No action needed
    None,
    /// Monitor situation
    Watch,
    /// Plan maneuver within 24 hours
    Yellow,
    /// Immediate action required
    Red,
}
```

### Trait Contract

```rust
/// Debris avoidance planning service for satellite collision mitigation.
pub trait DebrisAvoidancePlanner {
    /// Predicts debris trajectory forward in time.
    ///
    /// # Arguments
    /// * `debris` - The debris object to propagate
    /// * `duration_s` - How far to propagate (seconds)
    /// * `step_s` - Time step for position samples
    ///
    /// # Returns
    /// Vector of (timestamp, altitude_km, inclination_deg) tuples
    fn propagate_debris(
        &self,
        debris: &DebrisObject,
        duration_s: u64,
        step_s: u64,
    ) -> Vec<(u64, f64, f64)>;

    /// Screens for potential conjunctions within a time window.
    ///
    /// # Arguments
    /// * `satellite_altitude_km` - Current satellite altitude
    /// * `satellite_inclination_deg` - Current satellite inclination
    /// * `debris_catalog` - All tracked debris objects
    /// * `window_start_s` - Start of screening window (Unix time)
    /// * `window_end_s` - End of screening window (Unix time)
    /// * `threshold_km` - Miss distance threshold for reporting
    ///
    /// # Returns
    /// All conjunction events within threshold, sorted by TCA
    fn screen_conjunctions(
        &self,
        satellite_altitude_km: f64,
        satellite_inclination_deg: f64,
        debris_catalog: &[DebrisObject],
        window_start_s: u64,
        window_end_s: u64,
        threshold_km: f64,
    ) -> Vec<ConjunctionEvent>;

    /// Computes collision probability using NASA conjunction assessment formula.
    ///
    /// # Arguments
    /// * `miss_distance_m` - Predicted miss distance
    /// * `combined_covariance_m` - Combined position uncertainty (1-sigma)
    /// * `combined_rcs_m2` - Combined radar cross-section
    ///
    /// # Returns
    /// Probability of collision (0.0 to 1.0)
    fn compute_collision_probability(
        &self,
        miss_distance_m: f64,
        combined_covariance_m: f64,
        combined_rcs_m2: f64,
    ) -> f64;

    /// Assesses urgency level for a conjunction event.
    ///
    /// # Arguments
    /// * `event` - The conjunction event to assess
    /// * `current_time_s` - Current Unix timestamp
    ///
    /// # Returns
    /// Urgency classification
    fn assess_urgency(
        &self,
        event: &ConjunctionEvent,
        current_time_s: u64,
    ) -> AvoidanceUrgency;

    /// Plans an optimal avoidance maneuver for a conjunction.
    ///
    /// # Arguments
    /// * `event` - The conjunction to avoid
    /// * `fuel_available_kg` - Remaining propellant mass
    /// * `max_delta_v_mps` - Maximum delta-v capability
    ///
    /// # Returns
    /// Recommended maneuver, or None if no safe maneuver possible
    fn plan_avoidance_maneuver(
        &self,
        event: &ConjunctionEvent,
        fuel_available_kg: f64,
        max_delta_v_mps: f64,
    ) -> Option<AvoidanceManeuver>;

    /// Validates that a maneuver achieves sufficient miss distance.
    ///
    /// # Arguments
    /// * `maneuver` - The proposed maneuver
    /// * `min_miss_distance_m` - Required minimum miss distance
    ///
    /// # Returns
    /// True if maneuver achieves safe separation
    fn validate_maneuver(
        &self,
        maneuver: &AvoidanceManeuver,
        min_miss_distance_m: f64,
    ) -> bool;
}
```

### Standalone Functions to Implement

```rust
/// Calculates time to closest approach between two orbital objects.
/// Uses simplified circular orbit approximation.
pub fn time_to_closest_approach(
    sat_altitude_km: f64,
    sat_mean_anomaly_deg: f64,
    debris_altitude_km: f64,
    debris_mean_anomaly_deg: f64,
    debris_mean_motion_rev_day: f64,
) -> f64;

/// Determines if debris is in a threatening altitude band (within tolerance).
pub fn is_altitude_threatening(
    sat_altitude_km: f64,
    debris_altitude_km: f64,
    tolerance_km: f64,
) -> bool;

/// Computes fuel cost for a given delta-v using Tsiolkovsky equation.
/// fuel_mass = dry_mass * (exp(dv / (Isp * g0)) - 1)
pub fn fuel_cost_kg(
    delta_v_mps: f64,
    dry_mass_kg: f64,
    specific_impulse_s: f64,
) -> f64;

/// Calculates optimal burn time for maximum miss distance improvement.
/// Burn should occur at half the time to TCA for in-track maneuvers.
pub fn optimal_burn_time(tca_s: u64, current_time_s: u64) -> u64;

/// Normalizes a burn direction vector to unit length.
pub fn normalize_burn_direction(dir: &BurnDirection) -> BurnDirection;

/// Sorts conjunction events by risk priority (probability * 1/time_to_tca).
pub fn sort_by_risk_priority(events: &mut Vec<ConjunctionEvent>, current_time_s: u64);

/// Filters debris catalog to only include objects within altitude range.
pub fn filter_by_altitude_range(
    debris: &[DebrisObject],
    min_altitude_km: f64,
    max_altitude_km: f64,
) -> Vec<DebrisObject>;

/// Merges overlapping conjunction events (same debris, close TCA).
pub fn merge_conjunction_windows(
    events: &[ConjunctionEvent],
    time_tolerance_s: u64,
) -> Vec<ConjunctionEvent>;
```

### Acceptance Criteria

1. **Unit Tests (minimum 15):**
   - `test_propagate_debris_basic` - Verify trajectory propagation over 1 orbit
   - `test_propagate_debris_multi_day` - 7-day propagation accuracy
   - `test_screen_conjunctions_empty_catalog` - Handles empty debris list
   - `test_screen_conjunctions_finds_threats` - Detects objects within threshold
   - `test_screen_conjunctions_filters_by_window` - Respects time bounds
   - `test_collision_probability_high_miss` - Low probability for large miss distance
   - `test_collision_probability_near_miss` - High probability for close approach
   - `test_assess_urgency_none` - Low probability, far TCA returns None
   - `test_assess_urgency_red` - High probability, imminent TCA returns Red
   - `test_plan_maneuver_basic` - Generates valid maneuver plan
   - `test_plan_maneuver_insufficient_fuel` - Returns None when fuel limited
   - `test_validate_maneuver_success` - Accepts maneuver meeting threshold
   - `test_validate_maneuver_failure` - Rejects insufficient maneuver
   - `test_fuel_cost_calculation` - Tsiolkovsky equation accuracy
   - `test_sort_by_risk_priority` - Correct priority ordering

2. **Integration Points:**
   - Uses `orbit::orbital_period_minutes()` for period calculations
   - Uses `safety::collision_probability()` as reference (but implement correctly)
   - Uses `power::battery_soc()` to check power availability before maneuver
   - Integrates with `scheduling::contact_window_end()` for ground uplink timing

3. **Coverage:** Minimum 80% line coverage for the module

---

## Task 2: Solar Panel Orientation Optimizer

### Overview

Implement a solar panel orientation optimization module that maximizes power generation while accounting for thermal constraints, eclipse periods, and attitude control limitations. The optimizer must balance competing objectives: maximum sun exposure vs. thermal management vs. attitude stability.

### Module Location

Create `src/panel_optimizer.rs` and register in `src/lib.rs`.

### Required Structs

```rust
/// Solar panel physical configuration
#[derive(Debug, Clone)]
pub struct PanelConfig {
    /// Panel identifier
    pub panel_id: String,
    /// Maximum power output at optimal orientation (watts)
    pub max_power_w: f64,
    /// Panel area in square meters
    pub area_m2: f64,
    /// Maximum safe temperature (Celsius)
    pub max_temp_c: f64,
    /// Minimum operating temperature (Celsius)
    pub min_temp_c: f64,
    /// Rotation rate limit (degrees per second)
    pub max_rotation_rate_deg_s: f64,
}

/// Current sun position relative to spacecraft
#[derive(Debug, Clone)]
pub struct SunVector {
    /// Elevation above spacecraft body X-Y plane (degrees)
    pub elevation_deg: f64,
    /// Azimuth in spacecraft body frame (degrees)
    pub azimuth_deg: f64,
    /// Solar intensity (W/m^2), accounts for distance from sun
    pub intensity_w_m2: f64,
}

/// Panel orientation command
#[derive(Debug, Clone)]
pub struct OrientationCommand {
    /// Target panel identifier
    pub panel_id: String,
    /// Target rotation angle (degrees)
    pub angle_deg: f64,
    /// Command timestamp (Unix seconds)
    pub timestamp_s: u64,
    /// Expected power at this orientation
    pub expected_power_w: f64,
}

/// Optimization constraints
#[derive(Debug, Clone)]
pub struct OptimizationConstraints {
    /// Minimum power required for spacecraft operations (watts)
    pub min_power_w: f64,
    /// Maximum allowable panel temperature (Celsius)
    pub max_temp_c: f64,
    /// Attitude pointing accuracy requirement (degrees)
    pub pointing_accuracy_deg: f64,
    /// Eclipse entry time (Unix seconds), None if no eclipse
    pub eclipse_start_s: Option<u64>,
    /// Eclipse exit time (Unix seconds)
    pub eclipse_end_s: Option<u64>,
}

/// Optimization result
#[derive(Debug, Clone)]
pub struct OptimizationResult {
    /// Sequence of orientation commands
    pub commands: Vec<OrientationCommand>,
    /// Total expected energy over period (watt-hours)
    pub total_energy_wh: f64,
    /// Peak temperature reached (Celsius)
    pub peak_temp_c: f64,
    /// Optimization score (0.0 to 1.0)
    pub score: f64,
}

/// Panel thermal state
#[derive(Debug, Clone)]
pub struct PanelThermalState {
    /// Current temperature (Celsius)
    pub current_temp_c: f64,
    /// Heating rate at current orientation (degrees/second)
    pub heating_rate_c_s: f64,
    /// Time to max temperature (seconds), None if cooling
    pub time_to_max_s: Option<u64>,
}
```

### Trait Contract

```rust
/// Solar panel orientation optimization service.
pub trait PanelOrientationOptimizer {
    /// Computes optimal panel angle for maximum power at given sun position.
    ///
    /// # Arguments
    /// * `panel` - Panel configuration
    /// * `sun` - Current sun vector
    ///
    /// # Returns
    /// Optimal angle in degrees
    fn compute_optimal_angle(
        &self,
        panel: &PanelConfig,
        sun: &SunVector,
    ) -> f64;

    /// Predicts power output at a given panel angle.
    ///
    /// # Arguments
    /// * `panel` - Panel configuration
    /// * `sun` - Current sun vector
    /// * `angle_deg` - Panel rotation angle
    ///
    /// # Returns
    /// Predicted power output in watts
    fn predict_power_output(
        &self,
        panel: &PanelConfig,
        sun: &SunVector,
        angle_deg: f64,
    ) -> f64;

    /// Estimates panel thermal state at given orientation.
    ///
    /// # Arguments
    /// * `panel` - Panel configuration
    /// * `sun` - Current sun vector
    /// * `angle_deg` - Current panel angle
    /// * `ambient_temp_c` - Ambient spacecraft temperature
    ///
    /// # Returns
    /// Thermal state including temperature and heating rate
    fn estimate_thermal_state(
        &self,
        panel: &PanelConfig,
        sun: &SunVector,
        angle_deg: f64,
        ambient_temp_c: f64,
    ) -> PanelThermalState;

    /// Plans orientation commands for an optimization window.
    ///
    /// # Arguments
    /// * `panels` - All panel configurations
    /// * `sun_trajectory` - Predicted sun positions over time (timestamp, SunVector)
    /// * `constraints` - Optimization constraints
    /// * `window_start_s` - Start of planning window
    /// * `window_end_s` - End of planning window
    /// * `step_s` - Command time resolution
    ///
    /// # Returns
    /// Optimization result with command sequence
    fn optimize_orientation_plan(
        &self,
        panels: &[PanelConfig],
        sun_trajectory: &[(u64, SunVector)],
        constraints: &OptimizationConstraints,
        window_start_s: u64,
        window_end_s: u64,
        step_s: u64,
    ) -> OptimizationResult;

    /// Determines if panel should enter safe mode (feather) for thermal protection.
    ///
    /// # Arguments
    /// * `thermal_state` - Current thermal state
    /// * `panel` - Panel configuration
    ///
    /// # Returns
    /// True if safe mode recommended
    fn should_feather_panel(
        &self,
        thermal_state: &PanelThermalState,
        panel: &PanelConfig,
    ) -> bool;

    /// Calculates rotation command to move panel from current to target angle.
    ///
    /// # Arguments
    /// * `panel` - Panel configuration
    /// * `current_angle_deg` - Current orientation
    /// * `target_angle_deg` - Desired orientation
    /// * `timestamp_s` - Command timestamp
    ///
    /// # Returns
    /// Rotation time in seconds required
    fn calculate_rotation_time(
        &self,
        panel: &PanelConfig,
        current_angle_deg: f64,
        target_angle_deg: f64,
    ) -> f64;
}
```

### Standalone Functions to Implement

```rust
/// Computes cosine of incidence angle between panel normal and sun vector.
/// Returns value between -1.0 (backlit) and 1.0 (direct).
pub fn cosine_incidence_angle(panel_angle_deg: f64, sun_elevation_deg: f64, sun_azimuth_deg: f64) -> f64;

/// Calculates instantaneous power from solar flux and incidence.
/// power = intensity * area * cos(incidence) * efficiency
pub fn instantaneous_power_w(
    intensity_w_m2: f64,
    area_m2: f64,
    cosine_incidence: f64,
    efficiency: f64,
) -> f64;

/// Predicts panel temperature after time delta.
/// Uses simplified thermal model: T_new = T_old + heating_rate * dt
pub fn predict_temperature_c(
    current_temp_c: f64,
    heating_rate_c_s: f64,
    duration_s: f64,
) -> f64;

/// Computes heating rate from absorbed solar power.
/// heating_rate = (absorbed_power - radiated_power) / thermal_mass
pub fn heating_rate_c_per_s(
    absorbed_power_w: f64,
    radiated_power_w: f64,
    thermal_mass_j_c: f64,
) -> f64;

/// Normalizes angle to [-180, 180) range.
pub fn normalize_angle_deg(angle: f64) -> f64;

/// Shortest rotation direction between two angles.
/// Returns signed delta (positive = clockwise).
pub fn shortest_rotation_deg(from_deg: f64, to_deg: f64) -> f64;

/// Checks if rotation exceeds rate limit.
pub fn exceeds_rate_limit(
    rotation_deg: f64,
    duration_s: f64,
    max_rate_deg_s: f64,
) -> bool;

/// Integrates energy over command sequence.
pub fn integrate_energy_wh(commands: &[OrientationCommand]) -> f64;
```

### Acceptance Criteria

1. **Unit Tests (minimum 15):**
   - `test_optimal_angle_sun_overhead` - Returns 0 for sun at zenith
   - `test_optimal_angle_sun_at_45` - Correct angle for angled sun
   - `test_predict_power_direct_sunlight` - Maximum power at optimal angle
   - `test_predict_power_oblique` - Reduced power at off-angle
   - `test_predict_power_backlit` - Zero power when panel faces away
   - `test_thermal_state_heating` - Positive heating rate in sunlight
   - `test_thermal_state_cooling` - Negative rate in eclipse
   - `test_optimize_plan_basic` - Generates valid command sequence
   - `test_optimize_plan_respects_thermal` - Feathers panel near max temp
   - `test_optimize_plan_eclipse_handling` - Proper eclipse transition
   - `test_should_feather_near_max` - True when approaching max temp
   - `test_should_feather_safe` - False when temperature safe
   - `test_rotation_time_calculation` - Correct time for given rate
   - `test_normalize_angle_positive` - Handles angles > 180
   - `test_normalize_angle_negative` - Handles angles < -180

2. **Integration Points:**
   - Uses `power::solar_panel_output_watts()` as reference
   - Uses `scheduling::eclipse_duration_s()` for eclipse timing
   - Uses `orbit::eclipse_fraction()` for eclipse calculations
   - Integrates with `telemetry::health_score()` for panel health reporting

3. **Coverage:** Minimum 80% line coverage for the module

---

## Task 3: Telemetry Compression Service

### Overview

Implement a telemetry compression service that reduces downlink bandwidth requirements while preserving data fidelity for critical measurements. The service must support multiple compression strategies, detect anomalies in compressed streams, and provide configurable quality-bandwidth tradeoffs.

### Module Location

Create `src/telemetry_compression.rs` and register in `src/lib.rs`.

### Required Structs

```rust
/// Raw telemetry sample with metadata
#[derive(Debug, Clone)]
pub struct TelemetrySample {
    /// Channel identifier
    pub channel_id: String,
    /// Sample timestamp (Unix milliseconds)
    pub timestamp_ms: u64,
    /// Raw value (various units depending on channel)
    pub value: f64,
    /// Quality flag (0=good, 1=suspect, 2=bad)
    pub quality: u8,
}

/// Compressed telemetry packet
#[derive(Debug, Clone)]
pub struct CompressedPacket {
    /// Channel identifier
    pub channel_id: String,
    /// Start timestamp of packet window (Unix ms)
    pub start_timestamp_ms: u64,
    /// End timestamp of packet window (Unix ms)
    pub end_timestamp_ms: u64,
    /// Number of original samples
    pub sample_count: usize,
    /// Compressed representation
    pub data: CompressionPayload,
    /// Compression ratio achieved (original_size / compressed_size)
    pub compression_ratio: f64,
}

/// Compression payload variants
#[derive(Debug, Clone)]
pub enum CompressionPayload {
    /// Delta encoding: base value + deltas
    Delta {
        base_value: f64,
        deltas: Vec<i16>,
        scale_factor: f64,
    },
    /// Statistical summary: min, max, mean, std
    Summary {
        min: f64,
        max: f64,
        mean: f64,
        std_dev: f64,
    },
    /// Exception encoding: baseline + exceptions
    Exception {
        baseline: f64,
        exception_indices: Vec<u16>,
        exception_values: Vec<f64>,
        tolerance: f64,
    },
    /// Raw passthrough (no compression)
    Raw {
        values: Vec<f64>,
    },
}

/// Compression strategy selection
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompressionStrategy {
    /// Optimize for maximum compression ratio
    MaxCompression,
    /// Optimize for data fidelity (lossless where possible)
    MaxFidelity,
    /// Balance compression and fidelity
    Balanced,
    /// Adaptive based on data characteristics
    Adaptive,
}

/// Channel compression configuration
#[derive(Debug, Clone)]
pub struct ChannelConfig {
    /// Channel identifier
    pub channel_id: String,
    /// Preferred compression strategy
    pub strategy: CompressionStrategy,
    /// Maximum allowable error (for lossy compression)
    pub max_error: f64,
    /// Minimum samples before compression
    pub min_batch_size: usize,
    /// Critical flag (never use lossy compression)
    pub is_critical: bool,
}

/// Decompression result with quality metrics
#[derive(Debug, Clone)]
pub struct DecompressionResult {
    /// Reconstructed samples
    pub samples: Vec<TelemetrySample>,
    /// Maximum reconstruction error
    pub max_error: f64,
    /// Root mean square error
    pub rms_error: f64,
    /// Any anomalies detected during decompression
    pub anomalies: Vec<CompressionAnomaly>,
}

/// Anomaly detected in compressed stream
#[derive(Debug, Clone)]
pub struct CompressionAnomaly {
    /// Timestamp of anomaly
    pub timestamp_ms: u64,
    /// Anomaly type
    pub anomaly_type: AnomalyType,
    /// Severity (0.0 to 1.0)
    pub severity: f64,
    /// Description
    pub description: String,
}

/// Types of compression-related anomalies
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AnomalyType {
    /// Data exceeds expected range
    OutOfRange,
    /// Unexpected data pattern
    PatternAnomaly,
    /// Compression integrity failure
    IntegrityError,
    /// Timestamp discontinuity
    TimestampGap,
}
```

### Trait Contract

```rust
/// Telemetry compression service for bandwidth optimization.
pub trait TelemetryCompressor {
    /// Compresses a batch of telemetry samples.
    ///
    /// # Arguments
    /// * `samples` - Raw samples to compress (must be sorted by timestamp)
    /// * `config` - Channel-specific compression configuration
    ///
    /// # Returns
    /// Compressed packet
    fn compress(
        &self,
        samples: &[TelemetrySample],
        config: &ChannelConfig,
    ) -> CompressedPacket;

    /// Decompresses a packet back to individual samples.
    ///
    /// # Arguments
    /// * `packet` - Compressed packet to decompress
    ///
    /// # Returns
    /// Decompression result with samples and quality metrics
    fn decompress(
        &self,
        packet: &CompressedPacket,
    ) -> DecompressionResult;

    /// Selects optimal compression strategy based on data characteristics.
    ///
    /// # Arguments
    /// * `samples` - Sample batch to analyze
    /// * `bandwidth_budget_bps` - Available bandwidth in bits per second
    /// * `latency_budget_ms` - Maximum acceptable latency
    ///
    /// # Returns
    /// Recommended compression strategy
    fn select_strategy(
        &self,
        samples: &[TelemetrySample],
        bandwidth_budget_bps: u64,
        latency_budget_ms: u64,
    ) -> CompressionStrategy;

    /// Estimates compressed size for a sample batch.
    ///
    /// # Arguments
    /// * `samples` - Samples to estimate
    /// * `strategy` - Compression strategy to use
    ///
    /// # Returns
    /// Estimated size in bytes
    fn estimate_compressed_size(
        &self,
        samples: &[TelemetrySample],
        strategy: CompressionStrategy,
    ) -> usize;

    /// Validates packet integrity after transmission.
    ///
    /// # Arguments
    /// * `packet` - Packet to validate
    /// * `expected_checksum` - Expected checksum value
    ///
    /// # Returns
    /// True if packet is valid
    fn validate_packet(
        &self,
        packet: &CompressedPacket,
        expected_checksum: u32,
    ) -> bool;

    /// Detects anomalies in a compressed stream.
    ///
    /// # Arguments
    /// * `packets` - Sequence of compressed packets
    /// * `history` - Recent decompressed values for context
    ///
    /// # Returns
    /// List of detected anomalies
    fn detect_anomalies(
        &self,
        packets: &[CompressedPacket],
        history: &[TelemetrySample],
    ) -> Vec<CompressionAnomaly>;

    /// Computes compression statistics over multiple packets.
    ///
    /// # Arguments
    /// * `packets` - Packets to analyze
    ///
    /// # Returns
    /// (average_ratio, min_ratio, max_ratio)
    fn compression_statistics(
        &self,
        packets: &[CompressedPacket],
    ) -> (f64, f64, f64);
}
```

### Standalone Functions to Implement

```rust
/// Computes delta encoding for a value sequence.
/// Returns (base_value, deltas, scale_factor).
pub fn delta_encode(values: &[f64], precision: u8) -> (f64, Vec<i16>, f64);

/// Decodes delta-encoded values back to original.
pub fn delta_decode(base: f64, deltas: &[i16], scale_factor: f64) -> Vec<f64>;

/// Computes statistical summary of values.
pub fn compute_summary(values: &[f64]) -> (f64, f64, f64, f64);

/// Identifies exception indices where value deviates from baseline.
pub fn find_exceptions(values: &[f64], baseline: f64, tolerance: f64) -> Vec<(u16, f64)>;

/// Reconstructs values from exception encoding.
pub fn reconstruct_from_exceptions(
    count: usize,
    baseline: f64,
    exceptions: &[(u16, f64)],
) -> Vec<f64>;

/// Calculates compression ratio.
/// ratio = original_bytes / compressed_bytes
pub fn compression_ratio(original_bytes: usize, compressed_bytes: usize) -> f64;

/// Estimates entropy of a value sequence (bits per sample).
pub fn estimate_entropy(values: &[f64], bins: usize) -> f64;

/// Computes CRC32 checksum for packet validation.
pub fn compute_checksum(data: &[u8]) -> u32;

/// Detects timestamp gaps in sample sequence.
/// Returns indices where gap exceeds threshold.
pub fn detect_timestamp_gaps(samples: &[TelemetrySample], max_gap_ms: u64) -> Vec<usize>;

/// Merges multiple compressed packets for batch transmission.
pub fn merge_packets(packets: &[CompressedPacket]) -> Vec<u8>;
```

### Acceptance Criteria

1. **Unit Tests (minimum 15):**
   - `test_compress_delta_basic` - Delta encoding produces valid output
   - `test_compress_delta_high_variance` - Handles high-variance data
   - `test_compress_summary_constant` - Summary of constant values
   - `test_compress_exception_sparse` - Exception encoding for sparse changes
   - `test_decompress_delta_exact` - Delta decoding matches original
   - `test_decompress_summary_bounds` - Summary respects min/max
   - `test_select_strategy_low_bandwidth` - Chooses MaxCompression
   - `test_select_strategy_critical` - MaxFidelity for critical channels
   - `test_estimate_size_accurate` - Estimate within 10% of actual
   - `test_validate_packet_good` - Passes valid checksum
   - `test_validate_packet_corrupt` - Fails corrupt checksum
   - `test_detect_anomalies_out_of_range` - Catches range violations
   - `test_detect_anomalies_timestamp_gap` - Catches missing samples
   - `test_compression_ratio_calculation` - Correct ratio math
   - `test_entropy_estimation` - Reasonable entropy values

2. **Integration Points:**
   - Uses `telemetry::TelemetrySample` struct pattern as reference
   - Uses `telemetry::error_rate()` for quality assessment
   - Uses `routing::data_rate_mbps()` for bandwidth calculations
   - Integrates with `resilience::circuit_open()` for backpressure

3. **Coverage:** Minimum 80% line coverage for the module

---

## General Implementation Guidelines

### Architectural Patterns

Follow these patterns from the existing codebase:

1. **Module Structure:**
   - Public structs with `#[derive(Debug, Clone)]`
   - Standalone functions for stateless operations
   - Trait for complex service interfaces

2. **Error Handling:**
   - Return `Option<T>` for operations that may not produce results
   - Use descriptive types rather than `Result` for domain errors
   - Validate inputs at function boundaries

3. **Numeric Precision:**
   - Use `f64` for all floating-point calculations
   - Use `u64` for timestamps (Unix seconds or milliseconds)
   - Clamp values to valid ranges where appropriate

4. **Testing:**
   - Create test file at `tests/<module>_tests.rs`
   - Use descriptive test names: `test_<function>_<scenario>`
   - Include edge cases: empty inputs, boundary values, overflow

### Dependencies

Only use dependencies already in `Cargo.toml`:
- `serde` with `derive` feature for serialization

Additional standard library imports allowed:
- `std::collections::{HashMap, HashSet, VecDeque}`
- `std::f64::consts::{PI, TAU, E}`

### Registration

After implementing each module, register in `src/lib.rs`:

```rust
pub mod debris_avoidance;
pub mod panel_optimizer;
pub mod telemetry_compression;
```
