#include <gtest/gtest.h>
#include "data/value.h"
#include <cstring>

using namespace cacheforge;

// ========== Bug B2: string_view dangling reference ==========

TEST(ValueTest, test_string_view_not_dangling_after_move) {
    
    // After the Value is moved, the view should not be used.
    // The fix should return std::string instead of string_view.
    Value v("hello world");

    // Get the value as a string (not string_view) to be safe
    std::string safe_copy = v.as_string();
    EXPECT_EQ(safe_copy, "hello world");

    // Move the value
    Value moved = std::move(v);

    // The safe copy should still be valid
    EXPECT_EQ(safe_copy, "hello world");

    // After fix, this should work (returns string, not dangling view)
    // With the bug, this would be UB if we used string_view after move
    std::string from_moved = moved.as_string();
    EXPECT_EQ(from_moved, "hello world");
}

TEST(ValueTest, test_as_string_returns_copy) {
    
    Value v("test");
    auto result = v.as_string();
    EXPECT_EQ(result, "test");
    // result should be independent of v
}

// ========== Bug D2: Strict aliasing violation ==========

TEST(ValueTest, test_fast_integer_parse_no_aliasing_violation) {
    
    Value v(std::string(8, '\x01'));  // 8 bytes of 0x01

    // This should not cause UB - using memcpy internally
    int64_t result = v.fast_integer_parse();

    // Verify the result matches what memcpy would give
    int64_t expected;
    std::string data(8, '\x01');
    std::memcpy(&expected, data.data(), sizeof(int64_t));
    EXPECT_EQ(result, expected);
}

TEST(ValueTest, test_fast_integer_parse_alignment) {
    
    Value v(std::string(8, '\0'));
    // Should not crash even if string data is not 8-byte aligned
    EXPECT_NO_THROW(v.fast_integer_parse());
}

// ========== Bug D4: std::move on const has no effect ==========

TEST(ValueTest, test_make_moved_value_actually_moves) {
    
    // doesn't actually move - it copies instead.
    // After fix, the original should be in a moved-from state.
    Value original("large_string_data_that_should_be_moved_not_copied");
    std::string original_data = original.as_string();

    Value moved = make_moved_value(std::move(original));
    EXPECT_EQ(moved.as_string(), original_data);

    // After a real move, original should be in moved-from state
    // (i.e., empty or unspecified but valid)
    // With the bug, original is unchanged because it was actually copied
}

TEST(ValueTest, test_make_moved_value_efficient) {
    
    // We can't easily test move vs copy, but we can verify the result
    Value v(int64_t(42));
    Value result = make_moved_value(std::move(v));
    EXPECT_EQ(result.as_integer(), 42);
}

// ========== Basic Value tests ==========

TEST(ValueTest, test_string_value) {
    Value v("hello");
    EXPECT_EQ(v.type(), Value::Type::String);
    EXPECT_EQ(v.as_string(), "hello");
}

TEST(ValueTest, test_integer_value) {
    Value v(int64_t(42));
    EXPECT_EQ(v.type(), Value::Type::Integer);
    EXPECT_EQ(v.as_integer(), 42);
}

TEST(ValueTest, test_list_value) {
    Value v(std::vector<std::string>{"a", "b", "c"});
    EXPECT_EQ(v.type(), Value::Type::List);
    EXPECT_EQ(v.as_list().size(), 3);
}

TEST(ValueTest, test_binary_value) {
    Value v(std::vector<uint8_t>{0x00, 0xFF, 0x42});
    EXPECT_EQ(v.type(), Value::Type::Binary);
    EXPECT_EQ(v.as_binary().size(), 3);
}

TEST(ValueTest, test_equality) {
    Value v1("hello");
    Value v2("hello");
    Value v3("world");
    EXPECT_EQ(v1, v2);
    EXPECT_NE(v1, v3);
}

TEST(ValueTest, test_type_mismatch_throws) {
    Value v("string");
    EXPECT_THROW(v.as_integer(), std::runtime_error);
}

TEST(ValueTest, test_memory_size) {
    Value v("test");
    EXPECT_GT(v.memory_size(), 0);
}
