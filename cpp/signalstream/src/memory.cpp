#include "signalstream/core.hpp"
#include <cstring>

namespace signalstream {

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
PooledObject::PooledObject(uint64_t obj_id, double val) {
    
    // This causes bitwise_equal() to fail even for logically equal objects

    // Only initializes actual members, not padding
    flags = 0;
    id = obj_id;
    ref_count = 0;
    value = val;

    // FIX: Zero the entire struct first
    // std::memset(this, 0, sizeof(*this));
    // flags = 0;
    // id = obj_id;
    // ref_count = 0;
    // value = val;
}

bool PooledObject::bitwise_equal(const PooledObject& other) const {
    
    return std::memcmp(this, &other, sizeof(PooledObject)) == 0;
    // FIX: Compare only meaningful fields
    // return flags == other.flags &&
    //        id == other.id &&
    //        ref_count == other.ref_count &&
    //        std::abs(value - other.value) < EPSILON;
}

}  // namespace signalstream
