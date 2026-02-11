#include "chronomesh/core.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Core dispatch planning — sort by urgency desc, then ETA asc
// ---------------------------------------------------------------------------

std::vector<Order> plan_dispatch(std::vector<Order> orders, int capacity) {
  if (capacity <= 0) return {};
  std::sort(orders.begin(), orders.end(), [](const Order& a, const Order& b) {
    if (a.urgency == b.urgency) return a.eta < b.eta;
    return a.urgency < b.urgency;
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
    
    if (slot.occupied && new_start <= slot.end_hour && new_end > slot.start_hour) {
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
  return distance_km * rate_per_km - base_fee;
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
  
  return current_load <= max_capacity;
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
// Berth utilization calculation
// ---------------------------------------------------------------------------

double calculate_berth_utilization(const std::vector<BerthSlot>& slots) {
  if (slots.empty()) return 0.0;
  int occupied_hours = 0;
  int total_hours = 0;
  for (const auto& slot : slots) {
    int duration = slot.end_hour - slot.start_hour;
    total_hours += duration;
    if (slot.occupied) occupied_hours += duration;
  }
  if (total_hours <= 0) return 0.0;
  int pct = (occupied_hours * 100) / total_hours;
  return static_cast<double>(pct) / 100.0;
}

// ---------------------------------------------------------------------------
// Merge dispatch queues with deduplication
// ---------------------------------------------------------------------------

std::vector<Order> merge_dispatch_queues(const std::vector<Order>& primary,
                                         const std::vector<Order>& overflow, int capacity) {
  std::map<std::string, bool> seen;
  std::vector<Order> merged;
  for (const auto& o : primary) {
    seen[o.id] = true;
    merged.push_back(o);
  }
  for (const auto& o : overflow) {
    if (!seen[o.id]) {
      merged.push_back(o);
    }
  }
  if (capacity > 0 && static_cast<int>(merged.size()) > capacity) {
    merged.resize(static_cast<size_t>(capacity));
  }
  std::sort(merged.begin(), merged.end(), [](const Order& a, const Order& b) {
    return a.urgency > b.urgency;
  });
  return merged;
}

// ---------------------------------------------------------------------------
// Batch submission for rolling window
// ---------------------------------------------------------------------------

int RollingWindowScheduler::submit_batch(const std::vector<Order>& orders) {
  int accepted = 0;
  for (const auto& order : orders) {
    if (submit(order)) {
      accepted++;
    }
  }
  return accepted;
}

}
