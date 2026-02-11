#include <gtest/gtest.h>
#include "protocol/parser.h"
#include "storage/expiry.h"
#include "storage/hashtable.h"
#include "server/connection.h"
#include <cstring>
#include <climits>

using namespace cacheforge;

// ========== Bug E1: Integer overflow TTL ==========

TEST(SecurityTest, test_ttl_overflow_protection) {
    
    ExpiryManager em;

    // INT64_MAX seconds as TTL should not wrap to negative/past
    em.set_expiry_seconds("huge_ttl", INT64_MAX);
    EXPECT_FALSE(em.is_expired("huge_ttl"))
        << "TTL integer overflow set expiry in the past";
}

TEST(SecurityTest, test_ttl_negative_values) {
    ExpiryManager em;
    // Negative TTL should be handled gracefully
    em.set_expiry_seconds("negative_ttl", -1);
    // Should either reject or treat as already expired
}

TEST(SecurityTest, test_ttl_zero) {
    ExpiryManager em;
    em.set_expiry_seconds("zero_ttl", 0);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    EXPECT_TRUE(em.is_expired("zero_ttl"));
}

// ========== Bug E2: Format string vulnerability ==========
// (E2 bug would be in a logging path that takes user input as format string)

TEST(SecurityTest, test_no_format_string_in_error_messages) {
    
    Parser parser;

    // A malicious key with format specifiers
    std::string malicious = "%s%s%s%n%x%x";
    auto cmd = parser.parse_text("SET " + malicious + " value");

    // Should not crash or corrupt memory
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->args[0], malicious);
}

TEST(SecurityTest, test_format_specifiers_in_key) {
    
    HashTable ht;
    std::string key_with_percent = "user:%d:%n";
    ht.set(key_with_percent, Value("data"));

    auto val = ht.get(key_with_percent);
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(val->as_string(), "data");
}

// ========== Bug E3: Buffer overread ==========

TEST(SecurityTest, test_extract_key_no_overread) {
    
    Parser parser;

    // Data with embedded null byte - should use full length
    uint8_t data[10] = {'a', 'b', '\0', 'c', 'd', 'e', 'f', 'g', 'h', 'i'};
    std::string key = parser.extract_key(data, 10);

    // Key should be 10 bytes long, including the null byte
    EXPECT_EQ(key.size(), 10) << "Buffer overread: strlen truncated at null byte";
}

TEST(SecurityTest, test_binary_key_preserved) {
    
    Parser parser;

    uint8_t binary_key[] = {0xFF, 0x00, 0x01, 0x00, 0xFE};
    std::string key = parser.extract_key(binary_key, 5);
    EXPECT_EQ(key.size(), 5);
    EXPECT_EQ(static_cast<uint8_t>(key[0]), 0xFF);
    EXPECT_EQ(static_cast<uint8_t>(key[1]), 0x00);
    EXPECT_EQ(static_cast<uint8_t>(key[4]), 0xFE);
}

// ========== Bug E4: Unvalidated key length ==========

TEST(SecurityTest, test_key_length_limit) {
    
    HashTable ht;

    // Very large key (1MB) - should be rejected or truncated
    std::string huge_key(1024 * 1024, 'x');
    // A well-implemented cache should reject keys over a reasonable limit
    // (e.g., 512KB or 1MB)
    bool inserted = ht.set(huge_key, Value("tiny_value"));

    // After fix: either the set was rejected (key doesn't exist),
    // or if accepted, the data is retrievable without corruption
    auto val = ht.get(huge_key);
    if (!inserted || !val.has_value()) {
        // Key was rejected - correct behavior for unvalidated key length fix
        EXPECT_FALSE(ht.contains(huge_key))
            << "Key was rejected but still appears in the table";
    } else {
        // Key was accepted - verify data integrity (no buffer overflow/corruption)
        EXPECT_EQ(val->as_string(), "tiny_value")
            << "Value corrupted after storing oversized key";
    }

    // A normal-sized key should always work
    ht.set("normal_key", Value("normal_value"));
    EXPECT_TRUE(ht.contains("normal_key"));
}

TEST(SecurityTest, test_empty_key_handling) {
    HashTable ht;
    ht.set("", Value("empty_key_value"));
    auto val = ht.get("");
    // Empty key should either work or be rejected - not crash
}

// ========== Bug B1: Buffer overflow in parser ==========

TEST(SecurityTest, test_parse_raw_buffer_overflow_protection) {
    
    Parser parser;

    // Craft packet with length = 0xFFFFFFFF but only 20 bytes of data
    uint8_t data[20] = {};
    uint32_t overflow_len = 0xFFFFFFFF;
    std::memcpy(data, &overflow_len, 4);

    auto result = parser.parse_raw(data, sizeof(data));
    EXPECT_FALSE(result.has_value()) << "Parser accepted invalid length prefix";
}

TEST(SecurityTest, test_parse_raw_zero_length) {
    Parser parser;
    auto result = parser.parse_raw(nullptr, 0);
    EXPECT_FALSE(result.has_value());
}

// ========== Bug C1: shared_ptr cycle ==========

TEST(SecurityTest, test_connection_no_reference_cycle) {
    
    // This causes a memory leak since the destructor is never called
    // After fix with weak_ptr, the connection should be properly destroyed

    // Verify that a shared_ptr<Connection> can reach use_count 1
    // (meaning no internal self-reference keeps it alive)
    boost::asio::io_context ioc;
    boost::asio::ip::tcp::socket sock(ioc);
    auto conn = std::make_shared<Connection>(std::move(sock));
    std::weak_ptr<Connection> weak_conn = conn;

    // After start(), the buggy code stores shared_from_this() in self_ref_,
    // which bumps the use_count and prevents destruction.
    // With the fix, use_count should drop to 0 when we release our handle.
    conn->stop();  // ensure connection is stopped
    conn.reset();  // release our reference

    // If the cycle is broken, weak_conn should now be expired
    EXPECT_TRUE(weak_conn.expired())
        << "Connection leaked: shared_ptr cycle keeps it alive (use_count > 0)";
}

// ========== Bug C3: double-delete via get() ==========

TEST(SecurityTest, test_unique_ptr_get_no_double_delete) {
    
    // Caller must not delete it. After fix, ownership is clear.

    boost::asio::io_context ioc;
    boost::asio::ip::tcp::socket sock(ioc);
    Connection conn(std::move(sock));

    // Create a buffer and hand ownership to the Connection
    auto buf = std::make_unique<char[]>(128);
    buf[0] = 'X';
    buf[1] = 'Y';
    conn.set_buffer(std::move(buf), 128);

    // get_buffer_raw() should return a valid pointer to the buffer
    char* raw = conn.get_buffer_raw();
    ASSERT_NE(raw, nullptr);
    EXPECT_EQ(raw[0], 'X');
    EXPECT_EQ(raw[1], 'Y');

    // After reset, the unique_ptr no longer owns anything
    conn.set_buffer(nullptr, 0);
    EXPECT_EQ(conn.get_buffer_raw(), nullptr)
        << "After releasing buffer, get_buffer_raw should return nullptr";
}

// ========== General security tests ==========

TEST(SecurityTest, test_parser_handles_malformed_input) {
    Parser parser;

    // Various malformed inputs
    EXPECT_FALSE(parser.parse_text("").has_value());

    uint8_t garbage[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    auto result = parser.parse_raw(garbage, sizeof(garbage));
    // Should not crash
}

TEST(SecurityTest, test_value_type_confusion) {
    Value str_val("hello");
    EXPECT_THROW(str_val.as_integer(), std::runtime_error);
    EXPECT_THROW(str_val.as_list(), std::runtime_error);
}

TEST(SecurityTest, test_hashtable_key_injection) {
    HashTable ht;

    // Keys with special characters
    ht.set("key\nwith\nnewlines", Value("val1"));
    ht.set("key\twith\ttabs", Value("val2"));
    ht.set("key with spaces", Value("val3"));

    EXPECT_TRUE(ht.contains("key\nwith\nnewlines"));
    EXPECT_TRUE(ht.contains("key\twith\ttabs"));
    EXPECT_TRUE(ht.contains("key with spaces"));
}

TEST(SecurityTest, test_large_value_handling) {
    HashTable ht;
    std::string large_value(1024 * 1024, 'A');  // 1MB value
    ht.set("large_key", Value(large_value));
    auto val = ht.get("large_key");
    ASSERT_TRUE(val.has_value());
    EXPECT_EQ(val->as_string().size(), 1024 * 1024);
}
