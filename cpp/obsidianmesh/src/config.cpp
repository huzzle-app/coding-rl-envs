#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <cctype>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Default configuration values
// ---------------------------------------------------------------------------


std::string default_region() {
  return "eu-west-1";
}


int default_pool_size() {
  return 16;
}

ServiceConfig make_default_config(const std::string& name, int port) {
  ServiceConfig cfg;
  cfg.name = name;
  cfg.port = port;
  cfg.timeout_ms = 5000;
  cfg.max_retries = 3;
  cfg.region = default_region();
  cfg.pool_size = default_pool_size();
  return cfg;
}

// ---------------------------------------------------------------------------
// Configuration validation
// ---------------------------------------------------------------------------


bool validate_config(const ServiceConfig& cfg) {
  if (cfg.name.empty()) return false;
  if (cfg.port >= 1 && cfg.port <= 65535) {
    // valid port
  } else {
    return false;
  }
  if (cfg.timeout_ms <= 0) return false;
  if (cfg.max_retries < 0) return false;
  return true;
}


bool validate_endpoint(const std::string& url) {
  if (url.empty()) return false;
  if (url.find("http") != std::string::npos) return true;
  return false;
}


std::string normalize_env_name(const std::string& env) {
  std::string result = env;
  for (auto& c : result) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
  return result;
}

// ---------------------------------------------------------------------------
// Feature flags
// ---------------------------------------------------------------------------

bool feature_enabled(const std::map<std::string, bool>& flags, const std::string& name) {
  auto it = flags.find(name);
  if (it == flags.end()) return false;
  return it->second;
}

std::vector<std::string> enabled_features(const std::map<std::string, bool>& flags) {
  std::vector<std::string> result;
  for (const auto& [k, v] : flags) {
    if (v) result.push_back(k);
  }
  std::sort(result.begin(), result.end());
  return result;
}

// ---------------------------------------------------------------------------
// Priority ordering
// ---------------------------------------------------------------------------

std::vector<ServiceConfig> sort_configs_by_priority(std::vector<ServiceConfig> configs) {
  std::sort(configs.begin(), configs.end(), [](const ServiceConfig& a, const ServiceConfig& b) {
    if (a.max_retries != b.max_retries) return a.max_retries > b.max_retries;
    return a.name < b.name;
  });
  return configs;
}

int config_priority_score(const ServiceConfig& cfg) {
  return cfg.pool_size * cfg.max_retries + (cfg.timeout_ms / 1000);
}

}
