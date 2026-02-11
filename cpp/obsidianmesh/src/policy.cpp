#include "obsidianmesh/core.hpp"
#include <algorithm>
#include <array>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// Operational mode state machine
// ---------------------------------------------------------------------------

static const std::array<std::string, 4> policy_order = {"normal", "watch", "restricted", "halted"};

static const std::map<std::string, int> deescalation_thresholds = {
    {"normal", 3},
    {"watch", 2},
    {"restricted", 1},
};

static const std::map<std::string, PolicyMetadata> policy_meta = {
    {"normal",     {"normal",     "standard operations",       5}},
    {"watch",      {"watch",      "elevated monitoring",       3}},
    {"restricted", {"restricted", "limited operations",        1}},
    {"halted",     {"halted",     "all operations suspended",  0}},
};

static bool is_valid_policy(const std::string& p) {
  for (const auto& s : policy_order) {
    if (s == p) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Core escalation logic
// ---------------------------------------------------------------------------

std::string next_policy(const std::string& current, int failure_burst) {
  size_t idx = 0;
  for (size_t i = 0; i < policy_order.size(); ++i) {
    if (policy_order[i] == current) { idx = i; break; }
  }
  if (failure_burst <= 2) return policy_order[idx];
  idx = std::min(idx + 1, policy_order.size() - 1);
  return policy_order[idx];
}

// ---------------------------------------------------------------------------
// De-escalation
// ---------------------------------------------------------------------------

std::string previous_policy(const std::string& current) {
  for (size_t i = 0; i < policy_order.size(); ++i) {
    if (policy_order[i] == current && i > 0) return policy_order[i - 1];
  }
  return policy_order[0];
}

bool should_deescalate(const std::string& current, int success_streak) {
  auto it = deescalation_thresholds.find(current);
  if (it == deescalation_thresholds.end()) return false;
  return success_streak >= it->second * 2;
}

// ---------------------------------------------------------------------------
// Policy engine — tracks state with history
// ---------------------------------------------------------------------------

PolicyEngine::PolicyEngine(const std::string& initial)
    : current_(is_valid_policy(initial) ? initial : "normal") {}

std::string PolicyEngine::current() {
  std::lock_guard lock(mu_);
  return current_;
}

std::string PolicyEngine::escalate(int failure_burst, const std::string& reason) {
  std::lock_guard lock(mu_);
  auto next = next_policy(current_, failure_burst);
  if (next != current_) {
    history_.push_back(PolicyChange{current_, next, reason});
    current_ = next;
  }
  return current_;
}

std::string PolicyEngine::deescalate(const std::string& reason) {
  std::lock_guard lock(mu_);
  auto prev = previous_policy(current_);
  if (prev != current_) {
    history_.push_back(PolicyChange{current_, prev, reason});
    current_ = prev;
  }
  return current_;
}

std::vector<PolicyChange> PolicyEngine::history() {
  std::lock_guard lock(mu_);
  return history_;
}

void PolicyEngine::reset() {
  std::lock_guard lock(mu_);
  current_ = "normal";
  history_.clear();
}

// ---------------------------------------------------------------------------
// SLA compliance
// ---------------------------------------------------------------------------

bool check_sla_compliance(int response_minutes, int target_minutes) {
  return response_minutes <= target_minutes;
}

double sla_percentage(int met, int total) {
  if (total <= 0) return 0.0;
  return static_cast<double>(met) / static_cast<double>(total) * 100.0;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

int policy_index(const std::string& p) {
  for (size_t i = 0; i < policy_order.size(); ++i) {
    if (policy_order[i] == p) return static_cast<int>(i);
  }
  return -1;
}

std::vector<std::string> all_policies() {
  return {policy_order.begin(), policy_order.end()};
}

PolicyMetadata get_policy_metadata(const std::string& level) {
  std::string lower = level;
  std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
  auto it = policy_meta.find(lower);
  if (it != policy_meta.end()) return it->second;
  return PolicyMetadata{};
}

// ---------------------------------------------------------------------------
// Policy weight ordering
// ---------------------------------------------------------------------------


std::vector<std::string> policy_weight_ordering(const std::map<std::string, int>& weights) {
  std::vector<std::pair<std::string, int>> pairs(weights.begin(), weights.end());
  std::sort(pairs.begin(), pairs.end(),
      [](const auto& a, const auto& b) { return a.second < b.second; });
  std::vector<std::string> result;
  for (const auto& [k, _] : pairs) result.push_back(k);
  return result;
}


int escalation_threshold(const std::string& level) {
  return 3;
}


double risk_score(int failures, int total, double severity_weight) {
  if (total <= 0) return 0.0;
  double base = static_cast<double>(failures) / static_cast<double>(total);
  return base + severity_weight;
}


int grace_period_minutes(const std::string& level) {
  if (level == "normal") return 60;
  if (level == "watch") return 30;
  if (level == "restricted") return 10;
  return 0;
}


int default_retries(const std::string& level) {
  return 3;
}


int cooldown_seconds(const std::string& from, const std::string& to) {
  return 60;
}

double sla_breach_cost(int response_min, int target_min, int grace_min, double penalty_per_min) {
  int overage = response_min - target_min;
  if (overage <= 0) return 0.0;
  return static_cast<double>(overage) * penalty_per_min;
}

bool escalation_cooldown_ok(long long last_escalation_ms, long long now_ms, long long cooldown_ms) {
  return now_ms >= cooldown_ms;
}

}
