#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <vector>

namespace obsidianmesh {

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
// Config types (Phase 1)
// ---------------------------------------------------------------------------

struct ServiceConfig {
  std::string name;
  int port;
  int timeout_ms;
  int max_retries;
  std::string region;
  int pool_size;
};

// ---------------------------------------------------------------------------
// Event types (Phase 1)
// ---------------------------------------------------------------------------

struct TimedEvent {
  std::string id;
  long long timestamp;
  std::string kind;
  std::string payload;
};

// ---------------------------------------------------------------------------
// Telemetry types (Phase 1)
// ---------------------------------------------------------------------------

struct MetricSample {
  std::string name;
  double value;
  long long timestamp;
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

// New allocator functions (Phase 2)
double weighted_allocation(const std::vector<double>& weights, const std::vector<double>& values);
double berth_utilization(const std::vector<BerthSlot>& slots);
int round_allocation(double raw_value, int granularity);
double cost_per_unit(double total_cost, int units);
double normalize_urgency(int urgency, int max_urgency);
double priority_score(int urgency, double distance_km, double weight_urgency, double weight_distance);
bool is_over_capacity(int current, int max_cap, double threshold);
double accumulated_utilization(const std::vector<double>& window_rates);
double berth_rental_fee(double cargo_tons, double hours, double base_rate);
double dispatch_route_combined_score(const std::vector<Order>& orders, int capacity,
    const std::vector<Route>& routes);

// ---------------------------------------------------------------------------
// Routing functions
// ---------------------------------------------------------------------------

Route choose_route(const std::vector<Route>& routes, const std::vector<std::string>& blocked);
double channel_score(int latency, double reliability, int priority);
double estimate_transit_time(double distance_km, double speed_knots);
MultiLegPlan plan_multi_leg(const std::vector<Route>& routes, const std::vector<std::string>& blocked);
double estimate_route_cost(int latency, double fuel_rate, double distance_km);
int compare_routes(const Route& a, const Route& b);

// New routing functions (Phase 2)
double weighted_route_score(int latency, double reliability, double cost, double w_lat, double w_rel, double w_cost);
Route best_route_by_score(const std::vector<Route>& routes, const std::vector<double>& reliabilities);
Route failover_route(const std::vector<Route>& routes, const std::string& failed_channel);
double haversine_distance(double lat1, double lng1, double lat2, double lng2);
double normalize_latency(int latency, int max_latency);
double fuel_efficiency(double distance_km, double fuel_used);
double total_route_fees(const std::vector<Route>& legs, double fee_per_ms);
double knots_to_kmh(double knots);
double route_penalty(int latency, int threshold);
int count_active_routes(const std::vector<Route>& routes, int max_latency);
double weather_adjusted_eta(double distance_km, double speed_knots, double weather_factor);
double compute_route_reliability(int successes, int total);
Route select_most_reliable(const std::vector<Route>& routes,
    const std::vector<int>& successes, const std::vector<int>& totals, double min_reliability);

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

// New policy functions (Phase 2)
std::vector<std::string> policy_weight_ordering(const std::map<std::string, int>& weights);
int escalation_threshold(const std::string& level);
double risk_score(int failures, int total, double severity_weight);
int grace_period_minutes(const std::string& level);
int default_retries(const std::string& level);
int cooldown_seconds(const std::string& from, const std::string& to);
double sla_breach_cost(int response_min, int target_min, int grace_min, double penalty_per_min);
bool escalation_cooldown_ok(long long last_escalation_ms, long long now_ms, long long cooldown_ms);

// ---------------------------------------------------------------------------
// Queue functions
// ---------------------------------------------------------------------------

bool should_shed(int depth, int hard_limit, bool emergency);
HealthStatus queue_health(int depth, int hard_limit);
double estimate_wait_time(int depth, double processing_rate_per_sec);

// New queue functions (Phase 2)
int batch_enqueue_count(const std::vector<QueueItem>& items, int hard_limit, int current_depth);
int priority_boost(int base_priority, int wait_seconds, int boost_interval);
double fairness_index(const std::vector<int>& service_counts);
std::vector<QueueItem> requeue_failed(const std::vector<QueueItem>& failed, int penalty);
double weighted_wait_time(int depth, double rate, double priority_factor);
double queue_pressure_ratio(int depth, int hard_limit, int incoming_rate, int processing_rate);
double drain_percentage(int drained, int total);
std::vector<QueueItem> priority_queue_merge(const std::vector<QueueItem>& a, const std::vector<QueueItem>& b);
double policy_adjusted_queue_limit(const std::string& policy_level, int base_limit);
double weighted_priority_aging(int base_priority, long long age_ms, double aging_factor);

// ---------------------------------------------------------------------------
// Security functions
// ---------------------------------------------------------------------------

std::string digest(const std::string& payload);
bool verify_signature(const std::string& payload, const std::string& signature, const std::string& expected);
std::string sign_manifest(const std::string& payload, const std::string& secret);
bool verify_manifest(const std::string& payload, const std::string& signature, const std::string& secret);
std::string sanitise_path(const std::string& input);
bool is_allowed_origin(const std::string& origin, const std::vector<std::string>& allowlist);

// New security functions (Phase 2)
std::string token_format(const std::string& subject, long long expires_at);
int password_strength(const std::string& password);
std::string mask_sensitive(const std::string& input, int visible_chars);
std::string hmac_sign(const std::string& key, const std::string& message);
std::string rate_limit_key(const std::string& ip, const std::string& endpoint);
long long session_expiry(long long created_at, int ttl_seconds);
std::string sanitize_header(const std::string& value);
bool check_permissions(const std::vector<std::string>& user_perms, const std::vector<std::string>& required);
bool ip_in_allowlist(const std::string& ip, const std::vector<std::string>& allowlist);
std::string password_hash(const std::string& password, const std::string& salt);
double token_expiry_spread(const std::vector<long long>& expiry_times);

// ---------------------------------------------------------------------------
// Resilience functions
// ---------------------------------------------------------------------------

std::vector<Event> replay(const std::vector<Event>& events);
std::vector<Event> deduplicate(const std::vector<Event>& events);
bool replay_converges(const std::vector<Event>& events_a, const std::vector<Event>& events_b);

// New resilience functions (Phase 2)
std::vector<Event> replay_window(const std::vector<Event>& events, int from_seq, int to_seq);
bool events_ordered(const std::vector<Event>& events);
bool is_idempotent_safe(const std::vector<Event>& events);
std::vector<Event> compact_events(const std::vector<Event>& events, int max_per_id);
double retry_backoff(int attempt, double base_ms, double max_ms);
bool should_trip_breaker(int failures, int total, double threshold);
double jitter(double base_ms, double factor);
int half_open_max_calls(int failure_count);
bool in_failure_window(long long last_failure_ms, long long now_ms, long long window_ms);
double recovery_rate(int successes, int total);
int checkpoint_interval(int event_count, int base_interval);
double degradation_score(int failures, int total, double weight);
int bulkhead_limit(int total_capacity, int partition_count);
long long state_duration_ms(long long entered_at, long long now_ms);
std::string fallback_value(const std::string& primary, const std::string& fallback);
bool cascade_failure(const std::vector<bool>& service_health, double threshold);
double compute_reliability_score(int successes, int total);
std::string circuit_breaker_next_state(const std::string& current, int recent_failures,
    int recent_successes, int threshold);
int checkpoint_replay_count(const std::vector<Event>& events, int checkpoint_seq);
int cascade_failure_depth(const std::map<std::string, std::vector<std::string>>& dependency_graph,
    const std::string& failed_service);

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

// New statistics functions (Phase 2)
double weighted_mean(const std::vector<double>& values, const std::vector<double>& weights);
double exponential_moving_average(const std::vector<double>& values, double alpha);
double min_max_normalize(double value, double min_val, double max_val);
double covariance(const std::vector<double>& x, const std::vector<double>& y);
double correlation(const std::vector<double>& x, const std::vector<double>& y);
double sum_of_squares(const std::vector<double>& values);
double interquartile_range(std::vector<double> values);
double rate_of_change(double current, double previous, double interval);
double z_score(double value, double mean_val, double stddev_val);

// ---------------------------------------------------------------------------
// Workflow functions
// ---------------------------------------------------------------------------

bool can_transition(const std::string& from, const std::string& to);
std::vector<std::string> allowed_transitions(const std::string& from);
bool is_valid_state(const std::string& state);
bool is_terminal_state(const std::string& state);
std::vector<std::string> shortest_path(const std::string& from, const std::string& to);

// New workflow functions (Phase 2)
int transition_count(const std::vector<TransitionRecord>& records, const std::string& entity_id);
double time_in_state_hours(long long entered_at_ms, long long now_ms);
int parallel_entity_count(const std::vector<std::pair<std::string, std::string>>& entities);
std::map<std::string, int> state_distribution(const std::vector<std::pair<std::string, std::string>>& entities);
std::string bottleneck_state(const std::map<std::string, int>& distribution);
double completion_percentage(int completed, int total);
bool can_cancel(const std::string& state);
double estimated_completion_hours(int remaining_steps, double avg_step_hours);
double state_age_hours(long long entered_ms, long long now_ms);
int batch_register_count(const std::vector<std::string>& entity_ids, const std::string& initial_state);
bool is_valid_path(const std::vector<std::string>& path);
double workflow_throughput(int completed, double hours);
int chain_length(const std::vector<TransitionRecord>& records, const std::string& entity_id);
std::vector<TransitionRecord> merge_histories(
    const std::vector<TransitionRecord>& a, const std::vector<TransitionRecord>& b);
std::string build_transition_key(const TransitionRecord& r);
std::vector<std::string> validate_transition_sequence(const std::vector<std::string>& sequence);

// ---------------------------------------------------------------------------
// Model functions
// ---------------------------------------------------------------------------

extern const std::map<int, int> SLA_BY_SEVERITY;
extern const std::map<std::string, int> CONTRACTS;

std::vector<DispatchModel> create_batch_orders(int count, int base_severity, int base_sla);
std::string validate_dispatch_order(const DispatchModel& order);
int classify_severity(const std::string& description);

// New model functions (Phase 2)
std::string severity_label(int severity);
std::string weight_class(double cargo_tons);
int crew_estimation(int containers, double tons);
double hazmat_surcharge(double base_cost, bool is_hazmat);
double estimated_arrival_hours(double distance_km, double speed_knots);
double vessel_load_factor(int containers, int max_containers);
int crew_for_hazmat(int base_crew, bool is_hazmat, int containers);

// ---------------------------------------------------------------------------
// Contract functions
// ---------------------------------------------------------------------------

extern const std::map<std::string, ServiceDefinition> SERVICE_DEFS;

std::string get_service_url(const std::string& service_id, const std::string& base_domain);
ValidationResult validate_contract(const std::string& service_id);
std::vector<std::string> topological_order();

// New contract functions (Phase 2)
std::string health_endpoint(const std::string& service_id, const std::string& base_domain);
int dependency_depth(const std::string& service_id);
std::vector<std::string> critical_path();
bool has_port_collision(const std::vector<ServiceDefinition>& defs);
std::string service_summary(const std::string& service_id);
std::string format_port_range(int start_port, int count);
bool validate_service_version(const std::string& version);

// ---------------------------------------------------------------------------
// Config functions (Phase 1)
// ---------------------------------------------------------------------------

std::string default_region();
int default_pool_size();
ServiceConfig make_default_config(const std::string& name, int port);
bool validate_config(const ServiceConfig& cfg);
bool validate_endpoint(const std::string& url);
std::string normalize_env_name(const std::string& env);
bool feature_enabled(const std::map<std::string, bool>& flags, const std::string& name);
std::vector<std::string> enabled_features(const std::map<std::string, bool>& flags);
std::vector<ServiceConfig> sort_configs_by_priority(std::vector<ServiceConfig> configs);
int config_priority_score(const ServiceConfig& cfg);

// ---------------------------------------------------------------------------
// Concurrency functions (Phase 1)
// ---------------------------------------------------------------------------

bool barrier_reached(int arrived, int expected);
int merge_counts(const std::vector<int>& partials);
std::pair<std::vector<int>, std::vector<int>> partition_by_threshold(
    const std::vector<int>& values, int threshold);
std::vector<std::pair<std::string, int>> fan_out_merge(
    const std::vector<std::pair<std::string, int>>& inputs);
bool detect_cycle(const std::map<std::string, std::vector<std::string>>& graph);
std::vector<int> work_stealing(std::vector<int>& queue, int count);
int safe_counter_add(int current, int delta, int max_value);
std::vector<int> parallel_merge_sorted(const std::vector<int>& a, const std::vector<int>& b);

// ---------------------------------------------------------------------------
// Event functions (Phase 1)
// ---------------------------------------------------------------------------

std::vector<TimedEvent> sort_events_by_time(std::vector<TimedEvent> events);
std::vector<TimedEvent> dedup_by_id(const std::vector<TimedEvent>& events);
std::vector<TimedEvent> filter_time_window(const std::vector<TimedEvent>& events,
    long long start_ts, long long end_ts);
std::map<std::string, int> count_by_kind(const std::vector<TimedEvent>& events);
std::vector<int> detect_gaps(const std::vector<TimedEvent>& sorted_events, long long max_gap);
std::vector<TimedEvent> merge_event_streams(
    const std::vector<TimedEvent>& a, const std::vector<TimedEvent>& b);
std::vector<std::vector<TimedEvent>> batch_events(
    const std::vector<TimedEvent>& events, long long bucket_size);
double event_rate(const std::vector<TimedEvent>& events, long long window_ms);
std::vector<double> normalize_timestamps_to_seconds(const std::vector<long long>& timestamps_ms);
int count_event_bursts(const std::vector<double>& normalized_times, double gap_threshold);
int event_log_trim_count(int current_size, int max_size, int trim_batch);

// ---------------------------------------------------------------------------
// Telemetry functions (Phase 1)
// ---------------------------------------------------------------------------

double error_rate(int errors, int total);
std::string latency_bucket(double latency_ms);
double throughput(int requests, long long duration_ms);
double health_score(double availability, double error_ratio);
bool is_within_threshold(double value, double target, double tolerance);
double aggregate_metrics(const std::vector<double>& values);
double uptime_percentage(long long uptime_ms, long long total_ms);
bool should_alert(double current_value, double alert_threshold);
bool health_check_composite(double err_rate, double latency_ms, double err_thresh, double lat_thresh);

// ---------------------------------------------------------------------------
// Stateful classes
// ---------------------------------------------------------------------------

class RollingWindowScheduler {
public:
  explicit RollingWindowScheduler(int window_size);
  bool submit(const Order& order);
  std::vector<Order> flush();
  int count();

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

private:
  struct Entity {
    std::string state;
    std::vector<TransitionRecord> transitions;
  };

  std::mutex mu_;
  std::map<std::string, Entity> entities_;
  std::vector<TransitionRecord> log_;
};

// ---------------------------------------------------------------------------
// New stateful classes (Phase 1)
// ---------------------------------------------------------------------------

class AtomicCounter {
public:
  AtomicCounter();
  void increment();
  void decrement();
  int get();
  void reset();

private:
  std::mutex mu_;
  int value_;

  friend int compare_and_swap(AtomicCounter& counter, int expected, int desired);
};

int compare_and_swap(AtomicCounter& counter, int expected, int desired);

class SharedRegistry {
public:
  SharedRegistry();
  void register_entry(const std::string& key, const std::string& value);
  std::string lookup(const std::string& key);
  bool remove(const std::string& key);
  std::vector<std::string> keys();
  int size();

private:
  std::mutex mu_;
  std::map<std::string, std::string> entries_;
};

class EventLog {
public:
  explicit EventLog(int max_size = 1000);
  void append(const TimedEvent& event);
  std::vector<TimedEvent> get_all();
  int count();
  void clear();

private:
  std::mutex mu_;
  std::vector<TimedEvent> events_;
  int max_size_;
};

class MetricsCollector {
public:
  MetricsCollector();
  void record(const MetricSample& sample);
  std::vector<MetricSample> get_by_name(const std::string& name);
  int count();
  void clear();

private:
  std::mutex mu_;
  std::vector<MetricSample> samples_;
};

}
