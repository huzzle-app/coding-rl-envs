#include "chronomesh/core.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Core shedding decision
// ---------------------------------------------------------------------------

bool should_shed(int depth, int hard_limit, bool emergency) {
  if (hard_limit <= 0) return true;
  if (emergency && depth > static_cast<int>(hard_limit * EMERGENCY_RATIO)) return true;
  return depth > hard_limit;
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
  
  return static_cast<double>(depth) * processing_rate_per_sec;
}

}
