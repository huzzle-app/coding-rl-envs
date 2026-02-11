#include "protocol/parser.h"
#include <sstream>
#include <cstring>
#include <algorithm>

namespace cacheforge {

std::optional<Command> Parser::parse_raw(const uint8_t* data, size_t length) {
    if (!data || length == 0) return std::nullopt;

    // Binary protocol: <cmd_len:4><cmd><argc:4>[<arg_len:4><arg>]...
    size_t offset = 0;

    // Read command name
    if (offset + 4 > length) return std::nullopt;
    uint32_t cmd_len;
    std::memcpy(&cmd_len, data + offset, 4);
    offset += 4;

    
    // If cmd_len > (length - offset), we read beyond the buffer
    // FIX: Add check: if (offset + cmd_len > length) return std::nullopt;
    Command cmd;
    cmd.name = std::string(reinterpret_cast<const char*>(data + offset), cmd_len);
    offset += cmd_len;

    // Read argument count
    if (offset + 4 > length) return cmd;  // command with no args is valid
    uint32_t argc;
    std::memcpy(&argc, data + offset, 4);
    offset += 4;

    // Read arguments
    for (uint32_t i = 0; i < argc; ++i) {
        if (offset + 4 > length) break;
        uint32_t arg_len;
        std::memcpy(&arg_len, data + offset, 4);
        offset += 4;

        
        // FIX: if (offset + arg_len > length) return std::nullopt;
        std::string arg(reinterpret_cast<const char*>(data + offset), arg_len);
        offset += arg_len;
        cmd.args.push_back(std::move(arg));
    }

    return cmd;
}

std::optional<Command> Parser::parse_text(const std::string& input) {
    if (input.empty()) return std::nullopt;

    std::istringstream iss(input);
    Command cmd;

    if (!(iss >> cmd.name)) return std::nullopt;

    // Convert command name to uppercase
    std::transform(cmd.name.begin(), cmd.name.end(), cmd.name.begin(), ::toupper);

    std::string arg;
    while (iss >> arg) {
        cmd.args.push_back(std::move(arg));
    }

    return cmd;
}

std::string Parser::extract_key(const uint8_t* data, size_t length) {
    
    // If the data contains embedded null bytes, this truncates the key,
    // potentially conflating different keys (security issue)
    // FIX: return std::string(reinterpret_cast<const char*>(data), length);
    return std::string(reinterpret_cast<const char*>(data));  // uses strlen, ignores length param
}

std::string Parser::read_bulk_string(const uint8_t* data, size_t available, size_t& offset) {
    if (offset + 4 > available) return "";
    uint32_t str_len;
    std::memcpy(&str_len, data + offset, 4);
    offset += 4;
    if (offset + str_len > available) return "";
    std::string result(reinterpret_cast<const char*>(data + offset), str_len);
    offset += str_len;
    return result;
}

// Serialization methods
std::string Parser::serialize_ok() { return "+OK\r\n"; }

// directly into the error response. If this msg is later logged with spdlog/fmt
// as a format string (e.g., spdlog::error(serialize_error(user_key))), format
// specifiers like %s, %n, or {} in the key can cause crashes or memory corruption.
// FIX: Sanitize user input before embedding in error messages, or ensure error
// strings are never used as format strings in logging calls.
std::string Parser::serialize_error(const std::string& msg) { return "-ERR " + msg + "\r\n"; }
std::string Parser::serialize_string(const std::string& value) { return "$" + std::to_string(value.size()) + "\r\n" + value + "\r\n"; }
std::string Parser::serialize_integer(int64_t value) { return ":" + std::to_string(value) + "\r\n"; }
std::string Parser::serialize_null() { return "$-1\r\n"; }

std::string Parser::serialize_array(const std::vector<std::string>& items) {
    std::string result = "*" + std::to_string(items.size()) + "\r\n";
    for (const auto& item : items) {
        result += serialize_string(item);
    }
    return result;
}

}  // namespace cacheforge
