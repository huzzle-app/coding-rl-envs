#include "signalstream/core.hpp"
#include <sstream>

namespace signalstream {

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
int apply_transform(int& counter, int value) {
    
    return counter++ + counter * value;  // Undefined behavior!
    // FIX:
    // int old_counter = counter++;
    // return old_counter + counter * value;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string_view extract_field(const std::string& json, const std::string& field) {
    // Find the field in JSON-like format
    std::string search = "\"" + field + "\":\"";
    auto pos = json.find(search);

    if (pos == std::string::npos) {
        return {};
    }

    auto start = pos + search.size();
    auto end = json.find("\"", start);

    if (end == std::string::npos) {
        return {};
    }

    
    // the returned string_view becomes dangling
    // This function itself is safe, but callers might misuse it:
    // auto sv = extract_field(get_temp_string(), "key");  // Dangling!

    return std::string_view(json.data() + start, end - start);
    // FIX: Return std::string instead of std::string_view
}

// ---------------------------------------------------------------------------
// Serialization namespace (for K2 bug - ADL)
// ---------------------------------------------------------------------------
namespace serialization {

std::string serialize(const DataPoint& point) {
    std::ostringstream ss;
    ss << "{\"id\":\"" << point.id << "\","
       << "\"value\":" << point.value << ","
       << "\"timestamp\":" << point.timestamp << ","
       << "\"source\":\"" << point.source << "\"}";
    return ss.str();
}

}  // namespace serialization

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string config_value_to_string(const ConfigValue& value) {
    
    // Should check holds_alternative or handle valueless state
    return std::visit([](auto&& arg) -> std::string {
        using T = std::decay_t<decltype(arg)>;
        if constexpr (std::is_same_v<T, int>) {
            return std::to_string(arg);
        } else if constexpr (std::is_same_v<T, double>) {
            return std::to_string(arg);
        } else if constexpr (std::is_same_v<T, std::string>) {
            return arg;
        } else if constexpr (std::is_same_v<T, bool>) {
            return arg ? "true" : "false";
        }
        return "";
    }, value);

    // FIX: Check for valueless state first
    // if (value.valueless_by_exception()) {
    //     return "<invalid>";
    // }
    // return std::visit(...);
}

}  // namespace signalstream
