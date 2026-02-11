#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <vector>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Severity constants
// ---------------------------------------------------------------------------

constexpr int SEVERITY_CRITICAL = 5;
constexpr int SEVERITY_HIGH     = 4;
constexpr int SEVERITY_MEDIUM   = 3;
constexpr int SEVERITY_LOW      = 2;
constexpr int SEVERITY_INFO     = 1;

// ---------------------------------------------------------------------------
// Queue constants
// ---------------------------------------------------------------------------

constexpr int    DEFAULT_HARD_LIMIT = 1000;
constexpr double EMERGENCY_RATIO    = 0.8;
constexpr double WARN_RATIO         = 0.6;

// ---------------------------------------------------------------------------
// Circuit breaker states
// ---------------------------------------------------------------------------

inline const std::string CB_CLOSED    = "closed";
inline const std::string CB_OPEN      = "open";
inline const std::string CB_HALF_OPEN = "half_open";

// ---------------------------------------------------------------------------
// Core value types
// ---------------------------------------------------------------------------

struct Order {
  std::string id;
  int urgency;
  std::string eta;
};

struct BerthSlot {
  std::string berth_id;
  int start_hour;
  int end_hour;
  bool occupied;
};

struct AllocationResult {
  std::vector<Order> planned;
  std::vector<Order> rejected;
};

struct Route {
  std::string channel;
  int latency;
};

struct Waypoint {
  double lat;
  double lng;
};

struct MultiLegPlan {
  std::vector<Route> legs;
  int total_delay;
};

struct Event {
  std::string id;
  int sequence;
  bool operator==(const Event& other) const = default;
};

struct DispatchModel {
  int severity;
  int sla_minutes;
  int urgency_score() const;
  std::string to_string() const;
};

struct VesselManifest {
  std::string vessel_id;
  std::string name;
  double cargo_tons;
  int containers;
  bool hazmat;

  bool requires_hazmat_clearance() const;
};

// ---------------------------------------------------------------------------
// Policy types
// ---------------------------------------------------------------------------

struct PolicyMetadata {
  std::string level;
  std::string description;
  int max_retries;
};

struct PolicyChange {
  std::string from;
  std::string to;
  std::string reason;
};

// ---------------------------------------------------------------------------
// Queue types
// ---------------------------------------------------------------------------

struct QueueItem {
  std::string id;
  int priority;
};

struct HealthStatus {
  std::string status;
  double ratio;
  int depth;
  int hard_limit;
};

// ---------------------------------------------------------------------------
// Security types
// ---------------------------------------------------------------------------

struct Token {
  std::string value;
  std::string subject;
  long long expires_at;
};

// ---------------------------------------------------------------------------
// Workflow types
// ---------------------------------------------------------------------------

struct TransitionRecord {
  std::string entity_id;
  std::string from;
  std::string to;
};

struct TransitionResult {
  bool success;
  std::string reason;
  std::string from;
  std::string to;
};

// ---------------------------------------------------------------------------
// Statistics types
// ---------------------------------------------------------------------------

struct HeatmapCell {
  std::string zone;
  int count;
};

struct HeatmapEvent {
  double lat;
  double lng;
};

// ---------------------------------------------------------------------------
// Contract types
// ---------------------------------------------------------------------------

struct ServiceDefinition {
  std::string id;
  int port;
  std::string health_path;
  std::string version;
  std::vector<std::string> dependencies;
};

struct ValidationResult {
  bool valid;
  std::string reason;
  std::string service_id;
};

// ---------------------------------------------------------------------------
// Allocator functions
// ---------------------------------------------------------------------------

std::vector<Order> plan_dispatch(std::vector<Order> orders, int capacity);
AllocationResult dispatch_batch(const std::vector<Order>& orders, int capacity);
bool has_conflict(const std::vector<BerthSlot>& slots, int new_start, int new_end);
std::vector<BerthSlot> find_available_slots(const std::vector<BerthSlot>& slots, int duration_hours);
double estimate_cost(double distance_km, double rate_per_km, double base_fee);
std::vector<double> allocate_costs(double total_cost, const std::vector<double>& shares);
int compare_by_urgency_then_eta(const Order& a, const Order& b);
double estimate_turnaround(double cargo_tons, double crane_rate);
bool check_capacity(int current_load, int max_capacity);
std::string validate_order(const Order& order);
std::vector<std::string> validate_batch(const std::vector<Order>& orders);
double calculate_berth_utilization(const std::vector<BerthSlot>& slots);
std::vector<Order> merge_dispatch_queues(const std::vector<Order>& primary,
                                         const std::vector<Order>& overflow, int capacity);

// ---------------------------------------------------------------------------
// Routing functions
// ---------------------------------------------------------------------------

Route choose_route(const std::vector<Route>& routes, const std::vector<std::string>& blocked);
double channel_score(int latency, double reliability, int priority);
double estimate_transit_time(double distance_km, double speed_knots);
MultiLegPlan plan_multi_leg(const std::vector<Route>& routes, const std::vector<std::string>& blocked);
double estimate_route_cost(int latency, double fuel_rate, double distance_km);
int compare_routes(const Route& a, const Route& b);
bool is_hazmat_route_allowed(const std::string& channel, bool hazmat_cargo,
                             const std::vector<std::string>& restricted_channels);
double calculate_route_risk(const std::vector<Route>& legs, double base_risk);

// ---------------------------------------------------------------------------
// Policy functions
// ---------------------------------------------------------------------------

std::string next_policy(const std::string& current, int failure_burst);
std::string previous_policy(const std::string& current);
bool should_deescalate(const std::string& current, int success_streak);
bool check_sla_compliance(int response_minutes, int target_minutes);
double sla_percentage(int met, int total);
int policy_index(const std::string& p);
std::vector<std::string> all_policies();
PolicyMetadata get_policy_metadata(const std::string& level);
int calculate_breach_penalty(int severity, int minutes_over_sla);
bool should_auto_escalate(const std::string& current_policy, int consecutive_breaches, int severity);

// ---------------------------------------------------------------------------
// Queue functions
// ---------------------------------------------------------------------------

bool should_shed(int depth, int hard_limit, bool emergency);
HealthStatus queue_health(int depth, int hard_limit);
double estimate_wait_time(int depth, double processing_rate_per_sec);

// ---------------------------------------------------------------------------
// Security functions
// ---------------------------------------------------------------------------

std::string digest(const std::string& payload);
bool verify_signature(const std::string& payload, const std::string& signature, const std::string& expected);
std::string sign_manifest(const std::string& payload, const std::string& secret);
bool verify_manifest(const std::string& payload, const std::string& signature, const std::string& secret);
std::string sanitise_path(const std::string& input);
bool is_allowed_origin(const std::string& origin, const std::vector<std::string>& allowlist);
bool validate_token_chain(const std::vector<std::string>& tokens, const std::string& secret);

// ---------------------------------------------------------------------------
// Resilience functions
// ---------------------------------------------------------------------------

std::vector<Event> replay(const std::vector<Event>& events);
std::vector<Event> deduplicate(const std::vector<Event>& events);
bool replay_converges(const std::vector<Event>& events_a, const std::vector<Event>& events_b);
int find_replay_gap(const std::vector<Event>& events);

// ---------------------------------------------------------------------------
// Statistics functions
// ---------------------------------------------------------------------------

int percentile(std::vector<int> values, int pct);
double mean(const std::vector<double>& values);
double variance(const std::vector<double>& values);
double stddev(const std::vector<double>& values);
double median(std::vector<double> values);
std::pair<std::map<std::string, int>, std::vector<HeatmapCell>> generate_heatmap(
    const std::vector<HeatmapEvent>& events, int grid_size);
std::vector<double> moving_average(const std::vector<double>& values, int window_size);
double weighted_percentile(std::vector<double> values, const std::vector<double>& weights, int pct);
double exponential_moving_average_single(const std::vector<double>& values, double alpha);

// ---------------------------------------------------------------------------
// Workflow functions
// ---------------------------------------------------------------------------

bool can_transition(const std::string& from, const std::string& to);
std::vector<std::string> allowed_transitions(const std::string& from);
bool is_valid_state(const std::string& state);
bool is_terminal_state(const std::string& state);
std::vector<std::string> shortest_path(const std::string& from, const std::string& to);

// ---------------------------------------------------------------------------
// Model functions
// ---------------------------------------------------------------------------

extern const std::map<int, int> SLA_BY_SEVERITY;
extern const std::map<std::string, int> CONTRACTS;

std::vector<DispatchModel> create_batch_orders(int count, int base_severity, int base_sla);
std::string validate_dispatch_order(const DispatchModel& order);
int classify_severity(const std::string& description);
double estimate_port_fees(const VesselManifest& manifest, double base_rate);

// ---------------------------------------------------------------------------
// Contract functions
// ---------------------------------------------------------------------------

extern const std::map<std::string, ServiceDefinition> SERVICE_DEFS;

std::string get_service_url(const std::string& service_id, const std::string& base_domain);
ValidationResult validate_contract(const std::string& service_id);
std::vector<std::string> topological_order();
bool validate_manifest_chain(const std::vector<std::string>& payloads, const std::string& secret);
int dependency_depth(const std::string& service_id);

// ---------------------------------------------------------------------------
// Stateful classes
// ---------------------------------------------------------------------------

class RollingWindowScheduler {
public:
  explicit RollingWindowScheduler(int window_size);
  bool submit(const Order& order);
  std::vector<Order> flush();
  int count();
  int submit_batch(const std::vector<Order>& orders);

private:
  std::mutex mu_;
  int window_size_;
  std::vector<Order> scheduled_;
};

class RouteTable {
public:
  RouteTable();
  void add(const Route& route);
  Route* get(const std::string& channel);
  std::vector<Route> all();
  void remove(const std::string& channel);
  int count();

private:
  mutable std::shared_mutex mu_;
  std::map<std::string, Route> routes_;
};

class PolicyEngine {
public:
  explicit PolicyEngine(const std::string& initial);
  std::string current();
  std::string escalate(int failure_burst, const std::string& reason);
  std::string deescalate(const std::string& reason);
  std::vector<PolicyChange> history();
  void reset();
  bool try_recovery();
  int escalation_depth();

private:
  std::mutex mu_;
  std::string current_;
  std::vector<PolicyChange> history_;
};

class PriorityQueue {
public:
  PriorityQueue();
  void enqueue(const QueueItem& item);
  QueueItem* dequeue();
  QueueItem* peek();
  int size();
  bool is_empty();
  std::vector<QueueItem> drain(int count);
  void clear();

private:
  std::mutex mu_;
  std::vector<QueueItem> items_;
};

class RateLimiter {
public:
  RateLimiter(int max_tokens, double refill_rate_per_sec);
  bool try_acquire(int tokens);
  int available_tokens();
  void reset();

private:
  void refill();

  std::mutex mu_;
  double max_tokens_;
  double tokens_;
  double refill_rate_;
  long long last_refill_ms_;
};

class TokenStore {
public:
  TokenStore();
  void store(const Token& token);
  Token* validate(const std::string& value);
  void revoke(const std::string& value);
  int count();
  int cleanup();

private:
  mutable std::shared_mutex mu_;
  std::map<std::string, Token> tokens_;
};

class CheckpointManager {
public:
  CheckpointManager();
  void record(const std::string& stream_id, int sequence);
  int get_checkpoint(const std::string& stream_id);
  int last_sequence();
  bool should_checkpoint(int current_seq);
  void reset();

private:
  std::mutex mu_;
  std::map<std::string, int> checkpoints_;
  int last_sequence_;
};

class CircuitBreaker {
public:
  CircuitBreaker(int failure_threshold, long long recovery_time_ms);
  std::string state();
  bool is_allowed();
  void record_success();
  void record_failure();
  void reset();
  bool attempt(std::function<bool()> operation);

private:
  std::mutex mu_;
  std::string state_;
  int failures_;
  int failure_threshold_;
  long long recovery_time_ms_;
  long long last_failure_at_;
  int success_count_;
};

class ResponseTimeTracker {
public:
  explicit ResponseTimeTracker(int window_size);
  void record(double duration_ms);
  double p50();
  double p95();
  double p99();
  double average();
  int count();
  void reset();
  void merge(const std::vector<double>& other_samples);

private:
  double percentile_float(int pct);

  std::mutex mu_;
  std::vector<double> samples_;
  int window_size_;
};

class WorkflowEngine {
public:
  WorkflowEngine();
  bool register_entity(const std::string& entity_id, const std::string& initial_state);
  std::string get_state(const std::string& entity_id);
  TransitionResult transition(const std::string& entity_id, const std::string& to);
  bool is_terminal(const std::string& entity_id);
  int active_count();
  std::vector<TransitionRecord> entity_history(const std::string& entity_id);
  std::vector<TransitionRecord> audit_log();
  bool force_complete(const std::string& entity_id);
  std::vector<TransitionResult> bulk_transition(
      const std::vector<std::string>& entity_ids, const std::string& to);
  int terminal_count();

private:
  struct Entity {
    std::string state;
    std::vector<TransitionRecord> transitions;
  };

  std::mutex mu_;
  std::map<std::string, Entity> entities_;
  std::vector<TransitionRecord> log_;
};

}
