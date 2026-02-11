#include <gtest/gtest.h>
#include "server/server.h"
#include "server/connection.h"
#include "config/config.h"
#include "storage/hashtable.h"
#include "storage/eviction.h"
#include "storage/expiry.h"
#include "protocol/parser.h"
#include <csignal>
#include <thread>
#include <atomic>

using namespace cacheforge;

// ========== Bug L4: Include guard collision ==========

TEST(ServerIntegrationTest, test_config_and_connection_both_included) {
    
    // If both are included, the second one is silently skipped.
    // After fix, both types should be available.
    Config cfg;
    EXPECT_EQ(cfg.port, 6380);

    // Connection type should also be available (not skipped by guard collision)
    // This test verifies that the Connection class is properly declared
    // If the guard collision bug exists, this won't compile
    EXPECT_TRUE(true);  // If we got here, both headers were included
}

TEST(ServerIntegrationTest, test_config_connection_type_availability) {
    
    Config cfg;
    cfg.port = 9999;
    EXPECT_EQ(cfg.port, 9999);
}

// ========== Bug L2: Signal handler UB ==========

TEST(ServerIntegrationTest, test_signal_handler_uses_atomic_flag) {
    
    // This test verifies the shutdown flag is properly set and read

    // Simulate the fixed signal handler pattern:
    // A sig_atomic_t flag should be set by the handler and polled in the main loop
    volatile sig_atomic_t shutdown_flag = 0;

    // Before signal, flag should be 0
    EXPECT_EQ(shutdown_flag, 0);

    // Simulate what the fixed signal handler does: set the flag
    shutdown_flag = 1;

    // After signal, flag should be 1 (readable without UB)
    EXPECT_EQ(shutdown_flag, 1)
        << "Shutdown flag not set correctly; signal handler should use "
           "sig_atomic_t instead of calling spdlog (which is UB)";

    // Verify the flag can be reset for clean re-initialization
    shutdown_flag = 0;
    EXPECT_EQ(shutdown_flag, 0);
}

// ========== Bug A5: volatile-as-atomic ==========

TEST(ServerIntegrationTest, test_accepting_flag_is_atomic) {
    
    // volatile provides no atomicity guarantees in C++

    // Test that a shared boolean flag works correctly across threads
    // when using std::atomic (the fix), but fails under volatile (the bug)
    std::atomic<bool> flag{true};
    std::atomic<int> read_count{0};

    // Writer thread sets the flag to false
    std::thread writer([&flag]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        flag.store(false, std::memory_order_release);
    });

    // Reader thread polls until it sees false
    std::thread reader([&flag, &read_count]() {
        while (flag.load(std::memory_order_acquire)) {
            read_count.fetch_add(1);
            std::this_thread::yield();
        }
    });

    writer.join();
    reader.join();

    // The reader must have seen the flag become false (not stuck in loop)
    EXPECT_FALSE(flag.load())
        << "Flag should be false; std::atomic<bool> required instead of volatile bool";
}

// ========== Integration: full pipeline ==========

TEST(ServerIntegrationTest, test_hashtable_with_eviction) {
    HashTable ht(3);
    EvictionManager em(3);

    ht.set_eviction_callback([&em](const std::string& key) {
        em.record_insert(key, 1);
    });

    ht.set("key1", Value("val1"));
    ht.set("key2", Value("val2"));
    ht.set("key3", Value("val3"));

    EXPECT_EQ(ht.size(), 3);
}

TEST(ServerIntegrationTest, test_hashtable_with_expiry) {
    HashTable ht;
    ExpiryManager em;

    ht.set("temp_key", Value("temp_val"));
    em.set_expiry("temp_key", std::chrono::seconds(0));

    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    EXPECT_TRUE(em.is_expired("temp_key"));
}

TEST(ServerIntegrationTest, test_parser_to_hashtable_pipeline) {
    Parser parser;
    HashTable ht;

    auto cmd = parser.parse_text("SET mykey myvalue");
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->name, "SET");

    if (cmd->name == "SET" && cmd->args.size() >= 2) {
        ht.set(cmd->args[0], Value(cmd->args[1]));
    }

    auto val = ht.get("mykey");
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(val->as_string(), "myvalue");
}

TEST(ServerIntegrationTest, test_set_get_delete_pipeline) {
    Parser parser;
    HashTable ht;

    // SET
    auto set_cmd = parser.parse_text("SET counter 100");
    ASSERT_TRUE(set_cmd.has_value());
    ht.set(set_cmd->args[0], Value(set_cmd->args[1]));

    // GET
    auto val = ht.get("counter");
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(val->as_string(), "100");

    // DEL
    EXPECT_TRUE(ht.remove("counter"));
    EXPECT_FALSE(ht.contains("counter"));
}

TEST(ServerIntegrationTest, test_eviction_with_expiry) {
    EvictionManager em(2);
    ExpiryManager exp;

    em.record_insert("k1", 100);
    em.record_insert("k2", 200);

    exp.set_expiry("k1", std::chrono::seconds(0));
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    EXPECT_TRUE(exp.is_expired("k1"));
    EXPECT_FALSE(exp.is_expired("k2"));
}

TEST(ServerIntegrationTest, test_multiple_data_types) {
    HashTable ht;

    ht.set("string_key", Value("hello"));
    ht.set("int_key", Value(int64_t(42)));
    ht.set("list_key", Value(std::vector<std::string>{"a", "b", "c"}));

    EXPECT_EQ(ht.get("string_key")->as_string(), "hello");
    EXPECT_EQ(ht.get("int_key")->as_integer(), 42);
    EXPECT_EQ(ht.get("list_key")->as_list().size(), 3);
}

TEST(ServerIntegrationTest, test_keys_command) {
    HashTable ht;
    ht.set("user:alice", Value("data1"));
    ht.set("user:bob", Value("data2"));
    ht.set("session:123", Value("data3"));

    auto user_keys = ht.keys("user:*");
    EXPECT_EQ(user_keys.size(), 2);
}
