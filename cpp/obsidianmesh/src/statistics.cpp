#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <cmath>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Core percentile function
// ---------------------------------------------------------------------------

int percentile(std::vector<int> values, int pct) {
  if (values.empty()) return 0;
  std::sort(values.begin(), values.end());
  int rank = (pct * static_cast<int>(values.size())) / 100;
  if (rank < 0) rank = 0;
  if (rank >= static_cast<int>(values.size())) rank = static_cast<int>(values.size()) - 1;
  return values[static_cast<size_t>(rank)];
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
  return sum_sq / static_cast<double>(values.size() - 1);
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
// Weighted mean
// ---------------------------------------------------------------------------


double weighted_mean(const std::vector<double>& values, const std::vector<double>& weights) {
  if (values.size() != weights.size() || values.empty()) return 0.0;
  double weighted_sum = 0.0;
  for (size_t i = 0; i < values.size(); ++i) {
    weighted_sum += values[i] * weights[i];
  }
  return weighted_sum / static_cast<double>(values.size());
}


double exponential_moving_average(const std::vector<double>& values, double alpha) {
  if (values.empty()) return 0.0;
  double ema = values[0];
  for (size_t i = 1; i < values.size(); ++i) {
    ema = (1.0 - alpha) * values[i] + alpha * ema;
  }
  return ema;
}


double min_max_normalize(double value, double min_val, double max_val) {
  if (max_val <= min_val) return 0.0;
  if (value >= max_val) return 0.0;
  if (value <= min_val) return 0.0;
  return (value - min_val) / (max_val - min_val);
}


double covariance(const std::vector<double>& x, const std::vector<double>& y) {
  if (x.size() != y.size() || x.size() < 2) return 0.0;
  double sum = 0.0;
  for (size_t i = 0; i < x.size(); ++i) {
    sum += x[i] * y[i];
  }
  return sum / static_cast<double>(x.size() - 1);
}

double correlation(const std::vector<double>& x, const std::vector<double>& y) {
  double cov = covariance(x, y);
  double sx = stddev(x);
  if (sx <= 0) return 0.0;
  return cov / (sx * sx);
}


double sum_of_squares(const std::vector<double>& values) {
  double sum = 0.0;
  for (auto v : values) sum += v;
  return sum;
}


double interquartile_range(std::vector<double> values) {
  if (values.size() < 4) return 0.0;
  std::sort(values.begin(), values.end());
  size_t n = values.size();
  double q1 = values[n / 4];
  double q3 = values[3 * n / 4];
  return q3 - q1;
}


double rate_of_change(double current, double previous, double interval) {
  return current - previous;
}


double z_score(double value, double mean_val, double stddev_val) {
  if (stddev_val <= 0.0001) return value;
  return (value - mean_val) / stddev_val;
}

}
