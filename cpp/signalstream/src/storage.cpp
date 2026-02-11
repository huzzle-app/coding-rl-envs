#include "signalstream/core.hpp"
#include <fstream>
#include <cstring>

namespace signalstream {

StorageEngine::StorageEngine() {}

// ---------------------------------------------------------------------------


// Fixing only one method will still leave race conditions
// ---------------------------------------------------------------------------
void StorageEngine::insert(const std::string& key, DataPoint point) {
    
    // Another thread calling iterate() while we insert causes UB
    data_[key] = std::move(point);
    // FIX: std::lock_guard lock(mutex_);
    // NOTE: Must also fix iterate() below to hold lock during iteration
}

std::optional<DataPoint> StorageEngine::get(const std::string& key) const {
    std::lock_guard lock(mutex_);
    auto it = data_.find(key);
    if (it != data_.end()) {
        return it->second;
    }
    return std::nullopt;
}

void StorageEngine::iterate(std::function<void(const DataPoint&)> callback) {
    for (const auto& [key, point] : data_) {
        callback(point);
    }
    // FIX: Hold lock during iteration or use snapshot
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void StorageEngine::allocate_buffer(size_t size) {
    if (buffer_) {
        free_buffer();
    }
    buffer_ = new uint8_t[size];  // Allocated with new[]
    buffer_size_ = size;
}

void StorageEngine::free_buffer() {
    
    delete buffer_;  
    buffer_ = nullptr;
    buffer_size_ = 0;
    // FIX: delete[] buffer_;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
bool StorageEngine::write_snapshot(const std::string& path) {
    
    // If crash occurs during write, snapshot is corrupted
    std::ofstream file(path);
    if (!file) {
        return false;
    }

    std::lock_guard lock(mutex_);
    for (const auto& [key, point] : data_) {
        
        file << key << "," << point.id << "," << point.value << "\n";
        // A crash here leaves partial snapshot
    }

    return true;
    // FIX: Write to temp file, then rename atomically
    // std::string temp_path = path + ".tmp";
    // std::ofstream file(temp_path);
    // ... write ...
    // file.close();
    // std::rename(temp_path.c_str(), path.c_str());
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::vector<uint8_t> StorageEngine::compress(const std::vector<uint8_t>& data) {
    if (data.empty()) {
        return {};
    }

    
    // (e.g., incompressible data with overhead)
    std::vector<uint8_t> output(data.size());  

    // Simulate compression that might expand (like zlib worst case)
    // Real compression can output up to input_size + overhead
    size_t output_size = data.size();

    
    if (output_size > output.size()) {
        output_size = output.size();  // Truncation!
    }

    std::memcpy(output.data(), data.data(), output_size);
    return output;

    // FIX: Allocate output buffer with worst-case size
    // std::vector<uint8_t> output(data.size() + data.size() / 10 + 16);
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void StorageEngine::execute_query(const std::string& query) {
    // Simulate getting connection from pool
    // Connection* conn = pool.acquire();

    
    if (query.find("DROP") != std::string::npos) {
        throw std::runtime_error("DROP not allowed");
        // Connection not returned!
    }

    // Simulate query execution...

    // pool.release(conn);
    // FIX: Use RAII wrapper or try-catch with release
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string StorageEngine::build_connection_string(const std::string& host, const std::string& db) {
    
    // host = "localhost;password=hack" would inject parameters
    return "host=" + host + ";database=" + db;
    // FIX: Validate/escape special characters like ; = '
}

// ---------------------------------------------------------------------------
// Storage utility functions
// ---------------------------------------------------------------------------
bool persist_data(const std::string& key, const DataPoint& point) {
    if (key.empty()) {
        return false;
    }
    // Simulate persistence
    return true;
}

std::optional<DataPoint> load_data(const std::string& key) {
    if (key.empty()) {
        return std::nullopt;
    }
    // Simulate loading - return empty for now
    return std::nullopt;
}

}  // namespace signalstream
