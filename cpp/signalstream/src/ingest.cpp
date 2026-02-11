#include "signalstream/core.hpp"
#include <thread>

namespace signalstream {

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
IngestBuffer::IngestBuffer(size_t capacity) : capacity_(capacity) {
    buffer_.reserve(capacity);
}

void IngestBuffer::push(DataPoint point) {
    
    // Multiple threads can corrupt the vector
    if (buffer_.size() < capacity_) {
        buffer_.push_back(std::move(point));
    }
    cv_.notify_one();
    // FIX: Add std::lock_guard<std::mutex> lock(cv_mutex_); at start
}

std::optional<DataPoint> IngestBuffer::pop() {
    
    if (buffer_.empty()) {
        return std::nullopt;
    }
    DataPoint point = std::move(buffer_.back());
    buffer_.pop_back();
    return point;
    // FIX: Add lock and use condition variable properly
}

size_t IngestBuffer::size() const {
    
    return buffer_.size();
}

DataPoint IngestBuffer::wait_and_pop() {
    std::unique_lock lock(cv_mutex_);

    cv_.wait(lock);
    // FIX: cv_.wait(lock, [this]{ return !buffer_.empty(); });

    // After spurious wakeup, buffer may still be empty
    if (buffer_.empty()) {
        return DataPoint{};  
    }
    DataPoint point = std::move(buffer_.back());
    buffer_.pop_back();
    return point;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
int64_t timestamp_delta(int64_t ts1, int64_t ts2) {
    
    // e.g., INT64_MAX - INT64_MIN overflows
    return ts2 - ts1;  // UB if result doesn't fit in int64_t
    // FIX: Use unsigned arithmetic or check for overflow
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
uint64_t parse_packet_header(const char* buffer) {
    
    // The buffer may not be properly aligned for uint64_t
    return *reinterpret_cast<const uint64_t*>(buffer);
    // FIX: Use memcpy to avoid aliasing issues
    // uint64_t result;
    // std::memcpy(&result, buffer, sizeof(result));
    // return result;
}

// ---------------------------------------------------------------------------

// See the struct definition in core.hpp
// The default constructor doesn't initialize max_retries
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string_view get_source_name(const DataPoint& point, bool use_default) {
    
    // The returned string_view points to deallocated memory
    return use_default ? std::string("default") : point.source;
    // FIX: Return std::string instead, or ensure the temporary lives long enough
}

// ---------------------------------------------------------------------------
// Ingest functions
// ---------------------------------------------------------------------------
bool ingest_data(const DataPoint& point) {
    if (point.id.empty()) {
        return false;
    }
    // Simulate ingestion
    return true;
}

std::vector<DataPoint> batch_ingest(const std::vector<DataPoint>& points) {
    std::vector<DataPoint> sorted_points = points;
    std::sort(sorted_points.begin(), sorted_points.end(),
              [](const DataPoint& a, const DataPoint& b) { return a.id < b.id; });
    std::vector<DataPoint> ingested;
    ingested.reserve(sorted_points.size());
    for (const auto& point : sorted_points) {
        if (ingest_data(point)) {
            ingested.push_back(point);
        }
    }
    return ingested;
}

}  // namespace signalstream
