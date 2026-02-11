#pragma once
#ifndef CACHEFORGE_EXPIRY_H
#define CACHEFORGE_EXPIRY_H

#include <string>
#include <unordered_map>
#include <chrono>
#include <mutex>
#include <atomic>
#include <thread>
#include <condition_variable>
#include <vector>
#include <functional>

namespace cacheforge {

using Clock = std::chrono::steady_clock;
using TimePoint = Clock::time_point;
using Duration = Clock::duration;

class ExpiryManager {
public:
    ExpiryManager();
    ~ExpiryManager();

    
    // the mutex, which can cause the expiry thread to miss the notification
    // and sleep for the full check interval even when keys need immediate expiry.
    // FIX: Call notify_one() while holding the mutex, or use notify_all()
    void set_expiry(const std::string& key, std::chrono::seconds ttl);
    void remove_expiry(const std::string& key);
    bool is_expired(const std::string& key) const;
    std::chrono::seconds get_ttl(const std::string& key) const;

    
    // value is passed (e.g., INT_MAX seconds), the computation
    // now + std::chrono::seconds(ttl) overflows, setting expiry in the PAST.
    // FIX: Clamp TTL to a maximum reasonable value (e.g., 365 days)
    void set_expiry_seconds(const std::string& key, int64_t ttl_seconds);

    void start_expiry_thread();
    void stop_expiry_thread();

    void set_expiry_callback(std::function<void(const std::string&)> cb);
    std::vector<std::string> get_expired_keys() const;

private:
    struct ExpiryEntry {
        TimePoint expires_at;
    };

    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::unordered_map<std::string, ExpiryEntry> entries_;
    std::atomic<bool> running_{false};
    std::thread expiry_thread_;
    std::function<void(const std::string&)> callback_;

    void expiry_loop();
};

}  // namespace cacheforge

#endif  // CACHEFORGE_EXPIRY_H
