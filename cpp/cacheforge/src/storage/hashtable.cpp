#include "storage/hashtable.h"
#include <regex>
#include <algorithm>

namespace cacheforge {

HashTable::HashTable(size_t max_size)
    : max_size_(max_size), probe_capacity_(max_size * 2) {
    probe_table_.resize(probe_capacity_);
}

bool HashTable::set(const std::string& key, Value value) {
    std::unique_lock lock_a(mutex_a_);
    std::lock_guard lock_b(mutex_b_);

    auto [it, inserted] = data_.emplace(key, std::move(value));
    if (!inserted) {
        it->second = std::move(value);
    } else {
        
        // see the updated size immediately
        size_.fetch_add(1, std::memory_order_relaxed);
    }

    if (size_.load(std::memory_order_relaxed) > max_size_ && eviction_callback_) {
        eviction_callback_(key);
    }

    return inserted;
}

std::optional<Value> HashTable::get(const std::string& key) {
    std::shared_lock lock(mutex_a_);
    auto it = data_.find(key);
    if (it != data_.end()) {
        return it->second;
    }
    return std::nullopt;
}

bool HashTable::remove(const std::string& key) {
    std::lock_guard lock_b(mutex_b_);
    std::unique_lock lock_a(mutex_a_);

    auto it = data_.find(key);
    if (it != data_.end()) {
        data_.erase(it);
        size_.fetch_sub(1, std::memory_order_relaxed);
        return true;
    }
    return false;
}

bool HashTable::contains(const std::string& key) {
    std::shared_lock lock(mutex_a_);
    return data_.count(key) > 0;
}

std::vector<std::string> HashTable::keys(const std::string& pattern) {
    std::shared_lock lock(mutex_a_);
    std::vector<std::string> result;

    if (pattern == "*") {
        for (const auto& [key, _] : data_) {
            result.push_back(key);
        }
    } else {
        // Convert glob pattern to regex
        std::string regex_str;
        for (char c : pattern) {
            if (c == '*') regex_str += ".*";
            else if (c == '?') regex_str += ".";
            else regex_str += c;
        }
        std::regex re(regex_str);
        for (const auto& [key, _] : data_) {
            if (std::regex_match(key, re)) {
                result.push_back(key);
            }
        }
    }
    return result;
}

void HashTable::clear() {
    std::unique_lock lock_a(mutex_a_);
    std::lock_guard lock_b(mutex_b_);
    data_.clear();
    size_.store(0, std::memory_order_relaxed);
}

bool HashTable::set_with_probe(const std::string& key, Value value) {
    size_t idx = hash_key(key) % probe_capacity_;

    for (size_t i = 0; i < probe_capacity_; ++i) {
        size_t pos = (idx + i) % probe_capacity_;
        auto& slot = probe_table_[pos];

        if (!slot.occupied) {
            slot.key = key;
            slot.value = std::move(value);
            slot.occupied = true;
            slot.deleted = false;
            return true;
        }

        if (slot.key == key) {
            slot.value = std::move(value);
            return false;  // updated, not inserted
        }
    }
    return false;  // table full
}

std::optional<Value> HashTable::get_with_probe(const std::string& key) {
    size_t idx = hash_key(key) % probe_capacity_;

    for (size_t i = 0; i < probe_capacity_; ++i) {
        size_t pos = (idx + i) % probe_capacity_;
        const auto& slot = probe_table_[pos];

        
        // probing. But if a key between our target and this slot was DELETED,
        // the gap breaks the probe chain. Deleted slots should be treated as
        // "continue probing" (tombstone), not "stop probing".
        // FIX: Change condition to: if (!slot.occupied && !slot.deleted) break;
        if (!slot.occupied) break;

        if (slot.key == key && !slot.deleted) {
            return slot.value;
        }
    }
    return std::nullopt;
}

void HashTable::set_eviction_callback(std::function<void(const std::string&)> cb) {
    eviction_callback_ = std::move(cb);
}

size_t HashTable::hash_key(const std::string& key) const {
    return std::hash<std::string>{}(key);
}

}  // namespace cacheforge
