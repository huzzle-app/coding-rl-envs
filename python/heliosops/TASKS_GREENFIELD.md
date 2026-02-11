# HeliosOps - Greenfield Implementation Tasks

This document defines new modules to be implemented from scratch for the HeliosOps satellite operations platform. Each task requires creating a new service/module following existing architectural patterns.

---

## Task 1: Constellation Coordination Service

### Overview

Implement a **ConstellationCoordinator** service that manages multi-satellite maneuvers, inter-satellite link scheduling, and formation-keeping for satellite constellations. This service coordinates orbital adjustments across multiple spacecraft to maintain coverage, avoid collisions, and optimize communication windows.

### Module Location

```
heliosops/constellation.py
services/constellation/__init__.py
services/constellation/coordinator.py
```

### Interface Contract

```python
"""
HeliosOps Constellation Coordination Module
============================================

Coordinates multi-satellite operations including formation-keeping,
collision avoidance, and inter-satellite link scheduling for LEO
and MEO constellations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class ManeuverType(Enum):
    """Types of orbital maneuvers."""
    STATION_KEEPING = "station_keeping"
    COLLISION_AVOIDANCE = "collision_avoidance"
    PHASING = "phasing"
    ORBIT_RAISE = "orbit_raise"
    ORBIT_LOWER = "orbit_lower"
    DEORBIT = "deorbit"


class ManeuverStatus(Enum):
    """Lifecycle status of a planned maneuver."""
    PLANNED = "planned"
    APPROVED = "approved"
    UPLOADED = "uploaded"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass(frozen=True)
class OrbitalElements:
    """Keplerian orbital elements for a satellite."""
    semi_major_axis_km: float      # a - semi-major axis in km
    eccentricity: float            # e - orbital eccentricity (0-1)
    inclination_deg: float         # i - inclination in degrees
    raan_deg: float                # Omega - right ascension of ascending node
    arg_periapsis_deg: float       # omega - argument of periapsis
    true_anomaly_deg: float        # nu - true anomaly at epoch
    epoch: datetime                # reference time for elements


@dataclass
class Satellite:
    """A satellite in the constellation."""
    id: str
    name: str
    norad_id: str
    constellation_id: str
    orbital_elements: OrbitalElements
    propellant_kg: float
    power_available_watts: float
    health_status: str = "nominal"
    last_contact: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Maneuver:
    """A planned orbital maneuver."""
    id: str
    satellite_id: str
    maneuver_type: ManeuverType
    delta_v_mps: float             # required delta-v in m/s
    burn_duration_seconds: float
    scheduled_time: datetime
    status: ManeuverStatus = ManeuverStatus.PLANNED
    target_elements: Optional[OrbitalElements] = None
    propellant_required_kg: float = 0.0
    priority: int = 3              # 1=critical, 5=low
    dependencies: List[str] = field(default_factory=list)  # maneuver IDs


@dataclass
class CollisionRisk:
    """A predicted conjunction event between objects."""
    id: str
    primary_satellite_id: str
    secondary_object_id: str       # satellite or debris
    time_of_closest_approach: datetime
    miss_distance_km: float
    probability_of_collision: float
    relative_velocity_mps: float
    requires_maneuver: bool = False


@dataclass
class InterSatelliteLink:
    """A scheduled communication link between satellites."""
    id: str
    source_satellite_id: str
    target_satellite_id: str
    start_time: datetime
    end_time: datetime
    data_rate_mbps: float
    link_margin_db: float


class ConstellationCoordinator:
    """Coordinate multi-satellite operations for a constellation.

    Manages formation-keeping, collision avoidance, and inter-satellite
    link scheduling. Implements constraint propagation for maneuver
    sequencing and resource allocation.
    """

    def __init__(
        self,
        constellation_id: str,
        min_separation_km: float = 50.0,
        collision_threshold: float = 1e-4,
    ) -> None:
        """Initialize the coordinator.

        Parameters
        ----------
        constellation_id : str
            Identifier for the satellite constellation.
        min_separation_km : float
            Minimum safe separation distance between satellites.
        collision_threshold : float
            Probability threshold above which collision avoidance is required.
        """
        ...

    def register_satellite(self, satellite: Satellite) -> None:
        """Register a satellite with the constellation.

        Parameters
        ----------
        satellite : Satellite
            The satellite to register.

        Raises
        ------
        ValueError
            If satellite ID already exists or constellation mismatch.
        """
        ...

    def update_orbital_elements(
        self,
        satellite_id: str,
        elements: OrbitalElements,
    ) -> Satellite:
        """Update a satellite's orbital elements after tracking update.

        Parameters
        ----------
        satellite_id : str
            The satellite to update.
        elements : OrbitalElements
            New orbital elements from tracking.

        Returns
        -------
        Satellite
            The updated satellite record.
        """
        ...

    def plan_maneuver(
        self,
        satellite_id: str,
        maneuver_type: ManeuverType,
        target_elements: Optional[OrbitalElements] = None,
        scheduled_time: Optional[datetime] = None,
        priority: int = 3,
    ) -> Maneuver:
        """Plan a new orbital maneuver.

        Calculates required delta-v, propellant consumption, and
        checks for conflicts with existing maneuvers.

        Parameters
        ----------
        satellite_id : str
            The satellite to maneuver.
        maneuver_type : ManeuverType
            Type of maneuver to perform.
        target_elements : OrbitalElements, optional
            Target orbital elements after maneuver.
        scheduled_time : datetime, optional
            Requested execution time. If None, auto-scheduled.
        priority : int
            Maneuver priority (1=critical, 5=low).

        Returns
        -------
        Maneuver
            The planned maneuver.

        Raises
        ------
        ValueError
            If satellite not found or insufficient propellant.
        """
        ...

    def approve_maneuver(self, maneuver_id: str) -> Maneuver:
        """Approve a planned maneuver for execution.

        Validates all dependencies are satisfied and no conflicts exist.

        Parameters
        ----------
        maneuver_id : str
            The maneuver to approve.

        Returns
        -------
        Maneuver
            The approved maneuver.

        Raises
        ------
        ValueError
            If dependencies not met or resource conflicts.
        """
        ...

    def abort_maneuver(self, maneuver_id: str, reason: str) -> Maneuver:
        """Abort a planned or executing maneuver.

        Parameters
        ----------
        maneuver_id : str
            The maneuver to abort.
        reason : str
            Reason for abortion (logged for audit).

        Returns
        -------
        Maneuver
            The aborted maneuver.
        """
        ...

    def assess_collision_risks(
        self,
        time_horizon_hours: float = 72.0,
    ) -> List[CollisionRisk]:
        """Assess collision risks for all satellites over a time window.

        Uses propagated orbits to detect potential conjunctions.

        Parameters
        ----------
        time_horizon_hours : float
            How far ahead to look for conjunctions (default 72h).

        Returns
        -------
        list of CollisionRisk
            All detected collision risks, sorted by time.
        """
        ...

    def plan_collision_avoidance(
        self,
        risk: CollisionRisk,
        strategy: str = "optimal",
    ) -> Optional[Maneuver]:
        """Plan a collision avoidance maneuver for a risk event.

        Parameters
        ----------
        risk : CollisionRisk
            The collision risk to mitigate.
        strategy : str
            Avoidance strategy: 'optimal' (min fuel), 'early' (max margin),
            or 'radial' (change altitude only).

        Returns
        -------
        Maneuver or None
            The avoidance maneuver, or None if not required.
        """
        ...

    def schedule_inter_satellite_links(
        self,
        satellite_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        min_data_rate_mbps: float = 100.0,
    ) -> List[InterSatelliteLink]:
        """Schedule inter-satellite communication links.

        Computes visibility windows and optimal link scheduling
        for data relay across the constellation.

        Parameters
        ----------
        satellite_ids : list of str
            Satellites to include in link planning.
        start_time : datetime
            Start of scheduling window.
        end_time : datetime
            End of scheduling window.
        min_data_rate_mbps : float
            Minimum acceptable data rate.

        Returns
        -------
        list of InterSatelliteLink
            Scheduled links in chronological order.
        """
        ...

    def get_constellation_health(self) -> Dict[str, Any]:
        """Return health summary for the entire constellation.

        Returns
        -------
        dict
            Contains satellite count, health breakdown, pending maneuvers,
            active risks, and overall status.
        """
        ...

    def propagate_orbit(
        self,
        satellite_id: str,
        to_time: datetime,
    ) -> Tuple[float, float, float]:
        """Propagate satellite position to a future time.

        Uses SGP4/SDP4 propagator for accurate position prediction.

        Parameters
        ----------
        satellite_id : str
            The satellite to propagate.
        to_time : datetime
            Target time for position.

        Returns
        -------
        tuple of (x, y, z)
            ECEF coordinates in kilometers.
        """
        ...
```

### Required Data Structures

1. **OrbitalElements** - Keplerian elements (provided above)
2. **Satellite** - Spacecraft state including propellant and power
3. **Maneuver** - Planned orbital maneuver with dependencies
4. **CollisionRisk** - Conjunction assessment result
5. **InterSatelliteLink** - Scheduled ISL communication window

### Architectural Patterns to Follow

- Use `@dataclass` and `@dataclass(frozen=True)` for immutable domain objects (see `heliosops/models.py`)
- Implement circuit breaker pattern for external propagator calls (see `heliosops/resilience.py`)
- Use priority queue for maneuver scheduling (see `heliosops/dispatch.py:DispatchQueue`)
- Follow the async pattern for database operations (see `services/dispatch/engine.py`)
- Emit structured logs with appropriate levels (see `heliosops/scheduler.py`)

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/constellation_test.py`)
   - Test maneuver planning with valid/invalid inputs
   - Test collision risk assessment with mock orbital data
   - Test ISL scheduling for overlapping windows
   - Test propellant budget validation
   - Minimum 50 test cases

2. **Integration Tests** (`tests/integration/constellation_flow_test.py`)
   - Test full maneuver lifecycle (plan -> approve -> execute -> complete)
   - Test collision avoidance triggered by risk assessment
   - Test constraint propagation across dependent maneuvers

3. **Coverage Requirements**
   - Line coverage: >= 85%
   - Branch coverage: >= 75%

4. **Integration Points**
   - Must integrate with `heliosops/scheduler.py` for maneuver scheduling
   - Must emit events compatible with `services/audit/event_store.py`
   - Must use `heliosops/resilience.py:CircuitBreaker` for external calls

---

## Task 2: Anomaly Detection for Spacecraft Health

### Overview

Implement a **SpacecraftHealthMonitor** service that performs real-time anomaly detection on telemetry streams. The system should detect out-of-range values, trend anomalies, and correlation-based anomalies across multiple subsystems.

### Module Location

```
heliosops/health_monitor.py
services/health/__init__.py
services/health/anomaly_detector.py
```

### Interface Contract

```python
"""
HeliosOps Spacecraft Health Monitor
====================================

Real-time anomaly detection for spacecraft telemetry. Implements
statistical bounds checking, trend detection, and cross-correlation
analysis for early fault detection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class SubsystemType(Enum):
    """Spacecraft subsystem categories."""
    POWER = "power"
    THERMAL = "thermal"
    ATTITUDE = "attitude"
    PROPULSION = "propulsion"
    COMMUNICATIONS = "communications"
    PAYLOAD = "payload"
    COMMAND_DATA = "command_data"
    STRUCTURES = "structures"


class AlertSeverity(Enum):
    """Severity levels for health alerts."""
    INFO = 1
    WARNING = 2
    CAUTION = 3
    CRITICAL = 4
    EMERGENCY = 5


class AnomalyType(Enum):
    """Types of detected anomalies."""
    OUT_OF_RANGE = "out_of_range"
    RATE_OF_CHANGE = "rate_of_change"
    TREND = "trend"
    CORRELATION = "correlation"
    MISSING_DATA = "missing_data"
    STUCK_VALUE = "stuck_value"


@dataclass
class TelemetryPoint:
    """A single telemetry measurement."""
    timestamp: datetime
    spacecraft_id: str
    subsystem: SubsystemType
    parameter_name: str
    value: float
    unit: str
    quality: str = "good"  # good, suspect, bad


@dataclass
class TelemetryLimit:
    """Operational limits for a telemetry parameter."""
    parameter_name: str
    subsystem: SubsystemType
    red_low: Optional[float] = None      # emergency low
    yellow_low: Optional[float] = None   # warning low
    yellow_high: Optional[float] = None  # warning high
    red_high: Optional[float] = None     # emergency high
    rate_limit: Optional[float] = None   # max rate of change per second
    nominal_value: Optional[float] = None


@dataclass
class Anomaly:
    """A detected anomaly in telemetry data."""
    id: str
    spacecraft_id: str
    subsystem: SubsystemType
    parameter_name: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    detected_at: datetime
    value: float
    expected_range: Tuple[Optional[float], Optional[float]]
    description: str
    correlation_params: List[str] = field(default_factory=list)
    acknowledged: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class HealthReport:
    """Periodic health assessment for a spacecraft."""
    spacecraft_id: str
    report_time: datetime
    overall_status: str  # nominal, degraded, critical
    subsystem_status: Dict[SubsystemType, str]
    active_anomalies: List[Anomaly]
    trend_warnings: List[Dict[str, Any]]
    recommendations: List[str]


class SpacecraftHealthMonitor:
    """Monitor spacecraft health through telemetry analysis.

    Implements multi-level anomaly detection:
    1. Limit checking (red/yellow bounds)
    2. Rate-of-change monitoring
    3. Trend analysis (moving averages)
    4. Cross-parameter correlation
    5. Data quality assessment
    """

    def __init__(
        self,
        spacecraft_id: str,
        window_size: int = 100,
        correlation_threshold: float = 0.8,
    ) -> None:
        """Initialize the health monitor.

        Parameters
        ----------
        spacecraft_id : str
            Identifier for the monitored spacecraft.
        window_size : int
            Number of samples for rolling statistics.
        correlation_threshold : float
            Minimum correlation coefficient to flag correlation anomalies.
        """
        ...

    def configure_limits(
        self,
        limits: List[TelemetryLimit],
    ) -> None:
        """Configure operational limits for telemetry parameters.

        Parameters
        ----------
        limits : list of TelemetryLimit
            Limit definitions for each parameter.
        """
        ...

    def configure_correlations(
        self,
        correlation_groups: Dict[str, List[str]],
    ) -> None:
        """Configure expected correlations between parameters.

        Parameters
        ----------
        correlation_groups : dict
            Maps group name to list of parameter names that should correlate.
            Example: {"solar_array": ["power_sa1", "power_sa2", "sun_angle"]}
        """
        ...

    def ingest_telemetry(
        self,
        points: List[TelemetryPoint],
    ) -> List[Anomaly]:
        """Process a batch of telemetry points.

        Runs all anomaly detection algorithms and returns any new anomalies.

        Parameters
        ----------
        points : list of TelemetryPoint
            Telemetry measurements to process.

        Returns
        -------
        list of Anomaly
            Any anomalies detected in this batch.
        """
        ...

    def check_limits(
        self,
        point: TelemetryPoint,
    ) -> Optional[Anomaly]:
        """Check a telemetry point against configured limits.

        Parameters
        ----------
        point : TelemetryPoint
            The measurement to check.

        Returns
        -------
        Anomaly or None
            An anomaly if limits are violated.
        """
        ...

    def check_rate_of_change(
        self,
        point: TelemetryPoint,
    ) -> Optional[Anomaly]:
        """Check if parameter is changing too quickly.

        Parameters
        ----------
        point : TelemetryPoint
            Current measurement.

        Returns
        -------
        Anomaly or None
            An anomaly if rate limit is exceeded.
        """
        ...

    def detect_trend(
        self,
        parameter_name: str,
        subsystem: SubsystemType,
    ) -> Optional[Dict[str, Any]]:
        """Analyze trend for a parameter over the rolling window.

        Parameters
        ----------
        parameter_name : str
            The parameter to analyze.
        subsystem : SubsystemType
            The subsystem containing the parameter.

        Returns
        -------
        dict or None
            Trend info if significant trend detected, including slope,
            projected time to limit violation, and confidence.
        """
        ...

    def check_correlations(self) -> List[Anomaly]:
        """Check all configured correlation groups for anomalies.

        Detects when correlated parameters diverge unexpectedly.

        Returns
        -------
        list of Anomaly
            Any correlation anomalies detected.
        """
        ...

    def detect_stuck_value(
        self,
        parameter_name: str,
        subsystem: SubsystemType,
        min_variation: float = 0.001,
    ) -> Optional[Anomaly]:
        """Detect if a parameter is stuck at a constant value.

        Parameters
        ----------
        parameter_name : str
            The parameter to check.
        subsystem : SubsystemType
            The subsystem containing the parameter.
        min_variation : float
            Minimum expected standard deviation.

        Returns
        -------
        Anomaly or None
            An anomaly if value appears stuck.
        """
        ...

    def acknowledge_anomaly(
        self,
        anomaly_id: str,
        operator_id: str,
        notes: str = "",
    ) -> Anomaly:
        """Acknowledge an anomaly.

        Parameters
        ----------
        anomaly_id : str
            The anomaly to acknowledge.
        operator_id : str
            ID of the acknowledging operator.
        notes : str
            Optional operator notes.

        Returns
        -------
        Anomaly
            The acknowledged anomaly.
        """
        ...

    def resolve_anomaly(
        self,
        anomaly_id: str,
        resolution: str,
    ) -> Anomaly:
        """Mark an anomaly as resolved.

        Parameters
        ----------
        anomaly_id : str
            The anomaly to resolve.
        resolution : str
            Description of how the anomaly was resolved.

        Returns
        -------
        Anomaly
            The resolved anomaly.
        """
        ...

    def generate_health_report(self) -> HealthReport:
        """Generate a comprehensive health report.

        Returns
        -------
        HealthReport
            Current health status with all active anomalies and trends.
        """
        ...

    def get_parameter_statistics(
        self,
        parameter_name: str,
        subsystem: SubsystemType,
    ) -> Dict[str, float]:
        """Get rolling statistics for a parameter.

        Returns
        -------
        dict
            Contains mean, std, min, max, p50, p90, p99 over the window.
        """
        ...

    def export_anomaly_history(
        self,
        start_time: datetime,
        end_time: datetime,
        subsystem: Optional[SubsystemType] = None,
    ) -> List[Anomaly]:
        """Export historical anomalies for analysis.

        Parameters
        ----------
        start_time : datetime
            Start of export window.
        end_time : datetime
            End of export window.
        subsystem : SubsystemType, optional
            Filter to specific subsystem.

        Returns
        -------
        list of Anomaly
            Historical anomalies in the window.
        """
        ...
```

### Required Data Structures

1. **TelemetryPoint** - Individual telemetry measurement
2. **TelemetryLimit** - Operational bounds for parameters
3. **Anomaly** - Detected anomaly with context
4. **HealthReport** - Periodic health assessment

### Architectural Patterns to Follow

- Use rolling window statistics (see `heliosops/statistics.py:percentile`)
- Follow the severity/priority patterns (see `heliosops/models.py:Severity`)
- Implement thread-safe data structures for concurrent ingestion
- Use the event store pattern for anomaly history (see `services/audit/event_store.py`)
- Emit metrics compatible with the observability layer

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/health_monitor_test.py`)
   - Test limit checking for all boundary conditions
   - Test rate-of-change with various sample rates
   - Test trend detection with synthetic data
   - Test correlation detection with known correlated/uncorrelated data
   - Test stuck value detection
   - Minimum 60 test cases

2. **Stress Tests** (`tests/stress/telemetry_ingestion_test.py`)
   - Handle 10,000 telemetry points per second
   - Maintain < 100ms latency for anomaly detection
   - Test memory stability over extended periods

3. **Coverage Requirements**
   - Line coverage: >= 85%
   - Branch coverage: >= 75%

4. **Integration Points**
   - Must emit alerts to `services/notifications/channels.py`
   - Must log events to `services/audit/event_store.py`
   - Must integrate with `heliosops/statistics.py` for percentile calculations

---

## Task 3: Ground Station Scheduler

### Overview

Implement a **GroundStationScheduler** service that optimizes satellite-to-ground contact windows. The scheduler must handle multi-satellite, multi-ground-station scheduling with priority-based preemption and conflict resolution.

### Module Location

```
heliosops/ground_scheduler.py
services/ground/__init__.py
services/ground/scheduler.py
```

### Interface Contract

```python
"""
HeliosOps Ground Station Scheduler
===================================

Optimizes satellite-to-ground station contact scheduling. Handles
visibility windows, antenna constraints, priority-based allocation,
and conflict resolution for shared ground resources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class ContactPriority(Enum):
    """Priority levels for ground contacts."""
    EMERGENCY = 1       # life/safety, collision avoidance uplink
    CRITICAL = 2        # spacecraft safing commands
    HIGH = 3            # time-sensitive operations
    NORMAL = 4          # routine TT&C
    LOW = 5             # non-time-critical data download
    FILL = 6            # opportunistic, can be preempted


class ContactStatus(Enum):
    """Lifecycle status of a scheduled contact."""
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    CANCELLED = "cancelled"
    PREEMPTED = "preempted"


class AntennaType(Enum):
    """Ground station antenna types."""
    S_BAND = "s_band"
    X_BAND = "x_band"
    KA_BAND = "ka_band"
    OPTICAL = "optical"
    MULTI_BAND = "multi_band"


@dataclass(frozen=True)
class GroundLocation:
    """Geographic location of a ground station."""
    latitude: float
    longitude: float
    altitude_m: float
    name: str


@dataclass
class GroundStation:
    """A ground station facility."""
    id: str
    name: str
    location: GroundLocation
    antenna_types: List[AntennaType]
    min_elevation_deg: float = 5.0
    max_satellites_concurrent: int = 1
    operational_hours: Tuple[str, str] = ("00:00", "24:00")  # UTC
    maintenance_windows: List[Tuple[datetime, datetime]] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)  # uplink, downlink, ranging
    data_rate_mbps: float = 100.0


@dataclass
class VisibilityWindow:
    """A visibility window between satellite and ground station."""
    satellite_id: str
    ground_station_id: str
    aos_time: datetime          # acquisition of signal
    los_time: datetime          # loss of signal
    max_elevation_deg: float
    max_elevation_time: datetime
    azimuth_range: Tuple[float, float]  # start, end azimuth


@dataclass
class ContactRequest:
    """A request for ground station contact."""
    id: str
    satellite_id: str
    priority: ContactPriority
    min_duration_seconds: int
    preferred_duration_seconds: int
    earliest_start: datetime
    latest_end: datetime
    required_capabilities: List[str]
    antenna_types: List[AntennaType]
    data_volume_mb: float = 0.0
    notes: str = ""


@dataclass
class ScheduledContact:
    """A scheduled ground contact."""
    id: str
    request_id: str
    satellite_id: str
    ground_station_id: str
    start_time: datetime
    end_time: datetime
    priority: ContactPriority
    status: ContactStatus = ContactStatus.SCHEDULED
    visibility_window_id: str = ""
    preempted_by: Optional[str] = None
    data_transferred_mb: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleConflict:
    """A detected scheduling conflict."""
    id: str
    contact_a_id: str
    contact_b_id: str
    ground_station_id: str
    overlap_start: datetime
    overlap_end: datetime
    resolution: Optional[str] = None  # preempt_a, preempt_b, reschedule, manual


class GroundStationScheduler:
    """Schedule satellite ground contacts optimally.

    Implements constraint-based scheduling with visibility windows,
    priority-based preemption, and resource conflict resolution.
    """

    def __init__(
        self,
        scheduling_horizon_hours: float = 168.0,  # 1 week
        min_gap_between_contacts_seconds: int = 300,
    ) -> None:
        """Initialize the scheduler.

        Parameters
        ----------
        scheduling_horizon_hours : float
            How far ahead to generate schedules.
        min_gap_between_contacts_seconds : int
            Minimum gap between contacts at same station.
        """
        ...

    def register_ground_station(
        self,
        station: GroundStation,
    ) -> None:
        """Register a ground station with the scheduler.

        Parameters
        ----------
        station : GroundStation
            The ground station to register.

        Raises
        ------
        ValueError
            If station ID already exists.
        """
        ...

    def update_maintenance_window(
        self,
        station_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> GroundStation:
        """Add or update a maintenance window for a station.

        Automatically reschedules affected contacts.

        Parameters
        ----------
        station_id : str
            The ground station.
        start_time : datetime
            Maintenance start.
        end_time : datetime
            Maintenance end.

        Returns
        -------
        GroundStation
            The updated station record.
        """
        ...

    def compute_visibility_windows(
        self,
        satellite_id: str,
        orbital_elements: Any,  # OrbitalElements from constellation module
        start_time: datetime,
        end_time: datetime,
        station_ids: Optional[List[str]] = None,
    ) -> List[VisibilityWindow]:
        """Compute visibility windows for a satellite.

        Uses orbital propagation to find all passes over ground stations.

        Parameters
        ----------
        satellite_id : str
            The satellite.
        orbital_elements : OrbitalElements
            Current orbital elements.
        start_time : datetime
            Start of computation window.
        end_time : datetime
            End of computation window.
        station_ids : list of str, optional
            Limit to specific stations.

        Returns
        -------
        list of VisibilityWindow
            All visibility windows, sorted by AOS time.
        """
        ...

    def submit_contact_request(
        self,
        request: ContactRequest,
    ) -> ContactRequest:
        """Submit a contact request for scheduling.

        Parameters
        ----------
        request : ContactRequest
            The contact request.

        Returns
        -------
        ContactRequest
            The submitted request with ID assigned.
        """
        ...

    def schedule_contact(
        self,
        request_id: str,
        allow_preemption: bool = True,
    ) -> Tuple[Optional[ScheduledContact], List[ScheduleConflict]]:
        """Attempt to schedule a contact request.

        Parameters
        ----------
        request_id : str
            The request to schedule.
        allow_preemption : bool
            Whether to preempt lower-priority contacts if needed.

        Returns
        -------
        tuple of (ScheduledContact or None, list of ScheduleConflict)
            The scheduled contact if successful, plus any conflicts.
        """
        ...

    def batch_schedule(
        self,
        request_ids: List[str],
        optimization_goal: str = "maximize_coverage",
    ) -> Dict[str, Any]:
        """Schedule multiple requests optimally.

        Uses constraint satisfaction to find optimal allocation.

        Parameters
        ----------
        request_ids : list of str
            Requests to schedule.
        optimization_goal : str
            'maximize_coverage' - maximize total contact time
            'minimize_gaps' - minimize time between contacts per satellite
            'priority_first' - strictly schedule by priority order

        Returns
        -------
        dict
            Contains scheduled, failed, and conflicts lists.
        """
        ...

    def preempt_contact(
        self,
        contact_id: str,
        preempting_request_id: str,
        reason: str,
    ) -> Tuple[ScheduledContact, ScheduledContact]:
        """Preempt an existing contact for a higher-priority request.

        Parameters
        ----------
        contact_id : str
            The contact to preempt.
        preempting_request_id : str
            The higher-priority request.
        reason : str
            Reason for preemption.

        Returns
        -------
        tuple of (preempted_contact, new_contact)
            Both contact records.
        """
        ...

    def cancel_contact(
        self,
        contact_id: str,
        reason: str,
    ) -> ScheduledContact:
        """Cancel a scheduled contact.

        Parameters
        ----------
        contact_id : str
            The contact to cancel.
        reason : str
            Cancellation reason.

        Returns
        -------
        ScheduledContact
            The cancelled contact.
        """
        ...

    def get_schedule(
        self,
        start_time: datetime,
        end_time: datetime,
        satellite_id: Optional[str] = None,
        station_id: Optional[str] = None,
    ) -> List[ScheduledContact]:
        """Retrieve the schedule for a time window.

        Parameters
        ----------
        start_time : datetime
            Window start.
        end_time : datetime
            Window end.
        satellite_id : str, optional
            Filter to specific satellite.
        station_id : str, optional
            Filter to specific station.

        Returns
        -------
        list of ScheduledContact
            Scheduled contacts in chronological order.
        """
        ...

    def get_station_utilization(
        self,
        station_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Calculate utilization metrics for a ground station.

        Returns
        -------
        dict
            Contains total_time, scheduled_time, utilization_pct,
            contacts_count, and breakdown by satellite.
        """
        ...

    def detect_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[ScheduleConflict]:
        """Detect all scheduling conflicts in a time window.

        Returns
        -------
        list of ScheduleConflict
            All detected conflicts.
        """
        ...

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
    ) -> ScheduleConflict:
        """Resolve a scheduling conflict.

        Parameters
        ----------
        conflict_id : str
            The conflict to resolve.
        resolution : str
            Resolution strategy: 'preempt_a', 'preempt_b', 'reschedule_a',
            'reschedule_b', or 'manual'.

        Returns
        -------
        ScheduleConflict
            The resolved conflict.
        """
        ...

    def optimize_schedule(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Re-optimize the schedule for a time window.

        Attempts to improve coverage by rearranging non-fixed contacts.

        Returns
        -------
        dict
            Optimization results including changes made and metrics.
        """
        ...
```

### Required Data Structures

1. **GroundLocation** - Geographic position (frozen dataclass)
2. **GroundStation** - Station configuration with capabilities
3. **VisibilityWindow** - Computed visibility pass
4. **ContactRequest** - Scheduling request
5. **ScheduledContact** - Allocated contact
6. **ScheduleConflict** - Detected overlap

### Architectural Patterns to Follow

- Use frozen dataclasses for immutable value objects (see `heliosops/models.py:Location`)
- Implement priority queue for request scheduling (see `heliosops/dispatch.py`)
- Follow the SLA/deadline tracking pattern (see `heliosops/scheduler.py`)
- Use the haversine distance calculation (see `heliosops/geo.py`)
- Implement async database operations (see `services/dispatch/engine.py`)

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/ground_scheduler_test.py`)
   - Test visibility window computation
   - Test conflict detection with overlapping windows
   - Test priority-based preemption
   - Test maintenance window handling
   - Test batch scheduling optimization
   - Minimum 70 test cases

2. **Integration Tests** (`tests/integration/ground_schedule_flow_test.py`)
   - Test full scheduling lifecycle
   - Test multi-satellite, multi-station scenarios
   - Test emergency preemption cascades

3. **Coverage Requirements**
   - Line coverage: >= 85%
   - Branch coverage: >= 75%

4. **Integration Points**
   - Must integrate with Task 1's `ConstellationCoordinator` for orbital elements
   - Must emit scheduling events to `services/audit/event_store.py`
   - Must send notifications via `services/notifications/channels.py`

---

## General Implementation Guidelines

### Code Style

- Follow PEP 8 and use type hints consistently
- Use Google-style docstrings (see existing modules)
- Prefer composition over inheritance
- Keep functions focused and under 50 lines

### Error Handling

- Use specific exception types (avoid bare `except:`)
- Preserve exception chains with `raise X from Y`
- Log errors with structured context

### Testing

- Use `unittest` framework (see `tests/unit/*.py`)
- Mock external dependencies
- Test edge cases and error conditions
- Include property-based tests for complex algorithms

### Documentation

- Include module-level docstrings
- Document all public methods
- Include usage examples in docstrings

### Performance

- Use appropriate data structures (dict for O(1) lookup)
- Avoid N+1 patterns in queries
- Consider caching for computed results
- Profile before optimizing
