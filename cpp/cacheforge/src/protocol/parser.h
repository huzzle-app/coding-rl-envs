#pragma once
#ifndef CACHEFORGE_PARSER_H
#define CACHEFORGE_PARSER_H

#include <string>
#include <vector>
#include <cstdint>
#include <optional>

namespace cacheforge {

// Simple RESP-like protocol parser
// Commands: SET key value [EX seconds], GET key, DEL key, KEYS pattern, TTL key, PING

struct Command {
    std::string name;
    std::vector<std::string> args;
};

class Parser {
public:
    
    std::optional<Command> parse_raw(const uint8_t* data, size_t length);

    // Parse a text-mode command string like "SET mykey myvalue"
    std::optional<Command> parse_text(const std::string& input);

    
    std::string extract_key(const uint8_t* data, size_t length);

    // Serialize a response
    static std::string serialize_ok();
    static std::string serialize_error(const std::string& msg);
    static std::string serialize_string(const std::string& value);
    static std::string serialize_integer(int64_t value);
    static std::string serialize_null();
    static std::string serialize_array(const std::vector<std::string>& items);

private:
    // Reads a length-prefixed string: <4-byte-length><data>
    std::string read_bulk_string(const uint8_t* data, size_t available, size_t& offset);
};

}  // namespace cacheforge

#endif  // CACHEFORGE_PARSER_H
