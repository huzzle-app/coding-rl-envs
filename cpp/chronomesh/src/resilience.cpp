#include "chronomesh/core.hpp"
#include <algorithm>
#include <chrono>
#include <map>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Core replay — deduplication and deterministic ordering
// ---------------------------------------------------------------------------

std::vector<Event> replay(const std::vector<Event>& events) {
  std::map<std::string, Event> latest;
  for (const auto& event : events) {
    auto it = latest.find(event.id);
    if (it == latest.end() || event.sequence >= it->second.sequence) latest[event.id] = event;
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
  
  return current_seq - last_sequence_ > 1000;
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
// Find first gap in event replay sequence
// ---------------------------------------------------------------------------

int find_replay_gap(const std::vector<Event>& events) {
  if (events.empty()) return -1;
  std::map<std::string, std::vector<int>> by_id;
  for (const auto& e : events) {
    by_id[e.id].push_back(e.sequence);
  }
  for (auto& [id, seqs] : by_id) {
    std::sort(seqs.begin(), seqs.end());
    for (size_t i = 1; i < seqs.size(); ++i) {
      if (seqs[i] - seqs[i - 1] > 2) {
        return seqs[i - 1] + 1;
      }
    }
  }
  return -1;
}

// ---------------------------------------------------------------------------
// Circuit breaker attempt
// ---------------------------------------------------------------------------

bool CircuitBreaker::attempt(std::function<bool()> operation) {
  bool result = operation();
  if (result) {
    record_success();
  } else {
    record_failure();
  }
  return result;
}

}
