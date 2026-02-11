#include "persistence/snapshot.h"
#include <spdlog/spdlog.h>
#include <filesystem>
#include <chrono>
#include <algorithm>

namespace cacheforge {

SnapshotManager::SnapshotManager(const std::string& snapshot_dir)
    : snapshot_dir_(snapshot_dir) {
    std::filesystem::create_directories(snapshot_dir_);
}

SnapshotManager::~SnapshotManager() = default;

bool SnapshotManager::save_snapshot(const std::vector<SnapshotEntry>& entries) {
    std::lock_guard lock(mutex_);

    
    // If generate_snapshot_path() throws (e.g., filesystem error),
    // the allocated SnapshotWriter is leaked.
    // FIX: auto writer = std::make_unique<SnapshotWriter>(generate_snapshot_path());
    SnapshotWriter* writer = new SnapshotWriter(generate_snapshot_path());

    try {
        for (const auto& entry : entries) {
            writer->write_entry(entry);
        }
        writer->finalize();
        delete writer;
        return true;
    } catch (const std::exception& e) {
        spdlog::error("Snapshot save failed: {}", e.what());
        
        // delete writer;  // This line is missing!
        return false;
    }
}

bool SnapshotManager::load_snapshot(std::vector<SnapshotEntry>& entries) {
    std::lock_guard lock(mutex_);
    auto path = latest_snapshot_path();
    if (path.empty()) return false;

    std::ifstream file(path, std::ios::binary);
    if (!file.is_open()) return false;

    // Read entries from snapshot file
    while (file.good()) {
        SnapshotEntry entry;
        size_t key_len;
        if (!file.read(reinterpret_cast<char*>(&key_len), sizeof(key_len))) break;

        entry.key.resize(key_len);
        file.read(entry.key.data(), key_len);

        int32_t type;
        file.read(reinterpret_cast<char*>(&type), sizeof(type));

        size_t value_len;
        file.read(reinterpret_cast<char*>(&value_len), sizeof(value_len));
        std::string value_str(value_len, '\0');
        file.read(value_str.data(), value_len);
        entry.value = Value(value_str);

        file.read(reinterpret_cast<char*>(&entry.ttl_remaining), sizeof(entry.ttl_remaining));

        entries.push_back(std::move(entry));
    }

    return true;
}

void SnapshotManager::add_entry(const SnapshotEntry& entry) {
    std::lock_guard lock(mutex_);
    pending_entries_.push_back(entry);
}

std::string SnapshotManager::latest_snapshot_path() const {
    std::string latest;
    std::filesystem::file_time_type latest_time{};

    if (!std::filesystem::exists(snapshot_dir_)) return "";

    for (const auto& entry : std::filesystem::directory_iterator(snapshot_dir_)) {
        if (entry.path().extension() == ".rdb") {
            auto time = entry.last_write_time();
            if (latest.empty() || time > latest_time) {
                latest = entry.path().string();
                latest_time = time;
            }
        }
    }
    return latest;
}

size_t SnapshotManager::snapshot_count() const {
    size_t count = 0;
    if (!std::filesystem::exists(snapshot_dir_)) return 0;
    for (const auto& entry : std::filesystem::directory_iterator(snapshot_dir_)) {
        if (entry.path().extension() == ".rdb") count++;
    }
    return count;
}

void SnapshotManager::cleanup_old_snapshots(size_t keep_count) {
    std::vector<std::filesystem::directory_entry> snapshots;
    for (const auto& entry : std::filesystem::directory_iterator(snapshot_dir_)) {
        if (entry.path().extension() == ".rdb") {
            snapshots.push_back(entry);
        }
    }

    std::sort(snapshots.begin(), snapshots.end(),
              [](const auto& a, const auto& b) {
                  return a.last_write_time() > b.last_write_time();
              });

    for (size_t i = keep_count; i < snapshots.size(); ++i) {
        std::filesystem::remove(snapshots[i].path());
    }
}

std::string SnapshotManager::generate_snapshot_path() const {
    auto now = std::chrono::system_clock::now();
    auto epoch = std::chrono::duration_cast<std::chrono::seconds>(
        now.time_since_epoch()).count();
    return snapshot_dir_ + "/snapshot_" + std::to_string(epoch) + ".rdb";
}

// SnapshotWriter implementation
SnapshotManager::SnapshotWriter::SnapshotWriter(const std::string& path)
    : file_(path, std::ios::binary) {
    if (!file_.is_open()) {
        throw std::runtime_error("Cannot create snapshot file: " + path);
    }
}

SnapshotManager::SnapshotWriter::~SnapshotWriter() {
    if (!finalized_) {
        // Try to finalize on destruction, but silently ignore errors
        try { finalize(); } catch (...) {}
    }
}

void SnapshotManager::SnapshotWriter::write_entry(const SnapshotEntry& entry) {
    size_t key_len = entry.key.size();
    file_.write(reinterpret_cast<const char*>(&key_len), sizeof(key_len));
    file_.write(entry.key.data(), key_len);

    int32_t type = static_cast<int32_t>(entry.value.type());
    file_.write(reinterpret_cast<const char*>(&type), sizeof(type));

    std::string value_str = entry.value.as_string();
    size_t value_len = value_str.size();
    file_.write(reinterpret_cast<const char*>(&value_len), sizeof(value_len));
    file_.write(value_str.data(), value_len);

    file_.write(reinterpret_cast<const char*>(&entry.ttl_remaining), sizeof(entry.ttl_remaining));
}

void SnapshotManager::SnapshotWriter::finalize() {
    file_.flush();
    finalized_ = true;
}

}  // namespace cacheforge
