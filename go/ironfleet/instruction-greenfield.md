# IronFleet - Greenfield Tasks

## Overview

These 3 greenfield tasks require implementing new modules from scratch following IronFleet's architectural patterns. Each task builds on the fleet management platform's routing, security, and resilience capabilities, adding capabilities for fuel optimization, predictive maintenance, and geofence monitoring.

## Environment

- **Language**: Go
- **Infrastructure**: Internal packages for core logic, service layer for cross-service communication, shared contracts for topology
- **Difficulty**: Apex-Principal (production-grade codebase)

## Tasks

### Task 1: Fuel Consumption Optimizer (Greenfield Implementation)

Implement a fuel consumption optimization service that analyzes route segments, vessel characteristics, and environmental conditions. Expose a `FuelOptimizer` interface (internal/fuel) with methods for consumption estimation, optimal speed calculation, and route comparison. Implement fleet-level `FleetFuelAnalytics` (services/fuel) for aggregated efficiency metrics. Include `FuelAuditLog` for prediction vs actual variance tracking.

**Key Interfaces**:
- `FuelOptimizer`: RegisterRate, EstimateConsumption, ComputeOptimalSpeed, CompareRoutes
- `FleetFuelAnalytics`: ComputeFleetEfficiency, IdentifyWastage, ProjectMonthlyConsumption
- `FuelAuditLog`: Record, VarianceReport, AverageVariance

### Task 2: Maintenance Scheduler (Greenfield Implementation)

Implement a predictive maintenance scheduling system tracking vessel component health, scheduling preventive maintenance windows, and coordinating with dispatch. Expose a `MaintenanceScheduler` interface (internal/maintenance) with methods for component registration, health updates, failure prediction, and optimal window finding. Implement fleet-level `FleetMaintenanceCoordinator` (services/maintenance) for readiness metrics and prioritized queues. Include `MaintenanceHistory` for completed maintenance trend analysis.

**Key Interfaces**:
- `MaintenanceScheduler`: RegisterComponent, UpdateHealth, PredictFailure, ScheduleMaintenance, FindOptimalWindow, DetectConflicts, GetOverdueComponents
- `FleetMaintenanceCoordinator`: ComputeFleetReadiness, PrioritizeMaintenanceQueue, EstimateDowntime, GenerateMaintenanceReport
- `MaintenanceHistory`: Record, AverageDuration, TotalCost, FrequencyByVessel

### Task 3: Geofence Alert Service (Greenfield Implementation)

Implement a geofence monitoring service that tracks vessel positions against defined geographic zones, triggers alerts for boundary violations, and enforces operational restrictions. Expose a `GeofenceEngine` interface (internal/geofence) with methods for zone management, position checking, and violation detection. Implement fleet-level `FleetGeofenceMonitor` (services/geofence) for compliance metrics and high-risk identification. Include `GeofenceTracker` for real-time position updates with point-in-polygon and Haversine distance calculations.

**Key Interfaces**:
- `GeofenceEngine`: RegisterZone, UpdateZone, DeactivateZone, CheckPosition, IsInsideZone, FindNearbyZones, GetActiveViolations, AcknowledgeViolation, ProjectedViolation
- `FleetGeofenceMonitor`: ComputeComplianceRate, GetHighRiskVessels, GenerateHeatmap, EstimateRiskScore, BroadcastAlert
- `GeofenceTracker`: UpdatePosition, GetVesselsInZone, VesselZones, ViolationCount

## Getting Started

```bash
go test -v ./...
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md), including unit test coverage >80%, integration with existing services, and all tests passing.
