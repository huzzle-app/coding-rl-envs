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

    
    bool set(const std::string& key, Value value);
    std::optional<Value> get(const std::string& key);
    bool remove(const std::string& key);

    
    size_t size() const { return size_.load(std::memory_order_relaxed); }

    bool contains(const std::string& key);
    std::vector<std::string> keys(const std::string& pattern = "*");
    void clear();

    
    // Custom open-addressing probe table interface
    bool set_with_probe(const std::string& key, Value value);
    std::optional<Value> get_with_probe(const std::string& key);
    bool remove_with_probe(const std::string& key);

    void set_eviction_callback(std::function<void(const std::string&)> cb);

private:
    // The main storage
    std::unordered_map<std::string, Value> data_;

    // Custom open-addressing table for high-performance path
    struct Slot {
        std::string key;
        Value value;
        bool occupied = false;
        bool deleted = false;
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
