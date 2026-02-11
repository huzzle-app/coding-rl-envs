#include "chronomesh/core.hpp"
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using namespace chronomesh;

// ---------------------------------------------------------------------------
// Allocator tests
// ---------------------------------------------------------------------------

static bool allocator_capacity() {
  auto out = plan_dispatch({{"a", 1, "09:30"}, {"b", 3, "10:00"}, {"c", 3, "08:30"}}, 2);
  return out.size() == 2 && out[0].id == "c" && out[1].id == "b";
}

static bool allocator_batch() {
  auto result = dispatch_batch({{"a", 5, "09:00"}, {"b", 2, "10:00"}, {"c", 4, "08:30"}}, 2);
  return result.planned.size() == 2 && result.rejected.size() == 1 && result.rejected[0].id == "b";
}

static bool allocator_berth_conflict() {
  std::vector<BerthSlot> slots = {{"B1", 8, 12, true}, {"B2", 14, 18, false}};
  return has_conflict(slots, 10, 14) && !has_conflict(slots, 12, 14);
}

static bool allocator_available_slots() {
  std::vector<BerthSlot> slots = {{"B1", 8, 12, true}, {"B2", 14, 20, false}, {"B3", 22, 24, false}};
  auto avail = find_available_slots(slots, 4);
  return avail.size() == 1 && avail[0].berth_id == "B2";
}

static bool allocator_cost_estimation() {
  double cost = estimate_cost(100.0, 2.5, 50.0);
  return std::abs(cost - 300.0) < 0.01;
}

static bool allocator_cost_allocation() {
  auto costs = allocate_costs(100.0, {1.0, 3.0});
  return costs.size() == 2 && std::abs(costs[0] - 25.0) < 0.01 && std::abs(costs[1] - 75.0) < 0.01;
}

static bool allocator_turnaround() {
  double hours = estimate_turnaround(1000.0, 100.0);
  return std::abs(hours - 10.5) < 0.01;
}

static bool allocator_validation() {
  auto err1 = validate_order(Order{"", 1, "09:00"});
  auto err2 = validate_order(Order{"a", 1, "09:00"});
  return !err1.empty() && err2.empty();
}

// ---------------------------------------------------------------------------
// Routing tests
// ---------------------------------------------------------------------------

static bool routing_blocked() {
  auto route = choose_route({{"alpha", 8}, {"beta", 3}}, {"beta"});
  return route.channel == "alpha";
}

static bool routing_channel_score() {
  double score = channel_score(10, 0.5, 3);
  return score > 0;
}

static bool routing_transit_time() {
  double hours = estimate_transit_time(185.2, 10.0);
  return std::abs(hours - 10.0) < 0.01;
}

static bool routing_multi_leg() {
  auto plan = plan_multi_leg({{"a", 5}, {"b", 3}, {"c", 8}}, {"c"});
  return plan.legs.size() == 2 && plan.total_delay == 8 && plan.legs[0].channel == "b";
}

static bool routing_table() {
  RouteTable rt;
  rt.add(Route{"alpha", 5});
  rt.add(Route{"beta", 3});
  auto all = rt.all();
  return rt.count() == 2 && all[0].channel == "alpha" && rt.get("beta") != nullptr;
}

static bool routing_cost() {
  double cost = estimate_route_cost(10, 2.0, 100.0);
  return std::abs(cost - 205.0) < 0.01;
}

// ---------------------------------------------------------------------------
// Policy tests
// ---------------------------------------------------------------------------

static bool policy_escalation() { return next_policy("watch", 3) == "restricted"; }

static bool policy_deescalation() {
  return previous_policy("restricted") == "watch" && previous_policy("normal") == "normal";
}

static bool policy_engine_lifecycle() {
  PolicyEngine pe("normal");
  pe.escalate(5, "high failure rate");
  pe.escalate(5, "continued failures");
  auto cur = pe.current();
  auto hist = pe.history();
  pe.deescalate("recovery");
  return cur == "restricted" && hist.size() == 2 && pe.current() == "watch";
}

static bool policy_sla() {
  return check_sla_compliance(25, 30) && !check_sla_compliance(35, 30);
}

static bool policy_sla_percentage() {
  double pct = sla_percentage(90, 100);
  return std::abs(pct - 90.0) < 0.01;
}

static bool policy_metadata() {
  auto meta = get_policy_metadata("watch");
  return meta.max_retries == 3 && meta.description == "elevated monitoring";
}

// ---------------------------------------------------------------------------
// Queue tests
// ---------------------------------------------------------------------------

static bool queue_hard_limit() {
  return !should_shed(9, 10, false) && should_shed(11, 10, false) && should_shed(8, 10, true);
}

static bool queue_priority() {
  PriorityQueue pq;
  pq.enqueue(QueueItem{"a", 1});
  pq.enqueue(QueueItem{"b", 5});
  pq.enqueue(QueueItem{"c", 3});
  auto top = pq.dequeue();
  return top != nullptr && top->id == "b" && pq.size() == 2;
}

static bool queue_drain() {
  PriorityQueue pq;
  pq.enqueue(QueueItem{"a", 1});
  pq.enqueue(QueueItem{"b", 2});
  pq.enqueue(QueueItem{"c", 3});
  auto items = pq.drain(2);
  return items.size() == 2 && pq.size() == 1;
}

static bool queue_health_check() {
  auto h1 = queue_health(50, 100);
  auto h2 = queue_health(85, 100);
  auto h3 = queue_health(110, 100);
  return h1.status == "healthy" && h2.status == "warning" && h3.status == "critical";
}

static bool queue_wait_estimation() {
  double wait = estimate_wait_time(100, 10.0);
  return std::abs(wait - 10.0) < 0.01;
}

// ---------------------------------------------------------------------------
// Security tests
// ---------------------------------------------------------------------------

static bool security_signature() {
  auto sig = digest("manifest:v1");
  return verify_signature("manifest:v1", sig, sig) && !verify_signature("manifest:v1", sig.substr(0, sig.size() - 1), sig);
}

static bool security_manifest() {
  auto sig = sign_manifest("payload:test", "secret123");
  return verify_manifest("payload:test", sig, "secret123") && !verify_manifest("payload:test", sig, "wrong_secret");
}

static bool security_path_sanitise() {
  return sanitise_path("/a/b/c") == "/a/b/c" && sanitise_path("/../etc/passwd").empty();
}

static bool security_origin() {
  return is_allowed_origin("EXAMPLE.COM", {"example.com"}) && !is_allowed_origin("evil.com", {"example.com"});
}

// ---------------------------------------------------------------------------
// Resilience tests
// ---------------------------------------------------------------------------

static bool replay_latest() {
  auto out = replay({{"x", 1}, {"x", 2}, {"y", 1}});
  return out.size() == 2 && out.back().id == "x" && out.back().sequence == 2;
}

static bool replay_convergence() {
  auto a = replay({{"k", 1}, {"k", 2}});
  auto b = replay({{"k", 2}, {"k", 1}});
  return a == b;
}

static bool resilience_checkpoint() {
  CheckpointManager cm;
  cm.record("stream-a", 100);
  cm.record("stream-b", 200);
  return cm.get_checkpoint("stream-a") == 100 && cm.last_sequence() == 200;
}

static bool resilience_circuit_breaker() {
  CircuitBreaker cb(3, 60000);
  cb.record_failure();
  cb.record_failure();
  cb.record_failure();
  return cb.state() == CB_OPEN;
}

static bool resilience_dedup() {
  auto deduped = deduplicate({{"a", 1}, {"a", 1}, {"b", 2}});
  return deduped.size() == 2;
}

// ---------------------------------------------------------------------------
// Statistics tests
// ---------------------------------------------------------------------------

static bool percentile_sparse() { return percentile({4, 1, 9, 7}, 50) == 4 && percentile({}, 90) == 0; }

static bool stats_descriptive() {
  auto avg = mean({2.0, 4.0, 6.0});
  auto med = median({1.0, 3.0, 5.0, 7.0});
  return std::abs(avg - 4.0) < 0.01 && std::abs(med - 4.0) < 0.01;
}

static bool stats_variance() {
  auto var = variance({2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0});
  return var > 0;
}

static bool stats_response_tracker() {
  ResponseTimeTracker rt(100);
  rt.record(10.0);
  rt.record(20.0);
  rt.record(30.0);
  return rt.count() == 3 && rt.average() > 0;
}

static bool stats_moving_average() {
  auto ma = moving_average({1.0, 2.0, 3.0, 4.0, 5.0}, 3);
  return ma.size() == 5 && std::abs(ma[2] - 2.0) < 0.01;
}

static bool stats_heatmap() {
  auto [cells, hotspots] = generate_heatmap({{15.0, 25.0}, {15.0, 25.0}, {35.0, 45.0}}, 10);
  return cells.size() == 2 && !hotspots.empty();
}

// ---------------------------------------------------------------------------
// Workflow tests
// ---------------------------------------------------------------------------

static bool workflow_graph() { return can_transition("queued", "allocated") && !can_transition("queued", "arrived"); }

static bool workflow_shortest_path() {
  auto path = shortest_path("queued", "arrived");
  return path.size() == 4 && path[0] == "queued" && path.back() == "arrived";
}

static bool workflow_engine() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  auto r1 = we.transition("v1", "allocated");
  auto r2 = we.transition("v1", "departed");
  return r1.success && r2.success && we.get_state("v1") == "departed";
}

static bool workflow_terminal() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.transition("v1", "cancelled");
  return we.is_terminal("v1") && we.active_count() == 0;
}

static bool workflow_audit() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.transition("v1", "allocated");
  auto log = we.audit_log();
  return log.size() == 1 && log[0].from == "queued" && log[0].to == "allocated";
}

// ---------------------------------------------------------------------------
// Model tests
// ---------------------------------------------------------------------------

static bool model_urgency() {
  DispatchModel model{3, 30};
  return model.urgency_score() == 120;
}

static bool model_vessel_manifest() {
  VesselManifest vm{"V1", "TestShip", 5000.0, 200, true};
  return vm.requires_hazmat_clearance();
}

static bool model_batch_creation() {
  auto batch = create_batch_orders(5, 2, 30);
  return batch.size() == 5 && batch[0].severity == 2;
}

static bool model_validation() {
  auto err1 = validate_dispatch_order(DispatchModel{0, 30});
  auto err2 = validate_dispatch_order(DispatchModel{3, 30});
  return !err1.empty() && err2.empty();
}

static bool model_classify_severity() {
  return classify_severity("CRITICAL alert") == SEVERITY_CRITICAL && classify_severity("minor issue") == SEVERITY_LOW;
}

// ---------------------------------------------------------------------------
// Contract tests
// ---------------------------------------------------------------------------

static bool contracts_exposed() {
  return CONTRACTS.at("gateway") == 8140 && CONTRACTS.at("routing") > 0;
}

static bool contracts_service_defs() {
  auto it = SERVICE_DEFS.find("gateway");
  return it != SERVICE_DEFS.end() && it->second.port == 8140;
}

static bool contracts_url() {
  auto url = get_service_url("routing", "dispatch.local");
  return url == "http://dispatch.local:8141";
}

static bool contracts_validation() {
  auto r1 = validate_contract("gateway");
  auto r2 = validate_contract("nonexistent");
  return r1.valid && !r2.valid;
}

static bool contracts_topo_order() {
  auto order = topological_order();
  return !order.empty() && order.size() == SERVICE_DEFS.size();
}

// ---------------------------------------------------------------------------
// Integration tests
// ---------------------------------------------------------------------------

static bool flow_integration() {
  auto out = plan_dispatch({{"z", 5, "10:00"}}, 1);
  auto route = choose_route({{"north", 4}}, {});
  return out.size() == 1 && route.channel == "north" && can_transition("queued", "allocated");
}

static bool end_to_end_dispatch() {
  auto batch = dispatch_batch({{"a", 5, "08:00"}, {"b", 3, "09:00"}, {"c", 4, "08:30"}}, 2);
  auto route = choose_route({{"alpha", 5}, {"beta", 2}}, {});

  WorkflowEngine we;
  for (const auto& o : batch.planned) {
    we.register_entity(o.id, "queued");
    we.transition(o.id, "allocated");
  }

  auto sig = digest("manifest:" + batch.planned[0].id);
  return batch.planned.size() == 2 && route.channel == "beta"
      && we.get_state(batch.planned[0].id) == "allocated"
      && verify_signature("manifest:" + batch.planned[0].id, sig, sig);
}

// ---------------------------------------------------------------------------
// Latent bug tests (Category 1)
// ---------------------------------------------------------------------------

static bool allocator_berth_utilization() {
  std::vector<BerthSlot> slots = {
    {"B1", 8, 12, true},   // 4h occupied
    {"B2", 14, 22, false},  // 8h free
    {"B3", 0, 6, true}      // 6h occupied
  };
  // occupied = 4+6=10, total_hours = 4+8+6=18, utilization = 10/18 ≈ 0.5556
  double util = calculate_berth_utilization(slots);
  return std::abs(util - 10.0 / 18.0) < 0.001;
}

static bool allocator_berth_utilization_uniform() {
  std::vector<BerthSlot> slots = {
    {"B1", 0, 10, true},
    {"B2", 0, 10, false},
    {"B3", 0, 10, true}
  };
  // 20 occupied out of 30 total = 0.6667
  double util = calculate_berth_utilization(slots);
  return std::abs(util - 20.0 / 30.0) < 0.001;
}

static bool allocator_merge_queues() {
  std::vector<Order> primary = {{"a", 3, "08:00"}, {"b", 2, "09:00"}, {"c", 1, "10:00"}};
  std::vector<Order> overflow = {{"d", 9, "11:00"}, {"e", 7, "12:00"}};
  auto merged = merge_dispatch_queues(primary, overflow, 3);
  // Should sort by urgency descending first: d(9), e(7), a(3), b(2), c(1), then take top 3
  return merged.size() == 3 && merged[0].id == "d" && merged[0].urgency == 9;
}

static bool allocator_merge_dedup() {
  std::vector<Order> primary = {{"a", 5, "08:00"}};
  std::vector<Order> overflow = {{"a", 3, "09:00"}, {"b", 7, "10:00"}};
  auto merged = merge_dispatch_queues(primary, overflow, 10);
  // "a" is in primary, should not be duplicated from overflow
  return merged.size() == 2;
}

// ---------------------------------------------------------------------------
// Domain logic bug tests (Category 2)
// ---------------------------------------------------------------------------

static bool routing_hazmat_restricted() {
  // Hazmat cargo should NOT be allowed through restricted channels
  bool allowed = is_hazmat_route_allowed("narrow_strait", true, {"narrow_strait", "shallow_bay"});
  return !allowed;
}

static bool routing_hazmat_unrestricted() {
  // Hazmat through unrestricted channel should be allowed
  bool allowed = is_hazmat_route_allowed("deep_channel", true, {"narrow_strait"});
  return allowed;
}

static bool routing_hazmat_no_cargo() {
  // Non-hazmat cargo always allowed regardless of restrictions
  bool allowed = is_hazmat_route_allowed("narrow_strait", false, {"narrow_strait"});
  return allowed;
}

static bool routing_hazmat_zone_match() {
  // "north_strait" is a distinct channel from "north" — only exact name match should restrict
  bool allowed = is_hazmat_route_allowed("north_strait", true, {"north"});
  return allowed;
}

static bool routing_risk_compound() {
  // Two legs with latency 5 and 3, base risk 1.0
  // Compound risk: 1.0 * (1 + 0.5) * (1 + 0.3) = 1.95
  double risk = calculate_route_risk({{"a", 5}, {"b", 3}}, 1.0);
  return std::abs(risk - 1.95) < 0.01;
}

static bool routing_risk_single() {
  // Single leg, latency 10, base 2.0
  // Risk: 2.0 * (1 + 1.0) = 4.0
  double risk = calculate_route_risk({{"a", 10}}, 2.0);
  return std::abs(risk - 4.0) < 0.01;
}

static bool policy_breach_penalty_critical() {
  // CRITICAL severity (5) should have highest penalty weight
  // Weight 5 * 10 minutes over SLA = 50
  int penalty = calculate_breach_penalty(SEVERITY_CRITICAL, 10);
  return penalty == 50;
}

static bool policy_breach_penalty_info() {
  // INFO severity (1) should have lowest penalty weight
  // Weight 1 * 10 minutes over SLA = 10
  int penalty = calculate_breach_penalty(SEVERITY_INFO, 10);
  return penalty == 10;
}

static bool policy_breach_penalty_ordering() {
  // CRITICAL penalty must be strictly greater than LOW penalty for same overage
  int critical_pen = calculate_breach_penalty(SEVERITY_CRITICAL, 5);
  int low_pen = calculate_breach_penalty(SEVERITY_LOW, 5);
  return critical_pen > low_pen;
}

static bool policy_auto_escalate_at_threshold() {
  // CRITICAL threshold is 1 breach; from "watch" level, 1 breach should still trigger
  return should_auto_escalate("watch", 1, SEVERITY_CRITICAL);
}

static bool policy_auto_escalate_below() {
  // LOW threshold is 5, so 3 breaches should not trigger
  return !should_auto_escalate("normal", 3, SEVERITY_LOW);
}

static bool policy_auto_escalate_halted() {
  // Already halted, should never escalate further
  return !should_auto_escalate("halted", 100, SEVERITY_CRITICAL);
}

// ---------------------------------------------------------------------------
// Multi-step bug tests (Category 3)
// ---------------------------------------------------------------------------

static bool stats_weighted_percentile_unnormalized() {
  // Values [3.0, 1.0, 2.0] unsorted, weights [2.0, 3.0, 5.0]
  // After sorting values with paired weights: (1.0, 3.0), (2.0, 5.0), (3.0, 2.0)
  // Normalized: [0.3, 0.5, 0.2], cumulative: [0.3, 0.8, 1.0]
  // 30th percentile: first cumulative >= 0.3 at value 1.0
  double wp = weighted_percentile({3.0, 1.0, 2.0}, {2.0, 3.0, 5.0}, 30);
  return std::abs(wp - 1.0) < 0.01;
}

static bool stats_weighted_percentile_boundary() {
  // Pre-normalized weights summing to 1.0
  // 50th percentile: cumulative [0.2, 0.5, 1.0], target 0.5
  // Cumulative reaches exactly 0.5 at value 2.0, so result should be 2.0
  double wp = weighted_percentile({1.0, 2.0, 3.0}, {0.2, 0.3, 0.5}, 50);
  return std::abs(wp - 2.0) < 0.01;
}

static bool stats_weighted_percentile_low() {
  // 10th percentile: with weights [0.2, 0.3, 0.5], cumulative 0.2 >= 0.1, so value 1.0
  double wp = weighted_percentile({1.0, 2.0, 3.0}, {0.2, 0.3, 0.5}, 10);
  return std::abs(wp - 1.0) < 0.01;
}

// ---------------------------------------------------------------------------
// State machine bug tests (Category 4)
// ---------------------------------------------------------------------------

static bool policy_try_recovery_from_halted() {
  PolicyEngine pe("normal");
  pe.escalate(5, "r1");
  pe.escalate(5, "r2");
  pe.escalate(5, "r3");
  // Should be halted now
  pe.try_recovery();
  // Recovery should step down one level: halted → restricted
  return pe.current() == "restricted";
}

static bool policy_try_recovery_from_watch() {
  PolicyEngine pe("normal");
  pe.escalate(3, "r1");
  // Should be at watch
  pe.try_recovery();
  // Recovery should step to normal
  return pe.current() == "normal";
}

static bool policy_escalation_depth_normal() {
  PolicyEngine pe("normal");
  return pe.escalation_depth() == 0;
}

static bool policy_escalation_depth_halted() {
  PolicyEngine pe("normal");
  pe.escalate(5, "r1");
  pe.escalate(5, "r2");
  pe.escalate(5, "r3");
  return pe.escalation_depth() == 3;
}

static bool workflow_force_complete_transitions() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.force_complete("v1");
  // Path: queued → allocated → departed → arrived (3 transitions)
  auto hist = we.entity_history("v1");
  return we.get_state("v1") == "arrived" && hist.size() == 3;
}

static bool workflow_force_complete_from_departed() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.transition("v1", "allocated");
  we.transition("v1", "departed");
  we.force_complete("v1");
  // 2 manual transitions + 1 force transition = 3 total
  auto hist = we.entity_history("v1");
  return we.get_state("v1") == "arrived" && hist.size() == 3;
}

static bool workflow_force_complete_terminal() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.transition("v1", "cancelled");
  // Can't force_complete a cancelled entity
  return !we.force_complete("v1");
}

// ---------------------------------------------------------------------------
// Concurrency bug tests (Category 5 & 6)
// ---------------------------------------------------------------------------

static bool allocator_submit_batch_atomic() {
  RollingWindowScheduler rws(3);
  rws.submit(Order{"existing", 1, "00:00"});
  // Window has 1 item, capacity 3. Batch of 3 needs 3 slots but only 2 available.
  // Atomic batch should reject all (all-or-nothing)
  int accepted = rws.submit_batch({
    Order{"a", 5, "01:00"},
    Order{"b", 3, "02:00"},
    Order{"c", 2, "03:00"}
  });
  // If atomic: 0 accepted, count still 1
  // If non-atomic: 2 accepted, count is 3
  return accepted == 0 && rws.count() == 1;
}

static bool allocator_submit_batch_fits() {
  RollingWindowScheduler rws(5);
  int accepted = rws.submit_batch({
    Order{"a", 5, "01:00"},
    Order{"b", 3, "02:00"}
  });
  // Batch fits entirely, should accept all
  return accepted == 2 && rws.count() == 2;
}

static bool resilience_cb_attempt_open() {
  CircuitBreaker cb(3, 60000);
  cb.record_failure();
  cb.record_failure();
  cb.record_failure();
  // Circuit is open
  int call_count = 0;
  bool result = cb.attempt([&]() { call_count++; return true; });
  // Should not execute operation when circuit is open
  return !result && call_count == 0;
}

static bool resilience_cb_attempt_closed() {
  CircuitBreaker cb(3, 60000);
  int call_count = 0;
  bool result = cb.attempt([&]() { call_count++; return true; });
  // Should execute normally when closed
  return result && call_count == 1;
}

static bool workflow_bulk_transition_rollback() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.register_entity("v2", "arrived");  // terminal-like, no outgoing transitions
  we.register_entity("v3", "queued");

  auto results = we.bulk_transition({"v1", "v2", "v3"}, "allocated");
  // v2 can't transition (arrived has no transitions to allocated)
  // Batch should be atomic: if any fail, all should rollback
  // v1 should still be "queued" if atomic
  bool any_failed = false;
  for (const auto& r : results) {
    if (!r.success) any_failed = true;
  }
  return any_failed && we.get_state("v1") == "queued" && we.get_state("v3") == "queued";
}

static bool workflow_bulk_transition_all_valid() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.register_entity("v2", "queued");
  auto results = we.bulk_transition({"v1", "v2"}, "allocated");
  return results.size() == 2 && results[0].success && results[1].success
      && we.get_state("v1") == "allocated" && we.get_state("v2") == "allocated";
}

static bool stats_tracker_merge_window() {
  ResponseTimeTracker rt(5);
  rt.record(1.0);
  rt.record(2.0);
  rt.record(3.0);
  // Merge 4 more samples. Window is 5, so after merge should trim to 5.
  rt.merge({4.0, 5.0, 6.0, 7.0});
  return rt.count() == 5;
}

static bool workflow_terminal_count() {
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.register_entity("v2", "queued");
  we.register_entity("v3", "queued");
  we.transition("v1", "cancelled");
  we.transition("v2", "cancelled");
  return we.terminal_count() == 2 && we.active_count() == 1;
}

// ---------------------------------------------------------------------------
// Integration bug tests (Category 7)
// ---------------------------------------------------------------------------

static bool security_token_chain_valid() {
  // Each token signed and verified individually, chain should be valid
  bool valid = validate_token_chain({"alpha", "beta", "gamma"}, "secret_key");
  return valid;
}

static bool security_token_chain_single() {
  // Single token chain is always valid
  return validate_token_chain({"single"}, "key");
}

static bool security_token_chain_empty() {
  return validate_token_chain({}, "key");
}

static bool contracts_manifest_chain_valid() {
  bool valid = validate_manifest_chain({"order:1", "order:2", "order:3"}, "signing_key");
  return valid;
}

static bool contracts_manifest_chain_single() {
  return validate_manifest_chain({"single_manifest"}, "key");
}

static bool contracts_dependency_depth_leaf() {
  // "policy" has no dependencies, depth should be 0
  return dependency_depth("policy") == 0;
}

static bool contracts_dependency_depth_chain() {
  // "gateway" depends on "routing" which depends on "policy"
  // Depth: gateway → routing → policy = depth 2
  return dependency_depth("gateway") == 2;
}

static bool contracts_dependency_depth_unknown() {
  return dependency_depth("nonexistent") == 0;
}

static bool model_port_fees_hazmat() {
  VesselManifest vm{"V1", "HazShip", 100.0, 150, true};
  double fee = estimate_port_fees(vm, 1.0);
  // base: 1.0 * 100 = 100, hazmat: +0.5, containers > 100: +150*0.1=15, total: 115.5
  return std::abs(fee - 115.5) < 0.01;
}

static bool model_port_fees_normal() {
  VesselManifest vm{"V2", "NormShip", 200.0, 150, false};
  double fee = estimate_port_fees(vm, 2.0);
  // base: 2.0 * 200 = 400, containers > 100: +150*0.1 = 15, total: 415
  return std::abs(fee - 415.0) < 0.01;
}

static bool resilience_replay_gap_exists() {
  // Events: a has sequences 1, 3 (gap at 2), b has sequence 1
  int gap = find_replay_gap({{"a", 1}, {"a", 3}, {"b", 1}});
  return gap == 2;
}

static bool resilience_replay_no_gap() {
  int gap = find_replay_gap({{"a", 1}, {"a", 2}, {"a", 3}});
  return gap == -1;
}

static bool stats_ema_increasing() {
  double ema = exponential_moving_average_single({10.0, 20.0, 30.0}, 0.3);
  // Correct: 10, 0.3*20+0.7*10=13, 0.3*30+0.7*13=18.1
  return std::abs(ema - 18.1) < 0.01;
}

static bool stats_ema_constant() {
  double ema = exponential_moving_average_single({5.0, 5.0, 5.0, 5.0}, 0.5);
  // Constant input → EMA should equal the constant
  return std::abs(ema - 5.0) < 0.01;
}

// ---------------------------------------------------------------------------
// Hyper-matrix parametric test
// ---------------------------------------------------------------------------

static bool run_hyper_case(int idx) {
  const int severity_a = (idx % 7) + 1;
  const int severity_b = ((idx * 3) % 7) + 1;
  const int sla_a = 20 + (idx % 90);
  const int sla_b = 20 + ((idx * 2) % 90);

  DispatchModel model_a{severity_a, sla_a};
  DispatchModel model_b{severity_b, sla_b};

  auto planned = plan_dispatch(
      {
          {"a-" + std::to_string(idx), model_a.urgency_score(), "01:00"},
          {"b-" + std::to_string(idx), model_b.urgency_score(), "02:00"},
          {"c-" + std::to_string(idx), (idx % 50) + 2, "03:00"},
      },
      2);

  if (planned.empty() || planned.size() > 2) return false;
  if (planned.size() == 2 && planned[0].urgency < planned[1].urgency) return false;

  std::vector<std::string> blocked;
  if (idx % 5 == 0) blocked.push_back("beta");

  auto route = choose_route(
      {
          {"alpha", 2 + (idx % 9)},
          {"beta", idx % 3},
          {"gamma", 4 + (idx % 4)},
      },
      blocked);
  if (route.channel.empty()) return false;
  if (idx % 5 == 0 && route.channel == "beta") return false;

  const std::string src = idx % 2 == 0 ? "queued" : "allocated";
  const std::string dst = src == "queued" ? "allocated" : "departed";
  if (!can_transition(src, dst) || can_transition("arrived", "queued")) return false;

  const auto pol = next_policy(idx % 2 == 0 ? "normal" : "watch", 2 + (idx % 2));
  if (pol != "watch" && pol != "restricted" && pol != "halted") return false;

  const int depth = (idx % 30) + 1;
  if (should_shed(depth, 40, false) || !should_shed(41, 40, false)) return false;

  auto replayed = replay(
      {
          {"k-" + std::to_string(idx % 17), 1},
          {"k-" + std::to_string(idx % 17), 2},
          {"z-" + std::to_string(idx % 13), 1},
      });
  if (replayed.size() < 2) return false;

  const int p50 = percentile({idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11}, 50);
  if (p50 < 0) return false;

  if (idx % 17 == 0) {
    const std::string payload = "manifest:" + std::to_string(idx);
    const auto sig = digest(payload);
    if (!verify_signature(payload, sig, sig)) return false;
    if (verify_signature(payload, sig.substr(1), sig)) return false;
  }

  // Extended checks for richer code paths
  if (idx % 23 == 0) {
    auto batch = dispatch_batch(planned, 1);
    if (batch.planned.size() != 1) return false;
  }

  if (idx % 31 == 0) {
    auto multi = plan_multi_leg(
        {{"ch-a", 3 + (idx % 5)}, {"ch-b", 1 + (idx % 3)}, {"ch-c", 7}},
        blocked);
    if (multi.legs.empty()) return false;
  }

  if (idx % 41 == 0) {
    double score = channel_score(route.latency, 0.8, 5);
    if (score < 0) return false;
  }

  if (idx % 53 == 0) {
    auto health = queue_health(depth, 40);
    if (health.status.empty()) return false;
  }

  if (idx % 61 == 0) {
    auto sig2 = sign_manifest("order:" + std::to_string(idx), "key");
    if (!verify_manifest("order:" + std::to_string(idx), sig2, "key")) return false;
  }

  if (idx % 71 == 0) {
    auto deduped = deduplicate(replayed);
    if (deduped.size() > replayed.size()) return false;
  }

  if (idx % 83 == 0) {
    auto avg = mean({static_cast<double>(severity_a), static_cast<double>(severity_b)});
    if (avg <= 0) return false;
  }

  if (idx % 97 == 0) {
    auto path = shortest_path("queued", "arrived");
    if (path.empty()) return false;
  }

  if (idx % 7 == 0) {
    if (is_hazmat_route_allowed(route.channel, true, {route.channel})) return false;
  }

  if (idx % 11 == 0) {
    int crit_pen = calculate_breach_penalty(SEVERITY_CRITICAL, idx % 20 + 1);
    int info_pen = calculate_breach_penalty(SEVERITY_INFO, idx % 20 + 1);
    if (crit_pen <= info_pen) return false;
  }

  if (idx % 29 == 0) {
    double risk = calculate_route_risk({{"a", 5}, {"b", 3}}, 1.0);
    if (risk < 1.9) return false;
  }

  if (idx % 37 == 0) {
    double wp = weighted_percentile({3.0, 1.0, 2.0}, {0.2, 0.5, 0.3}, 50);
    if (std::abs(wp - 1.0) > 0.01) return false;
  }

  if (idx % 43 == 0) {
    double ema = exponential_moving_average_single({10.0, 20.0, 30.0}, 0.3);
    if (std::abs(ema - 18.1) > 1.0) return false;
  }

  if (idx % 47 == 0) {
    VesselManifest vm{"V1", "Test", 100.0, 150, true};
    double fee = estimate_port_fees(vm, 1.0);
    if (fee < 115.0) return false;
  }

  return true;
}

static bool hyper_matrix() {
  constexpr int total = 9200;
  int passed = 0;
  int failed = 0;
  for (int i = 0; i < total; ++i) {
    if (run_hyper_case(i)) ++passed;
    else ++failed;
  }
  std::cout << "TB_SUMMARY total=" << total << " passed=" << passed << " failed=" << failed << std::endl;
  return failed == 0;
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "expected one test case name" << std::endl;
    return 2;
  }

  const std::string name = argv[1];
  bool ok = false;

  // Allocator tests
  if (name == "allocator_capacity") ok = allocator_capacity();
  else if (name == "allocator_batch") ok = allocator_batch();
  else if (name == "allocator_berth_conflict") ok = allocator_berth_conflict();
  else if (name == "allocator_available_slots") ok = allocator_available_slots();
  else if (name == "allocator_cost_estimation") ok = allocator_cost_estimation();
  else if (name == "allocator_cost_allocation") ok = allocator_cost_allocation();
  else if (name == "allocator_turnaround") ok = allocator_turnaround();
  else if (name == "allocator_validation") ok = allocator_validation();
  // Routing tests
  else if (name == "routing_blocked") ok = routing_blocked();
  else if (name == "routing_channel_score") ok = routing_channel_score();
  else if (name == "routing_transit_time") ok = routing_transit_time();
  else if (name == "routing_multi_leg") ok = routing_multi_leg();
  else if (name == "routing_table") ok = routing_table();
  else if (name == "routing_cost") ok = routing_cost();
  // Policy tests
  else if (name == "policy_escalation") ok = policy_escalation();
  else if (name == "policy_deescalation") ok = policy_deescalation();
  else if (name == "policy_engine_lifecycle") ok = policy_engine_lifecycle();
  else if (name == "policy_sla") ok = policy_sla();
  else if (name == "policy_sla_percentage") ok = policy_sla_percentage();
  else if (name == "policy_metadata") ok = policy_metadata();
  // Queue tests
  else if (name == "queue_hard_limit") ok = queue_hard_limit();
  else if (name == "queue_priority") ok = queue_priority();
  else if (name == "queue_drain") ok = queue_drain();
  else if (name == "queue_health_check") ok = queue_health_check();
  else if (name == "queue_wait_estimation") ok = queue_wait_estimation();
  // Security tests
  else if (name == "security_signature") ok = security_signature();
  else if (name == "security_manifest") ok = security_manifest();
  else if (name == "security_path_sanitise") ok = security_path_sanitise();
  else if (name == "security_origin") ok = security_origin();
  // Resilience tests
  else if (name == "replay_latest") ok = replay_latest();
  else if (name == "replay_convergence") ok = replay_convergence();
  else if (name == "resilience_checkpoint") ok = resilience_checkpoint();
  else if (name == "resilience_circuit_breaker") ok = resilience_circuit_breaker();
  else if (name == "resilience_dedup") ok = resilience_dedup();
  // Statistics tests
  else if (name == "percentile_sparse") ok = percentile_sparse();
  else if (name == "stats_descriptive") ok = stats_descriptive();
  else if (name == "stats_variance") ok = stats_variance();
  else if (name == "stats_response_tracker") ok = stats_response_tracker();
  else if (name == "stats_moving_average") ok = stats_moving_average();
  else if (name == "stats_heatmap") ok = stats_heatmap();
  // Workflow tests
  else if (name == "workflow_graph") ok = workflow_graph();
  else if (name == "workflow_shortest_path") ok = workflow_shortest_path();
  else if (name == "workflow_engine") ok = workflow_engine();
  else if (name == "workflow_terminal") ok = workflow_terminal();
  else if (name == "workflow_audit") ok = workflow_audit();
  // Model tests
  else if (name == "model_urgency") ok = model_urgency();
  else if (name == "model_vessel_manifest") ok = model_vessel_manifest();
  else if (name == "model_batch_creation") ok = model_batch_creation();
  else if (name == "model_validation") ok = model_validation();
  else if (name == "model_classify_severity") ok = model_classify_severity();
  // Contract tests
  else if (name == "contracts_exposed") ok = contracts_exposed();
  else if (name == "contracts_service_defs") ok = contracts_service_defs();
  else if (name == "contracts_url") ok = contracts_url();
  else if (name == "contracts_validation") ok = contracts_validation();
  else if (name == "contracts_topo_order") ok = contracts_topo_order();
  // Integration tests
  else if (name == "flow_integration") ok = flow_integration();
  else if (name == "end_to_end_dispatch") ok = end_to_end_dispatch();
  // Latent bug tests
  else if (name == "allocator_berth_utilization") ok = allocator_berth_utilization();
  else if (name == "allocator_berth_utilization_uniform") ok = allocator_berth_utilization_uniform();
  else if (name == "allocator_merge_queues") ok = allocator_merge_queues();
  else if (name == "allocator_merge_dedup") ok = allocator_merge_dedup();
  // Domain logic tests
  else if (name == "routing_hazmat_restricted") ok = routing_hazmat_restricted();
  else if (name == "routing_hazmat_unrestricted") ok = routing_hazmat_unrestricted();
  else if (name == "routing_hazmat_no_cargo") ok = routing_hazmat_no_cargo();
  else if (name == "routing_hazmat_zone_match") ok = routing_hazmat_zone_match();
  else if (name == "routing_risk_compound") ok = routing_risk_compound();
  else if (name == "routing_risk_single") ok = routing_risk_single();
  else if (name == "policy_breach_penalty_critical") ok = policy_breach_penalty_critical();
  else if (name == "policy_breach_penalty_info") ok = policy_breach_penalty_info();
  else if (name == "policy_breach_penalty_ordering") ok = policy_breach_penalty_ordering();
  else if (name == "policy_auto_escalate_at_threshold") ok = policy_auto_escalate_at_threshold();
  else if (name == "policy_auto_escalate_below") ok = policy_auto_escalate_below();
  else if (name == "policy_auto_escalate_halted") ok = policy_auto_escalate_halted();
  // Multi-step tests
  else if (name == "stats_weighted_percentile_unnormalized") ok = stats_weighted_percentile_unnormalized();
  else if (name == "stats_weighted_percentile_boundary") ok = stats_weighted_percentile_boundary();
  else if (name == "stats_weighted_percentile_low") ok = stats_weighted_percentile_low();
  // State machine tests
  else if (name == "policy_try_recovery_from_halted") ok = policy_try_recovery_from_halted();
  else if (name == "policy_try_recovery_from_watch") ok = policy_try_recovery_from_watch();
  else if (name == "policy_escalation_depth_normal") ok = policy_escalation_depth_normal();
  else if (name == "policy_escalation_depth_halted") ok = policy_escalation_depth_halted();
  else if (name == "workflow_force_complete_transitions") ok = workflow_force_complete_transitions();
  else if (name == "workflow_force_complete_from_departed") ok = workflow_force_complete_from_departed();
  else if (name == "workflow_force_complete_terminal") ok = workflow_force_complete_terminal();
  // Concurrency tests
  else if (name == "allocator_submit_batch_atomic") ok = allocator_submit_batch_atomic();
  else if (name == "allocator_submit_batch_fits") ok = allocator_submit_batch_fits();
  else if (name == "resilience_cb_attempt_open") ok = resilience_cb_attempt_open();
  else if (name == "resilience_cb_attempt_closed") ok = resilience_cb_attempt_closed();
  else if (name == "workflow_bulk_transition_rollback") ok = workflow_bulk_transition_rollback();
  else if (name == "workflow_bulk_transition_all_valid") ok = workflow_bulk_transition_all_valid();
  else if (name == "stats_tracker_merge_window") ok = stats_tracker_merge_window();
  else if (name == "workflow_terminal_count") ok = workflow_terminal_count();
  // Integration tests (extended)
  else if (name == "security_token_chain_valid") ok = security_token_chain_valid();
  else if (name == "security_token_chain_single") ok = security_token_chain_single();
  else if (name == "security_token_chain_empty") ok = security_token_chain_empty();
  else if (name == "contracts_manifest_chain_valid") ok = contracts_manifest_chain_valid();
  else if (name == "contracts_manifest_chain_single") ok = contracts_manifest_chain_single();
  else if (name == "contracts_dependency_depth_leaf") ok = contracts_dependency_depth_leaf();
  else if (name == "contracts_dependency_depth_chain") ok = contracts_dependency_depth_chain();
  else if (name == "contracts_dependency_depth_unknown") ok = contracts_dependency_depth_unknown();
  else if (name == "model_port_fees_hazmat") ok = model_port_fees_hazmat();
  else if (name == "model_port_fees_normal") ok = model_port_fees_normal();
  else if (name == "resilience_replay_gap_exists") ok = resilience_replay_gap_exists();
  else if (name == "resilience_replay_no_gap") ok = resilience_replay_no_gap();
  else if (name == "stats_ema_increasing") ok = stats_ema_increasing();
  else if (name == "stats_ema_constant") ok = stats_ema_constant();
  // Hyper-matrix
  else if (name == "hyper_matrix") ok = hyper_matrix();
  else {
    std::cerr << "unknown test: " << name << std::endl;
    return 2;
  }

  return ok ? 0 : 1;
}
