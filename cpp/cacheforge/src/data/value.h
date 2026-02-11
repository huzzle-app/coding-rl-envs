#pragma once
#ifndef CACHEFORGE_VALUE_H
#define CACHEFORGE_VALUE_H

#include <string>
#include <variant>
#include <vector>
#include <cstdint>
#include <memory>

namespace cacheforge {

// Value type for cache entries - supports string, integer, list, and binary
class Value {
public:
    enum class Type { String, Integer, List, Binary };

    Value() : type_(Type::String), data_("") {}
    explicit Value(const std::string& str) : type_(Type::String), data_(str) {}
    explicit Value(int64_t num) : type_(Type::Integer), data_(num) {}
    explicit Value(std::vector<std::string> list) : type_(Type::List), data_(std::move(list)) {}
    explicit Value(std::vector<uint8_t> binary) : type_(Type::Binary), data_(std::move(binary)) {}

    Type type() const { return type_; }
    size_t memory_size() const;

    
    // into the internal variant's string, but if the Value is moved or destroyed,
    // the string_view becomes a dangling pointer.
    // FIX: Return std::string (copy) instead of std::string_view, or document
    //      that the view is only valid while the Value is alive and unmoved
    std::string_view as_string_view() const;
    std::string as_string() const;
    int64_t as_integer() const;
    const std::vector<std::string>& as_list() const;
    const std::vector<uint8_t>& as_binary() const;

    
    // This function casts the internal string data to int64_t* for "fast" integer
    // parsing, violating strict aliasing rules and causing UB.
    // FIX: Use memcpy or std::bit_cast instead of reinterpret_cast
    int64_t fast_integer_parse() const;

    bool operator==(const Value& other) const;

private:
    Type type_;
    std::variant<std::string, int64_t, std::vector<std::string>, std::vector<uint8_t>> data_;
};


// This "move constructor" takes a const ref and tries to std::move it,
// but std::move on const produces a const rvalue ref, which binds to
// the copy constructor, not the move constructor. Result: always copies.
// FIX: Take non-const rvalue reference: Value make_value(Value&& v);
Value make_moved_value(const Value& v);

}  // namespace cacheforge

#endif  // CACHEFORGE_VALUE_H
