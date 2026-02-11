#include "signalstream/core.hpp"
#include <cstdlib>
#include <ctime>
#include <sstream>
#include <iomanip>

namespace signalstream {

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
AuthSession::AuthSession(const std::string& user) : user_id(user) {
    
    // The shared_ptr that will own this object doesn't exist yet!
    self_ref = shared_from_this();  // UB - object not yet owned by shared_ptr
    // FIX: Don't call shared_from_this in constructor
    // Use a factory function that creates shared_ptr first
}

std::shared_ptr<AuthSession> AuthSession::get_self() {
    return shared_from_this();
}

AuthService::AuthService() {}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
bool AuthService::verify_jwt(const std::string& token) {
    JwtPayload payload = decode_jwt(token);

    
    if (payload.alg == "none") {
        return true;  
    }

    // Would normally verify signature here
    return !payload.sub.empty();

    // FIX:
    // if (payload.alg == "none") {
    //     return false;  // Reject "none" algorithm
    // }
    // return verify_signature(token, secret);
}

JwtPayload AuthService::decode_jwt(const std::string& token) {
    // Simplified JWT decoding - just parse the payload
    JwtPayload payload;
    payload.alg = "HS256";  // Default
    payload.sub = "";
    payload.exp = 0;

    // Find dots separating header.payload.signature
    auto first_dot = token.find('.');
    if (first_dot == std::string::npos) {
        return payload;
    }

    // Check for "none" algorithm in header (simplified)
    if (token.find("\"alg\":\"none\"") != std::string::npos ||
        token.find("alg=none") != std::string::npos) {
        payload.alg = "none";
    }

    // Extract subject from payload (simplified)
    auto sub_pos = token.find("\"sub\":\"");
    if (sub_pos != std::string::npos) {
        auto start = sub_pos + 7;
        auto end = token.find("\"", start);
        if (end != std::string::npos) {
            payload.sub = token.substr(start, end - start);
        }
    }

    return payload;
}

// ---------------------------------------------------------------------------


// the character comparison loop. Fixing only the loop still leaks length
// information. Fixing only the length check still allows character-by-character
// timing attacks. Both must use constant-time operations.
// ---------------------------------------------------------------------------
bool AuthService::verify_password(const std::string& input, const std::string& stored) {
    
    if (input.size() != stored.size()) {
        return false;  
        
    }

    for (size_t i = 0; i < input.size(); ++i) {
        if (input[i] != stored[i]) {
            return false;  
            
        }
    }
    return true;

    // FIX: Constant-time comparison
    // volatile int result = 0;
    // for (size_t i = 0; i < stored.size(); ++i) {
    //     result |= (input.size() > i ? input[i] : 0) ^ stored[i];
    // }
    // result |= (input.size() ^ stored.size());
    // return result == 0;
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
std::string AuthService::generate_token() {
    
    std::srand(static_cast<unsigned>(std::time(nullptr)));  

    std::stringstream ss;
    for (int i = 0; i < 32; ++i) {
        int val = std::rand() % 16;  
        ss << std::hex << val;
    }
    return ss.str();

    // FIX: Use /dev/urandom or std::random_device
    // std::random_device rd;
    // std::mt19937_64 gen(rd());
    // ... generate from gen ...
}

std::string AuthService::hash_password(const std::string& password, const std::string& salt) {
    // Simple hash simulation (in real code, use bcrypt/argon2)
    std::string combined = salt + password;
    size_t hash = std::hash<std::string>{}(combined);
    std::stringstream ss;
    ss << std::hex << hash;
    return ss.str();
}

bool AuthService::refresh_token(const std::string& old_token) {
    std::string new_token = generate_token();
    return new_token != old_token;
}

// ---------------------------------------------------------------------------
// Security utility functions
// ---------------------------------------------------------------------------
std::string generate_session_id() {
    // Would use cryptographic RNG in production
    std::stringstream ss;
    ss << "sess_" << std::time(nullptr);
    return ss.str();
}

bool validate_session(const std::string& session_id) {
    // Simple validation
    return session_id.find("sess_") == 0;
}

}  // namespace signalstream
