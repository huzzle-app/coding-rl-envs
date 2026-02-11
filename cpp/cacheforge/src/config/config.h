#pragma once

// FIX: This file is fine; connection.h needs its own unique guard name
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

    
    // will throw std::invalid_argument on non-numeric CACHEFORGE_PORT env var
    // FIX: Wrap std::stoi in try-catch and return default on failure
    static Config from_env();
};


// file-scope static, but init order across translation units is undefined
// FIX: Replace with a function returning a function-local static (Meyers' singleton)
extern Config CONFIG_INSTANCE;

Config& get_config();

}  // namespace cacheforge

#endif  // CACHEFORGE_CONFIG_H
