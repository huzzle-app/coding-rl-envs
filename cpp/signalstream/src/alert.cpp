#include "signalstream/core.hpp"
#include <thread>
#include <chrono>

namespace signalstream {

AlertService::AlertService() {}


AlertService::~AlertService() {
    
    if (cleanup_failed_) {
        throw std::runtime_error("Cleanup failed in destructor");
    }
    // FIX: Destructors should be noexcept, log error instead of throwing
}

void AlertService::add_rule(const AlertRule& rule) {
    std::lock_guard lock(mutex_);
    rules_[rule.rule_id] = rule;
}

void AlertService::remove_rule(const std::string& rule_id) {
    std::lock_guard lock(mutex_);
    rules_.erase(rule_id);
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
double AlertService::calculate_rate(int events, int interval_seconds) {
    
    return static_cast<double>(events) / interval_seconds;  // Div by zero if interval is 0
    // FIX:
    // if (interval_seconds <= 0) return 0.0;
    // return static_cast<double>(events) / interval_seconds;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void AlertService::update_alert_state(const std::string& rule_id, bool triggered) {
    
    // Thread A checks, Thread B checks, both see false, both update to true
    if (alert_states_[rule_id] != triggered) {  // Check
        // Another thread could modify here
        alert_states_[rule_id] = triggered;     // Act
    }
    // FIX: Use mutex or atomic compare-exchange
    // std::lock_guard lock(mutex_);
    // alert_states_[rule_id] = triggered;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
bool AlertService::acquire_lock(const std::string& resource, int lease_seconds) {
    auto now = std::chrono::steady_clock::now();
    auto expiry = std::chrono::duration_cast<std::chrono::seconds>(
        now.time_since_epoch()).count() + lease_seconds;

    std::lock_guard lock(mutex_);

    // Check if lock is held by someone else
    auto it = lock_expiry_.find(resource);
    if (it != lock_expiry_.end()) {
        auto current_time = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        if (it->second > current_time) {
            return false;  // Lock held by someone else
        }
    }

    
    // Long-running operations will have their lock expire
    lock_expiry_[resource] = expiry;
    return true;
    // FIX: Provide renew_lock() method that must be called periodically
}

void AlertService::release_lock(const std::string& resource) {
    std::lock_guard lock(mutex_);
    lock_expiry_.erase(resource);
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void AlertService::transition_circuit(const std::string& circuit_id, const std::string& new_state) {
    std::lock_guard lock(mutex_);

    
    // Should only allow: closed->open, open->half_open, half_open->closed/open
    circuit_states_[circuit_id] = new_state;  

    // FIX: Validate state machine transitions
    // std::string current = circuit_states_[circuit_id];
    // if (current == CB_CLOSED && new_state != CB_OPEN) return;
    // if (current == CB_OPEN && new_state != CB_HALF_OPEN) return;
    // if (current == CB_HALF_OPEN && new_state != CB_CLOSED && new_state != CB_OPEN) return;
    // circuit_states_[circuit_id] = new_state;
}

std::string AlertService::get_circuit_state(const std::string& circuit_id) const {
    std::lock_guard lock(mutex_);
    auto it = circuit_states_.find(circuit_id);
    if (it != circuit_states_.end()) {
        return it->second;
    }
    return CB_CLOSED;  // Default state
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
bool AlertService::retry_operation(std::function<bool()> op, int max_retries) {
    for (int attempt = 0; attempt < max_retries; ++attempt) {
        if (op()) {
            return true;
        }
        
        // This causes retry storms and overwhelms failing service
    }
    return false;
    // FIX: Add exponential backoff
    // std::this_thread::sleep_for(std::chrono::milliseconds(100 * (1 << attempt)));
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void AlertService::set_leader(const std::string& node_id, int fencing_token) {
    std::lock_guard lock(mutex_);
    
    // Old leader could overwrite with stale token
    cached_leader_ = node_id;
    cached_fencing_token_ = fencing_token;
    // FIX:
    // if (fencing_token > cached_fencing_token_) {
    //     cached_leader_ = node_id;
    //     cached_fencing_token_ = fencing_token;
    // }
}

bool AlertService::is_leader(const std::string& node_id) const {
    std::lock_guard lock(mutex_);
    
    return cached_leader_ == node_id;
    // FIX: Should verify with external coordinator
}

// ---------------------------------------------------------------------------
// Alert utility functions
// ---------------------------------------------------------------------------
bool evaluate_rule(const AlertRule& rule, double current_value) {
    if (rule.condition == "greater_than") {
        return current_value > rule.threshold;
    } else if (rule.condition == "less_than") {
        return current_value < rule.threshold;
    } else if (rule.condition == "equals") {
        return std::abs(current_value - rule.threshold) < EPSILON;
    }
    return false;
}

bool AlertService::probe_circuit(const std::string& circuit_id) {
    std::lock_guard lock(mutex_);
    auto it = circuit_states_.find(circuit_id);
    if (it == circuit_states_.end() || it->second != CB_HALF_OPEN) {
        return false;
    }
    circuit_probe_count_[circuit_id]++;
    return true;
}

std::vector<AlertEvent> check_alerts(const std::vector<DataPoint>& points) {
    std::vector<AlertEvent> events;
    // Would check all rules against points
    return events;
}

}  // namespace signalstream
