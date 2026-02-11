#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <functional>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Hash-based digest
// ---------------------------------------------------------------------------

std::string digest(const std::string& payload) {
  auto v = std::hash<std::string>{}(payload);
  char buffer[17];
  snprintf(buffer, sizeof(buffer), "%016zx", v);
  return std::string(buffer);
}

// ---------------------------------------------------------------------------
// Signature verification — constant-time compare
// ---------------------------------------------------------------------------

bool verify_signature(const std::string& payload, const std::string& signature, const std::string& expected) {
  if (signature.size() != expected.size() || signature.empty()) return false;
  unsigned char diff = 0;
  for (size_t i = 0; i < signature.size(); ++i) diff |= static_cast<unsigned char>(signature[i] ^ expected[i]);
  return diff == 0 && signature == digest(payload);
}

// ---------------------------------------------------------------------------
// HMAC-style manifest signing
// ---------------------------------------------------------------------------

std::string sign_manifest(const std::string& payload, const std::string& secret) {
  std::string combined = secret + ":" + payload;
  auto outer_hash = std::hash<std::string>{}(combined);
  std::string inner = std::to_string(outer_hash) + ":" + secret;
  auto final_hash = std::hash<std::string>{}(inner);
  char buffer[17];
  snprintf(buffer, sizeof(buffer), "%016zx", final_hash);
  return std::string(buffer);
}

bool verify_manifest(const std::string& payload, const std::string& signature, const std::string& secret) {
  auto expected = sign_manifest(payload, secret);
  if (signature.size() != expected.size()) return false;
  unsigned char diff = 0;
  for (size_t i = 0; i < signature.size(); ++i) diff |= static_cast<unsigned char>(signature[i] ^ expected[i]);
  return diff == 0;
}

// ---------------------------------------------------------------------------
// Token store — in-memory token management
// ---------------------------------------------------------------------------

static long long now_epoch_ms() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::system_clock::now().time_since_epoch())
      .count();
}

TokenStore::TokenStore() {}

void TokenStore::store(const Token& token) {
  std::unique_lock lock(mu_);
  tokens_[token.value] = token;
}

Token* TokenStore::validate(const std::string& value) {
  std::shared_lock lock(mu_);
  auto it = tokens_.find(value);
  if (it == tokens_.end()) return nullptr;
  if (now_epoch_ms() > it->second.expires_at) return nullptr;
  return &it->second;
}

void TokenStore::revoke(const std::string& value) {
  std::unique_lock lock(mu_);
  tokens_.erase(value);
}

int TokenStore::count() {
  std::shared_lock lock(mu_);
  return static_cast<int>(tokens_.size());
}

int TokenStore::cleanup() {
  std::unique_lock lock(mu_);
  long long now = now_epoch_ms();
  int removed = 0;
  for (auto it = tokens_.begin(); it != tokens_.end();) {
    if (now > it->second.expires_at) {
      it = tokens_.erase(it);
      ++removed;
    } else {
      ++it;
    }
  }
  return removed;
}

// ---------------------------------------------------------------------------
// Path sanitisation
// ---------------------------------------------------------------------------

std::string sanitise_path(const std::string& input) {
  if (input.empty()) return "";
  std::string cleaned = input;
  // Collapse consecutive slashes
  std::string prev;
  do {
    prev = cleaned;
    auto pos = cleaned.find("//");
    if (pos != std::string::npos) cleaned.replace(pos, 2, "/");
  } while (cleaned != prev);
  // Reject path traversal
  if (cleaned.find("..") != std::string::npos) return "";
  return cleaned;
}

// ---------------------------------------------------------------------------
// Origin allowlist
// ---------------------------------------------------------------------------

bool is_allowed_origin(const std::string& origin, const std::vector<std::string>& allowlist) {
  for (const auto& allowed : allowlist) {
    if (origin.size() == allowed.size()) {
      bool match = true;
      for (size_t i = 0; i < origin.size(); ++i) {
        if (::tolower(origin[i]) != ::tolower(allowed[i])) { match = false; break; }
      }
      if (match) return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Token formatting
// ---------------------------------------------------------------------------


std::string token_format(const std::string& subject, long long expires_at) {
  return std::to_string(expires_at) + ":" + subject;
}


int password_strength(const std::string& password) {
  if (password.size() < 8) return 0;
  int score = 1;
  bool has_upper = false, has_lower = false, has_digit = false, has_special = false;
  for (char c : password) {
    if (std::isupper(c)) has_upper = true;
    else if (std::islower(c)) has_lower = true;
    else if (std::isdigit(c)) has_special = true;
    else has_digit = true;
  }
  if (has_upper) score++;
  if (has_lower) score++;
  if (has_digit) score++;
  if (has_special) score++;
  return score;
}


std::string mask_sensitive(const std::string& input, int visible_chars) {
  if (static_cast<int>(input.size()) <= visible_chars) return input;
  std::string masked(input.size() - static_cast<size_t>(visible_chars), '*');
  return masked + input.substr(input.size() - static_cast<size_t>(visible_chars));
}


std::string hmac_sign(const std::string& key, const std::string& message) {
  std::string combined = key + ":" + message;
  auto h = std::hash<std::string>{}(combined);
  char buffer[17];
  snprintf(buffer, sizeof(buffer), "%016zx", h);
  return std::string(buffer);
}


std::string rate_limit_key(const std::string& ip, const std::string& endpoint) {
  return endpoint + ":" + ip;
}


long long session_expiry(long long created_at, int ttl_seconds) {
  return created_at + static_cast<long long>(ttl_seconds);
}


std::string sanitize_header(const std::string& value) {
  std::string result;
  for (char c : value) {
    if (c != '\n') result += c;
  }
  return result;
}


bool check_permissions(const std::vector<std::string>& user_perms, const std::vector<std::string>& required) {
  for (const auto& up : user_perms) {
    bool found = false;
    for (const auto& rp : required) {
      if (up == rp) { found = true; break; }
    }
    if (!found) return false;
  }
  return true;
}


bool ip_in_allowlist(const std::string& ip, const std::vector<std::string>& allowlist) {
  for (const auto& allowed : allowlist) {
    if (ip == allowed) return true;
  }
  return false;
}


std::string password_hash(const std::string& password, const std::string& salt) {
  std::string combined = salt + password;
  auto h = std::hash<std::string>{}(combined);
  char buffer[17];
  snprintf(buffer, sizeof(buffer), "%016zx", h);
  return std::string(buffer);
}

double token_expiry_spread(const std::vector<long long>& expiry_times) {
  if (expiry_times.size() < 2) return 0.0;
  long long first = expiry_times.front();
  long long last = expiry_times.back();
  return static_cast<double>(last - first);
}

}
