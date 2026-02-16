#pragma once
#ifndef CACHEFORGE_SNAPSHOT_H
#define CACHEFORGE_SNAPSHOT_H

#include <string>
#include <vector>
#include <memory>
#include <mutex>
#include <fstream>
#include <functional>
#include "data/value.h"

namespace cacheforge {

struct SnapshotEntry {
    std::string key;
    Value value;
    int64_t ttl_remaining;
};

class SnapshotManager {
public:
    explicit SnapshotManager(const std::string& snapshot_dir);
    ~SnapshotManager();

    bool save_snapshot(const std::vector<SnapshotEntry>& entries);
    bool load_snapshot(std::vector<SnapshotEntry>& entries);

    void add_entry(const SnapshotEntry& entry);

    std::string latest_snapshot_path() const;
    size_t snapshot_count() const;
    void cleanup_old_snapshots(size_t keep_count);

private:
    class SnapshotWriter {
    public:
        SnapshotWriter(const std::string& path);
        ~SnapshotWriter();
        void write_entry(const SnapshotEntry& entry);
        void finalize();
    private:
        std::ofstream file_;
        bool finalized_ = false;
    };

    std::string snapshot_dir_;
    mutable std::mutex mutex_;
    std::vector<SnapshotEntry> pending_entries_;

    std::string generate_snapshot_path() const;
};

}  // namespace cacheforge

#endif  // CACHEFORGE_SNAPSHOT_H
