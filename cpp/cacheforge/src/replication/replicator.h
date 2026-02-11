#pragma once
#ifndef CACHEFORGE_REPLICATOR_H
#define CACHEFORGE_REPLICATOR_H

#include <string>
#include <vector>
#include <memory>
#include <mutex>
#include <atomic>
#include <thread>
#include <queue>
#include <functional>

namespace cacheforge {

struct ReplicationEvent {
    enum class Type { Set, Delete, Expire };
    Type type;
    std::string key;
    std::string value;
    uint64_t sequence;
};

class Replicator {
public:
    Replicator(const std::string& host, uint16_t port);
    ~Replicator();

    
    // then accesses event.key for logging. After std::move, the string is
    // in a valid-but-unspecified state (likely empty).
    // FIX: Log before the move, or use a const reference to the queued copy
    void enqueue(ReplicationEvent event);

    
    // sequence_counter_ is int64_t and wraps around at INT64_MAX.
    // Signed integer overflow is undefined behavior in C++.
    // FIX: Use uint64_t for the counter, or check for overflow before increment
    uint64_t next_sequence();

    void start();
    void stop();
    bool is_connected() const { return connected_.load(); }

    size_t pending_count() const;
    std::vector<ReplicationEvent> drain_batch(size_t max_count);

private:
    std::string host_;
    uint16_t port_;
    std::atomic<bool> connected_{false};
    std::atomic<bool> running_{false};
    std::thread worker_;

    mutable std::mutex queue_mutex_;
    std::queue<ReplicationEvent> event_queue_;

    
    int64_t sequence_counter_ = 0;

    void run_loop();
    bool try_connect();
    void send_batch(const std::vector<ReplicationEvent>& batch);
};

}  // namespace cacheforge

#endif  // CACHEFORGE_REPLICATOR_H
