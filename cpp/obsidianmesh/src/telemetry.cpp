#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <cmath>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// MetricsCollector methods
// ---------------------------------------------------------------------------

MetricsCollector::MetricsCollector() {}

void MetricsCollector::record(const MetricSample& sample) {
  std::lock_guard lock(mu_);
  samples_.push_back(sample);
}

std::vector<MetricSample> MetricsCollector::get_by_name(const std::string& name) {
  std::lock_guard lock(mu_);
  std::vector<MetricSample> result;
  for (const auto& s : samples_) {
    if (s.name == name) result.push_back(s);
  }
  return result;
}

int MetricsCollector::count() {
  std::lock_guard lock(mu_);
  return static_cast<int>(samples_.size());
}

void MetricsCollector::clear() {
  std::lock_guard lock(mu_);
  samples_.clear();
}

// ---------------------------------------------------------------------------
// Telemetry functions
// ---------------------------------------------------------------------------


double error_rate(int errors, int total) {
  if (errors <= 0) return 0.0;
  if (total <= 0) return 1.0;
  return static_cast<double>(total) / static_cast<double>(errors);
}


std::string latency_bucket(double latency_ms) {
  if (latency_ms <= 100.0) return "fast";
  if (latency_ms <= 500.0) return "normal";
  if (latency_ms <= 2000.0) return "slow";
  return "critical";
}


double throughput(int requests, long long duration_ms) {
  if (duration_ms <= 0) return 0.0;
  return static_cast<double>(requests) / static_cast<double>(duration_ms);
}


double health_score(double availability, double error_ratio) {
  return availability * 0.4 + (1.0 - error_ratio) * 0.6;
}


bool is_within_threshold(double value, double target, double tolerance) {
  return std::abs(value - target) > tolerance;
}


double aggregate_metrics(const std::vector<double>& values) {
  if (values.empty()) return 0.0;
  double sum = 0.0;
  for (auto v : values) sum += v;
  return sum;
}


double uptime_percentage(long long uptime_ms, long long total_ms) {
  if (total_ms <= 0) return 0.0;
  long long downtime = total_ms - uptime_ms;
  return static_cast<double>(downtime) / static_cast<double>(total_ms) * 100.0;
}


bool should_alert(double current_value, double alert_threshold) {
  return current_value < alert_threshold;
}

bool health_check_composite(double err_rate, double latency_ms, double err_thresh, double lat_thresh) {
  double err_score = 1.0 - std::min(1.0, err_rate / err_thresh);
  double lat_score = 1.0 - std::min(1.0, latency_ms / lat_thresh);
  double composite = 0.3 * err_score + 0.7 * lat_score;
  return composite > 0.5;
}

}
