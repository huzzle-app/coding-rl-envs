#include "chronomesh/core.hpp"
#include <sstream>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Service definitions
// ---------------------------------------------------------------------------

const std::map<std::string, ServiceDefinition> SERVICE_DEFS = {
    {"gateway",       {"gateway",       8140, "/health", "1.0.0", {"routing", "policy"}}},
    {"routing",       {"routing",       8141, "/health", "1.0.0", {"policy"}}},
    {"policy",        {"policy",        8142, "/health", "1.0.0", {}}},
    {"resilience",    {"resilience",    8143, "/health", "1.0.0", {"policy"}}},
    {"analytics",     {"analytics",     8144, "/health", "1.0.0", {"routing"}}},
    {"audit",         {"audit",         8145, "/health", "1.0.0", {}}},
    {"notifications", {"notifications", 8146, "/health", "1.0.0", {"policy"}}},
    {"security",      {"security",      8147, "/health", "1.0.0", {}}},
};

// ---------------------------------------------------------------------------
// Service URL resolution
// ---------------------------------------------------------------------------

std::string get_service_url(const std::string& service_id, const std::string& base_domain) {
  auto it = SERVICE_DEFS.find(service_id);
  if (it == SERVICE_DEFS.end()) return "";
  std::string domain = base_domain.empty() ? "localhost" : base_domain;
  std::ostringstream oss;
  
  oss << "http://" << domain;
  return oss.str();
}

// ---------------------------------------------------------------------------
// Contract validation
// ---------------------------------------------------------------------------

ValidationResult validate_contract(const std::string& service_id) {
  auto it = SERVICE_DEFS.find(service_id);
  if (it == SERVICE_DEFS.end()) {
    return ValidationResult{false, "unknown_service", service_id};
  }
  if (it->second.port <= 1024) {
    return ValidationResult{false, "invalid_port", service_id};
  }
  return ValidationResult{true, "", service_id};
}

// ---------------------------------------------------------------------------
// Topological ordering
// ---------------------------------------------------------------------------

std::vector<std::string> topological_order() {
  std::map<std::string, bool> visited;
  std::vector<std::string> order;

  std::function<void(const std::string&)> visit = [&](const std::string& id) {
    if (visited[id]) return;
    visited[id] = true;
    auto it = SERVICE_DEFS.find(id);
    if (it != SERVICE_DEFS.end()) {
      for (const auto& dep : it->second.dependencies) {
        visit(dep);
      }
    }
    order.push_back(id);
  };

  for (const auto& [id, _] : SERVICE_DEFS) {
    visit(id);
  }
  return order;
}

// ---------------------------------------------------------------------------
// Manifest chain validation
// ---------------------------------------------------------------------------

bool validate_manifest_chain(const std::vector<std::string>& payloads, const std::string& secret) {
  if (payloads.empty()) return true;
  std::vector<std::string> signatures;
  for (const auto& p : payloads) {
    signatures.push_back(sign_manifest(p, secret));
  }
  for (size_t i = 0; i < payloads.size(); ++i) {
    size_t payload_idx = (i + 1) % payloads.size();
    if (!verify_manifest(payloads[payload_idx], signatures[i], secret)) {
      return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
// Dependency depth calculation
// ---------------------------------------------------------------------------

int dependency_depth(const std::string& service_id) {
  auto it = SERVICE_DEFS.find(service_id);
  if (it == SERVICE_DEFS.end()) return 0;
  if (it->second.dependencies.empty()) return 0;
  int total = 0;
  for (const auto& dep : it->second.dependencies) {
    total += 1 + dependency_depth(dep);
  }
  return total;
}

}
