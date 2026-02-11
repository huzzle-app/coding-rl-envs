#include "signalstream/core.hpp"
#include <algorithm>
#include <sstream>
#include <iostream>

namespace signalstream {

Telemetry::Telemetry() {}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void Telemetry::start_span(const std::string& name) {
    std::lock_guard lock(mutex_);

    // Generate new span ID
    std::stringstream ss;
    ss << "span_" << name << "_" << metrics_.size();

    
    // When async task runs, it won't have this context
    current_context_.parent_id = current_context_.span_id;
    current_context_.span_id = ss.str();
}

void Telemetry::end_span() {
    std::lock_guard lock(mutex_);
    // Pop back to parent
    current_context_.span_id = current_context_.parent_id;
    current_context_.parent_id = "";
    current_context_.trace_id = "";
}

TraceContext Telemetry::get_current_context() const {
    std::lock_guard lock(mutex_);
    return current_context_;
}

void Telemetry::set_context(const TraceContext& ctx) {
    std::lock_guard lock(mutex_);
    current_context_ = ctx;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void Telemetry::record_metric(const std::string& name, double value,
                               const std::unordered_map<std::string, std::string>& labels) {
    std::lock_guard lock(mutex_);

    
    // If labels include high-cardinality values (like user_id, request_id),
    // this causes memory explosion
    std::string key = name;
    for (const auto& [k, v] : labels) {
        key += "_" + k + "=" + v;  
    }

    metrics_[key].push_back(value);

    // FIX: Validate/limit labels and reject high-cardinality values
    // static const std::unordered_set<std::string> allowed_labels = {"method", "status", "endpoint"};
    // for (const auto& [k, v] : labels) {
    //     if (allowed_labels.count(k) == 0) continue;
    //     key += "_" + k + "=" + v;
    // }
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void Telemetry::set_log_level(const std::string& level) {
    std::lock_guard lock(mutex_);
    
    log_level_ = level;  // Stored as-is, but compared literally
    // FIX: Normalize to lowercase
    // log_level_ = level;
    // std::transform(log_level_.begin(), log_level_.end(), log_level_.begin(), ::tolower);
}

bool Telemetry::should_log(const std::string& level) const {
    std::lock_guard lock(mutex_);

    
    static const std::vector<std::string> levels = {"trace", "debug", "info", "warn", "error"};

    auto config_it = std::find(levels.begin(), levels.end(), log_level_);
    auto msg_it = std::find(levels.begin(), levels.end(), level);  

    if (config_it == levels.end() || msg_it == levels.end()) {
        return false;  
    }

    return msg_it >= config_it;

    // FIX: Convert both to lowercase before comparison
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void Telemetry::log_message(const std::string& level, const std::string& message) {
    
    // message = "ok\n[ERROR] Fake error injected" would create fake log entry
    std::cout << "[" << level << "] " << message << std::endl;

    // FIX: Sanitize newlines and control characters
    // std::string sanitized = message;
    // for (char& c : sanitized) {
    //     if (c == '\n' || c == '\r' || c < 32) c = ' ';
    // }
    // std::cout << "[" << level << "] " << sanitized << std::endl;
}

// ---------------------------------------------------------------------------
// Telemetry utility functions
// ---------------------------------------------------------------------------
void emit_metric(const std::string& name, double value) {
    // Simple metric emission
    std::cout << "METRIC " << name << "=" << value << std::endl;
}

void flush_metrics() {
    // Would flush to metrics backend
}

}  // namespace signalstream
