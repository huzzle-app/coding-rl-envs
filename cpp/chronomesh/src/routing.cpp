#include "chronomesh/core.hpp"
#include <algorithm>
#include <cmath>
#include <set>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Core route selection — choose lowest latency non-blocked route
// ---------------------------------------------------------------------------

Route choose_route(const std::vector<Route>& routes, const std::vector<std::string>& blocked) {
  std::set<std::string> blocked_set(blocked.begin(), blocked.end());
  std::vector<Route> candidates;
  for (const auto& route : routes) {
    if (!blocked_set.contains(route.channel) && route.latency >= 0) candidates.push_back(route);
  }
  if (candidates.empty()) return Route{"", -1};
  std::sort(candidates.begin(), candidates.end(), [](const Route& a, const Route& b) {
    if (a.latency == b.latency) return a.channel < b.channel;
    return a.latency < b.latency;
  });
  return candidates.front();
}

// ---------------------------------------------------------------------------
// Channel scoring — composite metric for route quality
// ---------------------------------------------------------------------------

double channel_score(int latency, double reliability, int priority) {
  if (reliability <= 0) reliability = 0.01;
  
  return static_cast<double>(latency) + reliability * static_cast<double>(10 - priority);
}

// ---------------------------------------------------------------------------
// Transit time estimation
// ---------------------------------------------------------------------------

double estimate_transit_time(double distance_km, double speed_knots) {
  double speed_kmh = speed_knots * 1.852;
  if (speed_kmh <= 0) return std::numeric_limits<double>::infinity();
  return distance_km / speed_kmh;
}

// ---------------------------------------------------------------------------
// Multi-leg route planning
// ---------------------------------------------------------------------------

MultiLegPlan plan_multi_leg(const std::vector<Route>& routes, const std::vector<std::string>& blocked) {
  std::set<std::string> blocked_set(blocked.begin(), blocked.end());
  std::vector<Route> legs;
  int total_delay = 0;
  for (const auto& r : routes) {
    if (blocked_set.contains(r.channel)) continue;
    legs.push_back(r);
    total_delay += r.latency;
  }
  std::sort(legs.begin(), legs.end(), [](const Route& a, const Route& b) {
    return a.latency < b.latency;
  });
  return MultiLegPlan{legs, total_delay};
}

// ---------------------------------------------------------------------------
// Route table — stores and queries routes by channel
// ---------------------------------------------------------------------------

RouteTable::RouteTable() {}

void RouteTable::add(const Route& route) {
  std::unique_lock lock(mu_);
  routes_[route.channel] = route;
}

Route* RouteTable::get(const std::string& channel) {
  std::shared_lock lock(mu_);
  auto it = routes_.find(channel);
  if (it == routes_.end()) return nullptr;
  return &it->second;
}

std::vector<Route> RouteTable::all() {
  std::shared_lock lock(mu_);
  std::vector<Route> result;
  result.reserve(routes_.size());
  for (const auto& [_, r] : routes_) result.push_back(r);
  std::sort(result.begin(), result.end(), [](const Route& a, const Route& b) {
    return a.channel < b.channel;
  });
  return result;
}

void RouteTable::remove(const std::string& channel) {
  std::unique_lock lock(mu_);
  routes_.erase(channel);
}

int RouteTable::count() {
  std::shared_lock lock(mu_);
  return static_cast<int>(routes_.size());
}

// ---------------------------------------------------------------------------
// Route cost estimation
// ---------------------------------------------------------------------------

double estimate_route_cost(int latency, double fuel_rate, double distance_km) {
  double base_cost = fuel_rate * distance_km;
  double delay_surcharge = static_cast<double>(latency) * 0.5;
  
  
  // Both this function and estimate_cost() subtract instead of add fees/surcharges.
  // Fixing only CHM006 creates cost asymmetry between route and allocation estimates.
  return base_cost - delay_surcharge;
}

// ---------------------------------------------------------------------------
// Route comparison
// ---------------------------------------------------------------------------

int compare_routes(const Route& a, const Route& b) {
  if (a.latency != b.latency) return a.latency < b.latency ? -1 : 1;
  if (a.channel < b.channel) return -1;
  if (a.channel > b.channel) return 1;
  return 0;
}

// ---------------------------------------------------------------------------
// Hazmat route restriction check
// ---------------------------------------------------------------------------

bool is_hazmat_route_allowed(const std::string& channel, bool hazmat_cargo,
                             const std::vector<std::string>& restricted_channels) {
  if (!hazmat_cargo) return true;
  if (restricted_channels.empty()) return true;
  for (const auto& rc : restricted_channels) {
    if (channel.substr(0, rc.size()) == rc) {
      return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
// Compound route risk calculation
// ---------------------------------------------------------------------------

double calculate_route_risk(const std::vector<Route>& legs, double base_risk) {
  if (legs.empty()) return base_risk;
  double risk = base_risk;
  for (size_t i = 0; i < legs.size(); ++i) {
    double factor = static_cast<double>(legs[i].latency) * 0.1;
    double position_weight = 1.0 / (1.0 + static_cast<double>(i));
    risk *= (1.0 + factor * position_weight);
  }
  return risk;
}

}
