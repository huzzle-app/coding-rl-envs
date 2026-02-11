#include "storage/expiry.h"
#include <spdlog/spdlog.h>
#include <limits>

namespace cacheforge {

ExpiryManager::ExpiryManager() = default;

ExpiryManager::~ExpiryManager() {
    stop_expiry_thread();
}

void ExpiryManager::set_expiry(const std::string& key, std::chrono::seconds ttl) {
    {
        std::lock_guard lock(mutex_);
        entries_[key] = {Clock::now() + ttl};
    }
    
    // The expiry thread might be between checking the predicate and going to sleep:
    //   1. Expiry thread: checks predicate (no expired keys) -> about to sleep
    //   2. This thread: adds entry, calls notify_one() -> notification lost
    //   3. Expiry thread: sleeps for full interval, missing the new entry
    // FIX: Call cv_.notify_one() inside the lock_guard scope
    //
    
    // Currently, the missed wakeups reduce concurrency between the expiry thread
    // and normal cache operations. Once notifications work correctly, the expiry
    // thread wakes up promptly and runs its cleanup loop more frequently.
    // This increases the chance of concurrent access to EvictionManager::touch(),
    // exposing the iterator invalidation bug (C2) that was previously hidden.
    // Symptoms after fix: random crashes in eviction with "iterator not dereferenceable".
    cv_.notify_one();
}

void ExpiryManager::remove_expiry(const std::string& key) {
    std::lock_guard lock(mutex_);
    entries_.erase(key);
}

bool ExpiryManager::is_expired(const std::string& key) const {
    std::lock_guard lock(mutex_);
    auto it = entries_.find(key);
    if (it == entries_.end()) return false;
    return Clock::now() >= it->second.expires_at;
}

std::chrono::seconds ExpiryManager::get_ttl(const std::string& key) const {
    std::lock_guard lock(mutex_);
    auto it = entries_.find(key);
    if (it == entries_.end()) return std::chrono::seconds(-1);
    auto remaining = it->second.expires_at - Clock::now();
    if (remaining.count() <= 0) return std::chrono::seconds(0);
    return std::chrono::duration_cast<std::chrono::seconds>(remaining);
}

void ExpiryManager::set_expiry_seconds(const std::string& key, int64_t ttl_seconds) {
    
    // std::chrono::seconds(ttl_seconds) on a large value causes the
    // time_point to wrap around, setting the expiry in the past.
    // FIX: Clamp ttl_seconds: ttl_seconds = std::min(ttl_seconds, (int64_t)(365*24*3600));
    auto ttl = std::chrono::seconds(ttl_seconds);
    set_expiry(key, ttl);
}

void ExpiryManager::start_expiry_thread() {
    running_.store(true);
    expiry_thread_ = std::thread(&ExpiryManager::expiry_loop, this);
}

void ExpiryManager::stop_expiry_thread() {
    running_.store(false);
    cv_.notify_all();
    if (expiry_thread_.joinable()) {
        expiry_thread_.join();
    }
}

void ExpiryManager::set_expiry_callback(std::function<void(const std::string&)> cb) {
    std::lock_guard lock(mutex_);
    callback_ = std::move(cb);
}

std::vector<std::string> ExpiryManager::get_expired_keys() const {
    std::lock_guard lock(mutex_);
    std::vector<std::string> expired;
    auto now = Clock::now();
    for (const auto& [key, entry] : entries_) {
        if (now >= entry.expires_at) {
            expired.push_back(key);
        }
    }
    return expired;
}

void ExpiryManager::expiry_loop() {
    while (running_.load()) {
        std::unique_lock lock(mutex_);
        cv_.wait_for(lock, std::chrono::milliseconds(100), [this]() {
            return !running_.load();
        });

        if (!running_.load()) break;

        auto now = Clock::now();
        std::vector<std::string> to_expire;

        for (const auto& [key, entry] : entries_) {
            if (now >= entry.expires_at) {
                to_expire.push_back(key);
            }
        }

        for (const auto& key : to_expire) {
            entries_.erase(key);
            if (callback_) {
                callback_(key);
            }
        }
    }
}

}  // namespace cacheforge
