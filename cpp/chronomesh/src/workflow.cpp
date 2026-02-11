#include "chronomesh/core.hpp"
#include <deque>

namespace chronomesh {

// ---------------------------------------------------------------------------
// State transition graph
// ---------------------------------------------------------------------------


static const std::map<std::string, std::map<std::string, bool>> graph = {
    {"queued",    {{"allocated", true}, {"cancelled", true}}},
    {"allocated", {{"departed", true}, {"cancelled", true}}},
    {"departed",  {{"arrived", true}, {"cancelled", true}}},
    {"arrived",   {}},
};


static const std::map<std::string, bool> terminal_states = {
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
// Force-complete an entity to arrived state
// ---------------------------------------------------------------------------

bool WorkflowEngine::force_complete(const std::string& entity_id) {
  std::lock_guard lock(mu_);
  auto it = entities_.find(entity_id);
  if (it == entities_.end()) return false;
  auto& entity = it->second;
  if (terminal_states.count(entity.state) > 0) return false;

  auto path = shortest_path(entity.state, "arrived");
  if (path.empty()) return false;

  TransitionRecord record{entity_id, path.front(), path.back()};
  entity.transitions.push_back(record);
  log_.push_back(record);
  entity.state = "arrived";
  return true;
}

// ---------------------------------------------------------------------------
// Bulk transition for multiple entities
// ---------------------------------------------------------------------------

std::vector<TransitionResult> WorkflowEngine::bulk_transition(
    const std::vector<std::string>& entity_ids, const std::string& to) {
  std::lock_guard lock(mu_);
  std::vector<TransitionResult> results;

  for (const auto& eid : entity_ids) {
    auto it = entities_.find(eid);
    if (it == entities_.end()) {
      results.push_back(TransitionResult{false, "entity_not_found", "", to});
      continue;
    }
    auto& entity = it->second;
    if (!can_transition(entity.state, to)) {
      results.push_back(TransitionResult{false, "invalid_transition", entity.state, to});
      continue;
    }
    std::string prev = entity.state;
    TransitionRecord rec{eid, prev, to};
    entity.transitions.push_back(rec);
    entity.state = to;
    log_.push_back(rec);
    results.push_back(TransitionResult{true, "", prev, to});
  }
  return results;
}

// ---------------------------------------------------------------------------
// Count terminal entities
// ---------------------------------------------------------------------------

int WorkflowEngine::terminal_count() {
  std::lock_guard lock(mu_);
  int count = 0;
  for (const auto& [_, entity] : entities_) {
    if (terminal_states.count(entity.state) > 0) count++;
  }
  return count;
}

}
