#include <gtest/gtest.h>
#include "storage/hashtable.h"
#include "storage/eviction.h"
#include <thread>
#include <future>
#include <chrono>

using namespace cacheforge;

// ========== Bug A2: Lock ordering deadlock - dedicated tests ==========

TEST(DeadlockTest, test_lock_ordering_set_remove) {
    
    // This test specifically targets the deadlock scenario
    HashTable ht;
    ht.set("target", Value("initial"));

    auto future1 = std::async(std::launch::async, [&ht]() {
        for (int i = 0; i < 500; ++i) {
            ht.set("target", Value("setter_" + std::to_string(i)));
        }
        return true;
    });

    auto future2 = std::async(std::launch::async, [&ht]() {
        for (int i = 0; i < 500; ++i) {
            ht.remove("target");
            ht.set("target", Value("remover_" + std::to_string(i)));
        }
        return true;
    });

    // If deadlock occurs, these will timeout
    auto status1 = future1.wait_for(std::chrono::seconds(10));
    auto status2 = future2.wait_for(std::chrono::seconds(10));

    EXPECT_NE(status1, std::future_status::timeout) << "Thread 1 deadlocked";
    EXPECT_NE(status2, std::future_status::timeout) << "Thread 2 deadlocked";
}

TEST(DeadlockTest, test_lock_ordering_three_threads) {
    
    HashTable ht;

    for (int i = 0; i < 20; ++i) {
        ht.set("key_" + std::to_string(i), Value("val"));
    }

    auto f1 = std::async(std::launch::async, [&ht]() {
        for (int i = 0; i < 100; ++i) {
            ht.set("key_" + std::to_string(i % 20), Value("f1"));
        }
    });

    auto f2 = std::async(std::launch::async, [&ht]() {
        for (int i = 0; i < 100; ++i) {
            ht.remove("key_" + std::to_string(i % 20));
        }
    });

    auto f3 = std::async(std::launch::async, [&ht]() {
        for (int i = 0; i < 10; ++i) {
            ht.keys("*");
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    });

    EXPECT_NE(f1.wait_for(std::chrono::seconds(10)), std::future_status::timeout);
    EXPECT_NE(f2.wait_for(std::chrono::seconds(10)), std::future_status::timeout);
    EXPECT_NE(f3.wait_for(std::chrono::seconds(10)), std::future_status::timeout);
}

TEST(DeadlockTest, test_hashtable_clear_concurrent) {
    HashTable ht;

    auto writer = std::async(std::launch::async, [&ht]() {
        for (int i = 0; i < 200; ++i) {
            ht.set("k" + std::to_string(i), Value("v"));
        }
    });

    auto clearer = std::async(std::launch::async, [&ht]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        ht.clear();
    });

    EXPECT_NE(writer.wait_for(std::chrono::seconds(5)), std::future_status::timeout);
    EXPECT_NE(clearer.wait_for(std::chrono::seconds(5)), std::future_status::timeout);
}

TEST(DeadlockTest, test_eviction_concurrent_access) {
    EvictionManager em(10);

    auto inserter = std::async(std::launch::async, [&em]() {
        for (int i = 0; i < 100; ++i) {
            em.record_insert("dk_" + std::to_string(i), 10);
        }
    });

    auto accessor = std::async(std::launch::async, [&em]() {
        for (int i = 0; i < 100; ++i) {
            em.record_access("dk_" + std::to_string(i % 10));
        }
    });

    auto evictor = std::async(std::launch::async, [&em]() {
        for (int i = 0; i < 50; ++i) {
            em.evict_one();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    });

    EXPECT_NE(inserter.wait_for(std::chrono::seconds(5)), std::future_status::timeout);
    EXPECT_NE(accessor.wait_for(std::chrono::seconds(5)), std::future_status::timeout);
    EXPECT_NE(evictor.wait_for(std::chrono::seconds(5)), std::future_status::timeout);
}
