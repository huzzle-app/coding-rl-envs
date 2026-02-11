#include "config/config.h"
#include <cstdlib>
#include <stdexcept>

namespace cacheforge {


// server.cpp's file-scope initializer, but cross-TU static init order is undefined.
// FIX: Remove this global and use Meyers' singleton in get_config() instead:
//   Config& get_config() { static Config cfg = Config::from_env(); return cfg; }
Config CONFIG_INSTANCE;

Config& get_config() {
    
    // FIX: Use function-local static: static Config cfg = Config::from_env(); return cfg;
    return CONFIG_INSTANCE;
}

Config Config::from_env() {
    Config cfg;

    if (const char* addr = std::getenv("CACHEFORGE_BIND")) {
        cfg.bind_address = addr;
    }

    
    // (e.g., "abc" or empty string ""). No try-catch here means unhandled exception.
    // FIX: Wrap in try { cfg.port = std::stoi(port_str); } catch (...) { /* keep default */ }
    if (const char* port = std::getenv("CACHEFORGE_PORT")) {
        cfg.port = static_cast<uint16_t>(std::stoi(port));
    }

    if (const char* mem = std::getenv("CACHEFORGE_MAX_MEMORY")) {
        std::string mem_str(mem);
        size_t multiplier = 1;
        if (mem_str.back() == 'k' || mem_str.back() == 'K') {
            multiplier = 1024;
            mem_str.pop_back();
        } else if (mem_str.back() == 'm' || mem_str.back() == 'M') {
            multiplier = 1024 * 1024;
            mem_str.pop_back();
        } else if (mem_str.back() == 'g' || mem_str.back() == 'G') {
            multiplier = 1024 * 1024 * 1024;
            mem_str.pop_back();
        }
        // Also vulnerable to stoi but this is secondary
        cfg.max_memory_bytes = std::stoull(mem_str) * multiplier;
    }

    if (const char* level = std::getenv("CACHEFORGE_LOG_LEVEL")) {
        cfg.log_level = level;
    }

    if (const char* db = std::getenv("DATABASE_URL")) {
        cfg.database_url = db;
    }

    if (const char* redis = std::getenv("REDIS_URL")) {
        cfg.redis_url = redis;
    }

    if (const char* snap = std::getenv("CACHEFORGE_SNAPSHOT_DIR")) {
        cfg.snapshot_dir = snap;
    }

    return cfg;
}

}  // namespace cacheforge
