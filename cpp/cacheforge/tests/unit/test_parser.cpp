#include <gtest/gtest.h>
#include "protocol/parser.h"
#include <cstring>

using namespace cacheforge;

// ========== Bug B1: Buffer overflow in parse_raw ==========

TEST(ParserTest, test_parse_raw_validates_command_length) {
    
    Parser parser;
    // Craft a packet where cmd_len = 1000 but actual data is only 20 bytes
    uint8_t data[20] = {};
    uint32_t fake_len = 1000;
    std::memcpy(data, &fake_len, 4);  // cmd_len = 1000

    auto result = parser.parse_raw(data, sizeof(data));
    // Should return nullopt because claimed length exceeds buffer
    EXPECT_FALSE(result.has_value());
}

TEST(ParserTest, test_parse_raw_validates_arg_length) {
    
    Parser parser;
    uint8_t data[24] = {};
    size_t offset = 0;

    // cmd_len = 3, cmd = "SET"
    uint32_t cmd_len = 3;
    std::memcpy(data + offset, &cmd_len, 4); offset += 4;
    std::memcpy(data + offset, "SET", 3); offset += 3;

    // argc = 1
    uint32_t argc = 1;
    std::memcpy(data + offset, &argc, 4); offset += 4;

    // arg_len = 500 (way more than remaining)
    uint32_t arg_len = 500;
    std::memcpy(data + offset, &arg_len, 4); offset += 4;

    auto result = parser.parse_raw(data, offset + 4);
    // Should not crash, and either return nullopt or partial command
    if (result.has_value()) {
        // Args should be empty since we couldn't read the full arg
        EXPECT_TRUE(result->args.empty());
    }
}

TEST(ParserTest, test_parse_raw_valid_command) {
    Parser parser;
    uint8_t data[32] = {};
    size_t offset = 0;

    uint32_t cmd_len = 3;
    std::memcpy(data + offset, &cmd_len, 4); offset += 4;
    std::memcpy(data + offset, "GET", 3); offset += 3;

    uint32_t argc = 1;
    std::memcpy(data + offset, &argc, 4); offset += 4;

    uint32_t arg_len = 5;
    std::memcpy(data + offset, &arg_len, 4); offset += 4;
    std::memcpy(data + offset, "mykey", 5); offset += 5;

    auto result = parser.parse_raw(data, offset);
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(result->name, "GET");
    ASSERT_EQ(result->args.size(), 1);
    EXPECT_EQ(result->args[0], "mykey");
}

TEST(ParserTest, test_parse_raw_null_data) {
    Parser parser;
    auto result = parser.parse_raw(nullptr, 0);
    EXPECT_FALSE(result.has_value());
}

// ========== Bug E3: Buffer overread (strlen vs explicit length) ==========

TEST(ParserTest, test_extract_key_respects_length_parameter) {
    
    Parser parser;
    const uint8_t data[] = {'h', 'e', 'l', 'l', 'o', '\0', 'w', 'o', 'r', 'l', 'd'};

    // With embedded null byte, we want the full 11-byte key
    std::string key = parser.extract_key(data, 11);
    EXPECT_EQ(key.size(), 11);
    EXPECT_NE(key, "hello");  // Should NOT stop at the null byte
}

TEST(ParserTest, test_extract_key_binary_safe) {
    
    Parser parser;
    uint8_t data[] = {0x00, 0x01, 0x00, 0x02};
    std::string key = parser.extract_key(data, 4);
    EXPECT_EQ(key.size(), 4);
}

TEST(ParserTest, test_parse_text_basic) {
    Parser parser;
    auto cmd = parser.parse_text("set mykey myvalue");
    ASSERT_TRUE(cmd.has_value());
    EXPECT_EQ(cmd->name, "SET");
    ASSERT_EQ(cmd->args.size(), 2);
    EXPECT_EQ(cmd->args[0], "mykey");
    EXPECT_EQ(cmd->args[1], "myvalue");
}

TEST(ParserTest, test_parse_text_empty) {
    Parser parser;
    auto cmd = parser.parse_text("");
    EXPECT_FALSE(cmd.has_value());
}

TEST(ParserTest, test_serialize_ok) {
    EXPECT_EQ(Parser::serialize_ok(), "+OK\r\n");
}

TEST(ParserTest, test_serialize_error) {
    EXPECT_EQ(Parser::serialize_error("bad key"), "-ERR bad key\r\n");
}

TEST(ParserTest, test_serialize_integer) {
    EXPECT_EQ(Parser::serialize_integer(42), ":42\r\n");
}

TEST(ParserTest, test_serialize_null) {
    EXPECT_EQ(Parser::serialize_null(), "$-1\r\n");
}
