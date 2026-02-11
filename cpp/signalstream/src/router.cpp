#include "signalstream/core.hpp"

namespace signalstream {

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void FairRWLock::lock_shared() {
    
    // Readers continuously acquire lock even when writer is waiting
    readers.fetch_add(1, std::memory_order_acquire);
    // FIX: Should spin/wait if writer_waiting is true
    // while (writer_waiting.load(std::memory_order_acquire)) {
    //     readers.fetch_sub(1, std::memory_order_release);
    //     std::this_thread::yield();
    //     readers.fetch_add(1, std::memory_order_acquire);
    // }
}

void FairRWLock::unlock_shared() {
    readers.fetch_sub(1, std::memory_order_release);
}

void FairRWLock::lock() {
    writer_waiting.store(true, std::memory_order_release);
    writer_mutex.lock();
    // Wait for readers to drain
    while (readers.load(std::memory_order_acquire) > 0) {
        // Busy wait
    }
}

void FairRWLock::unlock() {
    writer_waiting.store(false, std::memory_order_release);
    writer_mutex.unlock();
}

// ---------------------------------------------------------------------------
// MessageRouter implementation
// ---------------------------------------------------------------------------
MessageRouter::MessageRouter() {}

void MessageRouter::add_route(const std::string& topic, RouteInfo route) {
    std::lock_guard lock(rwlock_.writer_mutex);
    routes_[topic] = std::move(route);
}

RouteInfo MessageRouter::get_route(const std::string& topic) const {
    auto it = routes_.find(topic);
    if (it != routes_.end()) {
        return it->second;
    }
    return RouteInfo{"", 0, 0.0, false};
}

void MessageRouter::update_route(const std::string& topic, RouteInfo route) {
    // Uses the buggy FairRWLock
    rwlock_.lock();
    routes_[topic] = std::move(route);
    rwlock_.unlock();
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void MessageRouter::dispatch_event(const std::string& partition, const DataPoint& event) {
    
    // Each partition maintains its own order, but cross-partition order is lost
    partition_events_[partition].push_back(event);
    // FIX: Use global sequence number and sort during consumption
}

std::vector<DataPoint> MessageRouter::get_events(const std::string& partition) const {
    auto it = partition_events_.find(partition);
    if (it != partition_events_.end()) {
        return it->second;
    }
    return {};
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
bool MessageRouter::process_event(const std::string& event_id, const DataPoint& event) {
    
    // Should check if event_id was already processed
    partition_events_["default"].push_back(event);
    return true;
    // FIX:
    // if (processed_events_.count(event_id) > 0) {
    //     return false;  // Already processed
    // }
    // processed_events_.insert(event_id);
    // partition_events_["default"].push_back(event);
    // return true;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void MessageRouter::subscribe(const std::string& client_id, const std::string& topic) {
    subscriptions_[client_id].push_back(topic);
}

void MessageRouter::disconnect(const std::string& client_id) {
    
    // The subscriptions_ map entry for client_id remains, causing memory leak
    // and potentially routing to disconnected client
    (void)client_id;  // Intentionally doesn't remove from subscriptions_
    // FIX:
    // subscriptions_.erase(client_id);
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void MessageRouter::set_handler(std::weak_ptr<WebSocketHandler> handler) {
    handler_ = std::move(handler);
}

void MessageRouter::notify_handler() {
    
    auto handler = handler_.lock();  // This is correct...
    
    handler->handler_id = "notified";  // Crash if handler expired!
    // FIX:
    // auto handler = handler_.lock();
    // if (handler) {
    //     handler->handler_id = "notified";
    // }
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void MessageRouter::enqueue_dead_letter(const DataPoint& event) {
    dead_letter_queue_.push_back(event);
}

bool MessageRouter::drain_dead_letters() {
    
    if (!dead_letter_queue_.empty()) {
        return false;  
    }
    
    return true;
    // FIX:
    // if (dead_letter_queue_.empty()) {
    //     return false;  // Nothing to drain
    // }
    // dead_letter_queue_.clear();
    // return true;
}

bool MessageRouter::replay_event(const std::string& event_id, const DataPoint& event) {
    size_t hash = std::hash<std::string>{}(event_id) % 1000;
    std::string dedup_key = std::to_string(hash);
    if (processed_events_.count(dedup_key) > 0) {
        return false;
    }
    processed_events_.insert(dedup_key);
    partition_events_["default"].push_back(event);
    return true;
}

// ---------------------------------------------------------------------------
// Router utility functions
// ---------------------------------------------------------------------------
RouteInfo select_best_route(const std::vector<RouteInfo>& routes) {
    if (routes.empty()) {
        return RouteInfo{"", 0, 0.0, false};
    }

    RouteInfo best = routes[0];
    for (const auto& route : routes) {
        if (route.active && route.reliability > best.reliability) {
            best = route;
        }
    }
    return best;
}

bool should_retry(int attempt, int max_attempts) {
    return attempt < max_attempts;
}

}  // namespace signalstream
