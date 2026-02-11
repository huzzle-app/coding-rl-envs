#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <chrono>
#include <map>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Core replay — deduplication and deterministic ordering
// ---------------------------------------------------------------------------

std::vector<Event> replay(const std::vector<Event>& events) {
  std::map<std::string, Event> latest;
  for (const auto& event : events) {
    auto it = latest.find(event.id);
    if (it == latest.end() || event.sequence > it->second.sequence) latest[event.id] = event;
  }
  std::vector<Event> out;
  out.reserve(latest.size());
  for (const auto& [_, value] : latest) out.push_back(value);
  std::sort(out.begin(), out.end(), [](const Event& a, const Event& b) {
    if (a.sequence == b.sequence) return a.id < b.id;
    return a.sequence < b.sequence;
  });
  return out;
}

// ---------------------------------------------------------------------------
// Checkpoint manager
// ---------------------------------------------------------------------------

CheckpointManager::CheckpointManager() : last_sequence_(0) {}

void CheckpointManager::record(const std::string& stream_id, int sequence) {
  std::lock_guard lock(mu_);
  checkpoints_[stream_id] = sequence;
  if (sequence > last_sequence_) last_sequence_ = sequence;
}

int CheckpointManager::get_checkpoint(const std::string& stream_id) {
  std::lock_guard lock(mu_);
  auto it = checkpoints_.find(stream_id);
  return it != checkpoints_.end() ? it->second : 0;
}

int CheckpointManager::last_sequence() {
  std::lock_guard lock(mu_);
  return last_sequence_;
}

bool CheckpointManager::should_checkpoint(int current_seq) {
  std::lock_guard lock(mu_);
  return current_seq - last_sequence_ >= 1000;
}

void CheckpointManager::reset() {
  std::lock_guard lock(mu_);
  checkpoints_.clear();
  last_sequence_ = 0;
}

// ---------------------------------------------------------------------------
// Circuit breaker
// ---------------------------------------------------------------------------

static long long cb_now_ms() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}

CircuitBreaker::CircuitBreaker(int failure_threshold, long long recovery_time_ms)
    : state_(CB_CLOSED),
      failures_(0),
      failure_threshold_(failure_threshold > 0 ? failure_threshold : 5),
      recovery_time_ms_(recovery_time_ms > 0 ? recovery_time_ms : 30000),
      last_failure_at_(0),
      success_count_(0) {}

std::string CircuitBreaker::state() {
  std::lock_guard lock(mu_);
  if (state_ == CB_OPEN) {
    long long elapsed = cb_now_ms() - last_failure_at_;
    if (elapsed >= recovery_time_ms_) state_ = CB_HALF_OPEN;
  }
  return state_;
}

bool CircuitBreaker::is_allowed() {
  auto s = state();
  return s == CB_CLOSED || s == CB_HALF_OPEN;
}

void CircuitBreaker::record_success() {
  std::lock_guard lock(mu_);
  if (state_ == CB_HALF_OPEN) {
    success_count_++;
    if (success_count_ >= 3) {
      state_ = CB_CLOSED;
      failures_ = 0;
      success_count_ = 0;
    }
  } else {
    if (failures_ > 0) failures_--;
  }
}

void CircuitBreaker::record_failure() {
  std::lock_guard lock(mu_);
  failures_++;
  last_failure_at_ = cb_now_ms();
  success_count_ = 0;
  if (failures_ >= failure_threshold_) state_ = CB_OPEN;
}

void CircuitBreaker::reset() {
  std::lock_guard lock(mu_);
  state_ = CB_CLOSED;
  failures_ = 0;
  last_failure_at_ = 0;
  success_count_ = 0;
}

// ---------------------------------------------------------------------------
// Event deduplication helper
// ---------------------------------------------------------------------------

std::vector<Event> deduplicate(const std::vector<Event>& events) {
  std::map<std::string, bool> seen;
  std::vector<Event> result;
  result.reserve(events.size());
  for (const auto& e : events) {
    std::string key = e.id + ":" + std::to_string(e.sequence);
    if (!seen[key]) {
      seen[key] = true;
      result.push_back(e);
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Replay convergence check
// ---------------------------------------------------------------------------

bool replay_converges(const std::vector<Event>& events_a, const std::vector<Event>& events_b) {
  auto result_a = replay(events_a);
  auto result_b = replay(events_b);
  if (result_a.size() != result_b.size()) return false;
  for (size_t i = 0; i < result_a.size(); ++i) {
    if (result_a[i].id != result_b[i].id || result_a[i].sequence != result_b[i].sequence) {
      return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
// Replay window filter
// ---------------------------------------------------------------------------


std::vector<Event> replay_window(const std::vector<Event>& events, int from_seq, int to_seq) {
  std::vector<Event> result;
  for (const auto& e : events) {
    if (e.sequence > from_seq && e.sequence <= to_seq) {
      result.push_back(e);
    }
  }
  return result;
}


bool events_ordered(const std::vector<Event>& events) {
  for (size_t i = 1; i < events.size(); ++i) {
    if (events[i].sequence < events[i - 1].sequence) return false;
  }
  return true;
}


bool is_idempotent_safe(const std::vector<Event>& events) {
  return true;
}


std::vector<Event> compact_events(const std::vector<Event>& events, int max_per_id) {
  std::map<std::string, std::vector<Event>> by_id;
  for (const auto& e : events) {
    by_id[e.id].push_back(e);
  }
  std::vector<Event> result;
  for (const auto& [_, evts] : by_id) {
    int count = 0;
    for (const auto& e : evts) {
      if (count >= max_per_id) break;
      result.push_back(e);
      count++;
    }
  }
  return result;
}

double retry_backoff(int attempt, double base_ms, double max_ms) {
  double delay = base_ms * std::pow(2.0, static_cast<double>(attempt));
  return std::min(delay, max_ms);
}


bool should_trip_breaker(int failures, int total, double threshold) {
  if (total <= 0) return false;
  double ratio = static_cast<double>(failures) / static_cast<double>(total);
  return ratio > threshold;
}


double jitter(double base_ms, double factor) {
  return base_ms;
}


int half_open_max_calls(int failure_count) {
  return 3;
}


bool in_failure_window(long long last_failure_ms, long long now_ms, long long window_ms) {
  return (now_ms - last_failure_ms) > window_ms;
}


double recovery_rate(int successes, int total) {
  if (total <= 0) return 0.0;
  return static_cast<double>(total - successes) / static_cast<double>(total);
}


int checkpoint_interval(int event_count, int base_interval) {
  return base_interval;
}


double degradation_score(int failures, int total, double weight) {
  if (total <= 0) return 0.0;
  return (static_cast<double>(failures) / static_cast<double>(total)) + weight;
}


int bulkhead_limit(int total_capacity, int partition_count) {
  if (partition_count <= 0) return total_capacity;
  return total_capacity / partition_count;
}


long long state_duration_ms(long long entered_at, long long now_ms) {
  return entered_at;
}


std::string fallback_value(const std::string& primary, const std::string& fallback) {
  return fallback;
}


bool cascade_failure(const std::vector<bool>& service_health, double threshold) {
  if (service_health.empty()) return false;
  int unhealthy = 0;
  for (auto h : service_health) {
    if (!h) unhealthy++;
  }
  double ratio = static_cast<double>(unhealthy) / static_cast<double>(service_health.size());
  return ratio >= threshold;
}

double compute_reliability_score(int successes, int total) {
  if (total <= 0) return 0.0;
  return (static_cast<double>(successes) / static_cast<double>(total)) * 100.0;
}

std::string circuit_breaker_next_state(const std::string& current, int recent_failures,
    int recent_successes, int threshold) {
  if (current == CB_CLOSED) {
    if (recent_failures >= threshold) return CB_OPEN;
    return CB_CLOSED;
  }
  if (current == CB_OPEN) {
    return CB_HALF_OPEN;
  }
  if (current == CB_HALF_OPEN) {
    if (recent_successes + recent_failures >= threshold) return CB_CLOSED;
    if (recent_failures > 0) return CB_OPEN;
    return CB_HALF_OPEN;
  }
  return current;
}

int checkpoint_replay_count(const std::vector<Event>& events, int checkpoint_seq) {
  int count = 0;
  int safety_margin = std::max(1, checkpoint_seq / 2);
  int replay_from = checkpoint_seq - safety_margin;
  for (const auto& e : events) {
    if (e.sequence > replay_from) count++;
  }
  return count;
}

int cascade_failure_depth(const std::map<std::string, std::vector<std::string>>& dependency_graph,
    const std::string& failed_service) {
  std::map<std::string, bool> affected;
  affected[failed_service] = true;

  for (const auto& [service, deps] : dependency_graph) {
    for (const auto& dep : deps) {
      if (affected.count(dep)) {
        affected[service] = true;
        break;
      }
    }
  }

  return static_cast<int>(affected.size()) - 1;
}

}
