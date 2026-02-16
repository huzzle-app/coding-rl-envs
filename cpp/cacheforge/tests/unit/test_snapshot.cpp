#include <gtest/gtest.h>
#include "persistence/snapshot.h"
#include <filesystem>
#include <fstream>
#include <string>

#ifndef SOURCE_DIR
#define SOURCE_DIR "."
#endif

using namespace cacheforge;

// ========== Bug C4: Exception-unsafe raw new ==========

TEST(SnapshotTest, test_save_snapshot_no_memory_leak_on_error) {
    
    // allocated with raw new should not be leaked.
    // After fix, std::make_unique should be used.
    std::string dir = "/tmp/cacheforge_test_snapshot";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);

    std::vector<SnapshotEntry> entries;
    entries.push_back({"key1", Value("value1"), 100});
    entries.push_back({"key2", Value("value2"), 200});

    // Normal save should succeed
    EXPECT_TRUE(sm.save_snapshot(entries));
    EXPECT_GE(sm.snapshot_count(), 1);

    // Cleanup
    std::filesystem::remove_all(dir);
}

TEST(SnapshotTest, test_save_and_load_roundtrip) {
    std::string dir = "/tmp/cacheforge_test_roundtrip";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);

    std::vector<SnapshotEntry> entries;
    entries.push_back({"mykey", Value("myvalue"), 300});

    EXPECT_TRUE(sm.save_snapshot(entries));

    std::vector<SnapshotEntry> loaded;
    EXPECT_TRUE(sm.load_snapshot(loaded));
    ASSERT_GE(loaded.size(), 1);
    EXPECT_EQ(loaded[0].key, "mykey");

    std::filesystem::remove_all(dir);
}

TEST(SnapshotTest, test_snapshot_count) {
    std::string dir = "/tmp/cacheforge_test_count";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    EXPECT_EQ(sm.snapshot_count(), 0);

    std::vector<SnapshotEntry> entries = {{"k", Value("v"), 0}};
    sm.save_snapshot(entries);
    EXPECT_GE(sm.snapshot_count(), 1);

    std::filesystem::remove_all(dir);
}

TEST(SnapshotTest, test_cleanup_old_snapshots) {
    std::string dir = "/tmp/cacheforge_test_cleanup";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    std::vector<SnapshotEntry> entries = {{"k", Value("v"), 0}};

    // Create multiple snapshots
    for (int i = 0; i < 5; ++i) {
        sm.save_snapshot(entries);
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    sm.cleanup_old_snapshots(2);
    EXPECT_LE(sm.snapshot_count(), 2);

    std::filesystem::remove_all(dir);
}

TEST(SnapshotTest, test_load_nonexistent) {
    std::string dir = "/tmp/cacheforge_test_noexist";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    std::vector<SnapshotEntry> entries;
    EXPECT_FALSE(sm.load_snapshot(entries));

    std::filesystem::remove_all(dir);
}

TEST(SnapshotTest, test_add_entry) {
    std::string dir = "/tmp/cacheforge_test_add";
    std::filesystem::create_directories(dir);

    SnapshotManager sm(dir);
    sm.add_entry({"k1", Value("v1"), 0});
    sm.add_entry({"k2", Value("v2"), 100});

    // No crash, entries added to pending list
    std::filesystem::remove_all(dir);
}

// ========== Bug C4: Source check for exception-unsafe raw new ==========

TEST(SnapshotTest, test_save_snapshot_exception_safety) {
    std::string path = std::string(SOURCE_DIR) + "/src/persistence/snapshot.cpp";
    std::ifstream f(path);
    ASSERT_TRUE(f.is_open()) << "Could not read snapshot.cpp";
    std::string src(std::istreambuf_iterator<char>(f),
                    std::istreambuf_iterator<char>());

    EXPECT_EQ(src.find("new SnapshotWriter"), std::string::npos)
        << "save_snapshot uses raw new SnapshotWriter (leaks on exception). "
           "Use std::make_unique<SnapshotWriter>(...) instead.";
}
