#pragma once

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <shared_mutex>
#include <string>
#include <string_view>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <variant>
#include <vector>

namespace signalstream {

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

constexpr int DEFAULT_BUFFER_SIZE = 1024;
constexpr int MAX_CONNECTIONS = 100;
constexpr double EPSILON = 1e-9;

// Circuit breaker states
inline const std::string CB_CLOSED    = "closed";
inline const std::string CB_OPEN      = "open";
inline const std::string CB_HALF_OPEN = "half_open";

// ---------------------------------------------------------------------------
// Core value types
// ---------------------------------------------------------------------------

struct DataPoint {
    std::string id;
    double value;
    int64_t timestamp;
    std::string source;
};

struct StreamConfig {
    std::string stream_id;
    int buffer_size;
    int flush_interval_ms;
    bool compression_enabled;
    std::string compression_algo;
};

struct TimeWindow {
    int64_t start;
    int64_t end;
    int bucket_count;
};

struct AggregateResult {
    double sum;
    double mean;
    double min;
    double max;
    int count;
    double variance;
};

struct RouteInfo {
    std::string destination;
    int latency_ms;
    double reliability;
    bool active;
};

struct AlertRule {
    std::string rule_id;
    std::string condition;
    double threshold;
    int cooldown_seconds;
    std::string severity;
};

struct AlertEvent {
    std::string rule_id;
    std::string message;
    int64_t triggered_at;
    double current_value;
};

// ---------------------------------------------------------------------------
// Memory structures (for B bugs)
// ---------------------------------------------------------------------------


#pragma pack(push, 1)
struct ConnectionInfo {
    uint8_t flags;
    uint64_t connection_id;  // Misaligned - not on 8-byte boundary
    uint32_t timeout_ms;
    double throughput;       // Misaligned
};
#pragma pack(pop)


struct PooledObject {
    uint8_t flags;
    // 7 bytes padding
    uint64_t id;
    uint32_t ref_count;
    // 4 bytes padding
    double value;

    PooledObject() = default;
    PooledObject(uint64_t obj_id, double val);
    bool bitwise_equal(const PooledObject& other) const;
};

// ---------------------------------------------------------------------------
// Lock-free structures (for A bugs)
// ---------------------------------------------------------------------------

template<typename T>
struct alignas(64) AtomicCounter {
    std::atomic<T> value{0};
    
    // FIX: Add char padding[64 - sizeof(std::atomic<T>)];
};

struct LockFreeNode {
    void* data;
    LockFreeNode* next;
    
    // FIX: Add std::atomic<uint64_t> generation;
};

// ---------------------------------------------------------------------------
// Smart pointer types (for C bugs)
// ---------------------------------------------------------------------------

struct WebSocketHandler;

struct GatewaySession {
    std::string session_id;
    
    std::shared_ptr<WebSocketHandler> handler;
};

struct WebSocketHandler {
    std::string handler_id;
    
    std::shared_ptr<GatewaySession> session;
};


class AuthSession : public std::enable_shared_from_this<AuthSession> {
public:
    AuthSession(const std::string& user);
    std::shared_ptr<AuthSession> get_self();
    std::string user_id;
    std::shared_ptr<AuthSession> self_ref;  // Stores result of shared_from_this
};

// ---------------------------------------------------------------------------
// Variant types (for K5 bug)
// ---------------------------------------------------------------------------

struct ThrowingConfig {
    ThrowingConfig(int) { throw std::runtime_error("throw"); }
};

using ConfigValue = std::variant<int, double, std::string, bool, ThrowingConfig>;

struct ConfigEntry {
    std::string key;
    ConfigValue value;
};

// ---------------------------------------------------------------------------
// Template utilities (for K bugs)
// ---------------------------------------------------------------------------


template<typename T, std::enable_if_t<std::is_floating_point_v<T>>* = nullptr>
T process_numeric(T value) {
    return value * 2;
}


constexpr uint64_t compile_time_hash(const char* str) {
    uint64_t hash = 5381;
    while (*str) {
        
        hash = ((hash << 5) + hash) + static_cast<uint64_t>(*str++);
    }
    return hash;
}


template<typename T>
void forward_value(T& value) {  
    // This forces an lvalue, losing rvalue semantics
}


template<typename T>
concept Streamable = requires(T t) {
    { t.id } -> std::same_as<std::string&>;       
    { t.value } -> std::same_as<double&>;         
    { t.timestamp } -> std::same_as<int64_t&>;    
};


template<typename T>

// was to require size>=4 for BOTH types. Small floats like float16 slip through.
requires (std::is_integral_v<T> || (std::is_floating_point_v<T> && sizeof(T) >= 4))
T compute_value(T input) {
    return input;
}

// ---------------------------------------------------------------------------
// Concurrency primitives
// ---------------------------------------------------------------------------

class FairRWLock {
public:
    void lock_shared();
    void unlock_shared();
    void lock();
    void unlock();

    
    std::atomic<int> readers{0};
    std::atomic<bool> writer_waiting{false};
    std::mutex writer_mutex;
};

class Spinlock {
public:
    void lock();
    void unlock();
    
    std::atomic_flag flag = ATOMIC_FLAG_INIT;
};

// ---------------------------------------------------------------------------
// Thread pool
// ---------------------------------------------------------------------------

class ThreadPool {
public:
    explicit ThreadPool(size_t num_threads);
    ~ThreadPool();

    void submit(std::function<void()> task);
    void wait_idle();
    size_t pending_tasks() const;
    void shutdown();

private:
    std::vector<std::function<void()>> tasks_;
    mutable std::mutex mutex_;
    std::atomic<bool> stop_{false};
    std::atomic<size_t> pending_{0};
};

// ---------------------------------------------------------------------------
// Object pool
// ---------------------------------------------------------------------------

template<typename T>
class ObjectPool {
public:
    using Factory = std::function<std::unique_ptr<T>()>;

    explicit ObjectPool(Factory factory, size_t initial_size = 0);

    std::unique_ptr<T, std::function<void(T*)>> acquire();
    void release(std::unique_ptr<T> obj);
    size_t available() const;
    size_t in_use() const;

    
    void register_metrics(const std::string& pool_name);

private:
    Factory factory_;
    std::vector<std::unique_ptr<T>> pool_;
    mutable std::mutex mutex_;
    std::atomic<size_t> acquired_{0};
    std::atomic<size_t> released_{0};
};

// ---------------------------------------------------------------------------
// Global metric registry (BUG J3)
// ---------------------------------------------------------------------------

struct PoolMetricEntry {
    std::string pool_name;
    std::function<size_t()> get_size;
    std::function<size_t()> get_acquired;
};


inline std::vector<PoolMetricEntry>& global_pool_registry() {
    static std::vector<PoolMetricEntry> registry;
    return registry;
}

// ---------------------------------------------------------------------------
// Configuration (L bugs)
// ---------------------------------------------------------------------------

struct KafkaRebalanceConfig {
    std::string group_id;
    int session_timeout_ms = 30000;
    int heartbeat_interval_ms = 3000;
    bool auto_commit = false;
};


extern KafkaRebalanceConfig g_default_rebalance_config;

struct ServiceEndpoint {
    std::string host;
    uint16_t port;
    std::string protocol;
    bool healthy = true;
};


class ServiceRegistry {
public:
    static ServiceRegistry& instance();
    void register_service(const std::string& name, ServiceEndpoint ep);
    std::optional<ServiceEndpoint> resolve(const std::string& name) const;
    void clear();

private:
    ServiceRegistry() = default;
    mutable std::mutex mutex_;
    std::unordered_map<std::string, std::vector<ServiceEndpoint>> services_;
};


struct DbPoolConfig {
    size_t max_connections = 10;
    size_t min_connections = 2;
    int connection_timeout_s = 30;
    std::string host = "localhost";
    uint16_t port = 5432;

    
    bool validate() const { return true; }
};

// ---------------------------------------------------------------------------
// Health check (L5 bug)
// ---------------------------------------------------------------------------

class HealthCheck {
public:
    enum Status { NOT_READY, READY, DEGRADED };

    HealthCheck();
    void register_dependency(const std::string& name);
    void satisfy_dependency(const std::string& name);
    bool is_ready() const;
    
    Status status() const;

private:
    std::unordered_map<std::string, bool> dependencies_;
    mutable std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// Ingest buffer (A4, A5 bugs)
// ---------------------------------------------------------------------------

class IngestBuffer {
public:
    IngestBuffer(size_t capacity);

    
    void push(DataPoint point);
    std::optional<DataPoint> pop();
    size_t size() const;

    
    DataPoint wait_and_pop();

private:
    std::vector<DataPoint> buffer_;
    size_t capacity_;
    // Missing mutex!
    std::condition_variable cv_;
    std::mutex cv_mutex_;
};

// ---------------------------------------------------------------------------
// Ingest config (D3 bug)
// ---------------------------------------------------------------------------

struct IngestConfig {
    std::string source_id;
    int batch_size;
    int flush_interval_ms;
    int max_retries;        
    bool compression;

    IngestConfig() : source_id(""), batch_size(100), flush_interval_ms(1000), compression(false) {
        
    }
};

// ---------------------------------------------------------------------------
// Timestamp utilities (D1 bug)
// ---------------------------------------------------------------------------


int64_t timestamp_delta(int64_t ts1, int64_t ts2);


uint64_t parse_packet_header(const char* buffer);


std::string_view get_source_name(const DataPoint& point, bool use_default);

// ---------------------------------------------------------------------------
// Transform utilities (D4, B3, K6 bugs)
// ---------------------------------------------------------------------------

struct TransformResult {
    std::string output;
    int transform_count;
};


int apply_transform(int& counter, int value);


std::string_view extract_field(const std::string& json, const std::string& field);


template<typename T>
class DataWrapper {
public:
    // Bug: std::type_identity_t puts T in non-deduced context, so CTAD fails
    // FIX: Add deduction guide: template<typename T> DataWrapper(T) -> DataWrapper<T>;
    explicit DataWrapper(std::type_identity_t<T> value) : value_(std::move(value)) {}
    const T& get() const { return value_; }
private:
    T value_;
};

// ---------------------------------------------------------------------------
// Router (A6, C4, E1, E2, E3, E6 bugs)
// ---------------------------------------------------------------------------

class MessageRouter {
public:
    MessageRouter();

    void add_route(const std::string& topic, RouteInfo route);
    RouteInfo get_route(const std::string& topic) const;

    
    void update_route(const std::string& topic, RouteInfo route);

    
    void dispatch_event(const std::string& partition, const DataPoint& event);
    std::vector<DataPoint> get_events(const std::string& partition) const;

    
    bool process_event(const std::string& event_id, const DataPoint& event);

    
    void subscribe(const std::string& client_id, const std::string& topic);
    void disconnect(const std::string& client_id);  // Doesn't clean up subscriptions

    
    void set_handler(std::weak_ptr<WebSocketHandler> handler);
    void notify_handler();

    
    void enqueue_dead_letter(const DataPoint& event);
    bool drain_dead_letters();

    bool replay_event(const std::string& event_id, const DataPoint& event);

private:
    std::unordered_map<std::string, RouteInfo> routes_;
    std::unordered_map<std::string, std::vector<DataPoint>> partition_events_;
    std::unordered_set<std::string> processed_events_;
    std::unordered_map<std::string, std::vector<std::string>> subscriptions_;
    std::vector<DataPoint> dead_letter_queue_;
    std::weak_ptr<WebSocketHandler> handler_;
    mutable FairRWLock rwlock_;
};

// ---------------------------------------------------------------------------
// Aggregator (A7, F1-F7 bugs)
// ---------------------------------------------------------------------------

class Aggregator {
public:
    Aggregator();

    void add_value(double value);
    void add_values(const std::vector<double>& values);

    
    bool equals(double a, double b) const;

    
    int64_t accumulate_int(const std::vector<int>& values);

    
    std::vector<DataPoint> get_window(const std::vector<DataPoint>& points,
                                       int64_t start, int64_t end);

    
    double calculate_mean();

    
    double sum_values(const std::vector<double>& values);

    
    double running_sum() const;

    
    static thread_local std::vector<double> tls_buffer;
    void use_tls_buffer();

    double exponential_moving_avg(double new_value, double alpha);

private:
    std::vector<double> values_;
    double running_total_ = 0.0;
    mutable std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// Storage (B4, B5, E4, E5, G1, G6 bugs)
// ---------------------------------------------------------------------------

class StorageEngine {
public:
    StorageEngine();

    
    void insert(const std::string& key, DataPoint point);
    std::optional<DataPoint> get(const std::string& key) const;
    void iterate(std::function<void(const DataPoint&)> callback);

    
    void allocate_buffer(size_t size);
    void free_buffer();

    
    bool write_snapshot(const std::string& path);

    
    std::vector<uint8_t> compress(const std::vector<uint8_t>& data);

    
    void execute_query(const std::string& query);

    
    std::string build_connection_string(const std::string& host, const std::string& db);

private:
    std::unordered_map<std::string, DataPoint> data_;
    uint8_t* buffer_ = nullptr;
    size_t buffer_size_ = 0;
    mutable std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// Query engine (A8, G2-G5 bugs)
// ---------------------------------------------------------------------------

class QueryEngine {
public:
    QueryEngine();

    
    std::vector<DataPoint> execute(const std::string& query);

    
    std::string build_query(const std::string& table, const std::string& filter);

    
    void prepare_statement(const std::string& query);
    void close_statement();  // Not always called

    
    void iterate_results(std::function<void(const DataPoint&)> callback);

    
    std::vector<DataPoint> load_batch(const std::vector<std::string>& ids);

private:
    std::vector<DataPoint> results_;
    void* prepared_stmt_ = nullptr;
    mutable std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// Alert service (C5, F6, H1-H5 bugs)
// ---------------------------------------------------------------------------

class AlertService {
public:
    AlertService();
    
    ~AlertService();

    void add_rule(const AlertRule& rule);
    void remove_rule(const std::string& rule_id);

    
    double calculate_rate(int events, int interval_seconds);

    
    void update_alert_state(const std::string& rule_id, bool triggered);

    
    bool acquire_lock(const std::string& resource, int lease_seconds);
    void release_lock(const std::string& resource);

    
    void transition_circuit(const std::string& circuit_id, const std::string& new_state);
    std::string get_circuit_state(const std::string& circuit_id) const;

    
    bool retry_operation(std::function<bool()> op, int max_retries);

    
    void set_leader(const std::string& node_id, int fencing_token);
    bool is_leader(const std::string& node_id) const;

    bool probe_circuit(const std::string& circuit_id);

private:
    std::unordered_map<std::string, AlertRule> rules_;
    std::unordered_map<std::string, bool> alert_states_;
    std::unordered_map<std::string, int64_t> lock_expiry_;
    std::unordered_map<std::string, std::string> circuit_states_;
    std::unordered_map<std::string, int> circuit_probe_count_;
    std::string cached_leader_;
    int cached_fencing_token_ = 0;
    mutable std::mutex mutex_;
    bool cleanup_failed_ = false;
};

// ---------------------------------------------------------------------------
// Gateway security (I1-I3, I7 bugs)
// ---------------------------------------------------------------------------

class Gateway {
public:
    Gateway();

    
    bool parse_headers(const char* raw_headers, size_t len);

    
    std::string resolve_static_path(const std::string& requested_path);

    
    std::string get_client_ip(const std::unordered_map<std::string, std::string>& headers);
    bool check_rate_limit(const std::string& client_ip);

    
    std::unordered_map<std::string, std::string> get_cors_headers(const std::string& origin);

    
    void set_session(std::unique_ptr<GatewaySession> session);

private:
    char header_buffer_[256];  // Fixed size buffer for I1 bug
    std::unordered_map<std::string, int> rate_limits_;
    std::unique_ptr<GatewaySession> session_;
    std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// Auth service (I4-I6 bugs)
// ---------------------------------------------------------------------------

struct JwtPayload {
    std::string sub;
    int64_t exp;
    std::string alg;
};

class AuthService {
public:
    AuthService();

    
    bool verify_jwt(const std::string& token);
    JwtPayload decode_jwt(const std::string& token);

    
    bool verify_password(const std::string& input, const std::string& stored);

    
    std::string generate_token();

    std::string hash_password(const std::string& password, const std::string& salt);

    bool refresh_token(const std::string& old_token);

private:
    std::unordered_map<std::string, std::string> tokens_;
    mutable std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// Observability (J1, J2, J4, J5 bugs)
// ---------------------------------------------------------------------------

struct TraceContext {
    std::string trace_id;
    std::string span_id;
    std::string parent_id;
};

class Telemetry {
public:
    Telemetry();

    
    void start_span(const std::string& name);
    void end_span();
    TraceContext get_current_context() const;
    void set_context(const TraceContext& ctx);  // Must be called manually after async

    
    void record_metric(const std::string& name, double value,
                       const std::unordered_map<std::string, std::string>& labels);

    
    void set_log_level(const std::string& level);
    bool should_log(const std::string& level) const;

    
    void log_message(const std::string& level, const std::string& message);

private:
    TraceContext current_context_;
    std::unordered_map<std::string, std::vector<double>> metrics_;
    std::string log_level_ = "info";
    mutable std::mutex mutex_;
};

// ---------------------------------------------------------------------------
// ADL and serialization (K2 bug)
// ---------------------------------------------------------------------------

namespace serialization {
    std::string serialize(const DataPoint& point);
}


template<typename T>
std::string to_json(const T& obj) {
    
    return signalstream::serialization::serialize(obj);
}

// ---------------------------------------------------------------------------
// Variant visitor (K5 bug)
// ---------------------------------------------------------------------------


std::string config_value_to_string(const ConfigValue& value);

// ---------------------------------------------------------------------------
// Function declarations for source files
// ---------------------------------------------------------------------------

// config.cpp
KafkaRebalanceConfig& get_default_rebalance_config();
bool validate_db_config(const DbPoolConfig& config);

// ingest.cpp
bool ingest_data(const DataPoint& point);
std::vector<DataPoint> batch_ingest(const std::vector<DataPoint>& points);

// router.cpp
RouteInfo select_best_route(const std::vector<RouteInfo>& routes);
bool should_retry(int attempt, int max_attempts);

// aggregate.cpp
AggregateResult compute_aggregates(const std::vector<DataPoint>& points);
double compute_percentile(const std::vector<double>& values, int percentile);

// storage.cpp
bool persist_data(const std::string& key, const DataPoint& point);
std::optional<DataPoint> load_data(const std::string& key);

// query.cpp
std::vector<DataPoint> query_range(int64_t start, int64_t end);
std::vector<DataPoint> query_by_source(const std::string& source);

// alert.cpp
bool evaluate_rule(const AlertRule& rule, double current_value);
std::vector<AlertEvent> check_alerts(const std::vector<DataPoint>& points);

// gateway.cpp
bool authenticate_request(const std::string& token);
std::string handle_request(const std::string& path, const std::string& method);

// security.cpp
std::string generate_session_id();
bool validate_session(const std::string& session_id);

// telemetry.cpp
void emit_metric(const std::string& name, double value);
void flush_metrics();

// concurrency.cpp
void run_parallel(std::vector<std::function<void()>> tasks);
bool try_lock_resource(const std::string& resource, int timeout_ms);

// events.cpp
void publish_event(const std::string& topic, const DataPoint& event);
std::vector<DataPoint> consume_events(const std::string& topic, int max_count);

// ---------------------------------------------------------------------------
// Template implementations
// ---------------------------------------------------------------------------

template<typename T>
ObjectPool<T>::ObjectPool(Factory factory, size_t initial_size)
    : factory_(std::move(factory)) {
    for (size_t i = 0; i < initial_size; ++i) {
        pool_.push_back(factory_());
    }
}

template<typename T>
std::unique_ptr<T, std::function<void(T*)>> ObjectPool<T>::acquire() {
    std::lock_guard lock(mutex_);
    acquired_++;
    if (!pool_.empty()) {
        auto obj = std::move(pool_.back());
        pool_.pop_back();
        T* raw = obj.release();
        return std::unique_ptr<T, std::function<void(T*)>>(
            raw,
            [this](T* ptr) {
                if (ptr) release(std::unique_ptr<T>(ptr));
            }
        );
    }
    T* raw = factory_().release();
    return std::unique_ptr<T, std::function<void(T*)>>(
        raw,
        [this](T* ptr) {
            if (ptr) release(std::unique_ptr<T>(ptr));
        }
    );
}

template<typename T>
void ObjectPool<T>::release(std::unique_ptr<T> obj) {
    std::lock_guard lock(mutex_);
    released_++;
    pool_.push_back(std::move(obj));
}

template<typename T>
size_t ObjectPool<T>::available() const {
    std::lock_guard lock(mutex_);
    return pool_.size();
}

template<typename T>
size_t ObjectPool<T>::in_use() const {
    return acquired_.load() - released_.load();
}

template<typename T>
void ObjectPool<T>::register_metrics(const std::string& pool_name) {
    
    auto& registry = global_pool_registry();
    registry.push_back(PoolMetricEntry{
        .pool_name = pool_name,
        .get_size = [this]() { return available(); },
        .get_acquired = [this]() { return acquired_.load(); }
    });
}

}  // namespace signalstream
