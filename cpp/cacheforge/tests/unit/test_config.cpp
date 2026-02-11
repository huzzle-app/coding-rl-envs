#include <gtest/gtest.h>
#include "config/config.h"
#include <cstdlib>

using namespace cacheforge;

// ========== Bug L1: Static initialization fiasco ==========

TEST(ConfigTest, test_get_config_returns_valid_instance) {
    
    // instead of returning reference to global CONFIG_INSTANCE
    auto& cfg = get_config();
    // Should return a properly initialized config, not zero/garbage
    EXPECT_GT(cfg.port, 0);
    EXPECT_FALSE(cfg.bind_address.empty());
}

TEST(ConfigTest, test_config_singleton_same_address) {
    
    auto& cfg1 = get_config();
    auto& cfg2 = get_config();
    EXPECT_EQ(&cfg1, &cfg2);
}

TEST(ConfigTest, test_config_not_global_variable) {
    
    // static initialization order fiasco. Verify it's a function-local static.
    // After fix, CONFIG_INSTANCE should not be used for initialization.
    auto& cfg = get_config();
    EXPECT_EQ(cfg.port, 6380);  // default value
}

// ========== Bug L3: stoi exception on invalid port ==========

TEST(ConfigTest, test_config_handles_invalid_port_string) {
    
    setenv("CACHEFORGE_PORT", "not_a_number", 1);
    EXPECT_NO_THROW({
        Config cfg = Config::from_env();
        // Should fall back to default port
        EXPECT_EQ(cfg.port, 6380);
    });
    unsetenv("CACHEFORGE_PORT");
}

TEST(ConfigTest, test_config_handles_empty_port_string) {
    
    setenv("CACHEFORGE_PORT", "", 1);
    EXPECT_NO_THROW({
        Config cfg = Config::from_env();
        EXPECT_EQ(cfg.port, 6380);
    });
    unsetenv("CACHEFORGE_PORT");
}

TEST(ConfigTest, test_config_valid_port_string) {
    setenv("CACHEFORGE_PORT", "7777", 1);
    Config cfg = Config::from_env();
    EXPECT_EQ(cfg.port, 7777);
    unsetenv("CACHEFORGE_PORT");
}

TEST(ConfigTest, test_config_memory_parsing) {
    setenv("CACHEFORGE_MAX_MEMORY", "512m", 1);
    Config cfg = Config::from_env();
    EXPECT_EQ(cfg.max_memory_bytes, 512ULL * 1024 * 1024);
    unsetenv("CACHEFORGE_MAX_MEMORY");
}

TEST(ConfigTest, test_config_defaults) {
    Config cfg;
    EXPECT_EQ(cfg.bind_address, "0.0.0.0");
    EXPECT_EQ(cfg.port, 6380);
    EXPECT_EQ(cfg.max_memory_bytes, 256ULL * 1024 * 1024);
    EXPECT_EQ(cfg.log_level, "info");
}
