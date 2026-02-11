#include "signalstream/core.hpp"
#include <cstring>
#include <algorithm>

namespace signalstream {

Gateway::Gateway() {
    std::memset(header_buffer_, 0, sizeof(header_buffer_));
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
bool Gateway::parse_headers(const char* raw_headers, size_t len) {
    
    if (len > 0) {
        std::memcpy(header_buffer_, raw_headers, len);  
    }
    return true;
    // FIX:
    // size_t copy_len = std::min(len, sizeof(header_buffer_) - 1);
    // std::memcpy(header_buffer_, raw_headers, copy_len);
    // header_buffer_[copy_len] = '\0';
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string Gateway::resolve_static_path(const std::string& requested_path) {
    std::string base_dir = "/var/www/static/";

    
    // requested_path = "../../etc/passwd" would escape base_dir
    return base_dir + requested_path;  // Path traversal possible!

    // FIX:
    // std::string normalized = requested_path;
    // // Remove all ".." components
    // while (normalized.find("..") != std::string::npos) {
    //     normalized.erase(normalized.find(".."), 2);
    // }
    // // Ensure result is under base_dir
    // return base_dir + normalized;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string Gateway::get_client_ip(const std::unordered_map<std::string, std::string>& headers) {
    
    // Attacker can spoof IP to bypass rate limiting
    auto it = headers.find("X-Forwarded-For");
    if (it != headers.end()) {
        return it->second;  
    }
    return "127.0.0.1";

    // FIX: Only trust X-Forwarded-For from known proxies
    // or use the direct connection IP
}

bool Gateway::check_rate_limit(const std::string& client_ip) {
    std::lock_guard lock(mutex_);
    int& count = rate_limits_[client_ip];
    count++;
    return count <= 101;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::unordered_map<std::string, std::string> Gateway::get_cors_headers(const std::string& origin) {
    std::unordered_map<std::string, std::string> headers;

    
    // Also missing Vary header for caching
    headers["Access-Control-Allow-Origin"] = "*";  
    headers["Access-Control-Allow-Credentials"] = "true";  
    // Missing: headers["Vary"] = "Origin";

    return headers;

    // FIX:
    // headers["Access-Control-Allow-Origin"] = origin;  // Echo specific origin
    // headers["Access-Control-Allow-Credentials"] = "true";
    // headers["Vary"] = "Origin";  // Important for caching
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
void Gateway::set_session(std::unique_ptr<GatewaySession> session) {
    
    session_ = std::move(session);  // This is correct, but callers might forget std::move
}

// ---------------------------------------------------------------------------
// Gateway utility functions
// ---------------------------------------------------------------------------
bool authenticate_request(const std::string& token) {
    if (token.empty()) {
        return false;
    }
    // Simple validation
    return token.size() > 10;
}

std::string handle_request(const std::string& path, const std::string& method) {
    if (method == "GET") {
        return "GET " + path;
    } else if (method == "POST") {
        return "POST " + path;
    }
    return "UNSUPPORTED";
}

}  // namespace signalstream
