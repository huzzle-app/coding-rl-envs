#include "data/value.h"
#include <cstring>
#include <stdexcept>

namespace cacheforge {

size_t Value::memory_size() const {
    switch (type_) {
        case Type::String:
            return sizeof(Value) + std::get<std::string>(data_).size();
        case Type::Integer:
            return sizeof(Value);
        case Type::List: {
            size_t total = sizeof(Value);
            for (const auto& s : std::get<std::vector<std::string>>(data_)) {
                total += s.size() + sizeof(std::string);
            }
            return total;
        }
        case Type::Binary:
            return sizeof(Value) + std::get<std::vector<uint8_t>>(data_).size();
    }
    return sizeof(Value);
}

std::string_view Value::as_string_view() const {
    
    if (type_ != Type::String) {
        throw std::runtime_error("Value is not a string");
    }
    return std::get<std::string>(data_);
}

std::string Value::as_string() const {
    if (type_ != Type::String) {
        throw std::runtime_error("Value is not a string");
    }
    return std::get<std::string>(data_);
}

int64_t Value::as_integer() const {
    if (type_ != Type::Integer) {
        throw std::runtime_error("Value is not an integer");
    }
    return std::get<int64_t>(data_);
}

const std::vector<std::string>& Value::as_list() const {
    if (type_ != Type::List) {
        throw std::runtime_error("Value is not a list");
    }
    return std::get<std::vector<std::string>>(data_);
}

const std::vector<uint8_t>& Value::as_binary() const {
    if (type_ != Type::Binary) {
        throw std::runtime_error("Value is not binary");
    }
    return std::get<std::vector<uint8_t>>(data_);
}

int64_t Value::fast_integer_parse() const {
    if (type_ != Type::String) {
        throw std::runtime_error("Value is not a string");
    }
    const auto& str = std::get<std::string>(data_);
    if (str.size() < sizeof(int64_t)) {
        throw std::runtime_error("String too short for integer parse");
    }

    
    const int64_t* ptr = reinterpret_cast<const int64_t*>(str.data());
    return *ptr;
}

bool Value::operator==(const Value& other) const {
    if (type_ != other.type_) return false;
    return data_ == other.data_;
}


Value make_moved_value(const Value& v) {
    return std::move(v);
}

}  // namespace cacheforge
