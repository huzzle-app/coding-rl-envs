#include <gtest/gtest.h>
#include "persistence/snapshot.h"
#include "storage/hashtable.h"
#include "storage/eviction.h"
#include "data/value.h"
#include <filesystem>

using namespace cacheforge;

TEST(PersistenceIntegrationTest, test_snapshot_restore_full_state) {
    std::string dir = "/tmp/cacheforge_persist_test";
    std::filesystem::create_directories(dir);

    // Save
    {
        SnapshotManager sm(dir);
        std::vector<SnapshotEntry> entries;
        entries.push_back({"user:1", Value("alice"), 100});
        entries.push_back({"user:2", Value("bob"), 200});
        entries.push_back({"counter", Value("42"), -1});
        EXPECT_TRUE(sm.save_snapshot(entries));
    }

    // Load
    {
        SnapshotManager sm(dir);
        std::vector<SnapshotEntry> loaded;
        EXPECT_TRUE(sm.load_snapshot(loaded));
        EXPECT_GE(loaded.size(), 3);
    }

    std::filesystem::remove_all(dir);
}

TEST(PersistenceIntegrationTest, test_hashtable_to_snapshot) {
    HashTable ht;
    ht.set("key1", Value("value1"));
    ht.set("key2", Value("value2"));

    std::string dir = "/tmp/cacheforge_ht_snapshot";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    std::vector<SnapshotEntry> entries;

    auto keys = ht.keys();
    for (const auto& key : keys) {
        auto val = ht.get(key);
        if (val.has_value()) {
            entries.push_back({key, *val, -1});
        }
    }

    EXPECT_TRUE(sm.save_snapshot(entries));
    EXPECT_GE(sm.snapshot_count(), 1);

    std::filesystem::remove_all(dir);
}

TEST(PersistenceIntegrationTest, test_snapshot_with_ttl) {
    std::string dir = "/tmp/cacheforge_ttl_snapshot";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    std::vector<SnapshotEntry> entries;
    entries.push_back({"temp_key", Value("temp_val"), 60});
    entries.push_back({"perm_key", Value("perm_val"), -1});
    EXPECT_TRUE(sm.save_snapshot(entries));

    std::vector<SnapshotEntry> loaded;
    EXPECT_TRUE(sm.load_snapshot(loaded));
    ASSERT_GE(loaded.size(), 2);

    std::filesystem::remove_all(dir);
}

TEST(PersistenceIntegrationTest, test_multiple_snapshot_versions) {
    std::string dir = "/tmp/cacheforge_multi_snapshot";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);

    // Create 3 snapshots
    for (int i = 0; i < 3; ++i) {
        std::vector<SnapshotEntry> entries;
        entries.push_back({"version", Value(std::to_string(i)), 0});
        EXPECT_TRUE(sm.save_snapshot(entries));
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    // Should have 3 snapshots
    EXPECT_EQ(sm.snapshot_count(), 3);

    // Cleanup keeping 1
    sm.cleanup_old_snapshots(1);
    EXPECT_EQ(sm.snapshot_count(), 1);

    std::filesystem::remove_all(dir);
}

TEST(PersistenceIntegrationTest, test_empty_snapshot) {
    std::string dir = "/tmp/cacheforge_empty_snapshot";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    std::vector<SnapshotEntry> empty;
    EXPECT_TRUE(sm.save_snapshot(empty));

    std::filesystem::remove_all(dir);
}
