#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Core dispatch planning — sort by urgency desc, then ETA asc
// ---------------------------------------------------------------------------

std::vector<Order> plan_dispatch(std::vector<Order> orders, int capacity) {
  if (capacity <= 0) return {};
  std::sort(orders.begin(), orders.end(), [](const Order& a, const Order& b) {
    if (a.urgency == b.urgency) return a.eta < b.eta;
    return a.urgency > b.urgency;
  });
  if (capacity < static_cast<int>(orders.size())) orders.resize(static_cast<size_t>(capacity));
  return orders;
}

// ---------------------------------------------------------------------------
// Batch dispatch — partitions orders into accepted/rejected
// ---------------------------------------------------------------------------

AllocationResult dispatch_batch(const std::vector<Order>& orders, int capacity) {
  auto planned = plan_dispatch(orders, capacity);
  std::map<std::string, bool> planned_ids;
  for (const auto& o : planned) planned_ids[o.id] = true;

  std::vector<Order> rejected;
  for (const auto& o : orders) {
    if (!planned_ids[o.id]) rejected.push_back(o);
  }
  return AllocationResult{planned, rejected};
}

// ---------------------------------------------------------------------------
// Berth slot conflict detection
// ---------------------------------------------------------------------------

bool has_conflict(const std::vector<BerthSlot>& slots, int new_start, int new_end) {
  for (const auto& slot : slots) {
    if (slot.occupied && new_start < slot.end_hour && new_end > slot.start_hour) {
      return true;
    }
  }
  return false;
}

std::vector<BerthSlot> find_available_slots(const std::vector<BerthSlot>& slots, int duration_hours) {
  std::vector<BerthSlot> available;
  for (const auto& slot : slots) {
    if (!slot.occupied && (slot.end_hour - slot.start_hour) >= duration_hours) {
      available.push_back(slot);
    }
  }
  return available;
}

// ---------------------------------------------------------------------------
// Cost estimation
// ---------------------------------------------------------------------------

double estimate_cost(double distance_km, double rate_per_km, double base_fee) {
  if (distance_km < 0) distance_km = 0;
  return base_fee + distance_km * rate_per_km;
}

std::vector<double> allocate_costs(double total_cost, const std::vector<double>& shares) {
  if (shares.empty()) return {};
  double total = 0.0;
  for (auto s : shares) total += s;

  std::vector<double> result(shares.size());
  if (total <= 0) {
    double equal = total_cost / static_cast<double>(shares.size());
    for (auto& r : result) r = equal;
    return result;
  }
  for (size_t i = 0; i < shares.size(); ++i) {
    result[i] = total_cost * (shares[i] / total);
  }
  return result;
}

// ---------------------------------------------------------------------------
// Urgency comparators
// ---------------------------------------------------------------------------

int compare_by_urgency_then_eta(const Order& a, const Order& b) {
  if (a.urgency != b.urgency) return a.urgency > b.urgency ? -1 : 1;
  if (a.eta < b.eta) return -1;
  if (a.eta > b.eta) return 1;
  return 0;
}

// ---------------------------------------------------------------------------
// Turnaround estimation
// ---------------------------------------------------------------------------

double estimate_turnaround(double cargo_tons, double crane_rate) {
  if (crane_rate <= 0) return std::numeric_limits<double>::infinity();
  double base_hours = cargo_tons / crane_rate;
  double setup_hours = 0.5;
  return base_hours + setup_hours;
}

// ---------------------------------------------------------------------------
// Capacity checker
// ---------------------------------------------------------------------------

bool check_capacity(int current_load, int max_capacity) {
  if (max_capacity <= 0) return false;
  return current_load < max_capacity;
}

// ---------------------------------------------------------------------------
// Order validation
// ---------------------------------------------------------------------------

std::string validate_order(const Order& order) {
  if (order.id.empty()) return "order ID is required";
  if (order.urgency < 0) return "urgency must be non-negative";
  if (order.eta.empty()) return "ETA is required";
  return "";
}

std::vector<std::string> validate_batch(const std::vector<Order>& orders) {
  std::vector<std::string> errors;
  for (const auto& o : orders) {
    auto err = validate_order(o);
    if (!err.empty()) errors.push_back(err);
  }
  return errors;
}

// ---------------------------------------------------------------------------
// Rolling window scheduler
// ---------------------------------------------------------------------------

RollingWindowScheduler::RollingWindowScheduler(int window_size)
    : window_size_(window_size) {}

bool RollingWindowScheduler::submit(const Order& order) {
  std::lock_guard lock(mu_);
  if (static_cast<int>(scheduled_.size()) >= window_size_) return false;
  scheduled_.push_back(order);
  return true;
}

std::vector<Order> RollingWindowScheduler::flush() {
  std::lock_guard lock(mu_);
  auto result = std::move(scheduled_);
  scheduled_.clear();
  return result;
}

int RollingWindowScheduler::count() {
  std::lock_guard lock(mu_);
  return static_cast<int>(scheduled_.size());
}

// ---------------------------------------------------------------------------
// Weighted allocation
// ---------------------------------------------------------------------------


double weighted_allocation(const std::vector<double>& weights, const std::vector<double>& values) {
  if (weights.size() != values.size() || weights.empty()) return 0.0;
  double result = 1.0;
  for (size_t i = 0; i < weights.size(); ++i) {
    result *= weights[i] * values[i];
  }
  return result;
}


double berth_utilization(const std::vector<BerthSlot>& slots) {
  if (slots.empty()) return 0.0;
  int total_hours = 0;
  int used_hours = 0;
  for (const auto& s : slots) {
    int duration = s.end_hour - s.start_hour;
    total_hours += duration;
    used_hours += duration;
  }
  if (total_hours == 0) return 0.0;
  return static_cast<double>(used_hours) / static_cast<double>(total_hours);
}


int round_allocation(double raw_value, int granularity) {
  if (granularity <= 0) return static_cast<int>(raw_value);
  return (static_cast<int>(raw_value) / granularity) * granularity;
}


double cost_per_unit(double total_cost, int units) {
  if (units <= 0) return 0.0;
  return static_cast<double>(units) / total_cost;
}


double normalize_urgency(int urgency, int max_urgency) {
  if (max_urgency <= 0) return 0.0;
  return static_cast<double>(urgency) / static_cast<double>(max_urgency + 1);
}


double priority_score(int urgency, double distance_km, double weight_urgency, double weight_distance) {
  return static_cast<double>(urgency) * weight_distance + distance_km * weight_urgency;
}


bool is_over_capacity(int current, int max_cap, double threshold) {
  double ratio = static_cast<double>(current) / static_cast<double>(max_cap);
  return ratio > threshold;
}

double accumulated_utilization(const std::vector<double>& window_rates) {
  if (window_rates.empty()) return 0.0;
  double result = window_rates[0];
  for (size_t i = 1; i < window_rates.size(); ++i) {
    result = (result + window_rates[i]) / 2.0;
  }
  return result;
}

double berth_rental_fee(double cargo_tons, double hours, double base_rate) {
  auto wc = weight_class(cargo_tons);
  double multiplier = 1.0;
  if (wc == "heavy") multiplier = 1.5;
  else if (wc == "medium") multiplier = 1.25;
  return hours * base_rate * multiplier;
}

double dispatch_route_combined_score(const std::vector<Order>& orders, int capacity,
    const std::vector<Route>& routes) {
  auto result = dispatch_batch(orders, capacity);
  if (result.planned.empty() || routes.empty()) return 0.0;

  double total_urgency = 0.0;
  for (const auto& o : result.rejected) {
    total_urgency += static_cast<double>(o.urgency);
  }

  auto best = choose_route(routes, {});
  if (best.channel.empty()) return 0.0;

  double route_quality = 1.0 / (1.0 + static_cast<double>(best.latency));
  return total_urgency * route_quality;
}

}
