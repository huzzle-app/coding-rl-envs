#include <gtest/gtest.h>
#include "storage/hashtable.h"

using namespace cacheforge;

// ========== Bug A3: memory_order_relaxed on size ==========

TEST(HashTableTest, test_size_reflects_insertions_immediately) {
    
    // After fix with acquire/release, size should be immediately visible
    HashTable ht(100);
    ht.set("key1", Value("val1"));
    ht.set("key2", Value("val2"));
    ht.set("key3", Value("val3"));
    // Size must accurately reflect all insertions
    EXPECT_EQ(ht.size(), 3);
}

TEST(HashTableTest, test_size_after_remove) {
    HashTable ht(100);
    ht.set("key1", Value("val1"));
    ht.set("key2", Value("val2"));
    ht.remove("key1");
    EXPECT_EQ(ht.size(), 1);
}

// ========== Bug A2 (probe table variant): Hash probe chain broken by deletion ==========

TEST(HashTableTest, test_probe_table_find_after_delete) {

    // When two keys collide and the first is deleted, the second key should
    // still be findable via linear probing. With the bug, the deleted slot
    // (tombstone) stops the probe chain, making the second key unfindable.
    HashTable ht(16);  // small capacity to force collisions

    // Insert several keys that will be in a probe chain
    ht.set_with_probe("key_a", Value("value_a"));
    ht.set_with_probe("key_b", Value("value_b"));
    ht.set_with_probe("key_c", Value("value_c"));

    // Verify all findable
    EXPECT_TRUE(ht.get_with_probe("key_a").has_value());
    EXPECT_TRUE(ht.get_with_probe("key_b").has_value());
    EXPECT_TRUE(ht.get_with_probe("key_c").has_value());

    // Delete the first key - creates a tombstone
    EXPECT_TRUE(ht.remove_with_probe("key_a"));

    // With the bug, the tombstone breaks the probe chain. Keys that were
    // placed after key_a in the probe sequence become unreachable.
    // After fix, the tombstone should be skipped during probing.
    EXPECT_TRUE(ht.get_with_probe("key_b").has_value())
        << "Probe chain broken by tombstone - key_b unfindable after key_a deleted";
    EXPECT_TRUE(ht.get_with_probe("key_c").has_value())
        << "Probe chain broken by tombstone - key_c unfindable after key_a deleted";

    // The deleted key should no longer be findable
    EXPECT_FALSE(ht.get_with_probe("key_a").has_value());
}

TEST(HashTableTest, test_probe_table_tombstone_handling) {

    // Tombstones (deleted=true) must be treated as "continue probing",
    // while truly empty slots (occupied=false, deleted=false) stop the probe.
    HashTable ht(4);  // very small to guarantee collisions

    ht.set_with_probe("a", Value("1"));
    ht.set_with_probe("b", Value("2"));
    ht.set_with_probe("c", Value("3"));

    // Delete "a" and "b" to create tombstones
    ht.remove_with_probe("a");
    ht.remove_with_probe("b");

    // "c" was placed after "a" and "b" in the probe chain.
    // With the bug, the tombstones stop the probe and "c" is lost.
    auto val_c = ht.get_with_probe("c");
    EXPECT_TRUE(val_c.has_value())
        << "Tombstone handling broken: get_with_probe stops at deleted slots";
    if (val_c.has_value()) {
        EXPECT_EQ(val_c->as_string(), "3");
    }

    // Deleted keys should not be found
    EXPECT_FALSE(ht.get_with_probe("a").has_value());
    EXPECT_FALSE(ht.get_with_probe("b").has_value());
}

// ========== Basic hashtable operations ==========

TEST(HashTableTest, test_set_and_get) {
    HashTable ht;
    ht.set("hello", Value("world"));
    auto val = ht.get("hello");
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(val->as_string(), "world");
}

TEST(HashTableTest, test_set_overwrite) {
    HashTable ht;
    ht.set("key", Value("old"));
    ht.set("key", Value("new"));
    auto val = ht.get("key");
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(val->as_string(), "new");
}

TEST(HashTableTest, test_get_nonexistent) {
    HashTable ht;
    auto val = ht.get("no_such_key");
    EXPECT_FALSE(val.has_value());
}

TEST(HashTableTest, test_remove) {
    HashTable ht;
    ht.set("key", Value("val"));
    EXPECT_TRUE(ht.remove("key"));
    EXPECT_FALSE(ht.contains("key"));
}

TEST(HashTableTest, test_remove_nonexistent) {
    HashTable ht;
    EXPECT_FALSE(ht.remove("no_such_key"));
}

TEST(HashTableTest, test_contains) {
    HashTable ht;
    ht.set("exists", Value("yes"));
    EXPECT_TRUE(ht.contains("exists"));
    EXPECT_FALSE(ht.contains("nope"));
}

TEST(HashTableTest, test_keys_pattern) {
    HashTable ht;
    ht.set("user:1", Value("alice"));
    ht.set("user:2", Value("bob"));
    ht.set("session:1", Value("abc"));

    auto all_keys = ht.keys("*");
    EXPECT_EQ(all_keys.size(), 3);

    auto user_keys = ht.keys("user:*");
    EXPECT_EQ(user_keys.size(), 2);
}

TEST(HashTableTest, test_clear) {
    HashTable ht;
    ht.set("a", Value("1"));
    ht.set("b", Value("2"));
    ht.clear();
    EXPECT_EQ(ht.size(), 0);
    EXPECT_FALSE(ht.contains("a"));
}
