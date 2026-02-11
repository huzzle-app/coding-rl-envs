# OpalCommand - Greenfield Tasks

## Overview

Three greenfield implementation tasks for the OpalCommand maritime command and control platform, building new service modules from scratch. Each task requires implementing complete interfaces following existing architectural patterns and integrating with the service ecosystem.

## Environment

- **Language**: Ruby
- **Infrastructure**: Docker Compose with Redis, PostgreSQL, Kafka; shared contracts service registry; 21 modules with 9,263+ tests
- **Difficulty**: Apex-Principal

## Tasks

### Task 1: Berth Allocation Optimizer (Implementation)

Implement a berth allocation optimization service that assigns vessels to berths based on vessel dimensions, cargo type, berth capabilities, and scheduling constraints. The optimizer must handle priority vessels, hazmat requirements, and equipment availability while minimizing turnaround time.

**Key Interface Components:**
- `Berth` - Struct with capabilities (length_m, depth_m, crane_count, hazmat_certified, equipment)
- `VesselRequest` - Struct with requirements (length_m, draft_m, cargo_type, hazmat, priority, eta, estimated_hours)
- `BerthAssignment` - Struct representing confirmed assignments (vessel_id, berth_id, start_time, end_time, fitness_score)
- `BerthOptimizer` - Module with functions for compatibility checking, fitness computation, batch allocation, conflict detection, utilization metrics
- `BerthScheduler` - Thread-safe class managing assignment lifecycle with submit, cancel, and range queries

**Acceptance Criteria:** Berth compatibility checks validate length, draft, and hazmat requirements; fitness scores range 0.0-1.0; optimal berth selection returns highest fitness match; batch allocation respects priority ordering; conflict detection identifies overlapping time windows; thread-safe concurrent operations; utilization metrics computed correctly.

### Task 2: Cargo Manifest Validator (Implementation)

Implement a cargo manifest validation service that verifies cargo declarations against international maritime regulations, weight distribution limits, and hazmat segregation rules. The validator must detect declaration anomalies, compute cargo stability metrics, and generate compliance reports.

**Key Interface Components:**
- `CargoItem` - Struct for individual cargo (id, description, weight_kg, category, un_number, hazmat_class, container_id, position)
- `CargoManifest` - Struct for complete manifest (vessel_id, voyage_number, items, declared_at)
- `ValidationResult` - Struct for rule check results (rule, status, message, affected_items)
- `CargoValidator` - Module with HAZMAT_SEGREGATION constant; functions for item validation, hazmat segregation checking, weight distribution, duplicate detection, compliance report generation, segregation requirement checks
- `ManifestRegistry` - Thread-safe class with manifest versioning (register, current, version, versions)

**Acceptance Criteria:** Item validation catches missing required fields; hazmat segregation detects incompatible classes in same position; weight distribution computes correct percentages; duplicate detection finds containers declared multiple times; segregation matrix correctly consulted; manifest registry maintains version history; concurrent registration is thread-safe; current returns latest version.

### Task 3: Vessel Tracking Service (Implementation)

Implement a real-time vessel tracking service that processes AIS (Automatic Identification System) position reports, computes vessel trajectories, detects navigation anomalies, and generates proximity alerts. The service must handle high-frequency position updates efficiently and maintain historical track data.

**Key Interface Components:**
- `PositionReport` - Struct for AIS data (mmsi, latitude, longitude, speed_knots, course_deg, heading_deg, timestamp, nav_status)
- `TrackSegment` - Struct for computed tracks (mmsi, positions, total_distance_nm, avg_speed_knots, start_time, end_time)
- `NavigationAnomaly` - Struct for detected anomalies (mmsi, anomaly_type, description, detected_at, details)
- `ProximityAlert` - Struct for collision risks (mmsi_a, mmsi_b, distance_nm, cpa_nm, tcpa_minutes, severity)
- `VesselTracker` - Module with EARTH_RADIUS_NM constant; functions for haversine distance, position validation, track computation, anomaly detection, CPA computation, proximity checking, position interpolation, ETA estimation
- `PositionStore` - Thread-safe class for position history (record, latest, track, active_vessels, all_current_positions, cleanup)

**Acceptance Criteria:** Haversine distance computes correct great-circle distances; position validation catches invalid lat/lon ranges; track computation calculates correct distance and average speed; anomaly detection identifies speed violations and position jumps; CPA computation returns correct closest approach and time values; proximity alerts generated at correct thresholds; position interpolation returns correct intermediate positions; position store maintains correct history limits; record returns detected anomalies; track returns positions within time range; cleanup removes positions older than threshold; thread-safe under concurrent access.

## Getting Started

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). Each service must:
- Define core module in `lib/opalcommand/core/` with all required interfaces
- Provide service wrapper in `services/<name>/service.rb`
- Register in `shared/contracts/contracts.rb` with appropriate port and dependencies
- Include comprehensive unit tests in `tests/unit/` and service tests in `tests/services/`
- Follow existing architectural patterns (module_function for stateless operations, Mutex for thread-safe stateful classes, Struct with keyword_init for value objects)
