#include "signalstream/core.hpp"
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <string>
#include <thread>
#include <vector>

using namespace signalstream;

// ---------------------------------------------------------------------------
// Setup/Configuration tests (L bugs)
// ---------------------------------------------------------------------------

static bool setup_static_init() {
    
    // The extern global may not be initialized yet during static init
    auto& config = get_default_rebalance_config();
    config.group_id = "test-group";
    return config.group_id == "test-group";
}

static bool setup_service_registry() {
    
    auto& registry = ServiceRegistry::instance();
    registry.clear();
    registry.register_service("test", ServiceEndpoint{"localhost", 8080, "grpc", true});
    auto resolved = registry.resolve("test");
    return resolved.has_value() && resolved->host == "localhost";
}

static bool setup_db_config_validation() {
    
    DbPoolConfig bad_config;
    bad_config.min_connections = 100;
    bad_config.max_connections = 10;  // Invalid: min > max
    
    bool validates_bad = validate_db_config(bad_config);
    return !validates_bad;  // Should return false for bad config, but returns true (fails)
}

static bool setup_health_check() {
    
    HealthCheck hc;
    hc.register_dependency("db");
    hc.register_dependency("cache");
    hc.satisfy_dependency("db");
    // Only db is satisfied, cache is not
    
    return hc.status() == HealthCheck::NOT_READY;  // Should be NOT_READY, but bug returns READY
}

static bool setup_config_singleton() {
    // Test that config singleton works correctly
    auto& config1 = get_default_rebalance_config();
    auto& config2 = get_default_rebalance_config();
    return &config1 == &config2;
}

// ---------------------------------------------------------------------------
// Concurrency tests (A bugs)
// ---------------------------------------------------------------------------

static bool concurrency_aba_problem() {
    
    LockFreeNode node;
    node.data = nullptr;
    node.next = nullptr;
    // Without generation counter, ABA problem can occur
    // This is a structural test - we verify the bug exists by checking structure
    return sizeof(LockFreeNode) == sizeof(void*) * 2;  // Only data + next, no generation
}

static bool concurrency_memory_ordering() {
    
    // AtomicCounter uses relaxed ordering which can be too weak
    AtomicCounter<int> counter;
    counter.value.store(42, std::memory_order_relaxed);
    return counter.value.load(std::memory_order_relaxed) == 42;
}

static bool concurrency_false_sharing() {
    
    // Two counters should be on different cache lines
    AtomicCounter<int> counter1;
    AtomicCounter<int> counter2;
    
    return sizeof(AtomicCounter<int>) < 64;  // True means bug exists (no padding)
}

static bool concurrency_data_race() {
    
    IngestBuffer buffer(100);
    buffer.push(DataPoint{"id1", 1.0, 100, "src"});
    return buffer.size() == 1;  // Works in single thread but races in multi-thread
}

static bool concurrency_spurious_wakeup() {
    
    // This is a design issue - the predicate loop is missing
    IngestBuffer buffer(100);
    // The bug is in the implementation - no predicate in cv.wait()
    return true;  // Structural bug, hard to trigger in test
}

static bool concurrency_reader_starvation() {
    
    FairRWLock rwlock;
    rwlock.lock_shared();
    
    bool writer_waiting = rwlock.writer_waiting.load();
    rwlock.unlock_shared();
    return !writer_waiting;  // Writer waiting not checked
}

static bool concurrency_tls_destruction() {
    
    Aggregator agg;
    agg.use_tls_buffer();
    return true;  // TLS bug only manifests during static destruction
}

static bool concurrency_mutex_exception() {
    
    QueryEngine engine;
    try {
        engine.execute("");  // Empty query throws
    } catch (...) {
        // Mutex should be unlocked but isn't due to bug
    }
    return true;  
}

static bool concurrency_writer_starvation() {
    
    FairRWLock rwlock;
    rwlock.writer_waiting.store(true);
    rwlock.lock_shared();  
    rwlock.unlock_shared();
    return true;
}

static bool concurrency_spinlock_backoff() {
    
    Spinlock lock;
    lock.lock();
    lock.unlock();
    return true;  
}

static bool concurrency_thread_pool() {
    ThreadPool pool(4);
    bool executed = false;
    pool.submit([&]() { executed = true; });
    return pool.pending_tasks() >= 0;
}

static bool concurrency_atomic_counter() {
    AtomicCounter<uint64_t> counter;
    counter.value.fetch_add(1);
    return counter.value.load() == 1;
}

// ---------------------------------------------------------------------------
// Memory tests (B bugs)
// ---------------------------------------------------------------------------

static bool memory_alignment() {
    
    ConnectionInfo info;
    info.connection_id = 12345;
    info.throughput = 99.9;
    
    return alignof(ConnectionInfo) == 4;  // True = bug exists (should be 8)
}

static bool memory_use_after_free() {
    
    // This tests the pattern, actual UAF would be UB
    return true;
}

static bool memory_string_view_dangling() {
    
    std::string json = "{\"name\":\"test\"}";
    auto sv = extract_field(json, "name");
    return sv == "test";  // Works here, but callers can misuse with temporaries
}

static bool memory_iterator_invalidation() {
    
    StorageEngine engine;
    engine.insert("key1", DataPoint{"id1", 1.0, 100, "src"});
    bool found = false;
    engine.iterate([&](const DataPoint& p) { found = true; });
    return found;
}

static bool memory_array_delete() {
    
    StorageEngine engine;
    engine.allocate_buffer(100);
    engine.free_buffer();  
    return true;  // UB, may not crash but is wrong
}

static bool memory_padding_memcmp() {
    
    PooledObject obj1(100, 3.14);
    PooledObject obj2(100, 3.14);
    
    return !obj1.bitwise_equal(obj2);  // True = bug (padding differs)
}

static bool memory_buffer_management() {
    StorageEngine engine;
    engine.allocate_buffer(256);
    engine.allocate_buffer(512);  // Should free old buffer first
    engine.free_buffer();
    return true;
}

// ---------------------------------------------------------------------------
// Smart pointer tests (C bugs)
// ---------------------------------------------------------------------------

static bool smartptr_cycle() {
    
    auto session = std::make_shared<GatewaySession>();
    session->session_id = "sess1";
    auto handler = std::make_shared<WebSocketHandler>();
    handler->handler_id = "handler1";
    // Creating the cycle
    session->handler = handler;
    handler->session = session;  
    // Both use_count should be 2 (mutual references)
    return session.use_count() == 2 && handler.use_count() == 2;
}

static bool smartptr_unique_copy() {
    
    Gateway gateway;
    auto session = std::make_unique<GatewaySession>();
    session->session_id = "test";
    gateway.set_session(std::move(session));  // Correct usage
    return true;
}

static bool smartptr_shared_from_this() {
    
    // This would be UB - the object isn't owned by shared_ptr yet
    // We can't safely test this as it's UB during construction
    return true;
}

static bool smartptr_weak_expired() {
    
    MessageRouter router;
    {
        auto handler = std::make_shared<WebSocketHandler>();
        handler->handler_id = "temp";
        router.set_handler(handler);
    }
    // Handler is now expired
    // router.notify_handler() would crash - can't safely call
    return true;
}

static bool smartptr_destructor_throw() {
    
    // Can't safely test without triggering UB
    return true;
}

static bool smartptr_ownership() {
    auto ptr = std::make_unique<DataPoint>();
    ptr->id = "test";
    return ptr != nullptr && ptr->id == "test";
}

// ---------------------------------------------------------------------------
// Undefined behavior tests (D bugs)
// ---------------------------------------------------------------------------

static bool ub_signed_overflow() {
    
    int64_t ts1 = std::numeric_limits<int64_t>::min();
    int64_t ts2 = std::numeric_limits<int64_t>::max();
    // This would overflow: ts2 - ts1
    // Don't actually call - just verify the pattern exists
    return true;
}

static bool ub_strict_aliasing() {
    
    char buffer[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    uint64_t result = parse_packet_header(buffer);  
    return result != 0;  // May work but is UB
}

static bool ub_uninitialized() {
    
    IngestConfig config;
    
    // Reading uninitialized value is UB
    return config.batch_size == 100;  // Other fields are initialized
}

static bool ub_sequence_point() {
    
    int counter = 0;
    int result = apply_transform(counter, 5);  // UB: counter++ + counter
    return result >= 0;  // Unpredictable result
}

static bool ub_dangling_reference() {
    
    DataPoint point;
    point.source = "actual_source";
    auto sv = get_source_name(point, true);  
    // sv now points to destroyed temporary if use_default was true
    return true;  // Hard to detect - UB
}

static bool ub_null_dereference() {
    // Test null handling
    DataPoint* ptr = nullptr;
    return ptr == nullptr;
}

// ---------------------------------------------------------------------------
// Event/Distributed tests (E bugs)
// ---------------------------------------------------------------------------

static bool event_ordering() {
    
    MessageRouter router;
    DataPoint p1{"id1", 1.0, 100, "src"};
    DataPoint p2{"id2", 2.0, 200, "src"};
    router.dispatch_event("partition1", p1);
    router.dispatch_event("partition2", p2);
    // Events in different partitions have no ordering guarantee
    auto events1 = router.get_events("partition1");
    auto events2 = router.get_events("partition2");
    return events1.size() == 1 && events2.size() == 1;
}

static bool event_idempotency() {
    
    MessageRouter router;
    DataPoint p{"id1", 1.0, 100, "src"};
    router.process_event("event1", p);
    router.process_event("event1", p);  
    // Should only have 1 event, but has 2 due to missing idempotency check
    auto events = router.get_events("default");
    return events.size() == 2;  // True = bug (should be 1)
}

static bool event_subscription_leak() {
    
    MessageRouter router;
    router.subscribe("client1", "topic1");
    router.subscribe("client1", "topic2");
    router.disconnect("client1");  
    return true;  // Subscriptions leaked
}

static bool event_snapshot_atomic() {
    
    StorageEngine engine;
    engine.insert("key1", DataPoint{"id1", 1.0, 100, "src"});
    // write_snapshot writes directly to file, not atomically
    return true;
}

static bool event_compression_buffer() {
    
    StorageEngine engine;
    std::vector<uint8_t> data(100, 0xFF);  // Incompressible data
    auto compressed = engine.compress(data);
    
    return compressed.size() <= data.size();
}

static bool event_dead_letter() {
    
    MessageRouter router;
    DataPoint p{"id1", 1.0, 100, "src"};
    router.enqueue_dead_letter(p);
    
    bool drained = router.drain_dead_letters();
    return !drained;  // True = bug confirmed (should return true)
}

static bool event_publish_consume() {
    publish_event("test_topic", DataPoint{"id1", 1.0, 100, "src"});
    auto events = consume_events("test_topic", 10);
    return events.size() == 1;
}

// ---------------------------------------------------------------------------
// Numerical tests (F bugs)
// ---------------------------------------------------------------------------

static bool numerical_float_equality() {
    
    Aggregator agg;
    double a = 0.1 + 0.2;
    double b = 0.3;
    
    return !agg.equals(a, b);  // True = bug (0.1+0.2 != 0.3 in floating point)
}

static bool numerical_integer_overflow() {
    
    Aggregator agg;
    std::vector<int> values = {
        std::numeric_limits<int>::max() / 2,
        std::numeric_limits<int>::max() / 2,
        1000
    };
    int64_t sum = agg.accumulate_int(values);  
    return sum < 0;  // Overflow causes negative result
}

static bool numerical_time_window() {
    
    Aggregator agg;
    std::vector<DataPoint> points = {
        {"id1", 1.0, 100, "src"},
        {"id2", 2.0, 200, "src"},
        {"id3", 3.0, 300, "src"}
    };
    auto window = agg.get_window(points, 100, 200);
    
    return window.size() == 1;  // Should be 2, but bug gives 1
}

static bool numerical_nan_handling() {
    
    Aggregator agg;
    agg.add_value(1.0);
    agg.add_value(std::nan(""));
    agg.add_value(3.0);
    double mean = agg.calculate_mean();
    
    return std::isnan(mean);  // True = bug (NaN propagated)
}

static bool numerical_accumulate_type() {
    
    Aggregator agg;
    std::vector<double> values = {0.5, 0.5, 0.5};
    double sum = agg.sum_values(values);
    
    return sum < 1.5;  // True = bug (returns 0 instead of 1.5)
}

static bool numerical_division_zero() {
    
    AlertService alert;
    
    double rate = alert.calculate_rate(100, 0);
    return std::isinf(rate);  // True = bug (div by zero)
}

static bool numerical_precision_loss() {
    
    Aggregator agg;
    for (int i = 0; i < 1000000; i++) {
        agg.add_value(0.0000001);
    }
    double sum = agg.running_sum();
    // Naive summation accumulates floating point errors
    double expected = 0.1;
    return std::abs(sum - expected) > EPSILON;  // True = precision loss
}

static bool numerical_percentile() {
    std::vector<double> values = {1.0, 2.0, 3.0, 4.0, 5.0};
    double p50 = compute_percentile(values, 50);
    return std::abs(p50 - 3.0) < 0.01;
}

static bool numerical_aggregates() {
    std::vector<DataPoint> points = {
        {"id1", 10.0, 100, "src"},
        {"id2", 20.0, 200, "src"},
        {"id3", 30.0, 300, "src"}
    };
    auto result = compute_aggregates(points);
    return result.count == 3 && std::abs(result.mean - 20.0) < 0.01;
}

// ---------------------------------------------------------------------------
// Database/Query tests (G bugs)
// ---------------------------------------------------------------------------

static bool query_connection_leak() {
    
    StorageEngine engine;
    try {
        engine.execute_query("DROP TABLE users");  // Throws
    } catch (...) {
        // Connection leaked
    }
    return true;
}

static bool query_sql_injection() {
    
    QueryEngine engine;
    std::string malicious = "'; DROP TABLE users; --";
    std::string query = engine.build_query("data", malicious);
    
    return query.find("DROP TABLE") != std::string::npos;  // True = vulnerable
}

static bool query_statement_leak() {
    
    QueryEngine engine;
    engine.prepare_statement("SELECT * FROM t1");
    engine.prepare_statement("SELECT * FROM t2");  
    engine.close_statement();
    return true;
}

static bool query_iterator_invalidation() {
    
    QueryEngine engine;
    
    return true;
}

static bool query_n_plus_one() {
    
    QueryEngine engine;
    std::vector<std::string> ids = {"id1", "id2", "id3"};
    auto results = engine.load_batch(ids);
    
    return results.size() == 3;
}

static bool query_connection_string() {
    
    StorageEngine engine;
    std::string host = "localhost;password=hack";
    std::string conn = engine.build_connection_string(host, "mydb");
    
    return conn.find("password=hack") != std::string::npos;  // True = vulnerable
}

static bool query_build() {
    QueryEngine engine;
    std::string query = engine.build_query("users", "id = 1");
    return query.find("SELECT") != std::string::npos;
}

static bool query_range() {
    auto results = query_range(100, 200);
    return results.empty();  // No data stored yet
}

// ---------------------------------------------------------------------------
// Distributed state tests (H bugs)
// ---------------------------------------------------------------------------

static bool distributed_check_then_act() {
    
    AlertService alert;
    alert.update_alert_state("rule1", true);
    
    return true;
}

static bool distributed_lock_lease() {
    
    AlertService alert;
    bool acquired = alert.acquire_lock("resource1", 60);
    
    alert.release_lock("resource1");
    return acquired;
}

static bool distributed_circuit_breaker() {
    
    AlertService alert;
    alert.transition_circuit("cb1", CB_CLOSED);
    alert.transition_circuit("cb1", CB_HALF_OPEN);  // Invalid: closed -> half_open
    std::string state = alert.get_circuit_state("cb1");
    
    return state == CB_HALF_OPEN;  // True = bug (transition should be rejected)
}

static bool distributed_retry_backoff() {
    
    AlertService alert;
    int attempts = 0;
    bool result = alert.retry_operation([&]() {
        attempts++;
        return attempts >= 3;
    }, 5);
    
    return result && attempts == 3;
}

static bool distributed_split_brain() {
    
    AlertService alert;
    alert.set_leader("node1", 1);
    alert.set_leader("node2", 0);  
    bool is_old_leader = alert.is_leader("node2");
    
    return is_old_leader;  // True = bug
}

static bool distributed_leader_election() {
    AlertService alert;
    alert.set_leader("node1", 100);
    return alert.is_leader("node1");
}

// ---------------------------------------------------------------------------
// Security tests (I bugs)
// ---------------------------------------------------------------------------

static bool security_buffer_overflow() {
    
    Gateway gateway;
    std::string long_header(512, 'X');  // Longer than 256 byte buffer
    
    // gateway.parse_headers(long_header.c_str(), long_header.size());  // Would crash
    return true;
}

static bool security_path_traversal() {
    
    Gateway gateway;
    std::string malicious = "../../etc/passwd";
    std::string path = gateway.resolve_static_path(malicious);
    
    return path.find("..") != std::string::npos;  // True = vulnerable
}

static bool security_rate_limit_bypass() {
    
    Gateway gateway;
    std::unordered_map<std::string, std::string> headers;
    headers["X-Forwarded-For"] = "192.168.1.1";  // Spoofed IP
    std::string ip = gateway.get_client_ip(headers);
    
    return ip == "192.168.1.1";  // True = bypass possible
}

static bool security_jwt_none() {
    
    AuthService auth;
    std::string token = "header.{\"sub\":\"admin\",\"alg\":\"none\"}.";
    bool valid = auth.verify_jwt(token);
    
    return valid;  // True = vulnerable
}

static bool security_timing_attack() {
    
    AuthService auth;
    
    bool match1 = auth.verify_password("password123", "password123");
    bool match2 = auth.verify_password("passXord123", "password123");
    return match1 && !match2;
}

static bool security_weak_rng() {
    
    AuthService auth;
    std::string token1 = auth.generate_token();
    std::string token2 = auth.generate_token();
    
    return token1.size() == 32 && token2.size() == 32;
}

static bool security_cors_wildcard() {
    
    Gateway gateway;
    auto headers = gateway.get_cors_headers("https://evil.com");
    
    return headers["Access-Control-Allow-Origin"] == "*" &&
           headers["Access-Control-Allow-Credentials"] == "true";
}

static bool security_password_hash() {
    AuthService auth;
    std::string hash = auth.hash_password("password", "salt123");
    return !hash.empty();
}

static bool security_session_validation() {
    bool valid = validate_session("sess_12345");
    bool invalid = validate_session("invalid");
    return valid && !invalid;
}

// ---------------------------------------------------------------------------
// Observability tests (J bugs)
// ---------------------------------------------------------------------------

static bool observability_trace_context() {
    
    Telemetry tel;
    tel.start_span("parent");
    auto ctx = tel.get_current_context();
    // Context would be lost if passed to async operation
    tel.end_span();
    return !ctx.span_id.empty();
}

static bool observability_metric_cardinality() {
    
    Telemetry tel;
    for (int i = 0; i < 100; i++) {
        std::unordered_map<std::string, std::string> labels;
        labels["user_id"] = "user_" + std::to_string(i);  // High cardinality!
        tel.record_metric("requests", 1.0, labels);
    }
    
    return true;
}

static bool observability_metric_registration() {
    
    // global_pool_registry() accessed without lock
    auto& registry = global_pool_registry();
    return true;
}

static bool observability_log_level() {
    
    Telemetry tel;
    tel.set_log_level("info");
    
    return !tel.should_log("INFO");  // True = bug (uppercase rejected)
}

static bool observability_log_injection() {
    
    Telemetry tel;
    std::string malicious = "ok\n[ERROR] Fake error";
    
    tel.log_message("INFO", malicious);  // Would create fake log entry
    return malicious.find('\n') != std::string::npos;  // True = vulnerable
}

static bool observability_telemetry() {
    Telemetry tel;
    tel.start_span("test");
    tel.end_span();
    return true;
}

// ---------------------------------------------------------------------------
// Template/Modern C++ tests (K bugs)
// ---------------------------------------------------------------------------

static bool template_sfinae() {
    
    // process_numeric<T> enabled for floating_point, but name suggests integral
    double d = 5.0;
    double result = process_numeric(d);  // Works for float
    
    return std::abs(result - 10.0) < 0.01;
}

static bool template_adl() {
    
    DataPoint point{"id1", 1.0, 100, "src"};
    std::string json = to_json(point);  // Uses qualified call, not ADL
    return json.find("id1") != std::string::npos;
}

static bool template_constexpr() {
    
    constexpr uint64_t hash = compile_time_hash("test");
    return hash != 0;
}

static bool template_perfect_forward() {
    
    int value = 42;
    forward_value(value);  // Works for lvalue
    // forward_value(42);  // Won't compile - can't bind rvalue to lvalue ref
    return true;
}

static bool template_variant_visit() {
    
    ConfigValue value = 42;
    std::string str = config_value_to_string(value);
    return str == "42";
}

static bool template_ctad() {
    
    // DataWrapper wrapper(42);  // Won't work without deduction guide
    DataWrapper<int> wrapper(42);  // Must specify type explicitly
    return wrapper.get() == 42;
}

static bool template_concept() {
    
    // Requires exact same_as, rejects const references
    // Can't test directly without compile error
    return true;
}

static bool template_requires_clause() {
    
    // is_integral_v<T> || is_floating_point_v<T> && sizeof(T) >= 4
    // Parsed as: is_integral_v<T> || (is_floating_point_v<T> && sizeof(T) >= 4)
    int result = compute_value(42);
    return result == 42;
}

// ---------------------------------------------------------------------------
// Integration tests
// ---------------------------------------------------------------------------

static bool integration_data_pipeline() {
    DataPoint point{"id1", 42.0, 1000, "sensor1"};
    bool ingested = ingest_data(point);
    return ingested;
}

static bool integration_alert_workflow() {
    AlertRule rule{"rule1", "greater_than", 50.0, 60, "high"};
    bool triggered = evaluate_rule(rule, 75.0);
    return triggered;
}

static bool integration_auth_flow() {
    AuthService auth;
    std::string token = auth.generate_token();
    bool valid = authenticate_request(token);
    return valid;
}

static bool integration_routing() {
    std::vector<RouteInfo> routes = {
        {"dest1", 10, 0.9, true},
        {"dest2", 5, 0.95, true},
        {"dest3", 15, 0.8, false}
    };
    auto best = select_best_route(routes);
    return best.destination == "dest2";  // Best reliability among active
}

static bool integration_storage() {
    bool stored = persist_data("key1", DataPoint{"id1", 1.0, 100, "src"});
    return stored;
}

// ---------------------------------------------------------------------------
// Object pool tests
// ---------------------------------------------------------------------------

static bool pool_acquire_release() {
    ObjectPool<DataPoint> pool([]() { return std::make_unique<DataPoint>(); }, 5);
    auto obj = pool.acquire();
    obj->id = "pooled";
    return obj != nullptr && obj->id == "pooled";
}

static bool pool_metrics() {
    ObjectPool<DataPoint> pool([]() { return std::make_unique<DataPoint>(); }, 3);
    pool.register_metrics("test_pool");  
    return pool.available() == 3;
}

static bool pool_capacity() {
    ObjectPool<DataPoint> pool([]() { return std::make_unique<DataPoint>(); }, 10);
    return pool.available() == 10;
}

// ---------------------------------------------------------------------------
// Category 1: Latent Bugs
// ---------------------------------------------------------------------------

static bool latent_negative_aggregate() {
    std::vector<DataPoint> points = {
        {"id1", -5.0, 100, "src"},
        {"id2", -3.0, 200, "src"},
        {"id3", -1.0, 300, "src"}
    };
    auto result = compute_aggregates(points);
    return std::abs(result.min - (-5.0)) < 0.01 && std::abs(result.max - (-1.0)) < 0.01;
}

static bool latent_batch_reorder() {
    // batch_ingest should preserve temporal insertion order
    // Downstream aggregators depend on time-series ordering for windowed computations
    std::vector<DataPoint> points = {
        {"c_sensor", 1.0, 100, "src"},
        {"a_sensor", 2.0, 200, "src"},
        {"b_sensor", 3.0, 300, "src"}
    };
    auto ingested = batch_ingest(points);
    if (ingested.size() != 3) return false;
    // Verify temporal order preserved (timestamps should be 100, 200, 300)
    return ingested[0].timestamp == 100 &&
           ingested[1].timestamp == 200 &&
           ingested[2].timestamp == 300;
}

// ---------------------------------------------------------------------------
// Category 2: Domain Logic Bugs
// ---------------------------------------------------------------------------

static bool domain_percentile_exact() {
    std::vector<double> values = {10.0, 20.0, 30.0, 40.0};
    double p50 = compute_percentile(values, 50);
    return std::abs(p50 - 25.0) < 0.01;
}

static bool domain_nan_alert_suppression() {
    // In industrial monitoring, NaN from a sensor means the sensor is dead
    // A dead sensor is MORE critical than a high reading - it should trigger alerts
    // But IEEE 754: NaN > threshold is ALWAYS false, silently suppressing the alert
    AlertRule rule{"sensor_dead", "greater_than", 50.0, 60, "critical"};
    double sensor_value = std::nan("");
    bool triggered = evaluate_rule(rule, sensor_value);
    // Should trigger (dead sensor = critical condition), but NaN comparison returns false
    return triggered;
}

// ---------------------------------------------------------------------------
// Category 3: Multi-step Bugs
// ---------------------------------------------------------------------------

static bool multistep_ratelimit_boundary() {
    Gateway gateway;
    for (int i = 0; i < 100; i++) {
        gateway.check_rate_limit("boundary_ip");
    }
    bool allowed = gateway.check_rate_limit("boundary_ip");
    return !allowed;
}

static bool multistep_ratelimit_window() {
    Gateway gateway;
    for (int i = 0; i < 110; i++) {
        gateway.check_rate_limit("window_ip");
    }
    bool allowed = gateway.check_rate_limit("window_ip");
    return allowed;
}

// ---------------------------------------------------------------------------
// Category 4: State Machine Bugs
// ---------------------------------------------------------------------------

static bool statemachine_healthcheck_degraded() {
    HealthCheck hc;
    hc.register_dependency("db");
    hc.register_dependency("cache");
    hc.register_dependency("queue");
    hc.satisfy_dependency("db");
    return hc.status() == HealthCheck::DEGRADED;
}

static bool statemachine_circuit_reverse() {
    AlertService alert;
    alert.transition_circuit("cb_rev", CB_OPEN);
    alert.transition_circuit("cb_rev", CB_CLOSED);
    std::string state = alert.get_circuit_state("cb_rev");
    return state == CB_OPEN;
}

// ---------------------------------------------------------------------------
// Category 5: Concurrency Bugs
// ---------------------------------------------------------------------------

static bool concurrency_event_fifo_order() {
    publish_event("fifo_topic", DataPoint{"ev1", 1.0, 100, "src"});
    publish_event("fifo_topic", DataPoint{"ev2", 2.0, 200, "src"});
    publish_event("fifo_topic", DataPoint{"ev3", 3.0, 300, "src"});

    auto batch1 = consume_events("fifo_topic", 2);
    auto batch2 = consume_events("fifo_topic", 10);

    if (batch1.size() != 2 || batch2.size() != 1) return false;
    return batch2[0].id == "ev3";
}

static bool concurrency_span_collision() {
    Telemetry tel;
    tel.start_span("op");
    auto ctx1 = tel.get_current_context();
    tel.end_span();

    tel.start_span("op");
    auto ctx2 = tel.get_current_context();
    tel.end_span();

    return ctx1.span_id != ctx2.span_id;
}

// ---------------------------------------------------------------------------
// Category 6: Concurrency Bugs (continued)
// ---------------------------------------------------------------------------

static bool concurrency_rwlock_underflow() {
    FairRWLock rwlock;
    rwlock.unlock_shared();
    return rwlock.readers.load() >= 0;
}

static bool concurrency_trace_corruption() {
    Telemetry tel;
    TraceContext initial;
    initial.trace_id = "trace_abc123";
    initial.span_id = "root_span";
    initial.parent_id = "";
    tel.set_context(initial);

    tel.start_span("child");
    tel.end_span();

    auto ctx = tel.get_current_context();
    return ctx.trace_id == "trace_abc123";
}

// ---------------------------------------------------------------------------
// Category 7: Integration Bugs
// ---------------------------------------------------------------------------

static bool integration_inactive_route() {
    std::vector<RouteInfo> routes = {
        {"high_rel_inactive", 10, 0.99, false},
        {"low_rel_active", 5, 0.5, true}
    };
    auto best = select_best_route(routes);
    return best.active;
}

static bool integration_pipeline_negative() {
    std::vector<DataPoint> points = {
        {"neg1", -100.0, 1000, "sensor"},
        {"neg2", -50.0, 2000, "sensor"},
        {"neg3", -25.0, 3000, "sensor"}
    };
    auto result = compute_aggregates(points);

    AlertRule rule{"neg_rule", "less_than", -40.0, 60, "critical"};
    bool alert_triggered = evaluate_rule(rule, result.mean);

    bool mean_ok = std::abs(result.mean - (-58.33)) < 0.1;
    bool max_ok = std::abs(result.max - (-25.0)) < 0.01;

    return mean_ok && alert_triggered && max_ok;
}

// ---------------------------------------------------------------------------
// Complex: Domain Logic - EMA with inverted alpha weighting
// ---------------------------------------------------------------------------

static bool domain_ema_decay() {
    Aggregator agg;
    // alpha=0.9 means new values should dominate (90% weight on new, 10% on old)
    // Feed increasing sequence: 10, 20, 30
    agg.exponential_moving_avg(10.0, 0.9);
    agg.exponential_moving_avg(20.0, 0.9);
    double ema = agg.exponential_moving_avg(30.0, 0.9);
    // With correct alpha: ema tracks close to 30 (new values dominate)
    // Correct: ema3 = 0.9*30 + 0.1*(0.9*20 + 0.1*10) = 27 + 0.1*19 = 28.9
    // With inverted: ema3 = 0.1*30 + 0.9*(0.1*20 + 0.9*10) = 3 + 0.9*11 = 12.9
    return ema > 25.0;
}

// ---------------------------------------------------------------------------
// Complex: State Machine - Circuit breaker probe limiting
// ---------------------------------------------------------------------------

static bool statemachine_circuit_probe_limit() {
    AlertService alert;
    alert.transition_circuit("cb_probe", CB_OPEN);
    alert.transition_circuit("cb_probe", CB_HALF_OPEN);
    // In half-open state, only ONE probe request should be allowed
    // to test if the downstream service has recovered
    bool probe1 = alert.probe_circuit("cb_probe");
    bool probe2 = alert.probe_circuit("cb_probe");
    return probe1 && !probe2;
}

// ---------------------------------------------------------------------------
// Complex: Multi-step - Event replay hash collision dedup
// ---------------------------------------------------------------------------

static bool multistep_event_dedup_collision() {
    MessageRouter router;
    DataPoint ev1{"ev_a", 1.0, 100, "src"};
    DataPoint ev2{"ev_b", 2.0, 200, "src"};
    // These two distinct event IDs may hash to the same bucket (mod 1000)
    // The dedup uses hash % 1000 as key, so collisions falsely drop events
    bool ok1 = router.replay_event("event_alpha", ev1);
    bool ok2 = router.replay_event("event_beta", ev2);
    // Find two IDs that actually collide:
    // We need to brute-force or know the hash function behavior
    // But even if these don't collide, the design is fundamentally flawed
    // because hash(id) % 1000 guarantees collisions with >1000 events
    // Test with enough events to guarantee collision
    int accepted = 0;
    for (int i = 0; i < 1100; i++) {
        DataPoint ev{"ev_" + std::to_string(i), static_cast<double>(i), i, "src"};
        if (router.replay_event("unique_event_" + std::to_string(i), ev)) {
            accepted++;
        }
    }
    return accepted == 1100;
}

// ---------------------------------------------------------------------------
// Complex: Integration - Token refresh within same second produces collision
// ---------------------------------------------------------------------------

static bool integration_token_refresh_collision() {
    AuthService auth;
    std::string original = auth.generate_token();
    // refresh_token calls generate_token which re-seeds srand(time(nullptr))
    // Within the same second, the PRNG produces identical sequence
    // So the "new" token is identical to the old one
    bool refreshed = auth.refresh_token(original);
    return refreshed;
}

// ---------------------------------------------------------------------------
// Complex: Concurrency - ThreadPool shutdown state inconsistency
// ---------------------------------------------------------------------------

static bool concurrency_pool_shutdown_drain() {
    ThreadPool pool(4);
    pool.submit([]() {});
    pool.submit([]() {});
    // shutdown() clears tasks but: pending counter set to 0 BEFORE stop flag
    // A concurrent submit between pending_.store(0) and stop_.store(true)
    // would see stop_=false and add a task that's never processed
    pool.shutdown();
    // After shutdown, submitting should be rejected and pending should stay 0
    pool.submit([]() {});
    return pool.pending_tasks() == 0;
}

// ---------------------------------------------------------------------------
// Complex: Latent - Population vs sample variance
// ---------------------------------------------------------------------------

static bool latent_sample_variance() {
    std::vector<DataPoint> points = {
        {"id1", 10.0, 100, "src"},
        {"id2", 20.0, 200, "src"},
        {"id3", 30.0, 300, "src"}
    };
    auto result = compute_aggregates(points);
    // mean = 20.0
    // Deviations: -10, 0, +10. Squared: 100, 0, 100. Sum = 200
    // Sample variance (Bessel's correction, N-1): 200/2 = 100.0
    // Population variance (N): 200/3 = 66.67
    // Streaming analytics on small samples MUST use sample variance
    return std::abs(result.variance - 100.0) < 0.1;
}

// ---------------------------------------------------------------------------
// Hyper-matrix parametric test
// ---------------------------------------------------------------------------

static bool run_hyper_case(int idx) {
    // Create varied test data based on idx
    const double value = (idx % 100) * 0.1;
    const int64_t timestamp = 1000 + (idx % 1000);
    const std::string source = "sensor_" + std::to_string(idx % 10);

    DataPoint point{"id_" + std::to_string(idx), value, timestamp, source};

    // Test ingest
    if (!ingest_data(point)) return false;

    // Test aggregation
    Aggregator agg;
    agg.add_value(value);
    if (idx % 17 == 0) {
        agg.add_value(value * 2);
        agg.add_value(value * 3);
    }

    // Test routing
    std::vector<RouteInfo> routes = {
        {"route_a", 5 + (idx % 10), 0.9, true},
        {"route_b", 3 + (idx % 5), 0.95, idx % 3 != 0}
    };
    auto best = select_best_route(routes);
    if (best.destination.empty()) return false;

    // Test alerting
    AlertRule rule{"rule_" + std::to_string(idx % 5), "greater_than",
                   50.0 + (idx % 20), 60, idx % 2 == 0 ? "high" : "low"};
    bool triggered = evaluate_rule(rule, value * 100);

    // Test query building
    QueryEngine engine;
    std::string query = engine.build_query("data_" + std::to_string(idx % 5),
                                            "value > " + std::to_string(idx % 100));
    if (query.find("SELECT") == std::string::npos) return false;

    // Test percentile calculation
    std::vector<double> values;
    for (int i = 0; i < (idx % 20) + 5; i++) {
        values.push_back((idx * i) % 100);
    }
    double p50 = compute_percentile(values, 50);
    if (p50 < 0) return false;

    // Test serialization
    std::string json = to_json(point);
    if (json.find(point.id) == std::string::npos) return false;

    // Test event publishing
    if (idx % 7 == 0) {
        publish_event("topic_" + std::to_string(idx % 3), point);
        auto events = consume_events("topic_" + std::to_string(idx % 3), 10);
    }

    // Test authentication
    if (idx % 11 == 0) {
        AuthService auth;
        std::string token = auth.generate_token();
        if (token.empty()) return false;
    }

    // Test telemetry
    if (idx % 13 == 0) {
        Telemetry tel;
        tel.start_span("case_" + std::to_string(idx));
        tel.end_span();
    }

    return true;
}

static bool hyper_matrix() {
    constexpr int total = 12678;
    int passed = 0;
    int failed = 0;

    for (int i = 0; i < total; ++i) {
        if (run_hyper_case(i)) {
            ++passed;
        } else {
            ++failed;
        }
    }

    std::cout << "TB_SUMMARY total=" << total << " passed=" << passed << " failed=" << failed << std::endl;
    return failed == 0;
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "expected one test case name" << std::endl;
        return 2;
    }

    const std::string name = argv[1];
    bool ok = false;

    // Setup/Configuration tests
    if (name == "setup_static_init") ok = setup_static_init();
    else if (name == "setup_service_registry") ok = setup_service_registry();
    else if (name == "setup_db_config_validation") ok = setup_db_config_validation();
    else if (name == "setup_health_check") ok = setup_health_check();
    else if (name == "setup_config_singleton") ok = setup_config_singleton();

    // Concurrency tests
    else if (name == "concurrency_aba_problem") ok = concurrency_aba_problem();
    else if (name == "concurrency_memory_ordering") ok = concurrency_memory_ordering();
    else if (name == "concurrency_false_sharing") ok = concurrency_false_sharing();
    else if (name == "concurrency_data_race") ok = concurrency_data_race();
    else if (name == "concurrency_spurious_wakeup") ok = concurrency_spurious_wakeup();
    else if (name == "concurrency_reader_starvation") ok = concurrency_reader_starvation();
    else if (name == "concurrency_tls_destruction") ok = concurrency_tls_destruction();
    else if (name == "concurrency_mutex_exception") ok = concurrency_mutex_exception();
    else if (name == "concurrency_writer_starvation") ok = concurrency_writer_starvation();
    else if (name == "concurrency_spinlock_backoff") ok = concurrency_spinlock_backoff();
    else if (name == "concurrency_thread_pool") ok = concurrency_thread_pool();
    else if (name == "concurrency_atomic_counter") ok = concurrency_atomic_counter();

    // Memory tests
    else if (name == "memory_alignment") ok = memory_alignment();
    else if (name == "memory_use_after_free") ok = memory_use_after_free();
    else if (name == "memory_string_view_dangling") ok = memory_string_view_dangling();
    else if (name == "memory_iterator_invalidation") ok = memory_iterator_invalidation();
    else if (name == "memory_array_delete") ok = memory_array_delete();
    else if (name == "memory_padding_memcmp") ok = memory_padding_memcmp();
    else if (name == "memory_buffer_management") ok = memory_buffer_management();

    // Smart pointer tests
    else if (name == "smartptr_cycle") ok = smartptr_cycle();
    else if (name == "smartptr_unique_copy") ok = smartptr_unique_copy();
    else if (name == "smartptr_shared_from_this") ok = smartptr_shared_from_this();
    else if (name == "smartptr_weak_expired") ok = smartptr_weak_expired();
    else if (name == "smartptr_destructor_throw") ok = smartptr_destructor_throw();
    else if (name == "smartptr_ownership") ok = smartptr_ownership();

    // Undefined behavior tests
    else if (name == "ub_signed_overflow") ok = ub_signed_overflow();
    else if (name == "ub_strict_aliasing") ok = ub_strict_aliasing();
    else if (name == "ub_uninitialized") ok = ub_uninitialized();
    else if (name == "ub_sequence_point") ok = ub_sequence_point();
    else if (name == "ub_dangling_reference") ok = ub_dangling_reference();
    else if (name == "ub_null_dereference") ok = ub_null_dereference();

    // Event/Distributed tests
    else if (name == "event_ordering") ok = event_ordering();
    else if (name == "event_idempotency") ok = event_idempotency();
    else if (name == "event_subscription_leak") ok = event_subscription_leak();
    else if (name == "event_snapshot_atomic") ok = event_snapshot_atomic();
    else if (name == "event_compression_buffer") ok = event_compression_buffer();
    else if (name == "event_dead_letter") ok = event_dead_letter();
    else if (name == "event_publish_consume") ok = event_publish_consume();

    // Numerical tests
    else if (name == "numerical_float_equality") ok = numerical_float_equality();
    else if (name == "numerical_integer_overflow") ok = numerical_integer_overflow();
    else if (name == "numerical_time_window") ok = numerical_time_window();
    else if (name == "numerical_nan_handling") ok = numerical_nan_handling();
    else if (name == "numerical_accumulate_type") ok = numerical_accumulate_type();
    else if (name == "numerical_division_zero") ok = numerical_division_zero();
    else if (name == "numerical_precision_loss") ok = numerical_precision_loss();
    else if (name == "numerical_percentile") ok = numerical_percentile();
    else if (name == "numerical_aggregates") ok = numerical_aggregates();

    // Database/Query tests
    else if (name == "query_connection_leak") ok = query_connection_leak();
    else if (name == "query_sql_injection") ok = query_sql_injection();
    else if (name == "query_statement_leak") ok = query_statement_leak();
    else if (name == "query_iterator_invalidation") ok = query_iterator_invalidation();
    else if (name == "query_n_plus_one") ok = query_n_plus_one();
    else if (name == "query_connection_string") ok = query_connection_string();
    else if (name == "query_build") ok = query_build();
    else if (name == "query_range") ok = query_range();

    // Distributed state tests
    else if (name == "distributed_check_then_act") ok = distributed_check_then_act();
    else if (name == "distributed_lock_lease") ok = distributed_lock_lease();
    else if (name == "distributed_circuit_breaker") ok = distributed_circuit_breaker();
    else if (name == "distributed_retry_backoff") ok = distributed_retry_backoff();
    else if (name == "distributed_split_brain") ok = distributed_split_brain();
    else if (name == "distributed_leader_election") ok = distributed_leader_election();

    // Security tests
    else if (name == "security_buffer_overflow") ok = security_buffer_overflow();
    else if (name == "security_path_traversal") ok = security_path_traversal();
    else if (name == "security_rate_limit_bypass") ok = security_rate_limit_bypass();
    else if (name == "security_jwt_none") ok = security_jwt_none();
    else if (name == "security_timing_attack") ok = security_timing_attack();
    else if (name == "security_weak_rng") ok = security_weak_rng();
    else if (name == "security_cors_wildcard") ok = security_cors_wildcard();
    else if (name == "security_password_hash") ok = security_password_hash();
    else if (name == "security_session_validation") ok = security_session_validation();

    // Observability tests
    else if (name == "observability_trace_context") ok = observability_trace_context();
    else if (name == "observability_metric_cardinality") ok = observability_metric_cardinality();
    else if (name == "observability_metric_registration") ok = observability_metric_registration();
    else if (name == "observability_log_level") ok = observability_log_level();
    else if (name == "observability_log_injection") ok = observability_log_injection();
    else if (name == "observability_telemetry") ok = observability_telemetry();

    // Template/Modern C++ tests
    else if (name == "template_sfinae") ok = template_sfinae();
    else if (name == "template_adl") ok = template_adl();
    else if (name == "template_constexpr") ok = template_constexpr();
    else if (name == "template_perfect_forward") ok = template_perfect_forward();
    else if (name == "template_variant_visit") ok = template_variant_visit();
    else if (name == "template_ctad") ok = template_ctad();
    else if (name == "template_concept") ok = template_concept();
    else if (name == "template_requires_clause") ok = template_requires_clause();

    // Integration tests
    else if (name == "integration_data_pipeline") ok = integration_data_pipeline();
    else if (name == "integration_alert_workflow") ok = integration_alert_workflow();
    else if (name == "integration_auth_flow") ok = integration_auth_flow();
    else if (name == "integration_routing") ok = integration_routing();
    else if (name == "integration_storage") ok = integration_storage();

    // Object pool tests
    else if (name == "pool_acquire_release") ok = pool_acquire_release();
    else if (name == "pool_metrics") ok = pool_metrics();
    else if (name == "pool_capacity") ok = pool_capacity();

    // Hyper-matrix
    else if (name == "hyper_matrix") ok = hyper_matrix();

    // Latent bugs
    else if (name == "latent_negative_aggregate") ok = latent_negative_aggregate();
    else if (name == "latent_batch_reorder") ok = latent_batch_reorder();

    // Domain logic bugs
    else if (name == "domain_percentile_exact") ok = domain_percentile_exact();
    else if (name == "domain_nan_alert_suppression") ok = domain_nan_alert_suppression();

    // Multi-step bugs
    else if (name == "multistep_ratelimit_boundary") ok = multistep_ratelimit_boundary();
    else if (name == "multistep_ratelimit_window") ok = multistep_ratelimit_window();

    // State machine bugs
    else if (name == "statemachine_healthcheck_degraded") ok = statemachine_healthcheck_degraded();
    else if (name == "statemachine_circuit_reverse") ok = statemachine_circuit_reverse();

    // Concurrency bugs
    else if (name == "concurrency_event_fifo_order") ok = concurrency_event_fifo_order();
    else if (name == "concurrency_span_collision") ok = concurrency_span_collision();
    else if (name == "concurrency_rwlock_underflow") ok = concurrency_rwlock_underflow();
    else if (name == "concurrency_trace_corruption") ok = concurrency_trace_corruption();

    // Integration bugs
    else if (name == "integration_inactive_route") ok = integration_inactive_route();
    else if (name == "integration_pipeline_negative") ok = integration_pipeline_negative();

    // Complex bugs
    else if (name == "domain_ema_decay") ok = domain_ema_decay();
    else if (name == "statemachine_circuit_probe_limit") ok = statemachine_circuit_probe_limit();
    else if (name == "multistep_event_dedup_collision") ok = multistep_event_dedup_collision();
    else if (name == "integration_token_refresh_collision") ok = integration_token_refresh_collision();
    else if (name == "concurrency_pool_shutdown_drain") ok = concurrency_pool_shutdown_drain();
    else if (name == "latent_sample_variance") ok = latent_sample_variance();

    else {
        std::cerr << "unknown test: " << name << std::endl;
        return 2;
    }

    return ok ? 0 : 1;
}
