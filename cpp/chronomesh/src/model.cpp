#include "chronomesh/core.hpp"
#include <algorithm>
#include <sstream>

namespace chronomesh {

// ---------------------------------------------------------------------------
// SLA targets by severity
// ---------------------------------------------------------------------------

const std::map<int, int> SLA_BY_SEVERITY = {
    {SEVERITY_CRITICAL, 15},
    {SEVERITY_HIGH,     30},
    {SEVERITY_MEDIUM,   60},
    {SEVERITY_LOW,      120},
    {SEVERITY_INFO,     240},
};

// ---------------------------------------------------------------------------
// DispatchModel methods
// ---------------------------------------------------------------------------

int DispatchModel::urgency_score() const {
  return severity * sla_minutes;
}

std::string DispatchModel::to_string() const {
  std::ostringstream oss;
  oss << "DispatchModel{severity:" << severity
      << ", sla:" << sla_minutes
      << ", urgency:" << urgency_score() << "}";
  return oss.str();
}

// ---------------------------------------------------------------------------
// VesselManifest
// ---------------------------------------------------------------------------

bool VesselManifest::requires_hazmat_clearance() const {
  return hazmat;
}

// ---------------------------------------------------------------------------
// Backward-compatible CONTRACTS map
// ---------------------------------------------------------------------------

const std::map<std::string, int> CONTRACTS = {
    {"gateway",    8140},
    {"routing",    8141},
    {"policy",     8142},
    {"resilience", 8143},
};

// ---------------------------------------------------------------------------
// Batch creation
// ---------------------------------------------------------------------------

std::vector<DispatchModel> create_batch_orders(int count, int base_severity, int base_sla) {
  std::vector<DispatchModel> orders(static_cast<size_t>(count));
  for (int i = 0; i < count; ++i) {
    orders[static_cast<size_t>(i)] = DispatchModel{
        base_severity + (i % 3),
        base_sla + (i * 5),
    };
  }
  return orders;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

std::string validate_dispatch_order(const DispatchModel& order) {
  
  if (order.severity <= 0 || order.severity > 5) return "severity must be between 1 and 5";
  if (order.sla_minutes < 0) return "SLA minutes must be non-negative";
  return "";
}

// ---------------------------------------------------------------------------
// Classification
// ---------------------------------------------------------------------------

int classify_severity(const std::string& description) {
  std::string lower = description;
  std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
  if (lower.find("critical") != std::string::npos || lower.find("emergency") != std::string::npos) {
    return SEVERITY_CRITICAL;
  }
  if (lower.find("high") != std::string::npos || lower.find("urgent") != std::string::npos) {
    return SEVERITY_HIGH;
  }
  if (lower.find("medium") != std::string::npos || lower.find("moderate") != std::string::npos) {
    return SEVERITY_MEDIUM;
  }
  if (lower.find("low") != std::string::npos || lower.find("minor") != std::string::npos) {
    return SEVERITY_LOW;
  }
  return SEVERITY_INFO;
}

// ---------------------------------------------------------------------------
// Port fee estimation
// ---------------------------------------------------------------------------

double estimate_port_fees(const VesselManifest& manifest, double base_rate) {
  double fee = base_rate * manifest.cargo_tons;
  if (manifest.hazmat) {
    fee += base_rate * 0.5;
  } else if (manifest.containers > 100) {
    fee += static_cast<double>(manifest.containers) * 0.1;
  }
  return fee;
}

}
