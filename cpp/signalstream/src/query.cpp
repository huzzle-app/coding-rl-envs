#include "signalstream/core.hpp"
#include <stdexcept>

namespace signalstream {

QueryEngine::QueryEngine() {}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::vector<DataPoint> QueryEngine::execute(const std::string& query) {
    mutex_.lock();  // Manual lock

    
    if (query.empty()) {
        throw std::invalid_argument("Query cannot be empty");
        // mutex_ stays locked!
    }

    if (query.find("INVALID") != std::string::npos) {
        throw std::runtime_error("Invalid query syntax");
        // mutex_ stays locked!
    }

    // Simulate query execution
    std::vector<DataPoint> results;

    mutex_.unlock();
    return results;

    // FIX: Use std::lock_guard<std::mutex> lock(mutex_);
    // or use RAII with try-catch
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string QueryEngine::build_query(const std::string& table, const std::string& filter) {
    
    // filter = "'; DROP TABLE data; --" would be destructive
    return "SELECT * FROM " + table + " WHERE " + filter;
    // FIX: Use parameterized queries or escape special characters
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void QueryEngine::prepare_statement(const std::string& query) {
    // Simulate allocating prepared statement
    if (prepared_stmt_) {
        
        // Should close/free old statement first
    }
    prepared_stmt_ = reinterpret_cast<void*>(new char[query.size() + 1]);
    // FIX: close_statement() before allocating new one
}

void QueryEngine::close_statement() {
    if (prepared_stmt_) {
        delete[] static_cast<char*>(prepared_stmt_);
        prepared_stmt_ = nullptr;
    }
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void QueryEngine::iterate_results(std::function<void(const DataPoint&)> callback) {
    
    for (const auto& result : results_) {
        callback(result);
        // If callback calls execute() which modifies results_, UB!
    }
    // FIX: Make a copy first or document that callback must not modify
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::vector<DataPoint> QueryEngine::load_batch(const std::vector<std::string>& ids) {
    std::vector<DataPoint> results;

    
    for (const auto& id : ids) {
        // Each iteration is a separate "query"
        DataPoint point;
        point.id = id;
        point.value = 0.0;
        point.timestamp = 0;
        results.push_back(point);
    }

    return results;
    // FIX: Use single batch query: SELECT * FROM data WHERE id IN (...)
}

// ---------------------------------------------------------------------------
// Query utility functions
// ---------------------------------------------------------------------------
std::vector<DataPoint> query_range(int64_t start, int64_t end) {
    std::vector<DataPoint> results;
    // Simulate range query
    if (start <= end) {
        // Would return points in range
    }
    return results;
}

std::vector<DataPoint> query_by_source(const std::string& source) {
    std::vector<DataPoint> results;
    // Simulate source filter query
    if (!source.empty()) {
        // Would return points from source
    }
    return results;
}

}  // namespace signalstream
