#include <gtest/gtest.h>
#include "storage/eviction.h"

using namespace cacheforge;

// ========== Bug C2: LRU splice invalidation ==========

TEST(EvictionTest, test_lru_access_order_preserved) {

    // After fix with splice(), access order should be correctly maintained
    EvictionManager em(10);

    em.record_insert("key1", 100);
    em.record_insert("key2", 100);
    em.record_insert("key3", 100);

    // Access key1 to move it to front (most recently used)
    em.record_access("key1");

    // Access key1 again - with the bug, the lookup map still holds a dangling
    // iterator from the first touch(), so this second access dereferences freed memory.
    // After fix, repeated access should work without crashing.
    em.record_access("key1");

    // Evict should remove key2 (least recently used after key1 was touched)
    std::string victim = em.evict_one();
    EXPECT_EQ(victim, "key2");
}

TEST(EvictionTest, test_lru_touch_no_iterator_invalidation) {
    
    // should still be valid for subsequent operations
    EvictionManager em(10);

    em.record_insert("a", 50);
    em.record_insert("b", 50);
    em.record_insert("c", 50);

    // Touch 'a' multiple times - should not crash from dangling iterator
    em.record_access("a");
    em.record_access("a");
    em.record_access("a");

    // All entries should still be accessible
    EXPECT_EQ(em.entry_count(), 3);
}

TEST(EvictionTest, test_lru_eviction_order) {
    EvictionManager em(5);

    em.record_insert("oldest", 10);
    em.record_insert("middle", 10);
    em.record_insert("newest", 10);

    // Evict should remove the oldest (least recently used)
    EXPECT_EQ(em.evict_one(), "oldest");
    EXPECT_EQ(em.evict_one(), "middle");
    EXPECT_EQ(em.evict_one(), "newest");
}

TEST(EvictionTest, test_record_remove) {
    EvictionManager em(10);
    em.record_insert("key1", 100);
    em.record_insert("key2", 200);
    em.record_remove("key1");
    EXPECT_EQ(em.entry_count(), 1);
    EXPECT_EQ(em.current_size(), 200);
}

TEST(EvictionTest, test_should_evict) {
    EvictionManager em(2);
    em.record_insert("a", 10);
    EXPECT_FALSE(em.should_evict());
    em.record_insert("b", 10);
    EXPECT_TRUE(em.should_evict());
}

TEST(EvictionTest, test_evict_empty) {
    EvictionManager em(10);
    EXPECT_EQ(em.evict_one(), "");
}

TEST(EvictionTest, test_current_size_tracking) {
    EvictionManager em(100);
    em.record_insert("k1", 100);
    em.record_insert("k2", 200);
    EXPECT_EQ(em.current_size(), 300);
    em.record_remove("k1");
    EXPECT_EQ(em.current_size(), 200);
}
