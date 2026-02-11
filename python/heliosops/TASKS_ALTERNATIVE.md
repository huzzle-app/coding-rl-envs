# HeliosOps Alternative Tasks

This document describes alternative development tasks for the HeliosOps satellite operations platform. Each task simulates real-world engineering work that might be assigned to a senior developer working on the mission control system.

---

## Task 1: Orbital Conjunction Alert System (Feature Development)

### Description

Mission control has identified a critical gap in the current dispatch system: there is no automated mechanism to detect and alert operators when two tracked satellites are approaching a potential conjunction (close approach) event. Ground stations need advance warning to evaluate collision risk and potentially execute avoidance maneuvers.

The conjunction alert system should integrate with the existing geospatial and routing modules to calculate predicted satellite trajectories, identify close approaches within configurable distance thresholds, and generate prioritized alerts based on collision probability. The system must handle the high-throughput nature of satellite tracking data, where thousands of objects are monitored simultaneously, and conjunction events can occur rapidly during solar storm periods when atmospheric drag causes orbital decay.

Operators expect alerts to include time-to-conjunction, miss distance estimates, maneuver window recommendations, and links to the relevant satellite telemetry feeds. The alert prioritization should follow the existing severity model (1-5 scale) with appropriate SLA windows for operator response.

### Acceptance Criteria

- Conjunction detection algorithm accepts two orbital elements sets and returns predicted close approach events
- Distance threshold is configurable per satellite pair based on operational envelope size
- Alerts integrate with the existing incident priority queue and follow severity-based SLA windows
- Time-to-conjunction calculations account for orbital propagation uncertainty
- System handles batch processing of 10,000+ tracked objects without blocking the event loop
- Conjunction events are deduplicated to prevent alert fatigue from repeated detections
- Maneuver window recommendations include fuel cost estimates based on delta-v requirements
- All conjunction predictions are logged for post-mission analysis and model validation

### Test Command

```bash
python tests/run_all.py
```

---

## Task 2: Ground Station Contact Window Consolidation (Refactoring)

### Description

The current routing and scheduling modules evolved independently, resulting in significant code duplication around contact window calculations. Ground station visibility computations are scattered across multiple files: the geo module calculates line-of-sight geometry, the scheduler module handles pass prediction, and the routing module determines optimal downlink sequences. This fragmentation has led to subtle inconsistencies in how elevation masks, atmospheric refraction, and antenna slew times are modeled.

Operations teams have reported discrepancies between predicted and actual contact windows, particularly for polar-orbiting satellites where ground station coverage overlaps are complex. A unified contact window service should consolidate these calculations, eliminate redundant geometry computations, and provide a single source of truth for pass scheduling across all modules.

The refactoring must preserve backward compatibility with existing API contracts while enabling future enhancements such as inter-satellite link routing and multi-ground-station handoffs.

### Acceptance Criteria

- Contact window calculations are consolidated into a single module with clear interfaces
- Duplicate elevation mask computations are removed from geo, scheduler, and routing modules
- Atmospheric refraction corrections are applied consistently across all contact predictions
- Antenna slew time constraints are factored into minimum contact duration calculations
- Existing unit tests continue to pass without modification to test assertions
- API backward compatibility is maintained for all public functions
- Contact window predictions match within 0.1 second tolerance of original implementations
- Documentation comments explain the geometric models used for visibility calculations

### Test Command

```bash
python tests/run_all.py
```

---

## Task 3: Telemetry Downlink Throughput Optimization (Performance Optimization)

### Description

Satellite operators have observed that telemetry processing during high-activity periods causes significant latency in the dispatch queue. When multiple satellites simultaneously enter ground station coverage and begin downlinking buffered telemetry, the system struggles to maintain real-time processing guarantees. Profiling indicates that the bottleneck is in the event replay and deduplication pipeline, which was designed for moderate event rates but is now receiving burst traffic of 50,000+ telemetry frames per second.

The resilience module's event replay functionality is particularly problematic: it rebuilds projections from the full event stream on every query, and the deduplication algorithm uses a naive O(n) scan that scales poorly with event volume. Additionally, the circuit breaker is opening prematurely during these bursts because it interprets processing backpressure as service failures.

Optimization efforts should focus on reducing the computational complexity of hot paths, implementing incremental projection updates, and tuning the circuit breaker parameters for burst-tolerant operation without compromising fault detection for genuine outages.

### Acceptance Criteria

- Event replay deduplication achieves O(1) amortized lookup time using appropriate data structures
- Projection rebuilds are incremental rather than full-stream replays for append-only updates
- Telemetry processing sustains 50,000 events/second throughput with p99 latency under 100ms
- Circuit breaker distinguishes between processing backpressure and genuine service failures
- Memory usage remains bounded during sustained high-throughput periods
- Batch processing of telemetry frames uses vectorized operations where applicable
- Cache invalidation is precise to avoid unnecessary full rebuilds
- Performance improvements are validated by stress test suite without regressions

### Test Command

```bash
python tests/run_all.py
```

---

## Task 4: Spacecraft Command Authorization API (API Extension)

### Description

The current security module handles operator authentication and role-based access control, but spacecraft commanding requires an additional authorization layer. Before any command is uplinked to a satellite, it must pass through a command authorization workflow that verifies operator credentials, validates command syntax against the spacecraft database, checks for conflicting queued commands, and obtains supervisory approval for critical operations.

The authorization API should extend the existing RBAC framework with command-specific permissions that account for spacecraft mode (nominal, safe-mode, contingency), command criticality level, and organizational policies around dual-control requirements. Critical commands such as orbit maneuvers, software uploads, and safe-mode exits require approval from two independent operators with appropriate authority.

The API must support both synchronous authorization for interactive commanding sessions and asynchronous workflows where commands are queued for later execution during the next ground contact. All authorization decisions must be logged in the audit trail with sufficient detail for post-mission review.

### Acceptance Criteria

- Command authorization endpoint validates operator credentials and role permissions
- Command syntax validation checks parameters against spacecraft command dictionary
- Conflict detection identifies queued commands that contradict the new request
- Dual-control workflow requires two independent approvals for critical command categories
- Spacecraft mode restrictions prevent unauthorized commands during safe-mode operations
- Asynchronous command queuing integrates with the existing scheduling module
- Authorization decisions are logged with operator identity, timestamp, and justification
- API responses include estimated uplink window for queued commands

### Test Command

```bash
python tests/run_all.py
```

---

## Task 5: Legacy TLE to Ephemeris Format Migration (Migration)

### Description

The HeliosOps platform historically used Two-Line Element (TLE) sets for orbital state representation, which were adequate for catalog maintenance but lack the precision required for high-accuracy conjunction assessment and maneuver planning. The organization is transitioning to ephemeris-based state vectors with covariance data, which provide time-tagged position/velocity states and uncertainty information.

The migration involves updating all orbital state storage, the propagation algorithms in the geo module, the contact window predictions in the scheduler, and the proximity calculations used by dispatch. TLE-based systems assume SGP4/SDP4 propagation models, while ephemeris data uses numerical integration with higher-fidelity force models. The transition must be gradual, supporting dual-format operation during the migration period when some satellites still provide only TLE updates.

Data validation is critical: the system must detect and reject corrupted ephemeris data, handle gaps in coverage gracefully, and provide operators with confidence indicators for predictions made with stale or low-quality orbital data.

### Acceptance Criteria

- Ephemeris data model supports time-tagged state vectors with position, velocity, and covariance
- Orbital propagation switches from SGP4/SDP4 to numerical integration for ephemeris-based objects
- TLE and ephemeris formats coexist with automatic format detection on ingestion
- Contact window predictions use the appropriate propagation model based on data source
- Stale data detection flags satellites whose last update exceeds configurable age thresholds
- Covariance data is incorporated into conjunction probability calculations
- Migration utilities convert historical TLE archives to approximate ephemeris format
- Data quality indicators are exposed through the existing status and metrics endpoints

### Test Command

```bash
python tests/run_all.py
```
