#pragma once

#ifndef CACHEFORGE_CONFIG_H
#define CACHEFORGE_CONFIG_H

#include <string>
#include <cstdint>
#include <optional>
#include <chrono>

namespace cacheforge {

struct Config {
    std::string bind_address = "0.0.0.0";
    uint16_t port = 6380;
    size_t max_memory_bytes = 256 * 1024 * 1024;  // 256MB
    size_t max_connections = 1024;
    int eviction_policy = 0;  // 0=LRU, 1=LFU, 2=random
    std::chrono::seconds default_ttl{0};  // 0 = no expiry
    std::string log_level = "info";
    std::string snapshot_dir = "/tmp/cacheforge";
    int snapshot_interval_secs = 300;
    std::string replication_host;
    uint16_t replication_port = 0;
    std::string database_url;
    std::string redis_url;

    
    // NOTE: CACHEFORGE_PORT env var is parsed without error handling
    static Config from_env();
};


// Global configuration instance used across translation units
extern Config CONFIG_INSTANCE;

Config& get_config();

}  // namespace cacheforge

#endif  // CACHEFORGE_CONFIG_H
