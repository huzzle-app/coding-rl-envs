#pragma once
#ifndef CACHEFORGE_EVICTION_H
#define CACHEFORGE_EVICTION_H

#include <string>
#include <list>
#include <unordered_map>
#include <mutex>
#include <memory>
#include <cstddef>

namespace cacheforge {

// LRU eviction manager
class EvictionManager {
public:
    explicit EvictionManager(size_t max_entries);

    void record_access(const std::string& key);
    void record_insert(const std::string& key, size_t size_bytes);
    void record_remove(const std::string& key);

    
    // get_victim returns the next key to evict. Internally uses unique_ptr
    // but returns raw pointer. If caller deletes it, double-free occurs.
    // Actually, the bug here is more subtle: the eviction node is managed
    // by unique_ptr in the node map, but evict_one() also tries to delete it.
    // FIX: Don't expose raw pointers; return std::string instead
    std::string evict_one();

    
    // to the front. It erases and re-inserts, which invalidates the iterator
    // stored in the lookup map, causing subsequent lookups to dangle.
    // FIX: Use std::list::splice() which moves nodes without invalidation
    void touch(const std::string& key);

    size_t current_size() const;
    size_t entry_count() const;
    bool should_evict() const;

private:
    struct Node {
        std::string key;
        size_t size_bytes = 0;
    };

    size_t max_entries_;
    size_t total_size_ = 0;

    // LRU list: front = most recently used, back = least recently used
    std::list<Node> lru_list_;
    // Map from key to iterator in lru_list_
    std::unordered_map<std::string, std::list<Node>::iterator> lookup_;

    mutable std::mutex mutex_;
};

}  // namespace cacheforge

#endif  // CACHEFORGE_EVICTION_H
