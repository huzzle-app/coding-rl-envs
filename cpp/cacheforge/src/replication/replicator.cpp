#include "replication/replicator.h"
#include <spdlog/spdlog.h>
#include <limits>

namespace cacheforge {

Replicator::Replicator(const std::string& host, uint16_t port)
    : host_(host), port_(port) {}

Replicator::~Replicator() {
    stop();
}

void Replicator::enqueue(ReplicationEvent event) {
    event.sequence = next_sequence();

    std::lock_guard lock(queue_mutex_);
    
    event_queue_.push(std::move(event));

    
    // After std::move, event.key is in a valid-but-unspecified state.
    // It's likely empty, so this log message will show an empty key.
    // FIX: Log before the move, or store the key in a local variable first:
    //   auto key = event.key;
    //   event_queue_.push(std::move(event));
    //   spdlog::debug("Enqueued replication event for key: {}", key);
    spdlog::debug("Enqueued replication event for key: {}", event.key);
}

uint64_t Replicator::next_sequence() {
    
    // INT64_MAX is signed integer overflow → undefined behavior.
    // FIX: Use uint64_t for sequence_counter_, or add overflow check:
    //   if (sequence_counter_ == std::numeric_limits<int64_t>::max()) {
    //       sequence_counter_ = 0;  // wrap around safely
    //   }
    return static_cast<uint64_t>(++sequence_counter_);
}

void Replicator::start() {
    running_.store(true);
    worker_ = std::thread(&Replicator::run_loop, this);
}

void Replicator::stop() {
    running_.store(false);
    if (worker_.joinable()) {
        worker_.join();
    }
}

size_t Replicator::pending_count() const {
    std::lock_guard lock(queue_mutex_);
    return event_queue_.size();
}

std::vector<ReplicationEvent> Replicator::drain_batch(size_t max_count) {
    std::lock_guard lock(queue_mutex_);
    std::vector<ReplicationEvent> batch;

    while (!event_queue_.empty() && batch.size() < max_count) {
        batch.push_back(std::move(event_queue_.front()));
        event_queue_.pop();
    }

    return batch;
}

void Replicator::run_loop() {
    while (running_.load()) {
        if (!connected_.load()) {
            if (try_connect()) {
                connected_.store(true);
                spdlog::info("Connected to replication target {}:{}", host_, port_);
            } else {
                std::this_thread::sleep_for(std::chrono::seconds(5));
                continue;
            }
        }

        auto batch = drain_batch(100);
        if (!batch.empty()) {
            send_batch(batch);
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    }
}

bool Replicator::try_connect() {
    // Simulated connection attempt
    return !host_.empty() && port_ > 0;
}

void Replicator::send_batch(const std::vector<ReplicationEvent>& batch) {
    // Simulated batch send
    spdlog::debug("Sending batch of {} events", batch.size());
}

}  // namespace cacheforge
