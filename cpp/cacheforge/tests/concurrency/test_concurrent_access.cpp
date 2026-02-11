#include <gtest/gtest.h>
#include "storage/hashtable.h"
#include "storage/eviction.h"
#include "storage/expiry.h"
#include <thread>
#include <vector>
#include <atomic>

using namespace cacheforge;

// ========== Bug A1: Data race on connections vector ==========

TEST(ConcurrencyTest, test_concurrent_set_no_race) {
    
    // This test verifies thread-safe access to the hashtable
    HashTable ht(10000);
    std::atomic<int> errors{0};
    const int num_threads = 4;
    const int ops_per_thread = 100;

    std::vector<std::thread> threads;
    for (int t = 0; t < num_threads; ++t) {
        threads.emplace_back([&ht, &errors, t, ops_per_thread]() {
            for (int i = 0; i < ops_per_thread; ++i) {
                std::string key = "t" + std::to_string(t) + "_k" + std::to_string(i);
                ht.set(key, Value("value"));
                auto val = ht.get(key);
                if (!val.has_value()) {
                    errors.fetch_add(1);
                }
            }
        });
    }

    for (auto& t : threads) t.join();
    EXPECT_EQ(errors.load(), 0) << "Data race detected in concurrent access";
}

TEST(ConcurrencyTest, test_concurrent_set_and_get_no_crash) {
    
    HashTable ht;
    std::atomic<bool> running{true};

    // Writer thread
    std::thread writer([&]() {
        for (int i = 0; i < 500 && running.load(); ++i) {
            ht.set("key_" + std::to_string(i % 10), Value("val_" + std::to_string(i)));
        }
    });

    // Reader thread
    std::thread reader([&]() {
        for (int i = 0; i < 500 && running.load(); ++i) {
            ht.get("key_" + std::to_string(i % 10));
        }
    });

    writer.join();
    running.store(false);
    reader.join();
}

// ========== Bug A2: Lock ordering deadlock ==========

TEST(ConcurrencyTest, test_concurrent_set_and_remove_no_deadlock) {
    
    // mutex_b_ then mutex_a_. Concurrent set+remove can deadlock.
    HashTable ht;
    std::atomic<bool> deadlocked{false};

    // Pre-populate
    for (int i = 0; i < 100; ++i) {
        ht.set("key_" + std::to_string(i), Value("val"));
    }

    // Use a timeout to detect deadlock
    auto start = std::chrono::steady_clock::now();

    std::thread setter([&]() {
        for (int i = 0; i < 200; ++i) {
            ht.set("key_" + std::to_string(i % 100), Value("new_val"));
        }
    });

    std::thread remover([&]() {
        for (int i = 0; i < 200; ++i) {
            ht.remove("key_" + std::to_string(i % 100));
        }
    });

    // Wait with timeout
    std::thread watchdog([&]() {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        if (setter.joinable() || remover.joinable()) {
            deadlocked.store(true);
        }
    });

    setter.join();
    remover.join();
    watchdog.detach();

    auto elapsed = std::chrono::steady_clock::now() - start;
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();

    EXPECT_LT(ms, 5000) << "Possible deadlock detected (took " << ms << "ms)";
    EXPECT_FALSE(deadlocked.load()) << "Deadlock detected in concurrent set+remove";
}

TEST(ConcurrencyTest, test_no_deadlock_set_remove_pattern) {
    
    HashTable ht;

    ht.set("shared_key", Value("initial"));

    std::thread t1([&]() {
        for (int i = 0; i < 100; ++i) {
            ht.set("shared_key", Value("from_t1"));
        }
    });

    std::thread t2([&]() {
        for (int i = 0; i < 100; ++i) {
            ht.remove("shared_key");
            ht.set("shared_key", Value("from_t2"));
        }
    });

    t1.join();
    t2.join();
}

// ========== Bug A3: memory_order_relaxed ==========

TEST(ConcurrencyTest, test_size_visible_across_threads) {
    
    HashTable ht;
    std::atomic<bool> size_seen{false};

    std::thread writer([&ht]() {
        for (int i = 0; i < 50; ++i) {
            ht.set("key_" + std::to_string(i), Value("val"));
        }
    });

    std::thread reader([&ht, &size_seen]() {
        // Eventually we should see the correct size
        for (int attempt = 0; attempt < 100; ++attempt) {
            if (ht.size() > 0) {
                size_seen.store(true);
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    });

    writer.join();
    reader.join();

    EXPECT_TRUE(size_seen.load()) << "Size update not visible across threads";
    EXPECT_EQ(ht.size(), 50);
}

// ========== Bug A4: condvar misuse ==========

TEST(ConcurrencyTest, test_expiry_thread_responsiveness) {
    
    ExpiryManager em;
    std::atomic<bool> expired{false};

    em.set_expiry_callback([&expired](const std::string&) {
        expired.store(true);
    });

    em.start_expiry_thread();

    // Add an entry that expires immediately
    em.set_expiry("quick_expire", std::chrono::seconds(0));

    // Should expire within 500ms (not wait for full interval)
    auto start = std::chrono::steady_clock::now();
    while (!expired.load()) {
        auto elapsed = std::chrono::steady_clock::now() - start;
        if (elapsed > std::chrono::seconds(2)) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    EXPECT_TRUE(expired.load()) << "Expiry thread missed notification (condvar bug)";

    em.stop_expiry_thread();
}

// ========== Bug A5: volatile-as-atomic ==========

TEST(ConcurrencyTest, test_accepting_flag_thread_safe) {
    
    // After fix with std::atomic<bool>, this should work correctly
    std::atomic<bool> flag{true};
    std::atomic<bool> seen_false{false};

    std::thread writer([&flag]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        flag.store(false);
    });

    std::thread reader([&flag, &seen_false]() {
        while (flag.load()) {
            std::this_thread::yield();
        }
        seen_false.store(true);
    });

    writer.join();
    reader.join();

    EXPECT_TRUE(seen_false.load());
}

// ========== General concurrency tests ==========

TEST(ConcurrencyTest, test_concurrent_eviction) {
    EvictionManager em(5);

    std::thread inserter([&em]() {
        for (int i = 0; i < 20; ++i) {
            em.record_insert("key_" + std::to_string(i), 10);
        }
    });

    std::thread evictor([&em]() {
        for (int i = 0; i < 10; ++i) {
            em.evict_one();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    });

    inserter.join();
    evictor.join();
}

TEST(ConcurrencyTest, test_concurrent_expiry_operations) {
    ExpiryManager em;

    std::thread setter([&em]() {
        for (int i = 0; i < 50; ++i) {
            em.set_expiry("key_" + std::to_string(i), std::chrono::seconds(10));
        }
    });

    std::thread remover([&em]() {
        for (int i = 0; i < 50; ++i) {
            em.remove_expiry("key_" + std::to_string(i));
        }
    });

    setter.join();
    remover.join();
}

TEST(ConcurrencyTest, test_hashtable_stress) {
    HashTable ht(1000);
    const int num_threads = 8;
    const int ops = 100;

    std::vector<std::thread> threads;
    for (int t = 0; t < num_threads; ++t) {
        threads.emplace_back([&ht, t, ops]() {
            for (int i = 0; i < ops; ++i) {
                std::string key = "stress_" + std::to_string(t) + "_" + std::to_string(i);
                ht.set(key, Value("data"));
                ht.get(key);
                if (i % 3 == 0) ht.remove(key);
            }
        });
    }

    for (auto& t : threads) t.join();
}
