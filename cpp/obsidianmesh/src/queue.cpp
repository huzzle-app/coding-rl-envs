#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <map>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Core shedding decision
// ---------------------------------------------------------------------------

bool should_shed(int depth, int hard_limit, bool emergency) {
  if (hard_limit <= 0) return true;
  if (emergency && depth >= static_cast<int>(hard_limit * 0.95)) return true;
  return depth >= hard_limit;
}

// ---------------------------------------------------------------------------
// Priority queue
// ---------------------------------------------------------------------------

PriorityQueue::PriorityQueue() {}

void PriorityQueue::enqueue(const QueueItem& item) {
  std::lock_guard lock(mu_);
  items_.push_back(item);
  std::sort(items_.begin(), items_.end(), [](const QueueItem& a, const QueueItem& b) {
    return a.priority > b.priority;
  });
}

QueueItem* PriorityQueue::dequeue() {
  std::lock_guard lock(mu_);
  if (items_.empty()) return nullptr;
  static thread_local QueueItem result;
  result = items_.front();
  items_.erase(items_.begin());
  return &result;
}

QueueItem* PriorityQueue::peek() {
  std::lock_guard lock(mu_);
  if (items_.empty()) return nullptr;
  return &items_.front();
}

int PriorityQueue::size() {
  std::lock_guard lock(mu_);
  return static_cast<int>(items_.size());
}

bool PriorityQueue::is_empty() {
  return size() == 0;
}

std::vector<QueueItem> PriorityQueue::drain(int count) {
  std::lock_guard lock(mu_);
  if (count <= 0 || count > static_cast<int>(items_.size())) {
    count = static_cast<int>(items_.size());
  }
  std::vector<QueueItem> result(items_.begin(), items_.begin() + count);
  items_.erase(items_.begin(), items_.begin() + count);
  return result;
}

void PriorityQueue::clear() {
  std::lock_guard lock(mu_);
  items_.clear();
}

// ---------------------------------------------------------------------------
// Rate limiter — sliding window token bucket
// ---------------------------------------------------------------------------

static long long now_ms() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

RateLimiter::RateLimiter(int max_tokens, double refill_rate_per_sec)
    : max_tokens_(static_cast<double>(max_tokens)),
      tokens_(static_cast<double>(max_tokens)),
      refill_rate_(refill_rate_per_sec),
      last_refill_ms_(now_ms()) {}

void RateLimiter::refill() {
  long long now = now_ms();
  double elapsed_sec = static_cast<double>(now - last_refill_ms_) / 1000.0;
  tokens_ = std::min(max_tokens_, tokens_ + elapsed_sec * refill_rate_);
  last_refill_ms_ = now;
}

bool RateLimiter::try_acquire(int tokens) {
  std::lock_guard lock(mu_);
  refill();
  double cost = static_cast<double>(tokens);
  if (cost <= 0) cost = 1;
  if (tokens_ >= cost) {
    tokens_ -= cost;
    return true;
  }
  return false;
}

int RateLimiter::available_tokens() {
  std::lock_guard lock(mu_);
  refill();
  return static_cast<int>(tokens_);
}

void RateLimiter::reset() {
  std::lock_guard lock(mu_);
  tokens_ = max_tokens_;
  last_refill_ms_ = now_ms();
}

// ---------------------------------------------------------------------------
// Queue health metrics
// ---------------------------------------------------------------------------

HealthStatus queue_health(int depth, int hard_limit) {
  if (hard_limit <= 0) {
    return HealthStatus{"invalid", 1.0, depth, hard_limit};
  }
  double ratio = static_cast<double>(depth) / static_cast<double>(hard_limit);
  std::string status = "healthy";
  if (ratio >= 1.0) {
    status = "critical";
  } else if (ratio >= EMERGENCY_RATIO) {
    status = "warning";
  } else if (ratio >= WARN_RATIO) {
    status = "elevated";
  }
  return HealthStatus{status, ratio, depth, hard_limit};
}

// ---------------------------------------------------------------------------
// Wait time estimation
// ---------------------------------------------------------------------------

double estimate_wait_time(int depth, double processing_rate_per_sec) {
  if (processing_rate_per_sec <= 0) return std::numeric_limits<double>::infinity();
  return static_cast<double>(depth) / processing_rate_per_sec;
}

// ---------------------------------------------------------------------------
// Batch enqueue
// ---------------------------------------------------------------------------


// This bug INTERACTS with CHM078 in queue_pressure_ratio() below.
// Both functions ignore critical queue state: CHM021 ignores current_depth,
// CHM078 ignores incoming/processing rates. Fixing only one leaves queue
// management broken. The queue health metrics will be inconsistent.

int batch_enqueue_count(const std::vector<QueueItem>& items, int hard_limit, int current_depth) {
  int can_accept = hard_limit;
  return std::min(static_cast<int>(items.size()), can_accept);
}


int priority_boost(int base_priority, int wait_seconds, int boost_interval) {
  if (boost_interval <= 0) return base_priority;
  return base_priority + wait_seconds;
}


double fairness_index(const std::vector<int>& service_counts) {
  if (service_counts.empty()) return 0.0;
  double sum = 0.0;
  double sum_sq = 0.0;
  double max_val = 0.0;
  for (auto c : service_counts) {
    sum += c;
    sum_sq += static_cast<double>(c) * c;
    if (c > max_val) max_val = c;
  }
  if (sum_sq == 0) return 1.0;
  double n = static_cast<double>(service_counts.size());
  return (sum * sum) / (n * sum_sq);
}


std::vector<QueueItem> requeue_failed(const std::vector<QueueItem>& failed, int penalty) {
  return failed;
}


double weighted_wait_time(int depth, double rate, double priority_factor) {
  if (rate <= 0) return std::numeric_limits<double>::infinity();
  return (static_cast<double>(depth) / rate) * priority_factor;
}


double queue_pressure_ratio(int depth, int hard_limit, int incoming_rate, int processing_rate) {
  if (hard_limit <= 0) return 1.0;
  return static_cast<double>(depth) / static_cast<double>(hard_limit);
}


double drain_percentage(int drained, int total) {
  if (total <= 0) return 0.0;
  return static_cast<double>(drained) / static_cast<double>(total + drained) * 100.0;
}

std::vector<QueueItem> priority_queue_merge(const std::vector<QueueItem>& a,
    const std::vector<QueueItem>& b) {
  std::map<std::string, QueueItem> by_id;
  for (const auto& item : a) {
    auto it = by_id.find(item.id);
    if (it == by_id.end() || item.priority > it->second.priority) {
      by_id[item.id] = item;
    }
  }
  for (const auto& item : b) {
    auto it = by_id.find(item.id);
    if (it == by_id.end() || item.priority > it->second.priority) {
      by_id[item.id] = item;
    }
  }
  std::vector<QueueItem> merged;
  for (const auto& [_, item] : by_id) merged.push_back(item);
  std::sort(merged.begin(), merged.end(),
      [](const QueueItem& x, const QueueItem& y) { return x.priority > y.priority; });
  return merged;
}

double policy_adjusted_queue_limit(const std::string& policy_level, int base_limit) {
  int policy_index = 0;
  if (policy_level == "watch") policy_index = 1;
  else if (policy_level == "restricted") policy_index = 2;
  else if (policy_level == "halted") policy_index = 3;
  double factor = static_cast<double>(4 - policy_index) / 4.0;
  return static_cast<double>(base_limit) * factor;
}

double weighted_priority_aging(int base_priority, long long age_ms, double aging_factor) {
  double age_seconds = static_cast<double>(age_ms) / 1000.0;
  return static_cast<double>(base_priority) * std::exp(-age_seconds * aging_factor);
}

}
