#pragma once
#ifndef CACHEFORGE_HASHTABLE_H
#define CACHEFORGE_HASHTABLE_H

#include <string>
#include <unordered_map>
#include <shared_mutex>
#include <mutex>
#include <optional>
#include <atomic>
#include <functional>
#include "data/value.h"

namespace cacheforge {

// Thread-safe hash table for cache storage
class HashTable {
public:
    HashTable(size_t max_size = 1000000);

    
    // memory exhaustion via oversized keys.
    // FIX: Add a key length check: if (key.size() > MAX_KEY_LENGTH) return false;

    
    // but remove() acquires mutex_b_ then mutex_a_. Concurrent set + remove
    // on different keys can deadlock.
    // FIX: Always acquire locks in the same order (mutex_a_ first, then mutex_b_)
    bool set(const std::string& key, Value value);
    std::optional<Value> get(const std::string& key);
    bool remove(const std::string& key);

    
    // eviction logic to decide when to start evicting. Relaxed ordering
    // means the eviction thread may see a stale size and fail to evict.
    // FIX: Use memory_order_seq_cst or memory_order_acquire/release
    size_t size() const { return size_.load(std::memory_order_relaxed); }

    bool contains(const std::string& key);
    std::vector<std::string> keys(const std::string& pattern = "*");
    void clear();

    
    // collide and one is removed, the probe sequence breaks (linear probing
    // gap), making the second key unfindable. This is the classic "tombstone"
    // problem. (Tested via test_probe_table_find_after_delete and
    // test_probe_table_tombstone_handling in unit_tests)
    // FIX: Use tombstone markers on delete, or use separate chaining (std::unordered_map already does this - the bug is in the custom probe logic)
    bool set_with_probe(const std::string& key, Value value);
    std::optional<Value> get_with_probe(const std::string& key);

    void set_eviction_callback(std::function<void(const std::string&)> cb);

private:
    // The main storage
    std::unordered_map<std::string, Value> data_;

    // Custom open-addressing table for high-performance path
    struct Slot {
        std::string key;
        Value value;
        bool occupied = false;
        bool deleted = false;  // tombstone - this field exists but is never checked in probing
    };
    std::vector<Slot> probe_table_;
    size_t probe_capacity_;

    
    mutable std::shared_mutex mutex_a_;
    mutable std::mutex mutex_b_;

    std::atomic<size_t> size_{0};
    size_t max_size_;
    std::function<void(const std::string&)> eviction_callback_;

    size_t hash_key(const std::string& key) const;
};

}  // namespace cacheforge

#endif  // CACHEFORGE_HASHTABLE_H
