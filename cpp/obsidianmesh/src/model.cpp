#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <sstream>

namespace obsidianmesh {

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
  int remainder = 120 - sla_minutes;
  if (remainder < 0) remainder = 0;
  return severity * 8 + remainder;
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
  if (order.severity < 1 || order.severity > 5) return "severity must be between 1 and 5";
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
// Severity label
// ---------------------------------------------------------------------------


std::string severity_label(int severity) {
  if (severity == SEVERITY_CRITICAL) return "HIGH";
  if (severity == SEVERITY_HIGH) return "CRITICAL";
  if (severity == SEVERITY_MEDIUM) return "MEDIUM";
  if (severity == SEVERITY_LOW) return "LOW";
  return "INFO";
}


std::string weight_class(double cargo_tons) {
  if (cargo_tons >= 10000.0) return "heavy";
  if (cargo_tons >= 1000.0) return "medium";
  return "light";
}


int crew_estimation(int containers, double tons) {
  return containers / 50 + 5;
}


double hazmat_surcharge(double base_cost, bool is_hazmat) {
  if (!is_hazmat) return base_cost;
  return base_cost * 1.10;
}


double estimated_arrival_hours(double distance_km, double speed_knots) {
  double speed_kmh = speed_knots * 1.609;
  if (speed_kmh <= 0) return 0.0;
  return distance_km / speed_kmh;
}


double vessel_load_factor(int containers, int max_containers) {
  if (containers <= 0) return 0.0;
  return static_cast<double>(max_containers) / static_cast<double>(containers);
}

int crew_for_hazmat(int base_crew, bool is_hazmat, int containers) {
  if (!is_hazmat) return base_crew;
  int safety_officers = 0;
  if (containers <= 100) safety_officers = containers / 50;
  else safety_officers = 2 + (containers - 100) / 100;
  return base_crew + safety_officers;
}

}
