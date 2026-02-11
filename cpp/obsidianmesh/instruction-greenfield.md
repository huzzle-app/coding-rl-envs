# ObsidianMesh - Greenfield Implementation Tasks

## Overview

ObsidianMesh supports three greenfield implementation tasks that require building new modules from scratch. Each task must follow existing architectural patterns, integrate seamlessly with the codebase, and include comprehensive test coverage.

## Environment

- **Language**: C++ (C++20)
- **Infrastructure**: Docker-based with CMake build system, 14 source modules, 13 microservices
- **Difficulty**: Apex-Principal
- **Test Framework**: ctest with integration into existing ~12,678 test case suite

## Tasks

### Task 1: Mesh Topology Optimizer (Greenfield)

Implement a topology optimization service that analyzes the mesh network structure and recommends optimal node placement, connection routing, and load distribution to minimize latency and maximize resilience. The service must compute graph metrics (density, bridge nodes, connectivity), perform load balancing analysis, optimize latency through edge evaluation, and cluster nodes by geographic proximity. The system should also analyze resilience through minimum cuts and single points of failure.

**Key Components:**

- **MeshNode struct**: Represents a node in the mesh with location (lat/lng), capacity, current load, and peer connections
- **TopologyEdge struct**: Represents a connection with latency, bandwidth, and reliability metrics
- **OptimizationResult struct**: Contains recommended topology changes and expected improvements
- **ClusterAssignment struct**: Maps nodes to geographic/logical clusters
- **TopologyOptimizer class**: Stateful manager for topology analysis and optimization

**Core Functions:** Mesh density calculation, node degree analysis, bridge node detection, full connectivity checks, load imbalance scoring, load transfer suggestions, average path latency, high-latency edge detection, node clustering, intra-cluster latency, cluster gateway selection, minimum cut analysis, redundancy factor, single point of failure detection.

### Task 2: Node Health Monitor (Greenfield)

Implement a comprehensive health monitoring service that tracks node availability, performance metrics, and health trends. The service should detect degradation, predict failures, and maintain historical health data. It must record point-in-time health snapshots, compute composite health scores from multiple metrics, analyze trends using statistical methods, trigger alerts based on thresholds, and aggregate health data across clusters.

**Key Components:**

- **NodeHealthSnapshot struct**: Point-in-time metrics (CPU, memory, network usage, connections, error rates, response time)
- **HealthTrend struct**: Trend analysis for a specific metric (current value, average, slope, status)
- **HealthAlert struct**: Active alerts with severity, threshold, and trigger information
- **HealthReport struct**: Comprehensive health summary with score, trends, active alerts, and recommendations
- **NodeHealthMonitor class**: Stateful manager tracking history and managing alerts

**Core Functions:** Composite health score calculation, resource pressure metrics, request success rate, availability score, trend slope calculation, trend classification, exponential smoothing, failure prediction, alert triggering logic, severity determination, alert priority, alert cooldown expiration, cluster aggregation, unhealthy node counting, worst performer identification, health variance analysis.

### Task 3: Traffic Shaping Service (Greenfield)

Implement a traffic shaping service that manages bandwidth allocation, enforces rate limits per connection type, implements fair queuing, and provides traffic prioritization based on configurable policies. The service should support multiple traffic classes with priority and bandwidth shares, manage active traffic flows, make shaping decisions with allow/deny and delay information, and track comprehensive traffic statistics.

**Key Components:**

- **TrafficClass struct**: Defines a traffic class with priority, bandwidth share, burst limits, and token rates
- **TrafficFlow struct**: Represents an active traffic flow with source, destination, and statistics
- **ShapingDecision struct**: Result of a transmission request with allow/deny, bytes permitted, and delay
- **BandwidthAllocation struct**: Current allocation status for a traffic class
- **TrafficStats struct**: Aggregate statistics (bytes in/out, dropped, delayed, active flows, delays, utilization)
- **TrafficShaper class**: Stateful manager handling classes, flows, and shaping decisions

**Core Functions:** Effective bandwidth calculation, bytes per interval, bandwidth utilization, remaining quota, weighted fair share, deficit round-robin quantum, Jain fairness index, priority-weighted share, token bucket logic, token refill, leaky bucket rate, burst allowance, port-based classification, protocol classification, priority adjustment, congestion factor, shaping delay, jitter compensation, queue delay estimation, delay variation analysis.

## Getting Started

```bash
cmake -B build && cmake --build build
ctest --test-dir build --output-on-failure
```

## Implementation Requirements

### File Organization

```
obsidianmesh/
  include/obsidianmesh/
    core.hpp              # Add new types and function declarations
  src/
    topology.cpp          # Task 1 implementation
    health_monitor.cpp    # Task 2 implementation
    traffic_shaper.cpp    # Task 3 implementation
  tests/
    test_topology.cpp     # Task 1 tests (minimum 25 cases)
    test_health_monitor.cpp   # Task 2 tests (minimum 30 cases)
    test_traffic_shaper.cpp   # Task 3 tests (minimum 35 cases)
```

### Code Style and Patterns

1. **Namespace**: All code in `namespace obsidianmesh { }`
2. **Thread Safety**: Use `std::shared_mutex` for read-heavy workloads (reference: `RouteTable`)
3. **Lock Guards**: Use `std::lock_guard` or `std::unique_lock`/`std::shared_lock` appropriately
4. **Const Correctness**: Mark methods `const` where applicable
5. **Return Types**: Return empty containers or sentinel values for error cases
6. **Sorting**: Use `std::sort` with lambda comparators for deterministic ordering
7. **C++20 Features**: Leverage where appropriate
8. **Error Handling**: Use edge case handling (empty containers, zero denominators, negative values)

### Integration Points

- **Task 1**: Use `haversine_distance()` for geographic calculations, follow `weighted_route_score()` pattern for multi-factor scoring
- **Task 2**: Use existing `ResponseTimeTracker` patterns for history, follow `CircuitBreaker` for state management
- **Task 3**: Follow `RateLimiter` pattern for token bucket, use `PriorityQueue` for priority ordering

## Success Criteria

All tasks must meet their respective acceptance criteria including:

- **Minimum Test Cases**: Task 1 (25), Task 2 (30), Task 3 (35)
- **Coverage**: All public functions tested with edge cases
- **Thread Safety**: Concurrent access verified where applicable
- **Compilation**: Clean build with no warnings
- **Integration**: Seamless integration with existing codebase
- **Correctness**: Calculations verified against known values

Implementation should pass the full test suite including new test cases.
