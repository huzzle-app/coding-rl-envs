#include "storage/eviction.h"

namespace cacheforge {

EvictionManager::EvictionManager(size_t max_entries)
    : max_entries_(max_entries) {}

void EvictionManager::record_access(const std::string& key) {
    std::lock_guard lock(mutex_);
    touch(key);
}

void EvictionManager::record_insert(const std::string& key, size_t size_bytes) {
    std::lock_guard lock(mutex_);
    // Remove old entry if exists
    auto it = lookup_.find(key);
    if (it != lookup_.end()) {
        total_size_ -= it->second->size_bytes;
        lru_list_.erase(it->second);
        lookup_.erase(it);
    }

    // Insert at front (most recently used)
    lru_list_.push_front({key, size_bytes});
    lookup_[key] = lru_list_.begin();
    total_size_ += size_bytes;
}

void EvictionManager::record_remove(const std::string& key) {
    std::lock_guard lock(mutex_);
    auto it = lookup_.find(key);
    if (it != lookup_.end()) {
        total_size_ -= it->second->size_bytes;
        lru_list_.erase(it->second);
        lookup_.erase(it);
    }
}

std::string EvictionManager::evict_one() {
    std::lock_guard lock(mutex_);
    if (lru_list_.empty()) return "";

    // Evict from back (least recently used)
    auto& victim = lru_list_.back();
    std::string key = victim.key;
    total_size_ -= victim.size_bytes;
    lookup_.erase(key);
    lru_list_.pop_back();
    return key;
}

void EvictionManager::touch(const std::string& key) {
    // NOTE: This is called from record_access which already holds the lock
    auto it = lookup_.find(key);
    if (it == lookup_.end()) return;

    Node node = *it->second;
    lru_list_.erase(it->second);
    lru_list_.push_front(node);
}

size_t EvictionManager::current_size() const {
    std::lock_guard lock(mutex_);
    return total_size_;
}

size_t EvictionManager::entry_count() const {
    std::lock_guard lock(mutex_);
    return lru_list_.size();
}

bool EvictionManager::should_evict() const {
    std::lock_guard lock(mutex_);
    return lru_list_.size() >= max_entries_;
}

}  // namespace cacheforge
