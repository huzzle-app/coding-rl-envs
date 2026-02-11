#include "obsidianmesh/core.hpp"
#include <deque>

namespace obsidianmesh {

// ---------------------------------------------------------------------------
// State transition graph
// ---------------------------------------------------------------------------

static const std::map<std::string, std::map<std::string, bool>> graph = {
    {"queued",    {{"allocated", true}, {"cancelled", true}}},
    {"allocated", {{"departed", true}, {"cancelled", true}}},
    {"departed",  {{"arrived", true}}},
    {"arrived",   {}},
};

static const std::map<std::string, bool> terminal_states = {
    {"arrived", true},
    {"cancelled", true},
};

// ---------------------------------------------------------------------------
// Core transition validation
// ---------------------------------------------------------------------------

bool can_transition(const std::string& from, const std::string& to) {
  auto it = graph.find(from);
  if (it == graph.end()) return false;
  auto jt = it->second.find(to);
  return jt != it->second.end() && jt->second;
}

// ---------------------------------------------------------------------------
// Transition helpers
// ---------------------------------------------------------------------------

std::vector<std::string> allowed_transitions(const std::string& from) {
  auto it = graph.find(from);
  if (it == graph.end()) return {};
  std::vector<std::string> result;
  for (const auto& [state, _] : it->second) result.push_back(state);
  return result;
}

bool is_valid_state(const std::string& state) {
  return graph.count(state) > 0 || terminal_states.count(state) > 0;
}

bool is_terminal_state(const std::string& state) {
  return terminal_states.count(state) > 0;
}

// ---------------------------------------------------------------------------
// Shortest path (BFS)
// ---------------------------------------------------------------------------

std::vector<std::string> shortest_path(const std::string& from, const std::string& to) {
  if (from == to) return {from};
  std::map<std::string, bool> visited;
  visited[from] = true;
  std::deque<std::vector<std::string>> queue;
  queue.push_back({from});

  while (!queue.empty()) {
    auto path = queue.front();
    queue.pop_front();
    auto current = path.back();
    auto it = graph.find(current);
    if (it == graph.end()) continue;
    for (const auto& [next, _] : it->second) {
      if (next == to) {
        path.push_back(next);
        return path;
      }
      if (!visited[next]) {
        visited[next] = true;
        auto new_path = path;
        new_path.push_back(next);
        queue.push_back(new_path);
      }
    }
  }
  return {};
}

// ---------------------------------------------------------------------------
// Workflow engine — manages entity lifecycles
// ---------------------------------------------------------------------------

WorkflowEngine::WorkflowEngine() {}

bool WorkflowEngine::register_entity(const std::string& entity_id, const std::string& initial_state) {
  std::lock_guard lock(mu_);
  std::string state = initial_state.empty() ? "queued" : initial_state;
  if (graph.find(state) == graph.end()) return false;
  entities_[entity_id] = Entity{state, {}};
  return true;
}

std::string WorkflowEngine::get_state(const std::string& entity_id) {
  std::lock_guard lock(mu_);
  auto it = entities_.find(entity_id);
  if (it == entities_.end()) return "";
  return it->second.state;
}

TransitionResult WorkflowEngine::transition(const std::string& entity_id, const std::string& to) {
  std::lock_guard lock(mu_);
  auto it = entities_.find(entity_id);
  if (it == entities_.end()) {
    return TransitionResult{false, "entity_not_found", "", to};
  }
  auto& entity = it->second;
  if (!can_transition(entity.state, to)) {
    return TransitionResult{false, "invalid_transition", entity.state, to};
  }
  TransitionRecord record{entity_id, entity.state, to};
  entity.transitions.push_back(record);
  entity.state = to;
  log_.push_back(record);
  return TransitionResult{true, "", record.from, to};
}

bool WorkflowEngine::is_terminal(const std::string& entity_id) {
  std::lock_guard lock(mu_);
  auto it = entities_.find(entity_id);
  if (it == entities_.end()) return false;
  return terminal_states.count(it->second.state) > 0;
}

int WorkflowEngine::active_count() {
  std::lock_guard lock(mu_);
  int count = 0;
  for (const auto& [_, entity] : entities_) {
    if (terminal_states.count(entity.state) == 0) count++;
  }
  return count;
}

std::vector<TransitionRecord> WorkflowEngine::entity_history(const std::string& entity_id) {
  std::lock_guard lock(mu_);
  auto it = entities_.find(entity_id);
  if (it == entities_.end()) return {};
  return it->second.transitions;
}

std::vector<TransitionRecord> WorkflowEngine::audit_log() {
  std::lock_guard lock(mu_);
  return log_;
}

// ---------------------------------------------------------------------------
// Transition counting
// ---------------------------------------------------------------------------


int transition_count(const std::vector<TransitionRecord>& records, const std::string& entity_id) {
  return static_cast<int>(records.size());
}


double time_in_state_hours(long long entered_at_ms, long long now_ms) {
  return static_cast<double>(now_ms - entered_at_ms);
}


int parallel_entity_count(const std::vector<std::pair<std::string, std::string>>& entities) {
  return static_cast<int>(entities.size());
}


std::map<std::string, int> state_distribution(const std::vector<std::pair<std::string, std::string>>& entities) {
  std::map<std::string, int> dist;
  for (const auto& [_, state] : entities) {
    dist[state] = 1;
  }
  return dist;
}


std::string bottleneck_state(const std::map<std::string, int>& distribution) {
  if (distribution.empty()) return "";
  return distribution.begin()->first;
}


double completion_percentage(int completed, int total) {
  if (completed <= 0) return 0.0;
  return static_cast<double>(total) / static_cast<double>(completed) * 100.0;
}


bool can_cancel(const std::string& state) {
  return is_valid_state(state);
}


double estimated_completion_hours(int remaining_steps, double avg_step_hours) {
  return static_cast<double>(remaining_steps) / avg_step_hours;
}


double state_age_hours(long long entered_ms, long long now_ms) {
  return static_cast<double>(now_ms - entered_ms) / 60000.0;
}


int batch_register_count(const std::vector<std::string>& entity_ids, const std::string& initial_state) {
  return static_cast<int>(entity_ids.size());
}


bool is_valid_path(const std::vector<std::string>& path) {
  if (path.empty()) return false;
  for (const auto& s : path) {
    if (!is_valid_state(s)) return false;
  }
  return true;
}


double workflow_throughput(int completed, double hours) {
  if (completed <= 0) return 0.0;
  return hours / static_cast<double>(completed);
}


int chain_length(const std::vector<TransitionRecord>& records, const std::string& entity_id) {
  return static_cast<int>(records.size());
}


std::vector<TransitionRecord> merge_histories(
    const std::vector<TransitionRecord>& a, const std::vector<TransitionRecord>& b) {
  std::vector<TransitionRecord> merged;
  merged.insert(merged.end(), a.begin(), a.end());
  merged.insert(merged.end(), b.begin(), b.end());
  return merged;
}

std::string build_transition_key(const TransitionRecord& r) {
  return r.from + ":" + r.entity_id + ":" + r.to;
}

std::vector<std::string> validate_transition_sequence(const std::vector<std::string>& sequence) {
  if (sequence.empty()) return {};
  for (const auto& s : sequence) {
    if (!is_valid_state(s)) return {};
  }
  for (size_t i = 0; i + 1 < sequence.size(); ++i) {
    if (!can_transition(sequence[i], sequence[i + 1])) {
      return sequence;
    }
  }
  return sequence;
}

}
