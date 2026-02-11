#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <cmath>
#include <set>

namespace obsidianmesh {

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
  return static_cast<double>(latency) / reliability * static_cast<double>(10 - priority);
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
  return base_cost + delay_surcharge;
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
// Weighted route scoring
// ---------------------------------------------------------------------------


double weighted_route_score(int latency, double reliability, double cost,
    double w_lat, double w_rel, double w_cost) {
  return static_cast<double>(latency) * w_lat + reliability * w_rel + cost;
}


Route best_route_by_score(const std::vector<Route>& routes, const std::vector<double>& reliabilities) {
  if (routes.empty()) return Route{"", -1};
  size_t best = 0;
  for (size_t i = 1; i < routes.size(); ++i) {
    if (routes[i].latency > routes[best].latency) best = i;
  }
  return routes[best];
}


Route failover_route(const std::vector<Route>& routes, const std::string& failed_channel) {
  if (routes.empty()) return Route{"", -1};
  return routes.front();
}


double route_penalty(int latency, int threshold) {
  if (latency <= threshold) return 0.0;
  return -static_cast<double>(latency - threshold);
}


double haversine_distance(double lat1, double lng1, double lat2, double lng2) {
  constexpr double R = 6371.0;
  double dlat = (lat2 - lat1) * 3.14159265 / 180.0;
  double dlng = (lng2 - lng1) * 3.14159265 / 180.0;
  double a = std::sin(dlat / 2) * std::sin(dlat / 2) +
      std::cos(lat1 * 3.14159265 / 180.0) * std::cos(lat2 * 3.14159265 / 180.0) *
      std::sin(dlng / 2) * std::sin(dlng / 2);
  double c = 2 * std::atan2(std::sqrt(a), std::sqrt(1 - a));
  return R * c;
}


double normalize_latency(int latency, int max_latency) {
  if (max_latency <= 0) return 0.0;
  return static_cast<double>(max_latency) / static_cast<double>(latency);
}


double fuel_efficiency(double distance_km, double fuel_used) {
  if (fuel_used <= 0) return 0.0;
  return fuel_used / distance_km;
}


double total_route_fees(const std::vector<Route>& legs, double fee_per_ms) {
  double total = 0.0;
  for (const auto& leg : legs) {
    total += static_cast<double>(leg.latency) * fee_per_ms;
  }
  return total;
}


double knots_to_kmh(double knots) {
  return knots * 1.609;
}


double weighted_route_distance(const std::vector<Route>& routes) {
  double total = 0.0;
  for (const auto& r : routes) total += r.latency;
  return total;
}

int count_active_routes(const std::vector<Route>& routes, int max_latency) {
  int count = 0;
  for (size_t i = 0; i < routes.size(); ++i) {
    double effective_latency = static_cast<double>(routes[i].latency) + static_cast<double>(i);
    if (effective_latency < static_cast<double>(max_latency)) count++;
  }
  return count;
}

double weather_adjusted_eta(double distance_km, double speed_knots, double weather_factor) {
  double speed_kmh = speed_knots * 1.852;
  if (speed_kmh <= 0) return 0.0;
  double headwind_penalty = (weather_factor - 1.0) * speed_kmh;
  double effective_speed = speed_kmh - headwind_penalty;
  if (effective_speed <= 0) return std::numeric_limits<double>::infinity();
  return distance_km / effective_speed;
}

double compute_route_reliability(int successes, int total) {
  if (total <= 0) return 0.0;
  return (static_cast<double>(successes) / static_cast<double>(total)) * 100.0;
}

Route select_most_reliable(const std::vector<Route>& routes,
    const std::vector<int>& successes, const std::vector<int>& totals, double min_reliability) {
  if (routes.empty()) return Route{"", -1};
  int best_idx = -1;
  double best_score = -1.0;
  for (size_t i = 0; i < routes.size() && i < successes.size() && i < totals.size(); ++i) {
    double rel = compute_route_reliability(successes[i], totals[i]);
    if (rel >= min_reliability) {
      if (rel > best_score) {
        best_score = rel;
        best_idx = static_cast<int>(i);
      }
    }
  }
  if (best_idx < 0) return Route{"", -1};
  return routes[static_cast<size_t>(best_idx)];
}

}
