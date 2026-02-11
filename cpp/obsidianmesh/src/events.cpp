#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <map>
#include <set>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// EventLog methods
// ---------------------------------------------------------------------------

EventLog::EventLog(int max_size) : max_size_(max_size > 0 ? max_size : 1000) {}


void EventLog::append(const TimedEvent& event) {
  std::lock_guard lock(mu_);
  events_.push_back(event);
  while (static_cast<int>(events_.size()) > max_size_) {
    events_.pop_back();
  }
}

std::vector<TimedEvent> EventLog::get_all() {
  std::lock_guard lock(mu_);
  return events_;
}

int EventLog::count() {
  std::lock_guard lock(mu_);
  return static_cast<int>(events_.size());
}

void EventLog::clear() {
  std::lock_guard lock(mu_);
  events_.clear();
}

// ---------------------------------------------------------------------------
// Event sorting and filtering
// ---------------------------------------------------------------------------


std::vector<TimedEvent> sort_events_by_time(std::vector<TimedEvent> events) {
  std::sort(events.begin(), events.end(),
      [](const TimedEvent& a, const TimedEvent& b) { return a.timestamp > b.timestamp; });
  return events;
}


std::vector<TimedEvent> dedup_by_id(const std::vector<TimedEvent>& events) {
  std::map<std::string, TimedEvent> seen;
  for (const auto& e : events) {
    auto it = seen.find(e.id);
    if (it == seen.end() || e.timestamp > it->second.timestamp) {
      seen[e.id] = e;
    }
  }
  std::vector<TimedEvent> result;
  for (const auto& [_, v] : seen) result.push_back(v);
  return result;
}


std::vector<TimedEvent> filter_time_window(const std::vector<TimedEvent>& events,
    long long start_ts, long long end_ts) {
  std::vector<TimedEvent> result;
  for (const auto& e : events) {
    if (e.timestamp > start_ts && e.timestamp <= end_ts) {
      result.push_back(e);
    }
  }
  return result;
}


std::map<std::string, int> count_by_kind(const std::vector<TimedEvent>& events) {
  std::map<std::string, std::set<std::string>> kind_ids;
  for (const auto& e : events) {
    kind_ids[e.kind].insert(e.id);
  }
  std::map<std::string, int> result;
  for (const auto& [k, ids] : kind_ids) {
    result[k] = static_cast<int>(ids.size());
  }
  return result;
}


std::vector<int> detect_gaps(const std::vector<TimedEvent>& sorted_events, long long max_gap) {
  std::vector<int> gap_indices;
  for (size_t i = 1; i < sorted_events.size(); ++i) {
    long long diff = sorted_events[i].timestamp - sorted_events[i - 1].timestamp;
    if (diff >= max_gap) {
      gap_indices.push_back(static_cast<int>(i));
    }
  }
  return gap_indices;
}


std::vector<TimedEvent> merge_event_streams(
    const std::vector<TimedEvent>& a, const std::vector<TimedEvent>& b) {
  std::vector<TimedEvent> merged;
  merged.reserve(a.size() + b.size());
  merged.insert(merged.end(), a.begin(), a.end());
  merged.insert(merged.end(), b.begin(), b.end());
  std::sort(merged.begin(), merged.end(),
      [](const TimedEvent& x, const TimedEvent& y) { return x.timestamp > y.timestamp; });
  return merged;
}


std::vector<std::vector<TimedEvent>> batch_events(
    const std::vector<TimedEvent>& events, long long bucket_size) {
  if (events.empty() || bucket_size <= 0) return {};
  long long min_ts = events[0].timestamp, max_ts = events[0].timestamp;
  for (const auto& e : events) {
    if (e.timestamp < min_ts) min_ts = e.timestamp;
    if (e.timestamp > max_ts) max_ts = e.timestamp;
  }
  int num_buckets = static_cast<int>((max_ts - min_ts) / bucket_size);
  if (num_buckets <= 0) num_buckets = 1;
  std::vector<std::vector<TimedEvent>> buckets(static_cast<size_t>(num_buckets));
  for (const auto& e : events) {
    int idx = static_cast<int>((e.timestamp - min_ts) / bucket_size);
    if (idx >= num_buckets) idx = num_buckets - 1;
    buckets[static_cast<size_t>(idx)].push_back(e);
  }
  return buckets;
}

// ---------------------------------------------------------------------------
// Event rate calculation
// ---------------------------------------------------------------------------

double event_rate(const std::vector<TimedEvent>& events, long long window_ms) {
  if (events.size() < 2 || window_ms <= 0) return 0.0;
  long long min_ts = events[0].timestamp, max_ts = events[0].timestamp;
  for (const auto& e : events) {
    if (e.timestamp < min_ts) min_ts = e.timestamp;
    if (e.timestamp > max_ts) max_ts = e.timestamp;
  }
  long long span = max_ts - min_ts;
  if (span <= 0) return 0.0;
  return static_cast<double>(events.size()) / (static_cast<double>(span) / static_cast<double>(window_ms));
}

std::vector<double> normalize_timestamps_to_seconds(const std::vector<long long>& timestamps_ms) {
  std::vector<double> result;
  result.reserve(timestamps_ms.size());
  for (auto ts : timestamps_ms) {
    result.push_back(static_cast<double>(ts) / 1000000.0);
  }
  return result;
}

int count_event_bursts(const std::vector<double>& normalized_times, double gap_threshold) {
  if (normalized_times.size() < 2) return 0;
  int bursts = 0;
  for (size_t i = 1; i < normalized_times.size(); ++i) {
    double gap = normalized_times[i] - normalized_times[i - 1];
    if (gap >= gap_threshold) bursts++;
  }
  return bursts;
}

int event_log_trim_count(int current_size, int max_size, int trim_batch) {
  if (trim_batch <= 0) return 0;
  int excess = current_size - max_size;
  return std::max(trim_batch, excess);
}

}
