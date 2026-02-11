#include <gtest/gtest.h>
#include "storage/expiry.h"
#include <thread>
#include <chrono>

using namespace cacheforge;

// ========== Bug A4: condvar misuse (notify outside lock) ==========

TEST(ExpiryTest, test_set_expiry_notifies_thread_immediately) {
    
    // thread may miss the notification. With fix, expiry should trigger
    // within a short time after set_expiry is called.
    ExpiryManager em;

    bool expired = false;
    em.set_expiry_callback([&expired](const std::string& key) {
        expired = true;
    });

    em.start_expiry_thread();

    // Set a very short TTL
    em.set_expiry("test_key", std::chrono::seconds(0));

    // Wait a short time - the expiry should be detected quickly
    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    EXPECT_TRUE(expired) << "Expiry notification was missed (condvar bug)";

    em.stop_expiry_thread();
}

TEST(ExpiryTest, test_condvar_notification_not_lost) {
    
    ExpiryManager em;
    int expired_count = 0;
    std::mutex count_mutex;

    em.set_expiry_callback([&](const std::string& key) {
        std::lock_guard lock(count_mutex);
        expired_count++;
    });

    em.start_expiry_thread();

    // Set multiple entries with immediate expiry
    for (int i = 0; i < 5; ++i) {
        em.set_expiry("key_" + std::to_string(i), std::chrono::seconds(0));
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    {
        std::lock_guard lock(count_mutex);
        EXPECT_EQ(expired_count, 5) << "Some expiry notifications were lost";
    }

    em.stop_expiry_thread();
}

// ========== Bug E1: Integer overflow in TTL ==========

TEST(ExpiryTest, test_large_ttl_no_integer_overflow) {
    
    ExpiryManager em;

    int64_t huge_ttl = 9223372036854775807LL;  // INT64_MAX
    em.set_expiry_seconds("overflow_key", huge_ttl);

    // The key should NOT be expired immediately
    EXPECT_FALSE(em.is_expired("overflow_key"))
        << "TTL overflow caused key to expire immediately";
}

TEST(ExpiryTest, test_reasonable_large_ttl) {
    
    ExpiryManager em;

    int64_t ten_years = 10LL * 365 * 24 * 3600;
    em.set_expiry_seconds("long_lived", ten_years);

    EXPECT_FALSE(em.is_expired("long_lived"));
    auto ttl = em.get_ttl("long_lived");
    EXPECT_GT(ttl.count(), 0);
}

// ========== Basic expiry tests ==========

TEST(ExpiryTest, test_set_and_check_expiry) {
    ExpiryManager em;
    em.set_expiry("key", std::chrono::seconds(10));
    EXPECT_FALSE(em.is_expired("key"));
}

TEST(ExpiryTest, test_expired_key) {
    ExpiryManager em;
    em.set_expiry("key", std::chrono::seconds(0));
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    EXPECT_TRUE(em.is_expired("key"));
}

TEST(ExpiryTest, test_remove_expiry) {
    ExpiryManager em;
    em.set_expiry("key", std::chrono::seconds(1));
    em.remove_expiry("key");
    EXPECT_FALSE(em.is_expired("key"));
}

TEST(ExpiryTest, test_get_ttl) {
    ExpiryManager em;
    em.set_expiry("key", std::chrono::seconds(100));
    auto ttl = em.get_ttl("key");
    EXPECT_GT(ttl.count(), 90);
    EXPECT_LE(ttl.count(), 100);
}

TEST(ExpiryTest, test_get_ttl_nonexistent) {
    ExpiryManager em;
    auto ttl = em.get_ttl("no_such_key");
    EXPECT_EQ(ttl.count(), -1);
}

TEST(ExpiryTest, test_get_expired_keys) {
    ExpiryManager em;
    em.set_expiry("expired1", std::chrono::seconds(0));
    em.set_expiry("expired2", std::chrono::seconds(0));
    em.set_expiry("alive", std::chrono::seconds(100));

    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    auto expired = em.get_expired_keys();
    EXPECT_EQ(expired.size(), 2);
}
