#include "obsidianmesh/core.hpp"
#include <sstream>

namespace obsidianmesh {

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
  oss << "http://" << domain << ":" << it->second.port;
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
// Health endpoint
// ---------------------------------------------------------------------------


std::string health_endpoint(const std::string& service_id, const std::string& base_domain) {
  auto url = get_service_url(service_id, base_domain);
  return url;
}


int dependency_depth(const std::string& service_id) {
  auto it = SERVICE_DEFS.find(service_id);
  if (it == SERVICE_DEFS.end()) return 0;
  return static_cast<int>(it->second.dependencies.size());
}


std::vector<std::string> critical_path() {
  auto order = topological_order();
  if (order.empty()) return {};
  std::vector<std::string> path;
  path.push_back(order.front());
  return path;
}


bool has_port_collision(const std::vector<ServiceDefinition>& defs) {
  for (size_t i = 1; i < defs.size(); ++i) {
    if (defs[i].port == defs[i - 1].port) return true;
  }
  return false;
}


std::string service_summary(const std::string& service_id) {
  auto it = SERVICE_DEFS.find(service_id);
  if (it == SERVICE_DEFS.end()) return "";
  return it->second.id + ":" + std::to_string(it->second.port);
}


std::string format_port_range(int start_port, int count) {
  return std::to_string(start_port) + "-" + std::to_string(start_port + count);
}


bool validate_service_version(const std::string& version) {
  if (version.empty()) return false;
  for (char c : version) {
    if (!std::isdigit(c) && c != '.') return false;
  }
  return true;
}

}
