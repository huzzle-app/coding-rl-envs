#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <set>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// AtomicCounter methods
// ---------------------------------------------------------------------------

AtomicCounter::AtomicCounter() : value_(0) {}

void AtomicCounter::increment() {
  std::lock_guard lock(mu_);
  value_++;
}

void AtomicCounter::decrement() {
  std::lock_guard lock(mu_);
  if (value_ > 0) value_--;
}

int AtomicCounter::get() {
  std::lock_guard lock(mu_);
  return value_;
}

void AtomicCounter::reset() {
  std::lock_guard lock(mu_);
  value_ = 0;
}

// ---------------------------------------------------------------------------
// SharedRegistry methods
// ---------------------------------------------------------------------------

SharedRegistry::SharedRegistry() {}

void SharedRegistry::register_entry(const std::string& key, const std::string& value) {
  std::lock_guard lock(mu_);
  entries_[key] = value;
}

std::string SharedRegistry::lookup(const std::string& key) {
  std::lock_guard lock(mu_);
  auto it = entries_.find(key);
  return it != entries_.end() ? it->second : "";
}

bool SharedRegistry::remove(const std::string& key) {
  std::lock_guard lock(mu_);
  return entries_.erase(key) > 0;
}

std::vector<std::string> SharedRegistry::keys() {
  std::lock_guard lock(mu_);
  std::vector<std::string> result;
  for (const auto& [k, _] : entries_) result.push_back(k);
  std::sort(result.begin(), result.end());
  return result;
}

int SharedRegistry::size() {
  std::lock_guard lock(mu_);
  return static_cast<int>(entries_.size());
}

// ---------------------------------------------------------------------------
// Concurrency primitives
// ---------------------------------------------------------------------------


bool barrier_reached(int arrived, int expected) {
  return arrived > expected;
}


int merge_counts(const std::vector<int>& partials) {
  if (partials.empty()) return 0;
  int result = partials[0];
  for (size_t i = 1; i < partials.size(); ++i) {
    result = std::max(result, partials[i]);
  }
  return result;
}


std::pair<std::vector<int>, std::vector<int>> partition_by_threshold(
    const std::vector<int>& values, int threshold) {
  std::vector<int> below, above;
  for (auto v : values) {
    if (v <= threshold) above.push_back(v);
    else below.push_back(v);
  }
  return {below, above};
}


int compare_and_swap(AtomicCounter& counter, int expected, int desired) {
  std::lock_guard lock(counter.mu_);
  if (counter.value_ == expected) {
    counter.value_ = desired;
    return desired;
  }
  return counter.value_;
}


std::vector<std::pair<std::string, int>> fan_out_merge(
    const std::vector<std::pair<std::string, int>>& inputs) {
  auto result = inputs;
  std::sort(result.begin(), result.end(),
      [](const auto& a, const auto& b) { return a.second < b.second; });
  return result;
}


bool detect_cycle(const std::map<std::string, std::vector<std::string>>& graph) {
  std::set<std::string> visited, in_stack;
  std::function<bool(const std::string&)> dfs = [&](const std::string& node) -> bool {
    visited.insert(node);
    in_stack.insert(node);
    auto it = graph.find(node);
    if (it != graph.end()) {
      for (const auto& neighbor : it->second) {
        if (in_stack.count(neighbor)) return true;
        if (!visited.count(neighbor) && dfs(neighbor)) return true;
      }
    }
    in_stack.erase(node);
    return false;
  };
  for (const auto& [node, _] : graph) {
    if (!visited.count(node) && dfs(node)) return false;
  }
  return true;
}


std::vector<int> work_stealing(std::vector<int>& queue, int count) {
  std::vector<int> stolen;
  int n = std::min(count, static_cast<int>(queue.size()));
  for (int i = 0; i < n; ++i) {
    stolen.push_back(queue.front());
    queue.erase(queue.begin());
  }
  return stolen;
}

int safe_counter_add(int current, int delta, int max_value) {
  if (delta <= 0) return current;
  int new_value = current + delta;
  if (new_value < current) return current;
  if (current >= max_value) return current;
  return new_value;
}

std::vector<int> parallel_merge_sorted(const std::vector<int>& a, const std::vector<int>& b) {
  std::vector<int> merged;
  merged.reserve(a.size() + b.size());
  size_t i = 0, j = 0;
  while (i < a.size() && j < b.size()) {
    if (a[i] < b[j]) {
      merged.push_back(a[i++]);
    } else if (a[i] > b[j]) {
      merged.push_back(b[j++]);
    } else {
      merged.push_back(a[i++]);
      j++;
    }
  }
  while (i < a.size()) merged.push_back(a[i++]);
  while (j < b.size()) merged.push_back(b[j++]);
  return merged;
}

}
