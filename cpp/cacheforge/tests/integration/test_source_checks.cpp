#include <gtest/gtest.h>
#include <fstream>
#include <string>
#include <regex>

#ifndef SOURCE_DIR
#define SOURCE_DIR "."
#endif

static std::string read_source(const std::string& rel_path) {
    std::string path = std::string(SOURCE_DIR) + "/" + rel_path;
    std::ifstream f(path);
    if (!f.is_open()) return "";
    return std::string(std::istreambuf_iterator<char>(f),
                       std::istreambuf_iterator<char>());
}

// ========== Bug L2: Signal handler calls spdlog (not async-signal-safe) ==========

TEST(SourceCheckTest, test_signal_handler_no_spdlog) {
    std::string src = read_source("src/main.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read main.cpp";

    // Find the signal_handler function body
    auto pos = src.find("signal_handler");
    ASSERT_NE(pos, std::string::npos) << "signal_handler not found in main.cpp";

    auto brace = src.find('{', pos);
    ASSERT_NE(brace, std::string::npos);

    // Extract ~500 chars of the handler body
    std::string handler_body = src.substr(brace, 500);

    bool has_spdlog = handler_body.find("spdlog::") != std::string::npos;
    EXPECT_FALSE(has_spdlog)
        << "Signal handler calls spdlog (not async-signal-safe). "
           "Use write() or set a volatile sig_atomic_t flag instead.";
}

TEST(SourceCheckTest, test_signal_handler_uses_sig_atomic_t) {
    std::string src = read_source("src/main.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read main.cpp";

    bool has_sig_atomic = src.find("sig_atomic_t") != std::string::npos;
    EXPECT_TRUE(has_sig_atomic)
        << "main.cpp should use volatile sig_atomic_t for signal handler communication";
}

// ========== Bug A5: accepting_ is volatile bool (not thread-safe) ==========

TEST(SourceCheckTest, test_server_accepting_is_atomic) {
    std::string src = read_source("src/server/server.h");
    ASSERT_FALSE(src.empty()) << "Could not read server.h";

    bool has_volatile_bool = src.find("volatile bool accepting_") != std::string::npos;
    EXPECT_FALSE(has_volatile_bool)
        << "accepting_ uses volatile bool (not thread-safe). "
           "Use std::atomic<bool> instead.";
}

// ========== Bug A1: connection_count() / broadcast() lack synchronization ==========

TEST(SourceCheckTest, test_connection_count_is_synchronized) {
    std::string src = read_source("src/server/server.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read server.cpp";

    auto pos = src.find("connection_count");
    ASSERT_NE(pos, std::string::npos);

    std::string func_area = src.substr(pos, 200);
    bool has_lock = func_area.find("lock") != std::string::npos ||
                    func_area.find("mutex") != std::string::npos;
    EXPECT_TRUE(has_lock)
        << "connection_count() accesses connections_ without synchronization";
}

TEST(SourceCheckTest, test_broadcast_is_synchronized) {
    std::string src = read_source("src/server/server.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read server.cpp";

    auto pos = src.find("Server::broadcast");
    ASSERT_NE(pos, std::string::npos);

    std::string func_area = src.substr(pos, 300);
    bool has_lock = func_area.find("lock") != std::string::npos ||
                    func_area.find("mutex") != std::string::npos;
    EXPECT_TRUE(has_lock)
        << "broadcast() iterates connections_ without synchronization";
}

// ========== Bug C3: get_buffer_raw returns non-const char* ==========

TEST(SourceCheckTest, test_get_buffer_returns_const) {
    std::string src = read_source("src/server/connection.h");
    ASSERT_FALSE(src.empty()) << "Could not read connection.h";

    // Should be "const char* get_buffer_raw" not "char* get_buffer_raw"
    std::regex non_const_pattern(R"(\bchar\s*\*\s*get_buffer_raw)");
    std::regex const_pattern(R"(const\s+char\s*\*\s*get_buffer_raw)");

    bool has_non_const = std::regex_search(src, non_const_pattern);
    bool has_const = std::regex_search(src, const_pattern);

    // Non-const without const qualifier is a bug
    EXPECT_TRUE(!has_non_const || has_const)
        << "get_buffer_raw() returns non-const char* (breaks const correctness). "
           "Return const char* instead.";
}

// ========== Bug C4: save_snapshot uses raw new (exception-unsafe) ==========

TEST(SourceCheckTest, test_snapshot_uses_make_unique) {
    std::string src = read_source("src/persistence/snapshot.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read snapshot.cpp";

    bool has_raw_new = src.find("new SnapshotWriter") != std::string::npos;
    EXPECT_FALSE(has_raw_new)
        << "save_snapshot uses raw new SnapshotWriter (exception-unsafe, leaks on throw). "
           "Use std::make_unique instead.";
}

// ========== Bug D1: use-after-move in enqueue ==========

TEST(SourceCheckTest, test_no_use_after_move_in_enqueue) {
    std::string src = read_source("src/replication/replicator.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read replicator.cpp";

    // Find the enqueue function
    auto pos = src.find("Replicator::enqueue");
    ASSERT_NE(pos, std::string::npos);

    std::string func_body = src.substr(pos, 400);

    // Check if event.key is referenced AFTER std::move(event)
    auto move_pos = func_body.find("std::move(event)");
    if (move_pos != std::string::npos) {
        std::string after_move = func_body.substr(move_pos + 16);
        bool use_after_move = after_move.find("event.key") != std::string::npos;
        EXPECT_FALSE(use_after_move)
            << "enqueue() accesses event.key after std::move(event) (use-after-move UB)";
    }
}

// ========== Bug E2: User data as format string ==========

TEST(SourceCheckTest, test_no_user_data_as_format_string) {
    std::string src = read_source("src/server/connection.cpp");
    ASSERT_FALSE(src.empty()) << "Could not read connection.cpp";

    // Check for spdlog::xxx(variable) without format string literal
    // Safe: spdlog::debug("{}", msg)   Unsafe: spdlog::debug(msg)
    std::regex pattern(R"(spdlog::\w+\(\s*msg\s*\))");
    bool has_fmt_vuln = std::regex_search(src, pattern);
    EXPECT_FALSE(has_fmt_vuln)
        << "User data passed directly as format string to spdlog "
           "(format string vulnerability). Use spdlog::xxx(\"{}\", msg) instead.";
}
