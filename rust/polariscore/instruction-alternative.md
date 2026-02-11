# PolarisCore - Alternative Tasks

## Overview
Five engineering challenges spanning feature development, refactoring, performance optimization, API extension, and system migration. Each task builds on the existing PolarisCore logistics platform while testing different software development disciplines.

## Environment
- **Language**: Rust
- **Infrastructure**: Cold-chain logistics control plane with 13 microservices
- **Difficulty**: Hyper-Principal (70-140h expected)

## Tasks

### Task 1: Multi-Zone Fulfillment Window Scheduling (Feature Development)
Extend the allocation system to support fulfillment windows across multiple polar geographic zones, each with independent capacity constraints. High-priority shipments can preempt lower-priority allocations when zone capacity is constrained. Implement "thermal bridging" capacity requirements for shipments transitioning between zones with significant temperature differentials. Allocation reports must include zone-level utilization metrics while maintaining backward compatibility with existing single-zone workflows.

### Task 2: Risk Assessment Pipeline Refactoring (Refactoring)
Decompose the monolithic `risk_score` function into a composable architecture where load risk, incident risk, and thermal risk are evaluated independently. Create a `RiskAssessment` struct that encapsulates score, hold requirement, and compliance tier. Implement a `RiskAssessor` trait for pluggable risk calculation strategies. The refactoring must produce identical risk calculations while enabling new risk factors (geopolitical, weather forecast) to be added without modifying existing code.

### Task 3: Queue Processing Performance Optimization (Performance Optimization)
Optimize queue ordering and statistics calculations to eliminate redundant computations. Precompute priority weights before sorting rather than recalculating during comparisons. Combine severity and wait time summation into a single iteration pass. Implement a `PercentileCalculator` struct that pre-sorts data once for efficient multiple percentile lookups. Achieve at least 2x improvement for queue operations with 10,000 items while maintaining identical function signatures and return values.

### Task 4: Shipment Tracking Event API Extension (API Extension)
Expose shipment lifecycle events (intake, allocation, routing, fulfillment, delivery) through a structured API with full audit trail information. Implement event query functions supporting filters by shipment ID, time range, and event type. Add event aggregation functions for computing transit time, dwell time per hub, and service latency metrics. All API responses must include cryptographic signatures using the existing `simple_signature` mechanism, with field-level redaction based on authorization context.

### Task 5: Replay System Migration to Event Sourcing (Migration)
Migrate from stateless replay budget calculations to a proper event sourcing architecture for audit compliance. Introduce an `Event` trait and `EventStore` abstraction that captures all state-changing operations as immutable events. Implement concrete event types for allocation decisions, routing selections, policy evaluations, and failover triggers. Support point-in-time state reconstruction, event versioning with upcasting, and snapshot optimization for long-running shipment lifecycles.

## Getting Started
```bash
docker compose up -d
cargo test
```

## Success Criteria
Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
