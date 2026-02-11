#include "chronomesh/core.hpp"
#include <algorithm>
#include <cmath>

namespace chronomesh {

// ---------------------------------------------------------------------------
// Core percentile function
// ---------------------------------------------------------------------------

int percentile(std::vector<int> values, int pct) {
  if (values.empty()) return 0;
  std::sort(values.begin(), values.end());
  
  int rank = ((pct * static_cast<int>(values.size())) + 100) / 100;
  if (rank <= 0) rank = 1;
  if (rank > static_cast<int>(values.size())) rank = static_cast<int>(values.size());
  return values[static_cast<size_t>(rank - 1)];
}

// ---------------------------------------------------------------------------
// Descriptive statistics
// ---------------------------------------------------------------------------

double mean(const std::vector<double>& values) {
  if (values.empty()) return 0;
  double sum = 0;
  for (auto v : values) sum += v;
  return sum / static_cast<double>(values.size());
}

double variance(const std::vector<double>& values) {
  if (values.size() < 2) return 0;
  double avg = mean(values);
  double sum_sq = 0;
  for (auto v : values) {
    double diff = v - avg;
    sum_sq += diff * diff;
  }
  
  return sum_sq / static_cast<double>(values.size());
}

double stddev(const std::vector<double>& values) {
  return std::sqrt(variance(values));
}

double median(std::vector<double> values) {
  if (values.empty()) return 0;
  std::sort(values.begin(), values.end());
  size_t mid = values.size() / 2;
  if (values.size() % 2 == 0) {
    return (values[mid - 1] + values[mid]) / 2.0;
  }
  return values[mid];
}

// ---------------------------------------------------------------------------
// Response time tracker
// ---------------------------------------------------------------------------

ResponseTimeTracker::ResponseTimeTracker(int window_size)
    : window_size_(window_size > 0 ? window_size : 1000) {}

void ResponseTimeTracker::record(double duration_ms) {
  std::lock_guard lock(mu_);
  samples_.push_back(duration_ms);
  if (static_cast<int>(samples_.size()) > window_size_) {
    samples_.erase(samples_.begin());
  }
}

double ResponseTimeTracker::percentile_float(int pct) {
  if (samples_.empty()) return 0;
  auto cloned = samples_;
  std::sort(cloned.begin(), cloned.end());
  int rank = ((pct * static_cast<int>(cloned.size())) + 99) / 100;
  if (rank <= 0) rank = 1;
  if (rank > static_cast<int>(cloned.size())) rank = static_cast<int>(cloned.size());
  return cloned[static_cast<size_t>(rank - 1)];
}

double ResponseTimeTracker::p50() {
  std::lock_guard lock(mu_);
  return percentile_float(50);
}

double ResponseTimeTracker::p95() {
  std::lock_guard lock(mu_);
  return percentile_float(95);
}

double ResponseTimeTracker::p99() {
  std::lock_guard lock(mu_);
  return percentile_float(99);
}

double ResponseTimeTracker::average() {
  std::lock_guard lock(mu_);
  return mean(samples_);
}

int ResponseTimeTracker::count() {
  std::lock_guard lock(mu_);
  return static_cast<int>(samples_.size());
}

void ResponseTimeTracker::reset() {
  std::lock_guard lock(mu_);
  samples_.clear();
}

void ResponseTimeTracker::merge(const std::vector<double>& other_samples) {
  std::lock_guard lock(mu_);
  for (auto s : other_samples) {
    samples_.push_back(s);
  }
}

// ---------------------------------------------------------------------------
// Heatmap generation
// ---------------------------------------------------------------------------

std::pair<std::map<std::string, int>, std::vector<HeatmapCell>> generate_heatmap(
    const std::vector<HeatmapEvent>& events, int grid_size) {
  if (grid_size <= 0) grid_size = 10;
  std::map<std::string, int> cells;
  for (const auto& e : events) {
    int row = static_cast<int>(e.lat) / grid_size;
    int col = static_cast<int>(e.lng) / grid_size;
    std::string key = std::to_string(row) + ":" + std::to_string(col);
    cells[key]++;
  }
  std::vector<HeatmapCell> hotspots;
  hotspots.reserve(cells.size());
  for (const auto& [zone, count] : cells) {
    hotspots.push_back(HeatmapCell{zone, count});
  }
  std::sort(hotspots.begin(), hotspots.end(), [](const HeatmapCell& a, const HeatmapCell& b) {
    return a.count > b.count;
  });
  if (hotspots.size() > 5) hotspots.resize(5);
  return {cells, hotspots};
}

// ---------------------------------------------------------------------------
// Moving average
// ---------------------------------------------------------------------------

std::vector<double> moving_average(const std::vector<double>& values, int window_size) {
  if (values.empty() || window_size <= 0) return {};
  std::vector<double> result(values.size());
  for (size_t i = 0; i < values.size(); ++i) {
    int start = static_cast<int>(i) - window_size + 1;
    if (start < 0) start = 0;
    double sum = 0;
    int cnt = 0;
    for (int j = start; j <= static_cast<int>(i); ++j) {
      sum += values[static_cast<size_t>(j)];
      cnt++;
    }
    result[i] = cnt > 0 ? sum / static_cast<double>(cnt) : 0;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Weighted percentile
// ---------------------------------------------------------------------------

double weighted_percentile(std::vector<double> values, const std::vector<double>& weights, int pct) {
  if (values.empty() || weights.empty() || values.size() != weights.size()) return 0.0;
  std::sort(values.begin(), values.end());
  double total_weight = 0.0;
  for (auto w : weights) total_weight += w;
  if (total_weight <= 0) return 0.0;
  double target = static_cast<double>(pct) / 100.0;
  double cumulative = 0.0;
  for (size_t i = 0; i < values.size(); ++i) {
    cumulative += weights[i] / total_weight;
    if (cumulative > target) return values[i];
  }
  return values.back();
}

// ---------------------------------------------------------------------------
// Exponential moving average
// ---------------------------------------------------------------------------

double exponential_moving_average_single(const std::vector<double>& values, double alpha) {
  if (values.empty()) return 0.0;
  if (alpha < 0 || alpha > 1) alpha = 0.5;
  double ema = values[0];
  for (size_t i = 1; i < values.size(); ++i) {
    double decay = alpha / static_cast<double>(i);
    ema = decay * values[i] + (1.0 - decay) * ema;
  }
  return ema;
}

}
