#include <gtest/gtest.h>
#include <fstream>
#include <string>
#include <regex>
#include "data/value.h"

#ifndef SOURCE_DIR
#define SOURCE_DIR "."
#endif

using namespace cacheforge;

static std::string read_source(const std::string& rel_path) {
    std::string path = std::string(SOURCE_DIR) + "/" + rel_path;
    std::ifstream f(path);
    if (!f.is_open()) return "";
    return std::string(std::istreambuf_iterator<char>(f),
                       std::istreambuf_iterator<char>());
}

// ========== Bug D2: Strict aliasing violation in fast_integer_parse ==========

TEST(UBDetectionTest, test_fast_integer_parse_no_strict_aliasing_violation) {
    std::string src = read_source("src/data/value.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read value.cpp";

    // fast_integer_parse must NOT use reinterpret_cast to int64_t*
    // The safe alternative is std::memcpy
    bool has_reinterpret =
        src.find("reinterpret_cast<const int64_t*>") != std::string::npos ||
        src.find("reinterpret_cast<int64_t*>") != std::string::npos;
    EXPECT_FALSE(has_reinterpret)
        << "fast_integer_parse uses reinterpret_cast (strict aliasing violation / UB). "
           "Use std::memcpy instead.";
}

// ========== Bug D4: make_moved_value takes const& (prevents real move) ==========

TEST(UBDetectionTest, test_make_moved_value_actually_moves) {
    // Use a string long enough to avoid SSO (small string optimization)
    std::string long_str(100, 'X');
    Value v(long_str);

    Value moved = make_moved_value(v);

    // If make_moved_value truly moves (takes non-const ref),
    // v's internal string should be empty (moved-from state).
    // With const& (bug), v is copied — the original is unchanged.
    try {
        std::string after = v.as_string();
        EXPECT_NE(after, long_str)
            << "make_moved_value did not actually move the source value. "
               "Parameter is likely const& instead of Value&.";
    } catch (...) {
        // Accessing a moved-from value may throw — that's acceptable
    }
}

// ========== Bug B2: as_string_view returns string_view (dangling hazard) ==========

TEST(UBDetectionTest, test_string_view_return_type_safe) {
    std::string src = read_source("src/data/value.h");
    ASSERT_FALSE(src.empty()) << "Could not read value.h";

    // as_string_view should NOT return std::string_view because
    // the view dangles if the Value is moved or destroyed.
    // It should return const std::string& instead.
    std::regex sv_pattern(R"(string_view\s+as_string_view)");
    bool returns_string_view = std::regex_search(src, sv_pattern);
    EXPECT_FALSE(returns_string_view)
        << "as_string_view() returns string_view which dangles after Value is moved. "
           "Return const std::string& instead.";
}

// ========== Bug D3: sequence_counter_ is int64_t (signed overflow = UB) ==========

TEST(UBDetectionTest, test_sequence_counter_type_is_unsigned) {
    std::string src = read_source("src/replication/replicator.h");
    ASSERT_FALSE(src.empty()) << "Could not read replicator.h";

    // sequence_counter_ must be uint64_t, not int64_t.
    // Signed integer overflow is undefined behavior.
    bool has_signed = src.find("int64_t sequence_counter_") != std::string::npos &&
                      src.find("uint64_t sequence_counter_") == std::string::npos;
    EXPECT_FALSE(has_signed)
        << "sequence_counter_ is int64_t — signed overflow is UB. "
           "Use uint64_t instead.";
}
