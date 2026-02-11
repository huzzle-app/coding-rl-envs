# ObsidianMesh - Greenfield Implementation Tasks

These tasks require implementing new modules from scratch for the ObsidianMesh distributed mesh networking platform. Each task must follow existing architectural patterns, integrate with the codebase, and include comprehensive tests.

**Test Command:**
```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 1: Mesh Topology Optimizer

### Overview

Implement a topology optimization service that analyzes the mesh network structure and recommends optimal node placement, connection routing, and load distribution to minimize latency and maximize resilience.

### Interface Contract

Add to `include/obsidianmesh/core.hpp`:

```cpp
// ---------------------------------------------------------------------------
// Topology types
// ---------------------------------------------------------------------------

struct MeshNode {
  std::string node_id;
  double lat;
  double lng;
  int capacity;
  int current_load;
  std::vector<std::string> connected_peers;
};

struct TopologyEdge {
  std::string from_node;
  std::string to_node;
  int latency_ms;
  double bandwidth_mbps;
  double reliability;
};

struct OptimizationResult {
  std::vector<std::string> nodes_to_add;
  std::vector<std::string> nodes_to_remove;
  std::vector<std::pair<std::string, std::string>> connections_to_add;
  std::vector<std::pair<std::string, std::string>> connections_to_remove;
  double expected_latency_reduction;
  double expected_reliability_gain;
};

struct ClusterAssignment {
  std::string node_id;
  int cluster_id;
  double distance_to_centroid;
};

// ---------------------------------------------------------------------------
// Topology Optimizer functions
// ---------------------------------------------------------------------------

// Core topology analysis
double mesh_density(const std::vector<MeshNode>& nodes, const std::vector<TopologyEdge>& edges);
int node_degree(const std::string& node_id, const std::vector<TopologyEdge>& edges);
std::vector<std::string> find_bridge_nodes(const std::vector<MeshNode>& nodes, const std::vector<TopologyEdge>& edges);
bool is_fully_connected(const std::vector<MeshNode>& nodes, const std::vector<TopologyEdge>& edges);

// Load balancing
double load_imbalance_score(const std::vector<MeshNode>& nodes);
std::vector<std::pair<std::string, std::string>> suggest_load_transfers(
    const std::vector<MeshNode>& nodes, double threshold);
int optimal_capacity(int total_load, int node_count, double headroom_factor);

// Latency optimization
double average_path_latency(const std::vector<TopologyEdge>& edges);
std::vector<TopologyEdge> find_high_latency_edges(const std::vector<TopologyEdge>& edges, int threshold_ms);
double weighted_latency_score(int latency_ms, double bandwidth_mbps, double reliability);

// Clustering
std::vector<ClusterAssignment> cluster_nodes_by_location(
    const std::vector<MeshNode>& nodes, int cluster_count);
double intra_cluster_latency(const std::vector<ClusterAssignment>& assignments,
    const std::vector<TopologyEdge>& edges, int cluster_id);
std::string find_cluster_gateway(const std::vector<ClusterAssignment>& assignments,
    const std::vector<MeshNode>& nodes, int cluster_id);

// Resilience analysis
int minimum_cut_size(const std::vector<MeshNode>& nodes, const std::vector<TopologyEdge>& edges);
double redundancy_factor(const std::vector<MeshNode>& nodes, const std::vector<TopologyEdge>& edges);
std::vector<std::string> single_points_of_failure(const std::vector<MeshNode>& nodes,
    const std::vector<TopologyEdge>& edges);

// ---------------------------------------------------------------------------
// TopologyOptimizer class
// ---------------------------------------------------------------------------

class TopologyOptimizer {
public:
  TopologyOptimizer();

  void add_node(const MeshNode& node);
  void remove_node(const std::string& node_id);
  void add_edge(const TopologyEdge& edge);
  void remove_edge(const std::string& from, const std::string& to);

  std::vector<MeshNode> get_nodes();
  std::vector<TopologyEdge> get_edges();

  OptimizationResult optimize(double latency_weight, double reliability_weight, double cost_weight);
  double current_health_score();
  std::vector<std::string> get_recommendations();

  void reset();

private:
  mutable std::shared_mutex mu_;
  std::map<std::string, MeshNode> nodes_;
  std::vector<TopologyEdge> edges_;
};
```

### Implementation File

Create `src/topology.cpp` implementing all functions and the `TopologyOptimizer` class.

### Required Classes/Structs

| Type | Purpose |
|------|---------|
| `MeshNode` | Represents a node in the mesh with location, capacity, and peer connections |
| `TopologyEdge` | Represents a connection between nodes with latency/bandwidth/reliability metrics |
| `OptimizationResult` | Contains recommended topology changes and expected improvements |
| `ClusterAssignment` | Maps nodes to geographic/logical clusters |
| `TopologyOptimizer` | Stateful class managing topology and computing optimizations |

### Architectural Patterns to Follow

1. **Namespace**: All code in `namespace obsidianmesh { }`
2. **Thread Safety**: Use `std::shared_mutex` for read-heavy workloads (see `RouteTable`)
3. **Lock Guards**: Use `std::lock_guard` or `std::unique_lock`/`std::shared_lock` appropriately
4. **Const Correctness**: Mark methods `const` where applicable
5. **Return Types**: Return empty containers or sentinel values for error cases (see `choose_route`)
6. **Sorting**: Use `std::sort` with lambda comparators for deterministic ordering

### Acceptance Criteria

1. **Unit Tests**: Minimum 25 test cases in `tests/test_topology.cpp`:
   - Test empty topology handling
   - Test single node/edge cases
   - Test load balancing calculations
   - Test clustering with various node distributions
   - Test bridge node detection
   - Test fully connected graph detection
   - Test optimization result generation
   - Test thread safety with concurrent access

2. **Coverage Requirements**:
   - All public functions must have at least 2 test cases
   - Edge cases (empty input, single element, max values) tested
   - Error conditions tested (invalid node IDs, missing edges)

3. **Integration Points**:
   - Use `haversine_distance()` from routing for geographic calculations
   - Use `weighted_route_score()` pattern for multi-factor scoring
   - Compatible with `Route` and `Waypoint` types where applicable

---

## Task 2: Node Health Monitor

### Overview

Implement a comprehensive health monitoring service that tracks node availability, performance metrics, and health trends. The service should detect degradation, predict failures, and maintain historical health data.

### Interface Contract

Add to `include/obsidianmesh/core.hpp`:

```cpp
// ---------------------------------------------------------------------------
// Health Monitor types
// ---------------------------------------------------------------------------

struct NodeHealthSnapshot {
  std::string node_id;
  long long timestamp_ms;
  double cpu_usage;        // 0.0 - 1.0
  double memory_usage;     // 0.0 - 1.0
  double network_usage;    // 0.0 - 1.0
  int active_connections;
  int failed_requests;
  int total_requests;
  double response_time_ms;
};

struct HealthTrend {
  std::string node_id;
  std::string metric_name;
  double current_value;
  double average_value;
  double trend_slope;      // positive = degrading, negative = improving
  std::string status;      // "stable", "improving", "degrading", "critical"
};

struct HealthAlert {
  std::string node_id;
  std::string alert_type;  // "cpu", "memory", "network", "latency", "errors"
  std::string severity;    // "warning", "critical"
  double threshold;
  double actual_value;
  long long triggered_at;
};

struct HealthReport {
  std::string node_id;
  double overall_score;    // 0.0 - 100.0
  std::vector<HealthTrend> trends;
  std::vector<HealthAlert> active_alerts;
  std::string recommendation;
};

// ---------------------------------------------------------------------------
// Health Monitor functions
// ---------------------------------------------------------------------------

// Metric calculations
double composite_health_score(double cpu, double memory, double network, double error_rate);
double resource_pressure(double cpu, double memory, double network);
double request_success_rate(int failed, int total);
double availability_score(int healthy_checks, int total_checks);

// Trend analysis
double calculate_trend_slope(const std::vector<double>& values);
std::string classify_trend(double slope, double threshold);
double exponential_smoothing(const std::vector<double>& values, double alpha);
double predict_next_value(const std::vector<double>& history, int steps_ahead);

// Alert logic
bool should_trigger_alert(double value, double warning_threshold, double critical_threshold);
std::string determine_severity(double value, double warning_threshold, double critical_threshold);
int alert_priority(const std::string& severity, const std::string& alert_type);
bool alert_cooldown_expired(long long last_triggered, long long now_ms, long long cooldown_ms);

// Aggregation
double cluster_health_average(const std::vector<HealthReport>& reports);
int count_unhealthy_nodes(const std::vector<HealthReport>& reports, double threshold);
std::string worst_performing_node(const std::vector<HealthReport>& reports);
double health_variance(const std::vector<HealthReport>& reports);

// ---------------------------------------------------------------------------
// NodeHealthMonitor class
// ---------------------------------------------------------------------------

class NodeHealthMonitor {
public:
  explicit NodeHealthMonitor(int history_size = 100);

  void record_snapshot(const NodeHealthSnapshot& snapshot);
  HealthReport get_report(const std::string& node_id);
  std::vector<HealthReport> get_all_reports();

  std::vector<HealthAlert> get_active_alerts();
  void acknowledge_alert(const std::string& node_id, const std::string& alert_type);
  void clear_alerts(const std::string& node_id);

  void set_thresholds(const std::string& metric, double warning, double critical);

  std::vector<std::string> get_monitored_nodes();
  int snapshot_count(const std::string& node_id);

  void reset();

private:
  std::mutex mu_;
  int history_size_;
  std::map<std::string, std::vector<NodeHealthSnapshot>> history_;
  std::map<std::string, std::vector<HealthAlert>> alerts_;
  std::map<std::string, std::pair<double, double>> thresholds_;  // metric -> (warning, critical)
};
```

### Implementation File

Create `src/health_monitor.cpp` implementing all functions and the `NodeHealthMonitor` class.

### Required Classes/Structs

| Type | Purpose |
|------|---------|
| `NodeHealthSnapshot` | Point-in-time health metrics for a single node |
| `HealthTrend` | Trend analysis for a specific metric over time |
| `HealthAlert` | Active alert with severity and trigger information |
| `HealthReport` | Comprehensive health summary for a node |
| `NodeHealthMonitor` | Stateful class tracking health history and managing alerts |

### Architectural Patterns to Follow

1. **History Management**: Use sliding window pattern (see `ResponseTimeTracker`)
2. **Threshold Handling**: Use configurable thresholds (see `CircuitBreaker`)
3. **Alert State**: Track triggered/acknowledged state similar to circuit breaker states
4. **Metric Aggregation**: Follow patterns from `statistics.cpp` for calculations
5. **Time Handling**: Use `long long` for millisecond timestamps

### Acceptance Criteria

1. **Unit Tests**: Minimum 30 test cases in `tests/test_health_monitor.cpp`:
   - Test snapshot recording and retrieval
   - Test history sliding window behavior
   - Test trend calculation accuracy
   - Test alert triggering and severity
   - Test alert cooldown logic
   - Test cluster aggregation
   - Test threshold configuration
   - Test empty/single data point handling

2. **Coverage Requirements**:
   - All metric calculation functions tested with known values
   - Trend analysis tested with increasing, decreasing, and stable data
   - Alert logic tested at boundary conditions
   - Thread safety verified with concurrent snapshot recording

3. **Integration Points**:
   - Use `mean()`, `variance()`, `stddev()` from statistics
   - Use `exponential_moving_average()` pattern for smoothing
   - Compatible with `MetricSample` and `MetricsCollector` patterns
   - Alert severity compatible with existing severity constants

---

## Task 3: Traffic Shaping Service

### Overview

Implement a traffic shaping service that manages bandwidth allocation, enforces rate limits per connection type, implements fair queuing, and provides traffic prioritization based on configurable policies.

### Interface Contract

Add to `include/obsidianmesh/core.hpp`:

```cpp
// ---------------------------------------------------------------------------
// Traffic Shaping types
// ---------------------------------------------------------------------------

struct TrafficClass {
  std::string class_id;
  std::string name;
  int priority;           // 1 (highest) to 10 (lowest)
  double bandwidth_share; // 0.0 - 1.0, sum across classes should be 1.0
  int max_burst_bytes;
  int tokens_per_second;
};

struct TrafficFlow {
  std::string flow_id;
  std::string class_id;
  std::string source_node;
  std::string dest_node;
  int bytes_queued;
  int bytes_sent;
  long long started_at;
  long long last_activity;
};

struct ShapingDecision {
  std::string flow_id;
  bool allowed;
  int bytes_permitted;
  int delay_ms;
  std::string reason;
};

struct BandwidthAllocation {
  std::string class_id;
  double allocated_share;
  double used_share;
  int queued_bytes;
  int active_flows;
};

struct TrafficStats {
  long long total_bytes_in;
  long long total_bytes_out;
  long long bytes_dropped;
  long long bytes_delayed;
  int active_flows;
  double average_delay_ms;
  double utilization;
};

// ---------------------------------------------------------------------------
// Traffic Shaping functions
// ---------------------------------------------------------------------------

// Bandwidth calculations
double effective_bandwidth(double total_bandwidth, double utilization);
int bytes_per_interval(int tokens_per_second, int interval_ms);
double bandwidth_utilization(long long bytes_sent, long long capacity_bytes, long long interval_ms);
int remaining_quota(int allocated, int used);

// Fair queuing
double weighted_fair_share(double total_bandwidth, double weight, double total_weight);
int deficit_round_robin_quantum(int max_packet_size, int num_classes);
double jain_fairness_index(const std::vector<double>& throughputs);
int priority_weighted_share(int base_share, int priority, int max_priority);

// Rate limiting
bool token_bucket_allow(int tokens_available, int tokens_required, int max_tokens);
int tokens_to_add(long long elapsed_ms, int tokens_per_second, int max_tokens, int current_tokens);
double leaky_bucket_rate(int bucket_size, int drain_rate, int current_level);
int burst_allowance(int max_burst, int current_tokens, int base_rate);

// Traffic classification
int classify_by_port(int port);
std::string classify_by_protocol(const std::string& protocol);
int effective_priority(int base_priority, double congestion_level);
double congestion_factor(int queued_bytes, int queue_capacity);

// Delay calculations
int shaping_delay_ms(int bytes_to_send, int available_bandwidth_bps);
int jitter_compensation(int base_delay, double jitter_factor);
int queue_delay_estimate(int queue_depth, int service_rate);
double delay_variation(const std::vector<int>& delays);

// ---------------------------------------------------------------------------
// TrafficShaper class
// ---------------------------------------------------------------------------

class TrafficShaper {
public:
  explicit TrafficShaper(double total_bandwidth_mbps);

  void register_class(const TrafficClass& tc);
  void unregister_class(const std::string& class_id);
  TrafficClass* get_class(const std::string& class_id);

  void start_flow(const TrafficFlow& flow);
  void end_flow(const std::string& flow_id);
  TrafficFlow* get_flow(const std::string& flow_id);

  ShapingDecision request_transmission(const std::string& flow_id, int bytes);
  void record_transmission(const std::string& flow_id, int bytes_sent);

  std::vector<BandwidthAllocation> get_allocations();
  TrafficStats get_stats();

  void set_total_bandwidth(double bandwidth_mbps);
  void reset_stats();
  void reset();

private:
  struct ClassState {
    TrafficClass config;
    int tokens;
    long long last_refill;
    int deficit;
  };

  mutable std::shared_mutex mu_;
  double total_bandwidth_mbps_;
  std::map<std::string, ClassState> classes_;
  std::map<std::string, TrafficFlow> flows_;
  TrafficStats stats_;

  void refill_tokens(ClassState& state, long long now_ms);
};
```

### Implementation File

Create `src/traffic_shaper.cpp` implementing all functions and the `TrafficShaper` class.

### Required Classes/Structs

| Type | Purpose |
|------|---------|
| `TrafficClass` | Defines a traffic class with priority and bandwidth allocation |
| `TrafficFlow` | Represents an active traffic flow with statistics |
| `ShapingDecision` | Result of a transmission request with allow/deny and delay |
| `BandwidthAllocation` | Current allocation status for a traffic class |
| `TrafficStats` | Aggregate statistics for the traffic shaper |
| `TrafficShaper` | Stateful class managing traffic classes, flows, and shaping decisions |

### Architectural Patterns to Follow

1. **Token Bucket**: Follow `RateLimiter` pattern for token management
2. **Priority Queue**: Use priority-based ordering similar to `PriorityQueue`
3. **Statistics Tracking**: Follow `TrafficStats` accumulation pattern from telemetry
4. **Time-Based Refill**: Use elapsed time calculation similar to `RateLimiter::refill()`
5. **Read-Write Locks**: Use `std::shared_mutex` for flow/class lookups

### Acceptance Criteria

1. **Unit Tests**: Minimum 35 test cases in `tests/test_traffic_shaper.cpp`:
   - Test traffic class registration and lookup
   - Test flow lifecycle (start, transmit, end)
   - Test token bucket refill logic
   - Test fair queuing calculations
   - Test priority-based bandwidth allocation
   - Test shaping decisions under various conditions
   - Test statistics accumulation
   - Test bandwidth changes during operation

2. **Coverage Requirements**:
   - All bandwidth calculation functions tested with known values
   - Fair queuing tested with multiple classes and varying loads
   - Rate limiting tested at token depletion and refill
   - Jain fairness index tested for perfect and skewed distributions
   - Thread safety verified with concurrent flow operations

3. **Integration Points**:
   - Use existing `QueueItem` pattern for flow queueing
   - Compatible with `Route` latency values
   - Use `estimate_wait_time()` pattern for delay estimation
   - Statistics compatible with `MetricSample` format

---

## General Guidelines

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
    test_topology.cpp     # Task 1 tests
    test_health_monitor.cpp   # Task 2 tests
    test_traffic_shaper.cpp   # Task 3 tests
```

### CMake Integration

Add new source files to `CMakeLists.txt`:

```cmake
set(SOURCES
  # ... existing sources ...
  src/topology.cpp
  src/health_monitor.cpp
  src/traffic_shaper.cpp
)
```

### Code Style Requirements

1. Use C++20 features where appropriate
2. Follow existing naming conventions (snake_case for functions, PascalCase for types)
3. Include appropriate headers (`<algorithm>`, `<cmath>`, `<map>`, `<mutex>`, etc.)
4. Use `static_cast` for numeric conversions
5. Handle edge cases (empty containers, zero denominators, negative values)
6. Document complex algorithms with inline comments

### Testing Requirements

1. Use the existing test framework (appears to be Catch2 or similar)
2. Organize tests by function/feature
3. Include setup/teardown for stateful class tests
4. Test thread safety where applicable
5. Use descriptive test names that explain the scenario
