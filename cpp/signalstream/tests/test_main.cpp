#include "signalstream/core.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
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
    // Bug: validate() always returns true, even for invalid config
    // FIX: validate_db_config must reject min_connections > max_connections
    DbPoolConfig bad_config;
    bad_config.min_connections = 100;
    bad_config.max_connections = 10;  // Invalid: min > max
    bool validates_bad = validate_db_config(bad_config);
    return !validates_bad;  // Should be false for bad config
}

static bool setup_health_check() {
    // Bug: status() returns READY if ANY dependency is satisfied
    // FIX: status() must return NOT_READY unless ALL dependencies are satisfied
    HealthCheck hc;
    hc.register_dependency("db");
    hc.register_dependency("cache");
    hc.satisfy_dependency("db");
    // Only db is satisfied, cache is not => should be NOT_READY
    return hc.status() == HealthCheck::NOT_READY;
}

static bool setup_config_singleton() {
    auto& config1 = get_default_rebalance_config();
    auto& config2 = get_default_rebalance_config();
    return &config1 == &config2;
}

// ---------------------------------------------------------------------------
// Concurrency tests (A bugs)
// ---------------------------------------------------------------------------

static bool concurrency_aba_problem() {
    // Bug: LockFreeNode has no generation counter to prevent ABA problem
    // FIX: Add std::atomic<uint64_t> generation field to LockFreeNode
    // Fixed struct should be larger than just data + next pointers
    return sizeof(LockFreeNode) > sizeof(void*) * 2;
}

static bool concurrency_memory_ordering() {
    AtomicCounter<int> counter;
    counter.value.store(42, std::memory_order_relaxed);
    return counter.value.load(std::memory_order_relaxed) == 42;
}

static bool concurrency_false_sharing() {
    // Bug: AtomicCounter lacks padding to fill cache line
    // FIX: Add padding so sizeof(AtomicCounter<int>) == 64
    return sizeof(AtomicCounter<int>) >= 64;
}

static bool concurrency_data_race() {
    // Bug: IngestBuffer has no mutex protecting buffer_ operations
    // FIX: Add mutex protection to push/pop/size
    // Test with concurrent access
    IngestBuffer buffer(100);
    std::atomic<int> count{0};
    auto writer = [&]() {
        for (int i = 0; i < 50; i++) {
            buffer.push(DataPoint{"id_" + std::to_string(i), 1.0, i, "src"});
            count.fetch_add(1);
        }
    };
    std::thread t1(writer);
    std::thread t2(writer);
    t1.join();
    t2.join();
    return buffer.size() == static_cast<size_t>(count.load());
}

static bool concurrency_spurious_wakeup() {
    // Bug: wait_and_pop uses cv_.wait(lock) without predicate
    // FIX: Use cv_.wait(lock, [this]{ return !buffer_.empty(); })
    // With bug: push before wait loses notification, wait_and_pop hangs
    // With fix: predicate checks buffer, sees item, returns immediately
    IngestBuffer buffer(100);
    buffer.push(DataPoint{"id1", 1.0, 100, "src"});

    std::atomic<bool> finished{false};
    DataPoint result;

    std::thread t([&]() {
        result = buffer.wait_and_pop();
        finished.store(true);
    });

    auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(500);
    while (!finished.load() && std::chrono::steady_clock::now() < deadline) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    if (finished.load()) {
        t.join();
        return result.id == "id1";
    } else {
        t.detach();
        return false;
    }
}

static bool concurrency_reader_starvation() {
    // Bug: lock_shared() doesn't check writer_waiting flag
    // FIX: Readers must yield when writer_waiting is true
    FairRWLock rwlock;
    rwlock.writer_waiting.store(true);

    std::atomic<bool> acquired{false};
    std::thread t([&]() {
        rwlock.lock_shared();
        acquired.store(true);
        rwlock.unlock_shared();
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    bool reader_got_in = acquired.load();

    // Clean up: let thread finish
    rwlock.writer_waiting.store(false);
    t.join();

    // With bug: reader acquired immediately (ignoring writer_waiting)
    // With fix: reader blocked until writer_waiting cleared
    return !reader_got_in;
}

static bool concurrency_tls_destruction() {
    // Bug: thread_local buffer can be destroyed before use during static destruction
    // Verify TLS buffer works correctly in a spawned thread
    std::atomic<bool> ok{false};
    std::thread t([&]() {
        Aggregator agg;
        agg.use_tls_buffer();
        ok.store(true);
    });
    t.join();
    return ok.load();
}

static bool concurrency_mutex_exception() {
    // Bug: QueryEngine::execute uses manual lock/unlock, leaks mutex on exception
    // FIX: Use std::lock_guard instead of manual lock/unlock
    QueryEngine engine;
    try {
        engine.execute("");  // Throws with mutex locked
    } catch (...) {}

    // With bug: mutex still locked -> second execute deadlocks
    // With fix: lock_guard releases on exception -> second execute works
    std::atomic<bool> finished{false};
    std::thread t([&]() {
        try { engine.execute("SELECT 1"); } catch (...) {}
        finished.store(true);
    });

    auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(500);
    while (!finished.load() && std::chrono::steady_clock::now() < deadline) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    if (finished.load()) {
        t.join();
        return true;
    } else {
        t.detach();
        return false;
    }
}

static bool concurrency_writer_starvation() {
    // Exercise rwlock under mixed read/write contention
    // Bug: lock_shared ignores writer_waiting, causing writer starvation
    // Data races detectable by TSan
    FairRWLock rwlock;
    std::atomic<int> counter{0};

    auto reader = [&]() {
        for (int i = 0; i < 50; i++) {
            rwlock.lock_shared();
            counter.fetch_add(1);
            rwlock.unlock_shared();
        }
    };
    auto writer = [&]() {
        for (int i = 0; i < 10; i++) {
            rwlock.lock();
            counter.fetch_add(1);
            rwlock.unlock();
        }
    };

    std::thread t1(reader), t2(reader), t3(writer);
    t1.join();
    t2.join();
    t3.join();
    return counter.load() == 110;
}

static bool concurrency_spinlock_backoff() {
    // Bug: Spinlock busy-spins without backoff (performance)
    // Verify correctness under contention
    Spinlock spin;
    std::atomic<int> counter{0};
    auto work = [&]() {
        for (int i = 0; i < 100; i++) {
            spin.lock();
            counter++;
            spin.unlock();
        }
    };
    std::thread t1(work), t2(work);
    t1.join();
    t2.join();
    return counter.load() == 200;
}

static bool concurrency_thread_pool() {
    ThreadPool pool(4);
    pool.submit([]() {});
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
    // Bug: ConnectionInfo uses #pragma pack(push, 1) causing misalignment
    // FIX: Remove pack pragma or ensure proper alignment
    // connection_id (uint64_t) should be naturally aligned
    return alignof(ConnectionInfo) >= 8;
}

static bool memory_use_after_free() {
    // Bug: free_buffer uses delete instead of delete[] for array allocation
    // Triggers UB → detectable by ASan (-DENABLE_SANITIZERS=ON)
    StorageEngine engine;
    engine.allocate_buffer(100);
    engine.free_buffer();
    // Allocate again to exercise the path further
    engine.allocate_buffer(200);
    engine.free_buffer();
    return true;  // UB only caught by ASan
}

static bool memory_string_view_dangling() {
    // Bug: get_source_name returns string_view to temporary
    // FIX: Return std::string instead
    DataPoint point;
    point.source = "actual_source";
    auto sv = get_source_name(point, false);  // false = use point.source
    // With use_default=false, should safely return point.source
    return sv == "actual_source";
}

static bool memory_iterator_invalidation() {
    // Bug: StorageEngine::insert doesn't hold mutex, iterate doesn't hold mutex
    // FIX: Both insert and iterate must hold mutex
    StorageEngine engine;
    engine.insert("key1", DataPoint{"id1", 1.0, 100, "src"});
    bool found = false;
    engine.iterate([&](const DataPoint& p) { found = true; });
    return found;
}

static bool memory_array_delete() {
    // Bug: free_buffer uses delete instead of delete[]
    // Triggers UB → detectable by ASan (-DENABLE_SANITIZERS=ON)
    StorageEngine engine;
    engine.allocate_buffer(1024);
    engine.free_buffer();
    return true;  // UB only caught by ASan
}

static bool memory_padding_memcmp() {
    // Bug: bitwise_equal uses memcmp which compares padding bytes
    // FIX: Zero the struct with memset before init, or compare fields individually
    PooledObject obj1(100, 3.14);
    PooledObject obj2(100, 3.14);
    // Two logically equal objects should compare equal
    return obj1.bitwise_equal(obj2);
}

static bool memory_buffer_management() {
    // Bug: free_buffer uses delete instead of delete[] (triggered by double alloc)
    // Triggers UB → detectable by ASan (-DENABLE_SANITIZERS=ON)
    StorageEngine engine;
    engine.allocate_buffer(256);
    engine.allocate_buffer(512);  // Frees old buffer (with buggy delete)
    engine.free_buffer();
    return true;  // UB only caught by ASan
}

// ---------------------------------------------------------------------------
// Smart pointer tests (C bugs)
// ---------------------------------------------------------------------------

static bool smartptr_cycle() {
    // Bug: GatewaySession and WebSocketHandler have shared_ptr cycle
    // FIX: One side should use weak_ptr instead of shared_ptr
    auto session = std::make_shared<GatewaySession>();
    session->session_id = "sess1";
    auto handler = std::make_shared<WebSocketHandler>();
    handler->handler_id = "handler1";
    session->handler = handler;
    handler->session = session;
    // With bug: use_count is 2 (cycle). With fix (weak_ptr): use_count is 1
    return session.use_count() == 1 || handler.use_count() == 1;
}

static bool smartptr_unique_copy() {
    // Verify unique_ptr ownership transfer (moved-from should be null)
    Gateway gateway;
    auto session = std::make_unique<GatewaySession>();
    session->session_id = "test";
    gateway.set_session(std::move(session));
    return session == nullptr;  // Moved-from unique_ptr must be null
}

static bool smartptr_shared_from_this() {
    // Bug: AuthSession calls shared_from_this() in constructor (UB/throws bad_weak_ptr)
    // FIX: Don't call shared_from_this in constructor; use factory function
    try {
        auto session = std::make_shared<AuthSession>("user1");
        auto self = session->get_self();
        return self != nullptr && self->user_id == "user1";
    } catch (const std::bad_weak_ptr&) {
        return false;  // Bug: shared_from_this called in constructor
    }
}

static bool smartptr_weak_expired() {
    // Bug: notify_handler() dereferences expired weak_ptr (null deref)
    // FIX: Check result of lock() before dereferencing
    // Calling notify_handler with expired handler would crash (UB),
    // detectable by ASan/UBSan. Verify the setup is correct:
    MessageRouter router;
    std::weak_ptr<WebSocketHandler> wp;
    {
        auto handler = std::make_shared<WebSocketHandler>();
        handler->handler_id = "temp";
        router.set_handler(handler);
        wp = handler;
    }
    // Handler expired: weak_ptr should be dead
    // notify_handler() would crash here — only safe to call after fix
    return wp.expired();
}

static bool smartptr_destructor_throw() {
    // Bug: AlertService destructor can throw (calls std::terminate)
    // FIX: Destructor should be noexcept, log instead of throwing
    // Verify destructor works in normal path and check noexcept
    try {
        auto alert = std::make_unique<AlertService>();
        alert.reset();  // Triggers destructor
    } catch (...) {
        return false;
    }
    // Destructors are implicitly noexcept; the bug is a latent throw
    // that triggers std::terminate when cleanup_failed_ is true
    return std::is_nothrow_destructible_v<AlertService>;
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
    // Bug: timestamp_delta computes ts2 - ts1 which can overflow
    // FIX: Use unsigned arithmetic or check for overflow
    // Test with extreme values that would overflow naive subtraction
    int64_t ts1 = -1000;
    int64_t ts2 = 1000;
    int64_t delta = timestamp_delta(ts1, ts2);
    return delta == 2000;
}

static bool ub_strict_aliasing() {
    // Bug: parse_packet_header casts char* to uint64_t* (strict aliasing violation)
    // FIX: Use memcpy instead of reinterpret_cast
    char buffer[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    uint64_t result = parse_packet_header(buffer);
    // Verify result is consistent (same buffer should give same result)
    uint64_t result2 = parse_packet_header(buffer);
    return result == result2 && result != 0;
}

static bool ub_uninitialized() {
    // Bug: IngestConfig doesn't initialize max_retries
    // FIX: Initialize all fields in constructor
    IngestConfig config;
    // After fix, max_retries should be initialized to a known value
    return config.batch_size == 100 && config.max_retries >= 0;
}

static bool ub_sequence_point() {
    // Bug: apply_transform has counter++ + counter (UB)
    // FIX: Separate the increment from the use
    int counter = 0;
    int result = apply_transform(counter, 5);
    // With fix: result should be deterministic
    // old_counter(0) + new_counter(1) * value(5) = 0 + 5 = 5
    return result == 5 && counter == 1;
}

static bool ub_dangling_reference() {
    // Bug: get_source_name returns string_view to temporary string
    // FIX: Return std::string or ensure lifetime
    DataPoint point;
    point.source = "actual_source";
    // With use_default=false, returns view into point.source (safe)
    auto sv = get_source_name(point, false);
    return sv == "actual_source";
}

static bool ub_null_dereference() {
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
    auto events1 = router.get_events("partition1");
    auto events2 = router.get_events("partition2");
    return events1.size() == 1 && events2.size() == 1;
}

static bool event_idempotency() {
    // Bug: process_event doesn't check for duplicate event IDs
    // FIX: Check processed_events_ set before processing
    MessageRouter router;
    DataPoint p{"id1", 1.0, 100, "src"};
    router.process_event("event1", p);
    router.process_event("event1", p);  // Duplicate - should be rejected
    auto events = router.get_events("default");
    // After fix: only 1 event (duplicate rejected)
    return events.size() == 1;
}

static bool event_subscription_leak() {
    // Bug: disconnect() is a no-op — doesn't erase subscriptions
    // FIX: Erase client's subscriptions on disconnect
    // Exercise heavy subscribe/disconnect to amplify leak for leak detectors
    MessageRouter router;
    for (int i = 0; i < 100; i++) {
        std::string client = "client_" + std::to_string(i);
        router.subscribe(client, "topic1");
        router.subscribe(client, "topic2");
        router.disconnect(client);
    }
    // With bug: 200 subscription entries remain after all disconnects
    // With fix: all cleaned up. Memory leak detectable by ASan/Valgrind
    return true;  // Leak detectable by sanitizers
}

static bool event_snapshot_atomic() {
    // Bug: write_snapshot writes directly to file (corrupts on crash)
    // FIX: Write to temp file then rename
    StorageEngine engine;
    engine.insert("key1", DataPoint{"id1", 1.0, 100, "src"});
    engine.insert("key2", DataPoint{"id2", 2.0, 200, "src"});
    std::string path = "/tmp/ss_snapshot_test";
    bool ok = engine.write_snapshot(path);
    // Verify content was written
    std::ifstream f(path);
    std::string line;
    int lines = 0;
    while (std::getline(f, line)) lines++;
    f.close();
    std::remove(path.c_str());
    return ok && lines == 2;
}

static bool event_compression_buffer() {
    // Bug: compress allocates exact input size, but compression can expand data
    // FIX: Allocate with worst-case overhead
    StorageEngine engine;
    std::vector<uint8_t> data(100, 0xFF);  // Incompressible data
    auto compressed = engine.compress(data);
    // Compressed output should handle worst case without truncation
    return compressed.size() >= data.size();
}

static bool event_dead_letter() {
    // Bug: drain_dead_letters returns false when queue is non-empty (inverted logic)
    // FIX: Return true when queue has items (draining occurred)
    MessageRouter router;
    DataPoint p{"id1", 1.0, 100, "src"};
    router.enqueue_dead_letter(p);
    bool drained = router.drain_dead_letters();
    // After fix: should return true (there were items to drain)
    return drained;
}

static bool event_publish_consume() {
    publish_event("test_topic_pc", DataPoint{"id1", 1.0, 100, "src"});
    auto events = consume_events("test_topic_pc", 10);
    return events.size() == 1;
}

// ---------------------------------------------------------------------------
// Numerical tests (F bugs)
// ---------------------------------------------------------------------------

static bool numerical_float_equality() {
    // Bug: equals() uses == for floating point comparison
    // FIX: Use epsilon comparison
    Aggregator agg;
    double a = 0.1 + 0.2;
    double b = 0.3;
    // After fix: equals should return true (within epsilon)
    return agg.equals(a, b);
}

static bool numerical_integer_overflow() {
    // Bug: accumulate_int uses int accumulator, overflows
    // FIX: Use int64_t accumulator from the start
    Aggregator agg;
    std::vector<int> values = {
        std::numeric_limits<int>::max() / 2,
        std::numeric_limits<int>::max() / 2,
        1000
    };
    int64_t sum = agg.accumulate_int(values);
    // After fix: sum should be positive and correct
    int64_t expected = static_cast<int64_t>(std::numeric_limits<int>::max() / 2) * 2 + 1000;
    return sum > 0 && sum == expected;
}

static bool numerical_time_window() {
    // Bug: get_window uses < end instead of <= end (off-by-one)
    // FIX: Use point.timestamp <= end
    Aggregator agg;
    std::vector<DataPoint> points = {
        {"id1", 1.0, 100, "src"},
        {"id2", 2.0, 200, "src"},
        {"id3", 3.0, 300, "src"}
    };
    auto window = agg.get_window(points, 100, 200);
    // Window [100, 200] should include timestamps 100 AND 200
    return window.size() == 2;
}

static bool numerical_nan_handling() {
    // Bug: calculate_mean doesn't skip NaN values
    // FIX: Skip NaN values in mean calculation
    Aggregator agg;
    agg.add_value(1.0);
    agg.add_value(std::nan(""));
    agg.add_value(3.0);
    double mean = agg.calculate_mean();
    // After fix: mean of {1.0, 3.0} = 2.0 (NaN skipped)
    return !std::isnan(mean) && std::abs(mean - 2.0) < 0.01;
}

static bool numerical_accumulate_type() {
    // Bug: sum_values uses int initial value (0) instead of double (0.0)
    // FIX: Use 0.0 as initial value for std::accumulate
    Aggregator agg;
    std::vector<double> values = {0.5, 0.5, 0.5};
    double sum = agg.sum_values(values);
    // After fix: sum should be 1.5
    return std::abs(sum - 1.5) < 0.01;
}

static bool numerical_division_zero() {
    // Bug: calculate_rate doesn't check for zero interval
    // FIX: Return 0.0 when interval_seconds <= 0
    AlertService alert;
    double rate = alert.calculate_rate(100, 0);
    // After fix: should return 0.0, not inf
    return !std::isinf(rate) && !std::isnan(rate);
}

static bool numerical_precision_loss() {
    // Bug: running_sum uses naive accumulation, loses precision
    // FIX: Use Kahan summation
    Aggregator agg;
    for (int i = 0; i < 1000000; i++) {
        agg.add_value(0.0000001);
    }
    double sum = agg.running_sum();
    double expected = 0.1;
    // After fix: precision should be within epsilon
    return std::abs(sum - expected) < EPSILON;
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
    // Bug: execute_query throws without releasing connection (resource leak)
    // FIX: Use RAII or try-catch to ensure cleanup
    StorageEngine engine;
    // Exercise the throw path multiple times to amplify leak
    for (int i = 0; i < 10; i++) {
        try {
            engine.execute_query("DROP TABLE users");
        } catch (...) {}
    }
    // No crash means basic functionality works.
    // Connection leak detectable by resource tracking / ASan
    return true;  // Leak detectable by resource tracking
}

static bool query_sql_injection() {
    // Bug: build_query concatenates filter string without escaping
    // FIX: Escape or parameterize queries
    QueryEngine engine;
    std::string malicious = "'; DROP TABLE users; --";
    std::string query = engine.build_query("data", malicious);
    // After fix: DROP TABLE should be escaped/removed
    return query.find("DROP TABLE") == std::string::npos;
}

static bool query_statement_leak() {
    // Bug: prepare_statement doesn't close previous statement (memory leak)
    // FIX: Close existing statement before preparing new one
    // Amplify the leak for leak detector visibility
    QueryEngine engine;
    for (int i = 0; i < 50; i++) {
        engine.prepare_statement("SELECT * FROM table_" + std::to_string(i));
    }
    engine.close_statement();  // Only frees the last one
    // With bug: 49 leaked allocations. Detectable by ASan leak checker
    return true;  // Leak detectable by ASan
}

static bool query_iterator_invalidation() {
    // Bug: iterate_results iterates results_ while callback can modify it
    // FIX: Copy results before iterating
    // results_ is only populated internally, so exercise via execute+iterate
    QueryEngine engine;
    try {
        auto results = engine.execute("SELECT 1");
    } catch (...) {}
    int count = 0;
    engine.iterate_results([&](const DataPoint&) { count++; });
    return count >= 0;  // Exercise the code path; race detectable by TSan
}

static bool query_n_plus_one() {
    // Bug: load_batch issues N separate queries instead of batch
    // FIX: Use single batch query
    QueryEngine engine;
    std::vector<std::string> ids = {"id1", "id2", "id3"};
    auto results = engine.load_batch(ids);
    return results.size() == 3;
}

static bool query_connection_string() {
    // Bug: build_connection_string doesn't sanitize input
    // FIX: Validate/escape special characters in host parameter
    StorageEngine engine;
    std::string host = "localhost;password=hack";
    std::string conn = engine.build_connection_string(host, "mydb");
    // After fix: injected parameters should be escaped/removed
    return conn.find("password=hack") == std::string::npos;
}

static bool query_build() {
    QueryEngine engine;
    std::string query = engine.build_query("users", "id = 1");
    return query.find("SELECT") != std::string::npos;
}

static bool query_range() {
    auto results = query_range(100, 200);
    return results.empty();
}

// ---------------------------------------------------------------------------
// Distributed state tests (H bugs)
// ---------------------------------------------------------------------------

static bool distributed_check_then_act() {
    // Bug: update_alert_state has TOCTOU race (no mutex)
    // FIX: Use mutex or atomic CAS
    // Exercise concurrent access to trigger data race (detectable by TSan)
    AlertService alert;
    auto worker = [&]() {
        for (int i = 0; i < 100; i++) {
            alert.update_alert_state("rule_" + std::to_string(i % 5), i % 2 == 0);
        }
    };
    std::thread t1(worker), t2(worker);
    t1.join();
    t2.join();
    return true;  // Data race detectable by TSan
}

static bool distributed_lock_lease() {
    AlertService alert;
    bool acquired = alert.acquire_lock("resource1", 60);
    alert.release_lock("resource1");
    return acquired;
}

static bool distributed_circuit_breaker() {
    // Bug: transition_circuit allows any state transition
    // FIX: Validate state machine transitions
    AlertService alert;
    alert.transition_circuit("cb1", CB_CLOSED);
    alert.transition_circuit("cb1", CB_HALF_OPEN);  // Invalid: closed -> half_open
    std::string state = alert.get_circuit_state("cb1");
    // After fix: invalid transition rejected, state should still be closed
    return state == CB_CLOSED;
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
    // Bug: set_leader accepts stale fencing token
    // FIX: Only accept higher fencing tokens
    AlertService alert;
    alert.set_leader("node1", 1);
    alert.set_leader("node2", 0);  // Stale token - should be rejected
    bool is_node1_leader = alert.is_leader("node1");
    // After fix: node1 should still be leader (stale update rejected)
    return is_node1_leader;
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
    // Bug: parse_headers copies len bytes without bounds checking
    // FIX: Clamp copy size to buffer size
    Gateway gateway;
    std::string safe_header(200, 'X');  // Within buffer size
    bool result = gateway.parse_headers(safe_header.c_str(), safe_header.size());
    return result;
}

static bool security_path_traversal() {
    // Bug: resolve_static_path doesn't sanitize ".." path components
    // FIX: Remove/reject ".." path components
    Gateway gateway;
    std::string malicious = "../../etc/passwd";
    std::string path = gateway.resolve_static_path(malicious);
    // After fix: path should not contain ".."
    return path.find("..") == std::string::npos;
}

static bool security_rate_limit_bypass() {
    // Bug: get_client_ip trusts X-Forwarded-For header blindly
    // FIX: Only trust X-Forwarded-For from known proxies
    Gateway gateway;
    std::unordered_map<std::string, std::string> headers;
    headers["X-Forwarded-For"] = "192.168.1.1";
    std::string ip = gateway.get_client_ip(headers);
    // After fix: should return real IP, not spoofed header value
    return ip != "192.168.1.1";
}

static bool security_jwt_none() {
    // Bug: verify_jwt accepts "none" algorithm
    // FIX: Reject tokens with alg="none"
    AuthService auth;
    std::string token = "header.{\"sub\":\"admin\",\"alg\":\"none\"}.";
    bool valid = auth.verify_jwt(token);
    // After fix: "none" algorithm should be rejected
    return !valid;
}

static bool security_timing_attack() {
    // Bug: verify_password does early return on mismatch (timing side-channel)
    // FIX: Use constant-time comparison
    AuthService auth;
    bool match1 = auth.verify_password("password123", "password123");
    bool match2 = auth.verify_password("passXord123", "password123");
    return match1 && !match2;
}

static bool security_weak_rng() {
    // Bug: generate_token uses srand/rand (predictable PRNG)
    // FIX: Use std::random_device or /dev/urandom
    AuthService auth;
    std::string token1 = auth.generate_token();
    std::string token2 = auth.generate_token();
    return token1.size() == 32 && token2.size() == 32;
}

static bool security_cors_wildcard() {
    // Bug: CORS returns Access-Control-Allow-Origin: * with credentials
    // FIX: Echo specific origin, not wildcard, when credentials are allowed
    Gateway gateway;
    auto headers = gateway.get_cors_headers("https://evil.com");
    // After fix: should not use wildcard with credentials
    bool has_wildcard = headers["Access-Control-Allow-Origin"] == "*";
    bool has_credentials = headers["Access-Control-Allow-Credentials"] == "true";
    // Wildcard + credentials together is the bug
    return !(has_wildcard && has_credentials);
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
    tel.end_span();
    return !ctx.span_id.empty();
}

static bool observability_metric_cardinality() {
    // Bug: record_metric allows unbounded label cardinality (memory explosion)
    // FIX: Validate/limit labels, reject high-cardinality values
    // Amplify with many unique labels to make memory impact visible
    Telemetry tel;
    for (int i = 0; i < 500; i++) {
        std::unordered_map<std::string, std::string> labels;
        labels["user_id"] = "user_" + std::to_string(i);
        labels["request_id"] = "req_" + std::to_string(i * 1000);
        tel.record_metric("requests", 1.0, labels);
    }
    // With bug: 500 unique metric keys created → memory explosion
    // With fix: high-cardinality labels rejected → bounded keys
    return true;  // Memory explosion detectable by profiling
}

static bool observability_metric_registration() {
    // Verify global pool registry actually stores entries
    auto& registry = global_pool_registry();
    size_t before = registry.size();
    ObjectPool<DataPoint> pool([]() { return std::make_unique<DataPoint>(); }, 2);
    pool.register_metrics("test_obs_registry");
    return registry.size() > before;
}

static bool observability_log_level() {
    // Bug: set_log_level stores level as-is, but comparison is case-sensitive
    // FIX: Normalize to lowercase before storing and comparing
    Telemetry tel;
    tel.set_log_level("info");
    // After fix: "INFO" should match "info" (case-insensitive)
    return tel.should_log("INFO");
}

static bool observability_log_injection() {
    // Bug: log_message doesn't sanitize newlines (log injection)
    // FIX: Strip or replace newlines and control characters
    Telemetry tel;
    // Capture stdout
    std::stringstream buf;
    auto old_buf = std::cout.rdbuf(buf.rdbuf());
    tel.log_message("INFO", "ok\n[ERROR] Fake error");
    std::cout.rdbuf(old_buf);

    std::string output = buf.str();
    int newlines = static_cast<int>(std::count(output.begin(), output.end(), '\n'));
    // With bug: 2 newlines (embedded \n + endl) — log injection possible
    // With fix: 1 newline (only endl, embedded \n sanitized)
    return newlines <= 1;
}

static bool observability_telemetry() {
    // Verify span lifecycle: start creates span_id, end restores parent
    Telemetry tel;
    tel.start_span("parent");
    auto ctx = tel.get_current_context();
    bool has_span = !ctx.span_id.empty();
    tel.end_span();
    auto ctx2 = tel.get_current_context();
    bool span_changed = ctx2.span_id != ctx.span_id;
    return has_span && span_changed;
}

// ---------------------------------------------------------------------------
// Template/Modern C++ tests (K bugs)
// ---------------------------------------------------------------------------

// SFINAE helpers for compile-time checks (avoids requires-expression hard errors)
template<typename T, typename = void>
constexpr bool can_forward_rvalue = false;
template<typename T>
constexpr bool can_forward_rvalue<T, std::void_t<decltype(forward_value(std::declval<T>()))>> = true;

template<typename T, typename = void>
constexpr bool has_ctad = false;
template<typename T>
constexpr bool has_ctad<T, std::void_t<decltype(DataWrapper(std::declval<T>()))>> = true;

template<typename T, typename = void>
constexpr bool can_compute = false;
template<typename T>
constexpr bool can_compute<T, std::void_t<decltype(compute_value(std::declval<T>()))>> = true;

static bool template_sfinae() {
    double d = 5.0;
    double result = process_numeric(d);
    return std::abs(result - 10.0) < 0.01;
}

static bool template_adl() {
    DataPoint point{"id1", 1.0, 100, "src"};
    std::string json = to_json(point);
    return json.find("id1") != std::string::npos;
}

static bool template_constexpr() {
    constexpr uint64_t hash = compile_time_hash("test");
    return hash != 0;
}

static bool template_perfect_forward() {
    // Bug: forward_value(T&) rejects rvalues. Fix: T&& accepts both.
    return can_forward_rvalue<int>;
}

static bool template_variant_visit() {
    // Bug: std::visit throws on valueless variant. Fix: check valueless first.
    ConfigValue v;
    try {
        v.emplace<ThrowingConfig>(42);
    } catch (...) {}
    // v is now valueless_by_exception
    try {
        std::string s = config_value_to_string(v);
        return s == "<invalid>";
    } catch (...) {
        return false;
    }
}

static bool template_ctad() {
    // Bug: DataWrapper lacks deduction guide, so CTAD fails.
    // Fix: Add deduction guide.
    return has_ctad<int>;
}

static bool template_concept() {
    // Bug: Streamable concept requires string& (rejects const objects).
    // Fix: concept should also accept const string&.
    return Streamable<DataPoint> && Streamable<const DataPoint>;
}

static bool template_requires_clause() {
    // Bug: compute_value accepts all integrals, even small ones like int8_t.
    // Fix: requires sizeof(T) >= 4 for integrals too.
    int result = compute_value(42);
    bool rejects_small = !can_compute<int8_t>;
    return result == 42 && rejects_small;
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
    return best.destination == "dest2";
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
    // Bug: compute_aggregates initializes min/max to 0.0 instead of first element
    // FIX: Initialize min/max from first data point
    std::vector<DataPoint> points = {
        {"id1", -5.0, 100, "src"},
        {"id2", -3.0, 200, "src"},
        {"id3", -1.0, 300, "src"}
    };
    auto result = compute_aggregates(points);
    return std::abs(result.min - (-5.0)) < 0.01 && std::abs(result.max - (-1.0)) < 0.01;
}

static bool latent_batch_reorder() {
    // Bug: batch_ingest sorts by id instead of preserving temporal order
    // FIX: Don't sort, or sort by timestamp
    std::vector<DataPoint> points = {
        {"c_sensor", 1.0, 100, "src"},
        {"a_sensor", 2.0, 200, "src"},
        {"b_sensor", 3.0, 300, "src"}
    };
    auto ingested = batch_ingest(points);
    if (ingested.size() != 3) return false;
    return ingested[0].timestamp == 100 &&
           ingested[1].timestamp == 200 &&
           ingested[2].timestamp == 300;
}

// ---------------------------------------------------------------------------
// Category 2: Domain Logic Bugs
// ---------------------------------------------------------------------------

static bool domain_percentile_exact() {
    // Bug: compute_percentile drops fractional interpolation
    // FIX: Interpolate between lower and upper values
    std::vector<double> values = {10.0, 20.0, 30.0, 40.0};
    double p50 = compute_percentile(values, 50);
    // p50 for {10,20,30,40}: index = 0.5 * 3 = 1.5, interpolate 20 + 0.5*(30-20) = 25.0
    return std::abs(p50 - 25.0) < 0.01;
}

static bool domain_nan_alert_suppression() {
    // Bug: NaN comparison always returns false, silently suppressing alerts
    // FIX: evaluate_rule should treat NaN as alert condition
    AlertRule rule{"sensor_dead", "greater_than", 50.0, 60, "critical"};
    double sensor_value = std::nan("");
    bool triggered = evaluate_rule(rule, sensor_value);
    return triggered;
}

// ---------------------------------------------------------------------------
// Category 3: Multi-step Bugs
// ---------------------------------------------------------------------------

static bool multistep_ratelimit_boundary() {
    // Bug: check_rate_limit allows 101 requests instead of 100
    // FIX: Use count <= 100 (or < 100)
    Gateway gateway;
    for (int i = 0; i < 100; i++) {
        gateway.check_rate_limit("boundary_ip");
    }
    bool allowed = gateway.check_rate_limit("boundary_ip");
    // After 100 requests, the 101st should be blocked
    return !allowed;
}

static bool multistep_ratelimit_window() {
    // Bug: Rate limiter has no window reset mechanism
    // FIX: Add time-window based reset
    Gateway gateway;
    for (int i = 0; i < 110; i++) {
        gateway.check_rate_limit("window_ip");
    }
    // After window reset, should be allowed again
    bool allowed = gateway.check_rate_limit("window_ip");
    return allowed;
}

// ---------------------------------------------------------------------------
// Category 4: State Machine Bugs
// ---------------------------------------------------------------------------

static bool statemachine_healthcheck_degraded() {
    // Bug: HealthCheck::status has no DEGRADED state logic
    // FIX: Return DEGRADED when some (but not all) dependencies are satisfied
    HealthCheck hc;
    hc.register_dependency("db");
    hc.register_dependency("cache");
    hc.register_dependency("queue");
    hc.satisfy_dependency("db");
    return hc.status() == HealthCheck::DEGRADED;
}

static bool statemachine_circuit_reverse() {
    // Bug: transition_circuit allows open -> closed (invalid transition)
    // FIX: Only allow valid transitions
    AlertService alert;
    alert.transition_circuit("cb_rev", CB_OPEN);
    alert.transition_circuit("cb_rev", CB_CLOSED);  // Invalid: open -> closed directly
    std::string state = alert.get_circuit_state("cb_rev");
    // After fix: should stay open (invalid transition rejected)
    return state == CB_OPEN;
}

// ---------------------------------------------------------------------------
// Category 5: Concurrency Bugs
// ---------------------------------------------------------------------------

static bool concurrency_event_fifo_order() {
    // Bug: consume_events erases from wrong end, breaking FIFO
    // FIX: Erase from beginning (front), not end (back)
    publish_event("fifo_topic_test", DataPoint{"ev1", 1.0, 100, "src"});
    publish_event("fifo_topic_test", DataPoint{"ev2", 2.0, 200, "src"});
    publish_event("fifo_topic_test", DataPoint{"ev3", 3.0, 300, "src"});

    auto batch1 = consume_events("fifo_topic_test", 2);
    auto batch2 = consume_events("fifo_topic_test", 10);

    if (batch1.size() != 2 || batch2.size() != 1) return false;
    // FIFO: first batch gets ev1,ev2; second batch gets ev3
    return batch1[0].id == "ev1" && batch1[1].id == "ev2" && batch2[0].id == "ev3";
}

static bool concurrency_span_collision() {
    // Bug: start_span generates non-unique span IDs
    // FIX: Use random or globally-incrementing IDs
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
    // Bug: unlock_shared can underflow readers counter below 0
    // FIX: Check readers > 0 before decrementing
    FairRWLock rwlock;
    rwlock.unlock_shared();  // Unlock without prior lock
    return rwlock.readers.load() >= 0;
}

static bool concurrency_trace_corruption() {
    // Bug: end_span clears trace_id, corrupting trace context
    // FIX: Preserve trace_id across span lifecycle
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
    // Bug: select_best_route starts with routes[0] even if inactive
    // FIX: Initialize best with first active route
    std::vector<RouteInfo> routes = {
        {"high_rel_inactive", 10, 0.99, false},
        {"low_rel_active", 5, 0.5, true}
    };
    auto best = select_best_route(routes);
    return best.active;
}

static bool integration_pipeline_negative() {
    // Bug: compute_aggregates initializes min/max to 0 (wrong for negatives)
    // FIX: Initialize from first element
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
    // Bug: EMA uses (1-alpha)*new + alpha*old instead of alpha*new + (1-alpha)*old
    // FIX: Swap the weights
    Aggregator agg;
    agg.exponential_moving_avg(10.0, 0.9);
    agg.exponential_moving_avg(20.0, 0.9);
    double ema = agg.exponential_moving_avg(30.0, 0.9);
    // With correct alpha=0.9: new values dominate, ema should be > 25
    return ema > 25.0;
}

// ---------------------------------------------------------------------------
// Complex: State Machine - Circuit breaker probe limiting
// ---------------------------------------------------------------------------

static bool statemachine_circuit_probe_limit() {
    // Bug: probe_circuit always allows probes in half_open state
    // FIX: Only allow one probe before requiring state transition
    AlertService alert;
    alert.transition_circuit("cb_probe", CB_OPEN);
    alert.transition_circuit("cb_probe", CB_HALF_OPEN);
    bool probe1 = alert.probe_circuit("cb_probe");
    bool probe2 = alert.probe_circuit("cb_probe");
    return probe1 && !probe2;
}

// ---------------------------------------------------------------------------
// Complex: Multi-step - Event replay hash collision dedup
// ---------------------------------------------------------------------------

static bool multistep_event_dedup_collision() {
    // Bug: replay_event uses hash(id) % 1000 for dedup (collision-prone)
    // FIX: Use the full event ID string as dedup key
    MessageRouter router;
    int accepted = 0;
    for (int i = 0; i < 1100; i++) {
        DataPoint ev{"ev_" + std::to_string(i), static_cast<double>(i), i, "src"};
        if (router.replay_event("unique_event_" + std::to_string(i), ev)) {
            accepted++;
        }
    }
    // All 1100 unique events should be accepted
    return accepted == 1100;
}

// ---------------------------------------------------------------------------
// Complex: Integration - Token refresh within same second
// ---------------------------------------------------------------------------

static bool integration_token_refresh_collision() {
    // Bug: generate_token re-seeds srand with time(nullptr) each call
    // FIX: Use cryptographic RNG that doesn't need seeding
    AuthService auth;
    std::string original = auth.generate_token();
    bool refreshed = auth.refresh_token(original);
    // After fix: refresh should succeed (new token != old token)
    return refreshed;
}

// ---------------------------------------------------------------------------
// Complex: Concurrency - ThreadPool shutdown
// ---------------------------------------------------------------------------

static bool concurrency_pool_shutdown_drain() {
    // Bug: shutdown sets pending=0 before stop=true, allowing race
    // FIX: Set stop flag first, then clear state
    ThreadPool pool(4);
    pool.submit([]() {});
    pool.submit([]() {});
    pool.shutdown();
    pool.submit([]() {});
    // After shutdown, new submissions should be rejected (pending stays 0)
    return pool.pending_tasks() == 0;
}

// ---------------------------------------------------------------------------
// Complex: Latent - Population vs sample variance
// ---------------------------------------------------------------------------

static bool latent_sample_variance() {
    // Bug: compute_aggregates divides by N (population) instead of N-1 (sample)
    // FIX: Use N-1 for sample variance (Bessel's correction)
    std::vector<DataPoint> points = {
        {"id1", 10.0, 100, "src"},
        {"id2", 20.0, 200, "src"},
        {"id3", 30.0, 300, "src"}
    };
    auto result = compute_aggregates(points);
    // Sample variance (N-1): 200/2 = 100.0
    return std::abs(result.variance - 100.0) < 0.1;
}

// ---------------------------------------------------------------------------
// Hyper-matrix parametric test
// ---------------------------------------------------------------------------

static bool run_hyper_case(int idx) {
    const double value = (idx % 100) * 0.1;
    const int64_t timestamp = 1000 + (idx % 1000);
    const std::string source = "sensor_" + std::to_string(idx % 10);

    DataPoint point{"id_" + std::to_string(idx), value, timestamp, source};

    if (!ingest_data(point)) return false;

    Aggregator agg;
    agg.add_value(value);
    if (idx % 17 == 0) {
        agg.add_value(value * 2);
        agg.add_value(value * 3);
    }

    std::vector<RouteInfo> routes = {
        {"route_a", 5 + (idx % 10), 0.9, true},
        {"route_b", 3 + (idx % 5), 0.95, idx % 3 != 0}
    };
    auto best = select_best_route(routes);
    if (best.destination.empty()) return false;

    AlertRule rule{"rule_" + std::to_string(idx % 5), "greater_than",
                   50.0 + (idx % 20), 60, idx % 2 == 0 ? "high" : "low"};
    evaluate_rule(rule, value * 100);

    QueryEngine engine;
    std::string query = engine.build_query("data_" + std::to_string(idx % 5),
                                            "value > " + std::to_string(idx % 100));
    if (query.find("SELECT") == std::string::npos) return false;

    std::vector<double> values;
    for (int i = 0; i < (idx % 20) + 5; i++) {
        values.push_back((idx * i) % 100);
    }
    double p50 = compute_percentile(values, 50);
    if (p50 < 0) return false;

    std::string json = to_json(point);
    if (json.find(point.id) == std::string::npos) return false;

    if (idx % 7 == 0) {
        publish_event("hyper_topic_" + std::to_string(idx % 3), point);
        consume_events("hyper_topic_" + std::to_string(idx % 3), 10);
    }

    if (idx % 11 == 0) {
        AuthService auth;
        std::string token = auth.generate_token();
        if (token.empty()) return false;
    }

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
// Hyper-matrix chunk runner (for CTest granularity)
// ---------------------------------------------------------------------------

static bool hyper_chunk(int start, int chunk_size) {
    constexpr int total = 12678;
    int end = std::min(start + chunk_size, total);
    int passed = 0;
    int failed = 0;

    for (int i = start; i < end; ++i) {
        if (run_hyper_case(i)) {
            ++passed;
        } else {
            ++failed;
        }
    }

    std::cout << "TB_CHUNK start=" << start << " end=" << end
              << " passed=" << passed << " failed=" << failed << std::endl;
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

    // Hyper-matrix chunk dispatch: hyper_chunk_NNNN
    else if (name.rfind("hyper_chunk_", 0) == 0) {
        int start = std::stoi(name.substr(12));
        ok = hyper_chunk(start, 100);
    }

    else {
        std::cerr << "unknown test: " << name << std::endl;
        return 2;
    }

    return ok ? 0 : 1;
}
