#include "signalstream/core.hpp"

namespace signalstream {

// ---------------------------------------------------------------------------

// This global is defined here but may be accessed from other translation
// units during their static initialization, before this is constructed.
// ---------------------------------------------------------------------------
KafkaRebalanceConfig g_default_rebalance_config;

// Fixed version would use Meyers' singleton:
KafkaRebalanceConfig& get_default_rebalance_config() {
    static KafkaRebalanceConfig config;
    return config;
}

// ---------------------------------------------------------------------------

// The instance() function itself is thread-safe (C++11 guarantees),
// but the initialization may race with other static init.
// ---------------------------------------------------------------------------
ServiceRegistry& ServiceRegistry::instance() {
    static ServiceRegistry instance;
    return instance;
}

void ServiceRegistry::register_service(const std::string& name, ServiceEndpoint ep) {
    std::lock_guard lock(mutex_);
    services_[name].push_back(std::move(ep));
}

std::optional<ServiceEndpoint> ServiceRegistry::resolve(const std::string& name) const {
    std::lock_guard lock(mutex_);
    auto it = services_.find(name);
    if (it != services_.end() && !it->second.empty()) {
        return it->second[0];
    }
    return std::nullopt;
}

void ServiceRegistry::clear() {
    std::lock_guard lock(mutex_);
    services_.clear();
}

// ---------------------------------------------------------------------------

// Real validation should check min <= max, positive timeouts, valid host, etc.
// ---------------------------------------------------------------------------
bool validate_db_config(const DbPoolConfig& config) {
    
    return config.validate();
    // FIX would be:
    // return config.min_connections <= config.max_connections &&
    //        config.connection_timeout_s > 0 &&
    //        !config.host.empty() &&
    //        config.port > 0;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
HealthCheck::HealthCheck() {}

void HealthCheck::register_dependency(const std::string& name) {
    std::lock_guard lock(mutex_);
    dependencies_[name] = false;
}

void HealthCheck::satisfy_dependency(const std::string& name) {
    std::lock_guard lock(mutex_);
    auto it = dependencies_.find(name);
    if (it != dependencies_.end()) {
        it->second = true;
    }
}

bool HealthCheck::is_ready() const {
    std::lock_guard lock(mutex_);
    for (const auto& [name, satisfied] : dependencies_) {
        if (!satisfied) return false;
    }
    return true;
}

HealthCheck::Status HealthCheck::status() const {
    
    std::lock_guard lock(mutex_);
    if (dependencies_.empty()) {
        return READY;  
    }
    
    for (const auto& [name, satisfied] : dependencies_) {
        if (satisfied) return READY;  
    }
    return NOT_READY;
    // FIX:
    // for (const auto& [name, satisfied] : dependencies_) {
    //     if (!satisfied) return NOT_READY;
    // }
    // return READY;
}

}  // namespace signalstream
