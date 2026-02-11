# HeliosOps - Greenfield Implementation Tasks

## Overview

Three greenfield module implementation tasks for the HeliosOps satellite operations platform. Each requires building new services from scratch following existing architectural patterns: constellation coordination, spacecraft health monitoring, and ground station scheduling.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL x3, Redis, NATS
- **Difficulty**: Hyper-Principal

## Tasks

### Task 1: Constellation Coordination Service (Greenfield)

Implement `ConstellationCoordinator` service to manage multi-satellite maneuvers, inter-satellite link scheduling, and formation-keeping. Coordinates orbital adjustments across multiple spacecraft, detects collision risks, plans collision avoidance maneuvers, and schedules inter-satellite communication links.

**Key Interfaces:**
- `register_satellite(satellite: Satellite)` - Register spacecraft with constellation
- `plan_maneuver(satellite_id, maneuver_type, target_elements)` - Calculate delta-v and schedule maneuver
- `assess_collision_risks(time_horizon_hours)` - Detect conjunctions over 72h window
- `plan_collision_avoidance(risk, strategy)` - Generate mitigation maneuver
- `schedule_inter_satellite_links(satellite_ids, start_time, end_time)` - Optimize ISL scheduling
- `propagate_orbit(satellite_id, to_time)` - SGP4/SDP4 orbit propagation

**Required Data Structures:**
- `OrbitalElements` - Keplerian elements (frozen)
- `Satellite` - Spacecraft state with propellant, power
- `Maneuver` - Planned orbital maneuver with dependencies
- `CollisionRisk` - Conjunction assessment
- `InterSatelliteLink` - Scheduled ISL communication window

**Acceptance Criteria:**
- 50+ unit tests covering maneuver planning, collision assessment, ISL scheduling
- Integration tests for full maneuver lifecycle
- >=85% line coverage, >=75% branch coverage
- Integration with `heliosops/scheduler.py` and `services/audit/event_store.py`

### Task 2: Anomaly Detection for Spacecraft Health (Greenfield)

Implement `SpacecraftHealthMonitor` service for real-time anomaly detection on telemetry streams. Detects out-of-range values, rate-of-change violations, trend anomalies, and cross-parameter correlations for early fault detection across multiple subsystems.

**Key Interfaces:**
- `configure_limits(limits: List[TelemetryLimit])` - Set red/yellow bounds and rate limits
- `configure_correlations(correlation_groups: Dict)` - Define expected parameter correlations
- `ingest_telemetry(points: List[TelemetryPoint])` - Process batch, detect anomalies
- `check_limits(point: TelemetryPoint)` - Bounds checking against red/yellow thresholds
- `check_rate_of_change(point)` - Rate-of-change validation
- `detect_trend(parameter_name, subsystem)` - Trend analysis with slope prediction
- `check_correlations()` - Cross-parameter correlation validation
- `detect_stuck_value(parameter_name, subsystem)` - Detect constant value stuck conditions
- `generate_health_report()` - Comprehensive spacecraft health assessment

**Required Data Structures:**
- `TelemetryPoint` - Single measurement with timestamp, subsystem, value
- `TelemetryLimit` - Red/yellow bounds, rate limits, nominal values
- `Anomaly` - Detected anomaly with type, severity, description
- `HealthReport` - Periodic health assessment with subsystem breakdown

**Acceptance Criteria:**
- 60+ unit tests covering limit checking, rate-of-change, trends, correlations, stuck values
- Stress tests: handle 10,000 telemetry points/second with <100ms latency
- >=85% line coverage, >=75% branch coverage
- Integration with `services/notifications/channels.py` and `services/audit/event_store.py`

### Task 3: Ground Station Scheduler (Greenfield)

Implement `GroundStationScheduler` service to optimize satellite-to-ground contact windows. Handles multi-satellite, multi-ground-station scheduling with visibility window computation, priority-based preemption, and conflict resolution.

**Key Interfaces:**
- `register_ground_station(station: GroundStation)` - Register ground facility
- `compute_visibility_windows(satellite_id, orbital_elements, start_time, end_time)` - Orbital pass computation
- `submit_contact_request(request: ContactRequest)` - Queue scheduling request
- `schedule_contact(request_id, allow_preemption)` - Allocate contact window
- `batch_schedule(request_ids, optimization_goal)` - Multi-request optimization
- `preempt_contact(contact_id, preempting_request_id)` - High-priority preemption
- `detect_conflicts(start_time, end_time)` - Find overlapping allocations
- `get_station_utilization(station_id, start_time, end_time)` - Utilization metrics
- `optimize_schedule(start_time, end_time)` - Re-optimize window

**Required Data Structures:**
- `GroundLocation` - Geographic position (frozen)
- `GroundStation` - Facility with antennas, operational hours, maintenance windows
- `VisibilityWindow` - Computed satellite pass (AOS/LOS times)
- `ContactRequest` - Scheduling request with priority and duration
- `ScheduledContact` - Allocated contact with status tracking
- `ScheduleConflict` - Detected overlap with resolution strategy

**Acceptance Criteria:**
- 70+ unit tests covering visibility computation, conflict detection, preemption, batch optimization
- Integration tests for full scheduling lifecycle and emergency cascades
- >=85% line coverage, >=75% branch coverage
- Integration with constellation coordinator orbital elements and notifications

## Getting Started

```bash
python tests/run_all.py
```

## Success Criteria

Implementation meets the acceptance criteria and interfaces defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
