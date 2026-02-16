#include "obsidianmesh/core.hpp"
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using namespace obsidianmesh;

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

static bool allocator_weighted() {
  // weighted_allocation({0.5, 0.5}, {10.0, 20.0}) should be 0.5*10+0.5*20=15.0
  double result = weighted_allocation({0.5, 0.5}, {10.0, 20.0});
  return std::abs(result - 15.0) < 0.01;
}

static bool allocator_berth_utilization() {
  std::vector<BerthSlot> slots = {{"B1", 8, 12, true}, {"B2", 14, 18, false}};
  double util = berth_utilization(slots);
  // Only B1 is occupied: 4 of 8 hours = 0.5
  return std::abs(util - 0.5) < 0.01;
}

static bool allocator_rounding() {
  // round_allocation(17.5, 5) should round to nearest 5 = 20
  int result = round_allocation(17.5, 5);
  return result == 20;
}

static bool allocator_cost_per_unit() {
  double cpu = cost_per_unit(100.0, 4);
  return std::abs(cpu - 25.0) < 0.01;
}

static bool allocator_normalize_urgency() {
  double norm = normalize_urgency(5, 10);
  return std::abs(norm - 0.5) < 0.01;
}

static bool allocator_priority_score() {
  // priority_score(10, 100.0, 0.7, 0.3) = 10*0.7 + 100*0.3 = 7+30 = 37
  double score = priority_score(10, 100.0, 0.7, 0.3);
  return std::abs(score - 37.0) < 0.01;
}

static bool allocator_over_capacity() {
  // is_over_capacity(8, 10, 0.8) = 0.8 >= 0.8 should be true
  return is_over_capacity(8, 10, 0.8);
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

static bool routing_weighted_score() {
  // weighted_route_score(10, 0.9, 50.0, 0.3, 0.5, 0.2) = 10*0.3 + 0.9*0.5 + 50*0.2 = 3+0.45+10 = 13.45
  double score = weighted_route_score(10, 0.9, 50.0, 0.3, 0.5, 0.2);
  return std::abs(score - 13.45) < 0.01;
}

static bool routing_best_route() {
  // Should pick lowest latency route
  auto best = best_route_by_score({{"alpha", 10}, {"beta", 3}, {"gamma", 7}}, {0.9, 0.8, 0.7});
  return best.channel == "beta";
}

static bool routing_failover() {
  auto route = failover_route({{"alpha", 5}, {"beta", 3}}, "alpha");
  return route.channel == "beta";
}

static bool routing_distance() {
  // haversine(0,0, 0,1) should be ~111.19 km
  double dist = haversine_distance(0.0, 0.0, 0.0, 1.0);
  return dist > 100.0 && dist < 120.0;
}

static bool routing_normalize_latency() {
  double norm = normalize_latency(5, 10);
  return std::abs(norm - 0.5) < 0.01;
}

static bool routing_fuel_efficiency() {
  double eff = fuel_efficiency(200.0, 10.0);
  // distance/fuel = 200/10 = 20
  return std::abs(eff - 20.0) < 0.01;
}

static bool routing_total_fees() {
  double fees = total_route_fees({{"a", 100}, {"b", 200}}, 0.5);
  return std::abs(fees - 150.0) < 0.01;
}

static bool routing_knots_conversion() {
  double kmh = knots_to_kmh(10.0);
  return std::abs(kmh - 18.52) < 0.01;
}

static bool routing_penalty() {
  double p = route_penalty(150, 100);
  return std::abs(p - 50.0) < 0.01;
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

static bool policy_weight_ordering() {
  // Should sort descending by weight
  std::map<std::string, int> weights = {{"a", 3}, {"b", 1}, {"c", 5}};
  auto ordered = policy_weight_ordering(weights);
  return ordered.size() == 3 && ordered[0] == "c" && ordered[2] == "b";
}

static bool policy_escalation_threshold() {
  // escalation_threshold("normal") should be 5, "watch" should be 3, "restricted" should be 1
  int t1 = escalation_threshold("normal");
  int t2 = escalation_threshold("watch");
  return t1 == 5 && t2 == 3;
}

static bool policy_risk_score() {
  // risk_score(3, 10, 1.5) = (3/10) * 1.5 = 0.45
  double score = risk_score(3, 10, 1.5);
  return std::abs(score - 0.45) < 0.01;
}

static bool policy_grace_period() {
  int gp = grace_period_minutes("normal");
  return gp == 60;
}

static bool policy_retries_default() {
  int r1 = default_retries("normal");
  int r2 = default_retries("restricted");
  return r1 == 5 && r2 == 1;
}

static bool policy_cooldown() {
  int c1 = cooldown_seconds("normal", "watch");
  int c2 = cooldown_seconds("watch", "restricted");
  return c1 == 30 && c2 == 60;
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

static bool queue_batch_enqueue() {
  // hard_limit=10, current_depth=7, 5 items → can only accept 3
  std::vector<QueueItem> items = {{"a",1},{"b",2},{"c",3},{"d",4},{"e",5}};
  int accepted = batch_enqueue_count(items, 10, 7);
  return accepted == 3;
}

static bool queue_priority_boost() {
  // base=5, waited 30s, boost every 10s → 5 + 3 = 8
  int boosted = priority_boost(5, 30, 10);
  return boosted == 8;
}

static bool queue_fairness() {
  // Jain's fairness index for equal counts should be 1.0
  double fi = fairness_index({10, 10, 10});
  return std::abs(fi - 1.0) < 0.01;
}

static bool queue_requeue() {
  std::vector<QueueItem> failed = {{"a", 5}, {"b", 3}};
  auto requeued = requeue_failed(failed, 2);
  // Items should have priority reduced by penalty
  return requeued[0].priority == 3 && requeued[1].priority == 1;
}

static bool queue_weighted_wait() {
  // weighted_wait_time(10, 2.0, 0.5) = (10/2.0) / 0.5 = 10.0
  double wait = weighted_wait_time(10, 2.0, 0.5);
  return std::abs(wait - 10.0) < 0.01;
}

static bool queue_pressure_ratio() {
  // depth=50, limit=100, incoming=20, processing=10 → (50+20-10)/100 = 0.6
  double ratio = queue_pressure_ratio(50, 100, 20, 10);
  return std::abs(ratio - 0.6) < 0.01;
}

static bool queue_drain_pct() {
  double pct = drain_percentage(75, 100);
  return std::abs(pct - 75.0) < 0.01;
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

static bool security_token_format() {
  // Should be "subject:expires"
  auto fmt = token_format("user123", 999999);
  return fmt == "user123:999999";
}

static bool security_password_strength() {
  // "Abc123!@" has upper, lower, digit, special → score 5
  int score = password_strength("Abc123!@");
  return score == 5;
}

static bool security_masking() {
  // mask_sensitive("secret123", 3) → "sec******" (first 3 visible)
  auto masked = mask_sensitive("secret123", 3);
  return masked == "sec******";
}

static bool security_hmac() {
  auto sig1 = hmac_sign("key1", "message");
  auto sig2 = hmac_sign("key2", "message");
  return sig1 != sig2 && sig1.size() == 16;
}

static bool security_rate_limit_key() {
  auto key = rate_limit_key("192.168.1.1", "/api/v1");
  return key == "192.168.1.1:/api/v1";
}

static bool security_session_expiry() {
  long long exp = session_expiry(1000000, 3600);
  // created + ttl_seconds * 1000 = 1000000 + 3600000
  return exp == 4600000;
}

static bool security_header_sanitize() {
  auto cleaned = sanitize_header("value\r\ninjection");
  return cleaned.find('\r') == std::string::npos && cleaned.find('\n') == std::string::npos;
}

static bool security_permissions() {
  // User has [read,write], required is [read,write] → true
  bool ok1 = check_permissions({"read", "write"}, {"read", "write"});
  // User has [read], required is [read,write] → false
  bool ok2 = check_permissions({"read"}, {"read", "write"});
  return ok1 && !ok2;
}

static bool security_ip_allowlist() {
  return ip_in_allowlist("192.168.1.1", {"192.168.1.1", "10.0.0.1"}) &&
      !ip_in_allowlist("172.16.0.1", {"192.168.1.1"});
}

static bool security_password_hash() {
  auto h1 = password_hash("pass", "salt1");
  auto h2 = password_hash("pass", "salt2");
  return h1 != h2;
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

static bool resilience_replay_window() {
  // replay_window with from_seq=1, to_seq=3 should include seq 1,2,3
  auto result = replay_window({{"a",1},{"b",2},{"c",3},{"d",4}}, 1, 3);
  return result.size() == 3;
}

static bool resilience_event_ordering() {
  return events_ordered({{"a",1},{"b",2},{"c",3}}) && !events_ordered({{"a",3},{"b",1}});
}

static bool resilience_idempotent() {
  // Events with duplicate IDs are not idempotent-safe
  return !is_idempotent_safe({{"a",1},{"a",2}});
}

static bool resilience_compact() {
  // compact with max_per_id=1 should keep last event per ID
  auto result = compact_events({{"a",1},{"a",2},{"b",3}}, 1);
  // Should have 2 events (one per ID), and for "a" it should be seq 2 (latest)
  bool has_a2 = false;
  for (const auto& e : result) {
    if (e.id == "a" && e.sequence == 2) has_a2 = true;
  }
  return result.size() == 2 && has_a2;
}

static bool resilience_retry_backoff() {
  // retry_backoff(3, 100.0, 10000.0) = min(100 * 2^3, 10000) = 800, with some jitter
  double delay = retry_backoff(3, 100.0, 10000.0);
  // Should have jitter, so not exactly 800
  return delay >= 400.0 && delay <= 1000.0;
}

static bool resilience_should_trip() {
  // should_trip_breaker(5, 10, 0.5) = 0.5 >= 0.5 = true
  return should_trip_breaker(5, 10, 0.5);
}

static bool resilience_jitter() {
  double j = jitter(100.0, 0.5);
  // Should be between 50 and 150
  return j >= 50.0 && j <= 150.0;
}

static bool resilience_half_open_calls() {
  // half_open_max_calls(10) should return scaled value, not always 3
  int calls1 = half_open_max_calls(1);
  int calls2 = half_open_max_calls(10);
  return calls1 != calls2;
}

static bool resilience_failure_window() {
  // last_failure 100ms ago, window is 200ms → within window → true
  return in_failure_window(800, 900, 200);
}

static bool resilience_recovery_rate() {
  double rate = recovery_rate(7, 10);
  return std::abs(rate - 0.7) < 0.01;
}

static bool resilience_checkpoint_interval() {
  // checkpoint_interval(5000, 1000) with more events should reduce interval
  int i1 = checkpoint_interval(100, 1000);
  int i2 = checkpoint_interval(5000, 1000);
  return i1 != i2;
}

static bool resilience_degradation() {
  // degradation_score(3, 10, 2.0) = (3/10) * 2.0 = 0.6
  double score = degradation_score(3, 10, 2.0);
  return std::abs(score - 0.6) < 0.01;
}

static bool resilience_bulkhead() {
  // bulkhead_limit(100, 4) = ceil(100/4) = 25
  int limit = bulkhead_limit(100, 4);
  return limit == 25;
}

static bool resilience_state_duration() {
  long long duration = state_duration_ms(1000, 5000);
  return duration == 4000;
}

static bool resilience_fallback() {
  auto val1 = fallback_value("primary", "fallback");
  auto val2 = fallback_value("", "fallback");
  return val1 == "primary" && val2 == "fallback";
}

static bool resilience_cascade() {
  // 3 of 5 unhealthy = 0.6, threshold 0.5 → true (cascade)
  return cascade_failure({true, false, false, false, true}, 0.5);
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

static bool stats_weighted_mean() {
  // weighted_mean({10,20,30}, {1,2,3}) = (10+40+90)/(1+2+3) = 140/6 = 23.33
  double wm = weighted_mean({10.0, 20.0, 30.0}, {1.0, 2.0, 3.0});
  return std::abs(wm - 23.333) < 0.01;
}

static bool stats_ema() {
  // EMA with alpha=0.5 on {10,20,30}: ema=10, then 0.5*20+0.5*10=15, then 0.5*30+0.5*15=22.5
  double ema = exponential_moving_average({10.0, 20.0, 30.0}, 0.5);
  return std::abs(ema - 22.5) < 0.01;
}

static bool stats_min_max_normalize() {
  // min_max_normalize(5, 0, 10) = 0.5
  double norm = min_max_normalize(5.0, 0.0, 10.0);
  return std::abs(norm - 0.5) < 0.01;
}

static bool stats_covariance() {
  // covariance of {1,2,3} and {4,5,6} with mean subtracted
  double cov = covariance({1.0, 2.0, 3.0}, {4.0, 5.0, 6.0});
  return std::abs(cov - 1.0) < 0.01;
}

static bool stats_correlation() {
  // Perfect positive correlation
  double corr = correlation({1.0, 2.0, 3.0}, {2.0, 4.0, 6.0});
  return std::abs(corr - 1.0) < 0.01;
}

static bool stats_sum_of_squares() {
  // sum_of_squares({2,3,4}) with mean=3: (2-3)^2 + (3-3)^2 + (4-3)^2 = 2
  double ss = sum_of_squares({2.0, 3.0, 4.0});
  return std::abs(ss - 2.0) < 0.01;
}

static bool stats_iqr() {
  // IQR of {1,2,3,4,5,6,7,8} = Q3-Q1
  double iqr = interquartile_range({1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0});
  return iqr > 0;
}

static bool stats_rate_of_change() {
  // rate_of_change(20, 10, 5.0) = (20-10)/5.0 = 2.0
  double roc = rate_of_change(20.0, 10.0, 5.0);
  return std::abs(roc - 2.0) < 0.01;
}

static bool stats_z_score() {
  // z_score(15, 10, 2.5) = (15-10)/2.5 = 2.0
  double z = z_score(15.0, 10.0, 2.5);
  return std::abs(z - 2.0) < 0.01;
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

static bool workflow_transition_count() {
  std::vector<TransitionRecord> records = {
      {"v1", "queued", "allocated"}, {"v2", "queued", "cancelled"}, {"v1", "allocated", "departed"}};
  int count = transition_count(records, "v1");
  return count == 2;
}

static bool workflow_time_in_state() {
  // 3600000 ms = 1 hour
  double hours = time_in_state_hours(0, 3600000);
  return std::abs(hours - 1.0) < 0.01;
}

static bool workflow_parallel_count() {
  // 2 non-terminal entities
  std::vector<std::pair<std::string, std::string>> entities = {
      {"v1", "queued"}, {"v2", "allocated"}, {"v3", "arrived"}};
  int count = parallel_entity_count(entities);
  return count == 2;
}

static bool workflow_state_distribution() {
  std::vector<std::pair<std::string, std::string>> entities = {
      {"v1", "queued"}, {"v2", "queued"}, {"v3", "allocated"}};
  auto dist = state_distribution(entities);
  return dist["queued"] == 2 && dist["allocated"] == 1;
}

static bool workflow_bottleneck() {
  std::map<std::string, int> dist = {{"queued", 5}, {"allocated", 2}, {"departed", 1}};
  auto bn = bottleneck_state(dist);
  return bn == "queued";
}

static bool workflow_completion_pct() {
  double pct = completion_percentage(75, 100);
  return std::abs(pct - 75.0) < 0.01;
}

static bool workflow_cancel_from_any() {
  // Can cancel from non-terminal states only
  return can_cancel("queued") && can_cancel("allocated") && !can_cancel("arrived");
}

static bool workflow_estimated_completion() {
  double hours = estimated_completion_hours(5, 2.0);
  return std::abs(hours - 10.0) < 0.01;
}

static bool workflow_state_age() {
  // 7200000 ms = 2 hours
  double hours = state_age_hours(0, 7200000);
  return std::abs(hours - 2.0) < 0.01;
}

static bool workflow_batch_register() {
  // Only valid states should register
  int count = batch_register_count({"v1", "v2", "v3"}, "queued");
  return count == 3;
}

static bool workflow_valid_path() {
  // Valid path: queued → allocated → departed → arrived
  return is_valid_path({"queued", "allocated", "departed", "arrived"}) &&
      !is_valid_path({"queued", "arrived"});
}

static bool workflow_throughput() {
  // 10 completed in 5 hours = 2.0/hr
  double tp = workflow_throughput(10, 5.0);
  return std::abs(tp - 2.0) < 0.01;
}

static bool workflow_chain_length() {
  std::vector<TransitionRecord> records = {
      {"v1", "queued", "allocated"}, {"v2", "queued", "cancelled"}, {"v1", "allocated", "departed"}};
  int len = chain_length(records, "v1");
  return len == 2;
}

static bool workflow_merge_histories() {
  std::vector<TransitionRecord> a = {{"v1", "queued", "allocated"}};
  std::vector<TransitionRecord> b = {{"v2", "queued", "cancelled"}};
  auto merged = merge_histories(a, b);
  return merged.size() == 2;
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

static bool model_severity_label() {
  return severity_label(SEVERITY_CRITICAL) == "CRITICAL" && severity_label(SEVERITY_LOW) == "LOW";
}

static bool model_weight_class() {
  // 50000 tons → "heavy", 5000 → "medium", 500 → "light"
  return weight_class(50000.0) == "heavy" && weight_class(5000.0) == "medium" && weight_class(500.0) == "light";
}

static bool model_crew_estimation() {
  // crew_estimation(200, 5000.0) should account for both containers and tons
  int crew = crew_estimation(200, 5000.0);
  return crew > 5;
}

static bool model_hazmat_surcharge() {
  double cost = hazmat_surcharge(100.0, true);
  // Should be 125.0 (25% surcharge)
  return std::abs(cost - 125.0) < 0.01;
}

static bool model_eta() {
  // estimated_arrival_hours(185.2, 10) using 1.852 conversion
  double hours = estimated_arrival_hours(185.2, 10.0);
  return std::abs(hours - 10.0) < 0.01;
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

static bool contracts_health_endpoint() {
  auto ep = health_endpoint("gateway", "example.com");
  return ep == "http://example.com:8140/health";
}

static bool contracts_dependency_depth() {
  // gateway depends on routing, policy; routing depends on policy; policy has none
  // gateway → routing → policy: depth = 2 (transitive)
  int depth = dependency_depth("gateway");
  return depth == 2;
}

static bool contracts_critical_path() {
  auto path = critical_path();
  return path.size() > 1;
}

static bool contracts_port_collision() {
  // Same port → collision
  std::vector<ServiceDefinition> defs = {
      {"a", 8140, "/health", "1.0.0", {}}, {"b", 8140, "/health", "1.0.0", {}}};
  return has_port_collision(defs);
}

static bool contracts_summary_format() {
  auto summary = service_summary("gateway");
  // Should include version
  return summary.find("1.0.0") != std::string::npos;
}

// ---------------------------------------------------------------------------
// Config tests
// ---------------------------------------------------------------------------

static bool config_defaults() {
  auto cfg = make_default_config("test-service", 8080);
  return cfg.region == "us-east-1" && cfg.pool_size == 32 && cfg.timeout_ms == 5000;
}

static bool config_validate() {
  ServiceConfig valid{"svc", 8080, 5000, 3, "us-east-1", 32};
  ServiceConfig invalid_port{"svc", 0, 5000, 3, "us-east-1", 32};
  return validate_config(valid) && !validate_config(invalid_port);
}

static bool config_endpoint_validation() {
  // "http://example.com" is valid, "ftp://example.com" starts with ftp not http
  return validate_endpoint("http://example.com") && !validate_endpoint("ftp://example.com");
}

static bool config_env_normalization() {
  return normalize_env_name("Production") == "production";
}

static bool config_feature_flags() {
  std::map<std::string, bool> flags = {{"feature_a", true}, {"feature_b", false}, {"feature_c", true}};
  auto enabled = enabled_features(flags);
  return enabled.size() == 2 && enabled[0] == "feature_a" && enabled[1] == "feature_c";
}

static bool config_priority_ordering() {
  std::vector<ServiceConfig> configs = {
      {"a", 8080, 5000, 1, "us", 32},
      {"b", 8081, 5000, 5, "us", 32},
      {"c", 8082, 5000, 3, "us", 32},
  };
  auto sorted = sort_configs_by_priority(configs);
  return sorted[0].name == "b" && sorted[2].name == "a";
}

// ---------------------------------------------------------------------------
// Concurrency tests
// ---------------------------------------------------------------------------

static bool concurrency_barrier() {
  // barrier_reached(5, 5) should be true (5 >= 5)
  return barrier_reached(5, 5) && !barrier_reached(4, 5);
}

static bool concurrency_merge_counts() {
  // merge_counts({3, 7, 5}) = 3+7+5 = 15
  int total = merge_counts({3, 7, 5});
  return total == 15;
}

static bool concurrency_partition() {
  auto [below, above] = partition_by_threshold({1, 5, 3, 8, 2}, 4);
  // below: {1, 3, 2}, above: {5, 8}
  return below.size() == 3 && above.size() == 2;
}

static bool concurrency_atomic_counter() {
  AtomicCounter ac;
  ac.increment();
  ac.increment();
  ac.increment();
  ac.decrement();
  return ac.get() == 2;
}

static bool concurrency_registry() {
  SharedRegistry sr;
  sr.register_entry("svc-a", "http://a:8080");
  sr.register_entry("svc-b", "http://b:8081");
  auto keys = sr.keys();
  return sr.size() == 2 && keys[0] == "svc-a" && sr.lookup("svc-a") == "http://a:8080";
}

static bool concurrency_fan_out_merge() {
  // fan_out_merge should sort by key (alphabetically)
  auto result = fan_out_merge({{"b", 2}, {"a", 1}, {"c", 3}});
  return result[0].first == "a" && result[1].first == "b" && result[2].first == "c";
}

static bool concurrency_cycle_detection() {
  std::map<std::string, std::vector<std::string>> graph_with_cycle = {
      {"a", {"b"}}, {"b", {"c"}}, {"c", {"a"}}};
  std::map<std::string, std::vector<std::string>> dag = {
      {"a", {"b"}}, {"b", {"c"}}, {"c", {}}};
  return detect_cycle(graph_with_cycle) && !detect_cycle(dag);
}

static bool concurrency_work_stealing() {
  std::vector<int> queue = {1, 2, 3, 4, 5};
  auto stolen = work_stealing(queue, 2);
  // Should steal from back: {4, 5}
  return stolen.size() == 2 && stolen[0] == 4 && stolen[1] == 5 && queue.size() == 3;
}

// ---------------------------------------------------------------------------
// Events tests
// ---------------------------------------------------------------------------

static bool events_time_sorting() {
  auto sorted = sort_events_by_time({{"a", 300, "info", ""}, {"b", 100, "warn", ""}, {"c", 200, "info", ""}});
  return sorted[0].timestamp == 100 && sorted[2].timestamp == 300;
}

static bool events_dedup() {
  auto deduped = dedup_by_id({{"a", 100, "info", ""}, {"a", 200, "warn", ""}, {"b", 150, "info", ""}});
  // Should keep earliest per ID: a@100, b@150
  bool has_a100 = false;
  for (const auto& e : deduped) {
    if (e.id == "a" && e.timestamp == 100) has_a100 = true;
  }
  return deduped.size() == 2 && has_a100;
}

static bool events_time_window() {
  std::vector<TimedEvent> events = {{"a", 100, "x", ""}, {"b", 200, "x", ""}, {"c", 300, "x", ""}};
  auto filtered = filter_time_window(events, 100, 300);
  // Should include events at 100 (>= start), 200, 300 (<=end)
  return filtered.size() == 3;
}

static bool events_count_by_kind() {
  std::vector<TimedEvent> events = {
      {"a", 100, "info", ""}, {"b", 200, "warn", ""}, {"c", 300, "info", ""}};
  auto counts = count_by_kind(events);
  return counts["info"] == 2 && counts["warn"] == 1;
}

static bool events_log_eviction() {
  EventLog log(3);
  log.append(TimedEvent{"a", 100, "info", ""});
  log.append(TimedEvent{"b", 200, "info", ""});
  log.append(TimedEvent{"c", 300, "info", ""});
  log.append(TimedEvent{"d", 400, "info", ""});
  auto all = log.get_all();
  // Should evict oldest (a), keep b,c,d
  return all.size() == 3 && all[0].id == "b";
}

static bool events_gap_detection() {
  // Gaps > 100 (strictly greater)
  std::vector<TimedEvent> events = {
      {"a", 100, "", ""}, {"b", 200, "", ""}, {"c", 400, "", ""}};
  auto gaps = detect_gaps(events, 100);
  // 200→400 is a gap of 200 > 100
  return gaps.size() == 1 && gaps[0] == 2;
}

static bool events_batch_by_time() {
  std::vector<TimedEvent> events = {
      {"a", 0, "", ""}, {"b", 50, "", ""}, {"c", 100, "", ""}, {"d", 150, "", ""}};
  auto batches = batch_events(events, 100);
  // 0-99 and 100-199 → 2 buckets
  return batches.size() == 2;
}

static bool events_rate() {
  std::vector<TimedEvent> events = {
      {"a", 0, "", ""}, {"b", 500, "", ""}, {"c", 1000, "", ""}};
  double rate = event_rate(events, 1000);
  // 3 events over 1000ms, window 1000ms → rate = 3.0
  return std::abs(rate - 3.0) < 0.01;
}

// ---------------------------------------------------------------------------
// Telemetry tests
// ---------------------------------------------------------------------------

static bool telemetry_error_rate() {
  double rate = error_rate(5, 100);
  return std::abs(rate - 0.05) < 0.01;
}

static bool telemetry_latency_bucket() {
  // <100 fast, 100-499 normal, 500-1999 slow, >=2000 critical
  return latency_bucket(50.0) == "fast" && latency_bucket(100.0) == "normal" &&
      latency_bucket(500.0) == "slow" && latency_bucket(2000.0) == "critical";
}

static bool telemetry_throughput() {
  // 1000 requests in 2000ms = 500/sec
  double tp = throughput(1000, 2000);
  return std::abs(tp - 500.0) < 0.01;
}

static bool telemetry_health_score() {
  // health_score(0.99, 0.01) = 0.99*0.6 + 0.99*0.4 = 0.594 + 0.396 = 0.99
  double score = health_score(0.99, 0.01);
  return std::abs(score - 0.99) < 0.01;
}

static bool telemetry_threshold_check() {
  // is_within_threshold(10.5, 10.0, 1.0) → |0.5| <= 1.0 → true
  return is_within_threshold(10.5, 10.0, 1.0) && !is_within_threshold(12.0, 10.0, 1.0);
}

static bool telemetry_aggregate() {
  // aggregate_metrics({10,20,30}) = average = 20
  double avg = aggregate_metrics({10.0, 20.0, 30.0});
  return std::abs(avg - 20.0) < 0.01;
}

static bool telemetry_uptime() {
  // uptime_percentage(9000, 10000) = 90%
  double pct = uptime_percentage(9000, 10000);
  return std::abs(pct - 90.0) < 0.01;
}

static bool telemetry_alerting() {
  // should_alert(95.0, 90.0) → 95 > 90 → true
  return should_alert(95.0, 90.0) && !should_alert(85.0, 90.0);
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

static bool config_registry_workflow() {
  auto cfg = make_default_config("gateway", 8140);
  SharedRegistry reg;
  reg.register_entry(cfg.name, cfg.region);
  WorkflowEngine we;
  we.register_entity("order-1", "queued");
  we.transition("order-1", "allocated");
  return reg.lookup("gateway") != "" && we.get_state("order-1") == "allocated";
}

static bool event_driven_workflow() {
  EventLog log(100);
  log.append(TimedEvent{"evt-1", 1000, "order_created", ""});
  log.append(TimedEvent{"evt-2", 2000, "order_allocated", ""});
  WorkflowEngine we;
  we.register_entity("v1", "queued");
  we.transition("v1", "allocated");
  return log.count() == 2 && we.get_state("v1") == "allocated";
}

static bool telemetry_collection_flow() {
  MetricsCollector mc;
  mc.record(MetricSample{"latency", 50.0, 1000});
  mc.record(MetricSample{"latency", 75.0, 2000});
  mc.record(MetricSample{"errors", 1.0, 1000});
  auto latencies = mc.get_by_name("latency");
  return mc.count() == 3 && latencies.size() == 2;
}

// ---------------------------------------------------------------------------
// Latent bug tests
// ---------------------------------------------------------------------------

static bool latent_accumulated_utilization() {
  // Average of {0.9, 0.1, 0.1, 0.1} should be 0.3
  double avg = accumulated_utilization({0.9, 0.1, 0.1, 0.1});
  return std::abs(avg - 0.3) < 0.01;
}

static bool latent_active_route_count() {
  // Routes at 5, 7, 9, 15 with max=10. Active means latency strictly less than max.
  int count = count_active_routes({{"a", 5}, {"b", 7}, {"c", 9}, {"d", 15}}, 10);
  return count == 3;
}

static bool latent_transition_key() {
  TransitionRecord r{"v1", "queued", "allocated"};
  auto key = build_transition_key(r);
  // Key format should be "entity_id:from:to"
  return key == "v1:queued:allocated";
}

static bool latent_token_expiry_spread() {
  // Unsorted expiry times: spread should be max - min = 500 - 100 = 400
  double spread = token_expiry_spread({500, 100, 300});
  return std::abs(spread - 400.0) < 0.01;
}

// ---------------------------------------------------------------------------
// Domain logic bug tests
// ---------------------------------------------------------------------------

static bool domain_berth_fee() {
  // Heavy vessel (15000 tons) at berth for 8 hours at $100/hr
  // Heavy multiplier should be 2.0x: 8 * 100 * 2.0 = $1600
  double fee = berth_rental_fee(15000.0, 8.0, 100.0);
  return std::abs(fee - 1600.0) < 0.01;
}

static bool domain_sla_breach() {
  // Response 35 min, target 30 min, grace 10 min, penalty $5/min
  // Within grace period (35 < 30+10=40), so no penalty: cost = 0
  double cost = sla_breach_cost(35, 30, 10, 5.0);
  return std::abs(cost - 0.0) < 0.01;
}

static bool domain_weather_eta() {
  // 185.2 km, 10 knots, weather factor 1.5
  // Base time = 185.2 / (10 * 1.852) = 10.0 hours
  // Weather adjusted = 10.0 * 1.5 = 15.0 hours
  double eta = weather_adjusted_eta(185.2, 10.0, 1.5);
  return std::abs(eta - 15.0) < 0.01;
}

static bool domain_hazmat_crew() {
  // Base crew 10, hazmat cargo with 200 containers
  // IMO requires 1 safety officer per 50 containers: 200/50 = 4 extra
  // Total = 10 + 4 = 14
  int crew = crew_for_hazmat(10, true, 200);
  return crew == 14;
}

// ---------------------------------------------------------------------------
// Multi-step bug tests
// ---------------------------------------------------------------------------

static bool multistep_normalize_timestamps() {
  // Convert milliseconds to seconds: {1000, 2000, 3000} → {1.0, 2.0, 3.0}
  auto result = normalize_timestamps_to_seconds({1000, 2000, 3000});
  return result.size() == 3 && std::abs(result[0] - 1.0) < 0.01
      && std::abs(result[1] - 2.0) < 0.01 && std::abs(result[2] - 3.0) < 0.01;
}

static bool multistep_event_bursts() {
  // Times {1.0, 2.0, 5.0, 6.0} with gap threshold 3.0
  // Gaps: 1.0, 3.0, 1.0. Only gap > 3.0 counts as burst boundary.
  // Gap of 3.0 is NOT greater than 3.0, so 0 burst boundaries.
  int bursts = count_event_bursts({1.0, 2.0, 5.0, 6.0}, 3.0);
  return bursts == 0;
}

static bool multistep_reliability_score() {
  // 90 successes out of 100 total: reliability = 0.9
  double score = compute_reliability_score(90, 100);
  return std::abs(score - 0.9) < 0.01;
}

static bool multistep_select_reliable() {
  // 3 routes: reliabilities 90%, 60%, 95%. min_reliability = 0.8
  // Only routes with reliability >= 0.8 should qualify (90% and 95%)
  // Route at index 2 has 95% and should be selected
  // But compute_route_reliability returns 90, 60, 95 (percentages)
  // so 60 > 0.8 passes threshold (bug), and route at index 2 still wins.
  // With min=0.65, route at index 1 (60%) should be filtered out.
  auto best = select_most_reliable(
      {{"slow", 50}, {"cheap", 2}, {"fast", 5}},
      {60, 60, 95}, {100, 100, 100}, 0.65);
  // With correct reliability (0.6, 0.6, 0.95), only route 2 passes 0.65 threshold.
  // With buggy reliability (60, 60, 95), all pass 0.65 threshold, best=95→"fast"
  // Correct answer is "fast" but for the wrong reason. Let's make it clearer:
  // If only qualifying route should be returned when others are below threshold
  auto filtered = select_most_reliable(
      {{"alpha", 50}, {"beta", 2}},
      {50, 95}, {100, 100}, 0.8);
  // Correct: alpha reliability=0.5 (fails 0.8), beta reliability=0.95 → beta selected
  // Bug: alpha reliability=50 (passes 0.8), beta reliability=95 → beta wins (same)
  // Need a case where wrong filtering changes the result:
  auto wrong = select_most_reliable(
      {{"alpha", 50}, {"beta", 2}},
      {50, 30}, {100, 100}, 0.6);
  // Correct: alpha=0.5 fails 0.6, beta=0.3 fails 0.6 → no route (empty channel)
  // Bug: alpha=50 passes 0.6, beta=30 passes 0.6 → alpha selected (wrong!)
  return wrong.channel.empty();
}

// ---------------------------------------------------------------------------
// State machine bug tests
// ---------------------------------------------------------------------------

static bool statemachine_escalation_cooldown() {
  // Last escalation was 500ms ago, cooldown is 2000ms
  // Should NOT allow escalation (500 < 2000)
  bool ok = escalation_cooldown_ok(5000, 5500, 2000);
  return !ok;
}

static bool statemachine_transition_sequence() {
  // Sequence: queued → allocated → departed → cancelled
  // departed can only go to arrived, not cancelled, so valid prefix is first 3
  auto valid = validate_transition_sequence({"queued", "allocated", "departed", "cancelled"});
  return valid.size() == 3 && valid.back() == "departed";
}

static bool statemachine_circuit_breaker_recovery() {
  // half_open state: 2 failures, 3 successes, threshold=3
  // Despite having 3 successes, failures > 0 means recovery failed → open
  // Bug counts successes+failures together (2+3=5>=3) → closed
  auto next = circuit_breaker_next_state("half_open", 2, 3, 3);
  return next == CB_OPEN;
}

// ---------------------------------------------------------------------------
// Concurrency bug tests
// ---------------------------------------------------------------------------

static bool concurrency_safe_counter_overflow() {
  // current=90, delta=20, max=100. 90+20=110 > 100, should reject
  int result = safe_counter_add(90, 20, 100);
  return result == 90;
}

static bool concurrency_parallel_merge() {
  // Merge two sorted arrays ascending: {1,3,5} + {2,3,6} → {1,2,3,3,5,6}
  auto merged = parallel_merge_sorted({1, 3, 5}, {2, 3, 6});
  return merged.size() == 6 && merged[0] == 1 && merged[1] == 2
      && merged[2] == 3 && merged[3] == 3 && merged[5] == 6;
}

static bool concurrency_queue_merge() {
  // Merge two priority queues with overlapping IDs, all items should be preserved
  auto merged = priority_queue_merge({{"a", 5}, {"b", 1}}, {{"a", 3}, {"c", 2}});
  return merged.size() == 4 && merged[0].priority == 5 && merged[1].priority == 3;
}

static bool concurrency_event_trim() {
  // Current size 50, max 100, batch 10. Under capacity, should NOT trim.
  int trimmed = event_log_trim_count(50, 100, 10);
  return trimmed == 0;
}

// ---------------------------------------------------------------------------
// Integration bug tests
// ---------------------------------------------------------------------------

static bool integration_dispatch_route_score() {
  // Dispatch 2 of 3 orders, then route PLANNED orders (not rejected)
  // Orders: a(urgency=5), b(urgency=2), c(urgency=4). Cap=2 → plan a,c. reject b.
  // Best route: beta(latency=3). route_quality=1/(1+3)=0.25
  // Score = total_planned_urgency * route_quality = (5+4)*0.25 = 2.25
  double score = dispatch_route_combined_score(
      {{"a", 5, "08:00"}, {"b", 2, "10:00"}, {"c", 4, "09:00"}}, 2,
      {{"alpha", 10}, {"beta", 3}});
  return std::abs(score - 2.25) < 0.01;
}

static bool integration_policy_queue_limit() {
  // watch policy should reduce queue limit to 80% of base
  // base=100, watch → 80.0
  double limit = policy_adjusted_queue_limit("watch", 100);
  return std::abs(limit - 80.0) < 0.01;
}

static bool integration_health_composite() {
  // Both error rate AND latency must be within thresholds for healthy
  // error_rate=0.5 (bad, threshold=0.1), latency=50.0 (good, threshold=200.0)
  // Should be false (error rate exceeds threshold)
  bool healthy = health_check_composite(0.5, 50.0, 0.1, 200.0);
  return !healthy;
}

static bool integration_checkpoint_replay() {
  // Events: [{a,1}, {b,2}, {c,3}], checkpoint at seq=2
  // Should replay events AFTER checkpoint: only {c,3} → count = 1
  int count = checkpoint_replay_count({{"a", 1}, {"b", 2}, {"c", 3}}, 2);
  return count == 1;
}

static bool integration_priority_aging() {
  // base_priority=5, age=10000ms (10 sec), aging_factor=0.1
  // Priority should INCREASE with age: 5 + 10 * 0.1 = 6.0
  double priority = weighted_priority_aging(5, 10000, 0.1);
  return std::abs(priority - 6.0) < 0.01;
}

static bool integration_cascade_depth() {
  // Dependency graph: A depends on B, B depends on C, D depends on C
  // Failing C should cascade to B (direct) and A (transitive) = depth 3
  std::map<std::string, std::vector<std::string>> deps = {
      {"A", {"B"}}, {"B", {"C"}}, {"C", {}}, {"D", {"C"}}};
  int depth = cascade_failure_depth(deps, "C");
  // B and D depend on C directly (depth 1), A depends on B which depends on C (depth 2)
  // Total affected services: B, D (direct), A (transitive) = 3
  return depth == 3;
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

  // Phase 2 expanded checks: config, concurrency, events, telemetry
  if (idx % 13 == 0) {
    auto cfg = make_default_config("svc-" + std::to_string(idx), 8080 + (idx % 100));
    if (cfg.name.empty()) return false;
    if (!validate_config(cfg)) return false;
  }

  if (idx % 19 == 0) {
    int counts = merge_counts({idx % 10, (idx * 3) % 10, (idx * 7) % 10});
    if (counts < 0) return false;
  }

  if (idx % 29 == 0) {
    std::vector<TimedEvent> evts = {
        {"e1", static_cast<long long>(idx), "info", ""},
        {"e2", static_cast<long long>(idx + 100), "warn", ""}};
    auto sorted = sort_events_by_time(evts);
    if (sorted.empty()) return false;
  }

  if (idx % 37 == 0) {
    double er = error_rate(idx % 10, 100);
    if (er < 0) return false;
  }

  if (idx % 43 == 0) {
    auto rw = replay_window(replayed, 0, 2);
    if (rw.empty() && replayed.size() > 0) return false;
  }

  if (idx % 47 == 0) {
    double wm = weighted_mean({1.0, 2.0, 3.0}, {1.0, 1.0, 1.0});
    if (wm <= 0) return false;
  }

  if (idx % 59 == 0) {
    int tc = transition_count(
        {{"v1", "queued", "allocated"}, {"v1", "allocated", "departed"}}, "v1");
    if (tc <= 0) return false;
  }

  if (idx % 67 == 0) {
    auto label = severity_label(severity_a > 5 ? 5 : severity_a);
    if (label.empty()) return false;
  }

  if (idx % 73 == 0) {
    auto ep = health_endpoint("gateway", "localhost");
    if (ep.empty()) return false;
  }

  if (idx % 79 == 0) {
    bool reached = barrier_reached(5, 5);
    if (!reached) return false;
  }

  if (idx % 89 == 0) {
    auto bucket = latency_bucket(static_cast<double>(idx % 3000));
    if (bucket.empty()) return false;
  }

  if (idx % 101 == 0) {
    double hs = health_score(0.99, 0.01);
    if (hs <= 0) return false;
  }

  if (idx % 103 == 0) {
    auto tok = token_format("user", 999);
    if (tok.empty()) return false;
  }

  if (idx % 107 == 0) {
    auto wsc = weighted_route_score(5, 0.9, 10.0, 0.3, 0.5, 0.2);
    if (wsc <= 0) return false;
  }

  if (idx % 109 == 0) {
    auto pwt = policy_weight_ordering({{"a", 3}, {"b", 1}});
    if (pwt.empty()) return false;
  }

  if (idx % 113 == 0) {
    int be = batch_enqueue_count({{"a",1},{"b",2}}, 10, 5);
    if (be < 0) return false;
  }

  return true;
}

static bool hyper_matrix() {
  constexpr int total = 12500;
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
// False-pass detection tests — catch bugs hidden by symmetric inputs
// ---------------------------------------------------------------------------

static bool resilience_jitter_variance() {
  // jitter(100, 0.5) should NOT always return exactly 100.0
  // With factor=0.5, range is [50, 150]; pure constant means no jitter
  bool all_same = true;
  for (int i = 0; i < 20; ++i) {
    if (jitter(100.0, 0.5) != 100.0) { all_same = false; break; }
  }
  return !all_same;
}

static bool resilience_retry_with_jitter() {
  // retry_backoff(3, 100, 10000) base=800; with jitter it shouldn't always be exactly 800
  bool all_exact = true;
  for (int i = 0; i < 20; ++i) {
    if (retry_backoff(3, 100.0, 10000.0) != 800.0) { all_exact = false; break; }
  }
  return !all_exact;
}

static bool stats_ema_asymmetric() {
  // EMA alpha=0.3 on {10,20,30}
  // Correct: ema=10, 0.3*20+0.7*10=13, 0.3*30+0.7*13=18.1
  // Buggy (swapped): ema=10, 0.7*20+0.3*10=17, 0.7*30+0.3*17=26.1
  double ema = exponential_moving_average({10.0, 20.0, 30.0}, 0.3);
  return std::abs(ema - 18.1) < 0.01;
}

static bool telemetry_health_asymmetric() {
  // health_score(0.95, 0.3) with correct weights 0.6/0.4:
  // 0.95*0.6 + 0.7*0.4 = 0.57 + 0.28 = 0.85
  // Buggy weights 0.4/0.6: 0.95*0.4 + 0.7*0.6 = 0.38 + 0.42 = 0.80
  double score = health_score(0.95, 0.3);
  return std::abs(score - 0.85) < 0.01;
}

static bool stats_normalize_boundary() {
  // min_max_normalize(10, 0, 10) = 1.0 (value at max boundary)
  double norm = min_max_normalize(10.0, 0.0, 10.0);
  return std::abs(norm - 1.0) < 0.01;
}

static bool contracts_depth_transitive() {
  // analytics → routing → policy: transitive depth = 2
  // Bug returns direct dep count = 1 (only routing)
  int depth = dependency_depth("analytics");
  return depth == 2;
}

static bool concurrency_fan_out_by_key() {
  // Sort by key: {{"c",1}, {"a",3}, {"b",2}} → {{"a",3}, {"b",2}, {"c",1}}
  // Bug sorts by value: → {{"c",1}, {"b",2}, {"a",3}}
  auto result = fan_out_merge({{"c", 1}, {"a", 3}, {"b", 2}});
  return result[0].first == "a" && result[1].first == "b" && result[2].first == "c";
}

static bool events_count_duplicates() {
  // Two events with same ID and kind — should count 2, not unique IDs (1)
  std::vector<TimedEvent> events = {
      {"a", 100, "info", ""}, {"a", 200, "info", ""}, {"b", 300, "warn", ""}};
  auto counts = count_by_kind(events);
  return counts["info"] == 2 && counts["warn"] == 1;
}

static bool config_endpoint_strict() {
  // "ftp://httpserver.com" contains "http" in hostname but is NOT a valid http endpoint
  return !validate_endpoint("ftp://httpserver.com");
}

static bool model_vessel_load() {
  // vessel_load_factor(50, 100) = 50/100 = 0.5
  // Bug: returns max/containers = 100/50 = 2.0
  double lf = vessel_load_factor(50, 100);
  return std::abs(lf - 0.5) < 0.01;
}

// ---------------------------------------------------------------------------
// Targeted reinforcement tests — 50 additional tests for shallow bugs
// ---------------------------------------------------------------------------

// --- False-pass fixes ---

static bool resilience_bulkhead_nonexact() {
  // bulkhead_limit(100, 3) = ceil(100/3) = 34. Bug: truncates to 33
  return bulkhead_limit(100, 3) == 34;
}

static bool workflow_batch_invalid_state() {
  // Invalid initial state should register 0 entities. Bug: returns size regardless.
  return batch_register_count({"v1", "v2"}, "nonexistent_state") == 0;
}

static bool model_crew_tons_matter() {
  // Same containers, different tons should give different crew
  return crew_estimation(100, 1000.0) != crew_estimation(100, 50000.0);
}

static bool contracts_port_collision_gap() {
  // Non-adjacent same ports should be detected. Bug: only checks adjacent pairs.
  std::vector<ServiceDefinition> defs = {
      {"a", 8140, "/health", "1.0.0", {}},
      {"b", 8141, "/health", "1.0.0", {}},
      {"c", 8140, "/health", "1.0.0", {}}};
  return has_port_collision(defs);
}

static bool events_merge_streams_order() {
  // Merged events should be sorted ascending by timestamp. Bug: sorts descending.
  auto merged = merge_event_streams(
      {{"a", 100, "info", ""}, {"b", 300, "info", ""}},
      {{"c", 200, "warn", ""}});
  return merged.size() == 3 && merged[0].timestamp <= merged[1].timestamp
      && merged[1].timestamp <= merged[2].timestamp;
}

// --- Allocator reinforcement ---

static bool allocator_weighted_with_zero() {
  // weighted_allocation({1.0, 0.0}, {5.0, 10.0}) = 1*5 + 0*10 = 5.0
  // Bug: product chain → 1*5 * 0*10 = 0
  return std::abs(weighted_allocation({1.0, 0.0}, {5.0, 10.0}) - 5.0) < 0.01;
}

static bool allocator_berth_util_occupied() {
  // Three slots: one occupied (4h), two free (4h each). Util = 4/12 = 0.333
  std::vector<BerthSlot> slots = {
      {"B1", 8, 12, true}, {"B2", 14, 18, false}, {"B3", 20, 24, false}};
  return std::abs(berth_utilization(slots) - 0.333) < 0.01;
}

static bool allocator_round_ceiling() {
  // round_allocation(7.3, 3) = ceil → 9. Bug: truncates to 6
  return round_allocation(7.3, 3) == 9;
}

static bool allocator_cost_unit_exact() {
  // cost_per_unit(250.0, 10) = 250/10 = 25.0. Bug: 10/250 = 0.04
  return std::abs(cost_per_unit(250.0, 10) - 25.0) < 0.01;
}

static bool allocator_normalize_urg_exact() {
  // normalize_urgency(10, 10) = 10/10 = 1.0. Bug: 10/11 = 0.909
  return std::abs(normalize_urgency(10, 10) - 1.0) < 0.01;
}

// --- Routing reinforcement ---

static bool routing_best_route_min_lat() {
  // Should select lowest latency. Bug: selects highest.
  auto best = best_route_by_score({{"fast", 2}, {"slow", 10}, {"mid", 5}}, {0.9, 0.8, 0.7});
  return best.channel == "fast";
}

static bool routing_failover_filtered() {
  // Failover should skip the failed channel. Bug: returns front() regardless.
  auto route = failover_route({{"alpha", 5}, {"beta", 3}, {"gamma", 7}}, "alpha");
  return route.channel != "alpha";
}

static bool routing_penalty_positive_val() {
  // route_penalty(15, 10) should be positive (5.0). Bug: returns -5.0
  return route_penalty(15, 10) > 0;
}

static bool routing_normalize_lat_exact() {
  // normalize_latency(5, 10) = 5/10 = 0.5. Bug: 10/5 = 2.0
  return std::abs(normalize_latency(5, 10) - 0.5) < 0.01;
}

static bool routing_fuel_eff_correct() {
  // fuel_efficiency(200, 50) = 200/50 = 4.0. Bug: 50/200 = 0.25
  return std::abs(fuel_efficiency(200.0, 50.0) - 4.0) < 0.01;
}

// --- Policy reinforcement ---

static bool policy_risk_multiply() {
  // risk_score(3, 10, 0.5) = (3/10) * 0.5 = 0.15. Bug: (3/10) + 0.5 = 0.8
  return std::abs(risk_score(3, 10, 0.5) - 0.15) < 0.01;
}

static bool policy_retries_by_level() {
  // Different levels should have different retry counts. Bug: always returns 3.
  return default_retries("normal") != default_retries("restricted");
}

static bool policy_cooldown_by_levels() {
  // Cooldown should vary by transition. Bug: always returns 60.
  return cooldown_seconds("normal", "watch") != cooldown_seconds("watch", "restricted");
}

// --- Queue reinforcement ---

static bool queue_shed_emergency_ratio() {
  // should_shed(80, 100, true) at EMERGENCY_RATIO=0.8 → 80% >= 80% → true
  // Bug: uses 0.95 threshold → 80 < 95 → false
  return should_shed(80, 100, true);
}

static bool queue_batch_depth_limit() {
  // batch_enqueue_count(items, hard=10, depth=8) → can accept 2 more
  // Bug: ignores current_depth, returns min(4, 10) = 4
  return batch_enqueue_count({{"a",1},{"b",2},{"c",3},{"d",4}}, 10, 8) == 2;
}

static bool queue_boost_with_interval() {
  // priority_boost(5, 300, 60) = 5 + 300/60 = 10. Bug: 5 + 300 = 305
  return priority_boost(5, 300, 60) == 10;
}

static bool queue_requeue_with_penalty() {
  // Requeued items should have priority reduced. Bug: returns unchanged.
  auto result = requeue_failed({{"a", 10}, {"b", 5}}, 3);
  return result.size() == 2 && result[0].priority == 7 && result[1].priority == 2;
}

static bool queue_weighted_wait_factor() {
  // weighted_wait_time(20, 4.0, 2.0) = (20/4)/2 = 2.5. Bug: (20/4)*2 = 10.0
  return std::abs(weighted_wait_time(20, 4.0, 2.0) - 2.5) < 0.01;
}

static bool queue_pressure_with_rates() {
  // queue_pressure_ratio(50, 100, 20, 10) should factor in rates
  // Simple depth ratio = 0.5, but with rates it should be higher (net growth)
  double p1 = queue_pressure_ratio(50, 100, 20, 10);
  double p2 = queue_pressure_ratio(50, 100, 10, 20);
  return p1 != p2;
}

static bool queue_drain_pct_correct() {
  // drain_percentage(30, 100) = 30/100 = 30%. Bug: 30/(100+30)*100 = 23.1%
  return std::abs(drain_percentage(30, 100) - 30.0) < 0.01;
}

// --- Security reinforcement ---

static bool security_token_order() {
  // token_format("alice", 1234) should be "alice:1234". Bug: "1234:alice"
  return token_format("alice", 1234) == "alice:1234";
}

static bool security_mask_first() {
  // mask_sensitive("abcdef", 2) = "ab****". Bug: shows last 2 → "****ef"
  return mask_sensitive("abcdef", 2) == "ab****";
}

static bool security_rate_key_ip_first() {
  // rate_limit_key("10.0.0.1", "/api") = "10.0.0.1:/api". Bug: "/api:10.0.0.1"
  return rate_limit_key("10.0.0.1", "/api") == "10.0.0.1:/api";
}

static bool security_session_ms() {
  // session_expiry(1000, 60) = 1000 + 60*1000 = 61000. Bug: 1000+60=1060
  return session_expiry(1000, 60) == 61000;
}

static bool security_header_cr() {
  // Should remove both \r and \n. Bug: only removes \n
  return sanitize_header("hello\r\nworld") == "helloworld";
}

static bool security_perms_subset() {
  // Required ⊆ user_perms. Bug: checks user_perms ⊆ required (reversed)
  bool ok1 = check_permissions({"read", "write"}, {"read"});
  bool ok2 = check_permissions({"read"}, {"read", "write"});
  return ok1 && !ok2;
}

// --- Resilience reinforcement ---

static bool resilience_idempotent_method() {
  // Duplicate IDs with different sequences should NOT be idempotent safe
  // Bug: always returns true
  return !is_idempotent_safe({{"a", 1}, {"a", 2}});
}

static bool resilience_compact_last() {
  // compact_events should keep LAST per ID. Bug: keeps first.
  // ID "a" has seq 1,2,3, max_per_id=2 → should keep {2,3}
  auto result = compact_events({{"a", 1}, {"a", 2}, {"a", 3}, {"b", 1}}, 2);
  bool has_a3 = false;
  for (const auto& e : result) {
    if (e.id == "a" && e.sequence == 3) has_a3 = true;
  }
  return has_a3;
}

static bool resilience_recovery_correct() {
  // recovery_rate(8, 10) = 8/10 = 0.8. Bug: (10-8)/10 = 0.2
  return std::abs(recovery_rate(8, 10) - 0.8) < 0.01;
}

static bool resilience_degradation_mult() {
  // degradation_score(3, 10, 0.5) = (3/10)*0.5 = 0.15. Bug: 0.3+0.5=0.8
  return std::abs(degradation_score(3, 10, 0.5) - 0.15) < 0.01;
}

static bool resilience_fallback_primary() {
  // Should return primary when non-empty. Bug: always returns fallback.
  return fallback_value("primary_value", "fallback_value") == "primary_value";
}

// --- Statistics reinforcement ---

static bool stats_weighted_mean_denom() {
  // weighted_mean({10,20}, {2,3}) = (10*2+20*3)/(2+3) = 80/5 = 16
  // Bug: divides by count=2 → 80/2=40
  return std::abs(weighted_mean({10.0, 20.0}, {2.0, 3.0}) - 16.0) < 0.01;
}

static bool stats_covariance_centered() {
  // covariance({2,4}, {1,3}) with means subtracted: ((2-3)(1-2)+(4-3)(3-2))/1 = 2
  // Bug: without means: (2*1+4*3)/1 = 14
  return std::abs(covariance({2.0, 4.0}, {1.0, 3.0}) - 2.0) < 0.01;
}

static bool stats_correlation_bivariate() {
  // correlation({1,2,3}, {2,4,6}) using sy too. Perfect correlation = 1.0
  // Bug: uses sx*sx instead of sx*sy → cov/(sx^2) ≠ 1.0 if sy≠sx
  double corr = correlation({1.0, 2.0, 3.0}, {10.0, 20.0, 30.0});
  return std::abs(corr - 1.0) < 0.01;
}

static bool stats_sum_sq_deviation() {
  // sum_of_squares({1,2,3}) with mean=2: (1-2)²+(2-2)²+(3-2)² = 2
  // Bug: returns simple sum 1+2+3=6
  return std::abs(sum_of_squares({1.0, 2.0, 3.0}) - 2.0) < 0.01;
}

static bool stats_rate_change_interval() {
  // rate_of_change(10, 4, 2) = (10-4)/2 = 3.0. Bug: returns 10-4=6.0
  return std::abs(rate_of_change(10.0, 4.0, 2.0) - 3.0) < 0.01;
}

// --- Workflow reinforcement ---

static bool workflow_transition_entity() {
  // transition_count filtered by entity_id. Bug: counts ALL records.
  std::vector<TransitionRecord> records = {
      {"v1", "queued", "allocated"}, {"v2", "queued", "cancelled"},
      {"v1", "allocated", "departed"}};
  return transition_count(records, "v1") == 2;
}

static bool workflow_time_ms_to_hours() {
  // time_in_state_hours(0, 3600000) = 3600000ms = 1.0 hour
  // Bug: returns raw ms difference = 3600000
  return std::abs(time_in_state_hours(0, 3600000) - 1.0) < 0.01;
}

static bool workflow_parallel_active() {
  // parallel_entity_count should count only non-terminal entities
  // Bug: counts all entities
  std::vector<std::pair<std::string, std::string>> entities = {
      {"v1", "queued"}, {"v2", "arrived"}, {"v3", "allocated"}};
  return parallel_entity_count(entities) == 2;
}

static bool workflow_completion_correct() {
  // completion_percentage(8, 10) = 8/10*100 = 80%. Bug: 10/8*100 = 125%
  return std::abs(completion_percentage(8, 10) - 80.0) < 0.01;
}

static bool workflow_throughput_rate() {
  // workflow_throughput(20, 4.0) = 20/4 = 5.0/hr. Bug: 4/20 = 0.2
  return std::abs(workflow_throughput(20, 4.0) - 5.0) < 0.01;
}

// --- Telemetry reinforcement ---

static bool telemetry_error_ratio() {
  // error_rate(5, 100) = 5/100 = 0.05. Bug: 100/5 = 20.0
  return std::abs(error_rate(5, 100) - 0.05) < 0.01;
}

static bool telemetry_throughput_sec() {
  // throughput(100, 2000) = 100/2000*1000 = 50/sec. Bug: 100/2000 = 0.05
  return std::abs(throughput(100, 2000) - 50.0) < 0.01;
}

static bool telemetry_uptime_calc() {
  // uptime_percentage(8000, 10000) = 80%. Bug: calculates downtime = 20%
  return std::abs(uptime_percentage(8000, 10000) - 80.0) < 0.01;
}

static bool telemetry_alert_direction() {
  // should_alert(95, 90) → 95 > 90 → true. Bug: 95 < 90 → false
  return should_alert(95.0, 90.0);
}

// --- Events reinforcement ---

static bool events_dedup_first() {
  // dedup_by_id should keep earliest event. Bug: keeps latest.
  std::vector<TimedEvent> events = {
      {"a", 100, "info", "v1"}, {"a", 200, "info", "v2"}, {"b", 150, "warn", "v3"}};
  auto deduped = dedup_by_id(events);
  bool a_is_first = false;
  for (const auto& e : deduped) {
    if (e.id == "a" && e.timestamp == 100) a_is_first = true;
  }
  return a_is_first;
}

static bool events_window_inclusive() {
  // filter_time_window [100, 300] should include all 3 events.
  // Bug: uses > start (excludes ts=100) giving only 2 events.
  std::vector<TimedEvent> events = {
      {"a", 100, "info", ""}, {"b", 200, "info", ""}, {"c", 300, "info", ""}};
  auto filtered = filter_time_window(events, 100, 300);
  return filtered.size() == 3;
}

static bool events_normalize_divisor() {
  // normalize_timestamps_to_seconds({5000}) = 5000/1000 = 5.0
  // Bug: divides by 1000000 → 0.005
  auto result = normalize_timestamps_to_seconds({5000});
  return result.size() == 1 && std::abs(result[0] - 5.0) < 0.01;
}

// ---------------------------------------------------------------------------
// False-pass tightening tests (round 3)
// ---------------------------------------------------------------------------

static bool routing_score_quality() {
  // channel_score formula is inverted: latency/reliability*(10-priority)
  // Higher latency → higher score (wrong). Good route should score better.
  // Good route: low latency, high reliability, high priority
  double good = channel_score(5, 0.9, 8);
  // Bad route: high latency, low reliability, low priority
  double bad = channel_score(50, 0.1, 1);
  // Good route should have BETTER (higher) score than bad route
  return good > bad;
}

static bool routing_active_exact() {
  // count_active_routes adds index i to latency (bug: effective = latency + i)
  // Two routes with latency 9, max_latency=10:
  //   Buggy: effective[0]=9+0=9 (<10 ✓), effective[1]=9+1=10 (<10 ✗) → returns 1
  //   Correct: both latency 9 < 10 → returns 2
  std::vector<Route> routes = {{"a", 9}, {"b", 9}};
  int count = count_active_routes(routes, 10);
  return count == 2;
}

static bool routing_weighted_cost() {
  // weighted_route_score(lat, rel, cost, w_lat, w_rel, w_cost)
  // Bug: ignores w_cost, just adds raw cost
  // Expected: 10*1.0 + 0.8*1.0 + 5.0*2.0 = 20.8
  // Buggy:    10*1.0 + 0.8*1.0 + 5.0     = 15.8
  double score = weighted_route_score(10, 0.8, 5.0, 1.0, 1.0, 2.0);
  return std::abs(score - 20.8) < 0.01;
}

static bool resilience_trip_at_thresh() {
  // should_trip_breaker uses > instead of >=
  // ratio = 50/100 = 0.5, threshold = 0.5
  // Correct (>=): 0.5 >= 0.5 = true
  // Buggy (>):    0.5 > 0.5 = false
  return should_trip_breaker(50, 100, 0.5);
}

static bool resilience_duration_diff() {
  // state_duration_ms(entered_at, now_ms) should return now_ms - entered_at
  // Bug: returns entered_at (100) instead of duration (400)
  long long duration = state_duration_ms(100, 500);
  return duration == 400;
}

static bool resilience_window_check() {
  // in_failure_window(last_failure, now, window): check if within failure window
  // Last failure at 90ms, now at 100ms, window 20ms → 10ms since failure < 20ms window → IN window
  // Bug: uses > (outside window check) instead of < (inside window check)
  // Buggy: (100-90) > 20 → false; Correct: (100-90) < 20 → true
  return in_failure_window(90, 100, 20);
}

static bool resilience_halfopen_scales() {
  // half_open_max_calls(failure_count) always returns 3 regardless of input
  // With failure_count=10, should return something > 3 (e.g. scaled by failures)
  int calls = half_open_max_calls(10);
  return calls > 3;
}

static bool resilience_ckpt_scales() {
  // checkpoint_interval(event_count, base_interval) always returns base_interval
  // With event_count=5000, base=100, should scale up (e.g. 5000 events need wider interval)
  int interval = checkpoint_interval(5000, 100);
  return interval != 100;
}

static bool stats_z_zero_stddev() {
  // z_score with tiny stddev returns raw value instead of 0.0
  // Bug: if (stddev <= 0.0001) return value; — returns 10.0 instead of 0.0
  double z = z_score(10.0, 5.0, 0.00001);
  return std::abs(z) < 0.01;
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
  else if (name == "allocator_weighted") ok = allocator_weighted();
  else if (name == "allocator_berth_utilization") ok = allocator_berth_utilization();
  else if (name == "allocator_rounding") ok = allocator_rounding();
  else if (name == "allocator_cost_per_unit") ok = allocator_cost_per_unit();
  else if (name == "allocator_normalize_urgency") ok = allocator_normalize_urgency();
  else if (name == "allocator_priority_score") ok = allocator_priority_score();
  else if (name == "allocator_over_capacity") ok = allocator_over_capacity();
  // Routing tests
  else if (name == "routing_blocked") ok = routing_blocked();
  else if (name == "routing_channel_score") ok = routing_channel_score();
  else if (name == "routing_transit_time") ok = routing_transit_time();
  else if (name == "routing_multi_leg") ok = routing_multi_leg();
  else if (name == "routing_table") ok = routing_table();
  else if (name == "routing_cost") ok = routing_cost();
  else if (name == "routing_weighted_score") ok = routing_weighted_score();
  else if (name == "routing_best_route") ok = routing_best_route();
  else if (name == "routing_failover") ok = routing_failover();
  else if (name == "routing_distance") ok = routing_distance();
  else if (name == "routing_normalize_latency") ok = routing_normalize_latency();
  else if (name == "routing_fuel_efficiency") ok = routing_fuel_efficiency();
  else if (name == "routing_total_fees") ok = routing_total_fees();
  else if (name == "routing_knots_conversion") ok = routing_knots_conversion();
  else if (name == "routing_penalty") ok = routing_penalty();
  // Policy tests
  else if (name == "policy_escalation") ok = policy_escalation();
  else if (name == "policy_deescalation") ok = policy_deescalation();
  else if (name == "policy_engine_lifecycle") ok = policy_engine_lifecycle();
  else if (name == "policy_sla") ok = policy_sla();
  else if (name == "policy_sla_percentage") ok = policy_sla_percentage();
  else if (name == "policy_metadata") ok = policy_metadata();
  else if (name == "policy_weight_ordering") ok = policy_weight_ordering();
  else if (name == "policy_escalation_threshold") ok = policy_escalation_threshold();
  else if (name == "policy_risk_score") ok = policy_risk_score();
  else if (name == "policy_grace_period") ok = policy_grace_period();
  else if (name == "policy_retries_default") ok = policy_retries_default();
  else if (name == "policy_cooldown") ok = policy_cooldown();
  // Queue tests
  else if (name == "queue_hard_limit") ok = queue_hard_limit();
  else if (name == "queue_priority") ok = queue_priority();
  else if (name == "queue_drain") ok = queue_drain();
  else if (name == "queue_health_check") ok = queue_health_check();
  else if (name == "queue_wait_estimation") ok = queue_wait_estimation();
  else if (name == "queue_batch_enqueue") ok = queue_batch_enqueue();
  else if (name == "queue_priority_boost") ok = queue_priority_boost();
  else if (name == "queue_fairness") ok = queue_fairness();
  else if (name == "queue_requeue") ok = queue_requeue();
  else if (name == "queue_weighted_wait") ok = queue_weighted_wait();
  else if (name == "queue_pressure_ratio") ok = queue_pressure_ratio();
  else if (name == "queue_drain_pct") ok = queue_drain_pct();
  // Security tests
  else if (name == "security_signature") ok = security_signature();
  else if (name == "security_manifest") ok = security_manifest();
  else if (name == "security_path_sanitise") ok = security_path_sanitise();
  else if (name == "security_origin") ok = security_origin();
  else if (name == "security_token_format") ok = security_token_format();
  else if (name == "security_password_strength") ok = security_password_strength();
  else if (name == "security_masking") ok = security_masking();
  else if (name == "security_hmac") ok = security_hmac();
  else if (name == "security_rate_limit_key") ok = security_rate_limit_key();
  else if (name == "security_session_expiry") ok = security_session_expiry();
  else if (name == "security_header_sanitize") ok = security_header_sanitize();
  else if (name == "security_permissions") ok = security_permissions();
  else if (name == "security_ip_allowlist") ok = security_ip_allowlist();
  else if (name == "security_password_hash") ok = security_password_hash();
  // Resilience tests
  else if (name == "replay_latest") ok = replay_latest();
  else if (name == "replay_convergence") ok = replay_convergence();
  else if (name == "resilience_checkpoint") ok = resilience_checkpoint();
  else if (name == "resilience_circuit_breaker") ok = resilience_circuit_breaker();
  else if (name == "resilience_dedup") ok = resilience_dedup();
  else if (name == "resilience_replay_window") ok = resilience_replay_window();
  else if (name == "resilience_event_ordering") ok = resilience_event_ordering();
  else if (name == "resilience_idempotent") ok = resilience_idempotent();
  else if (name == "resilience_compact") ok = resilience_compact();
  else if (name == "resilience_retry_backoff") ok = resilience_retry_backoff();
  else if (name == "resilience_should_trip") ok = resilience_should_trip();
  else if (name == "resilience_jitter") ok = resilience_jitter();
  else if (name == "resilience_half_open_calls") ok = resilience_half_open_calls();
  else if (name == "resilience_failure_window") ok = resilience_failure_window();
  else if (name == "resilience_recovery_rate") ok = resilience_recovery_rate();
  else if (name == "resilience_checkpoint_interval") ok = resilience_checkpoint_interval();
  else if (name == "resilience_degradation") ok = resilience_degradation();
  else if (name == "resilience_bulkhead") ok = resilience_bulkhead();
  else if (name == "resilience_state_duration") ok = resilience_state_duration();
  else if (name == "resilience_fallback") ok = resilience_fallback();
  else if (name == "resilience_cascade") ok = resilience_cascade();
  // Statistics tests
  else if (name == "percentile_sparse") ok = percentile_sparse();
  else if (name == "stats_descriptive") ok = stats_descriptive();
  else if (name == "stats_variance") ok = stats_variance();
  else if (name == "stats_response_tracker") ok = stats_response_tracker();
  else if (name == "stats_moving_average") ok = stats_moving_average();
  else if (name == "stats_heatmap") ok = stats_heatmap();
  else if (name == "stats_weighted_mean") ok = stats_weighted_mean();
  else if (name == "stats_ema") ok = stats_ema();
  else if (name == "stats_min_max_normalize") ok = stats_min_max_normalize();
  else if (name == "stats_covariance") ok = stats_covariance();
  else if (name == "stats_correlation") ok = stats_correlation();
  else if (name == "stats_sum_of_squares") ok = stats_sum_of_squares();
  else if (name == "stats_iqr") ok = stats_iqr();
  else if (name == "stats_rate_of_change") ok = stats_rate_of_change();
  else if (name == "stats_z_score") ok = stats_z_score();
  // Workflow tests
  else if (name == "workflow_graph") ok = workflow_graph();
  else if (name == "workflow_shortest_path") ok = workflow_shortest_path();
  else if (name == "workflow_engine") ok = workflow_engine();
  else if (name == "workflow_terminal") ok = workflow_terminal();
  else if (name == "workflow_audit") ok = workflow_audit();
  else if (name == "workflow_transition_count") ok = workflow_transition_count();
  else if (name == "workflow_time_in_state") ok = workflow_time_in_state();
  else if (name == "workflow_parallel_count") ok = workflow_parallel_count();
  else if (name == "workflow_state_distribution") ok = workflow_state_distribution();
  else if (name == "workflow_bottleneck") ok = workflow_bottleneck();
  else if (name == "workflow_completion_pct") ok = workflow_completion_pct();
  else if (name == "workflow_cancel_from_any") ok = workflow_cancel_from_any();
  else if (name == "workflow_estimated_completion") ok = workflow_estimated_completion();
  else if (name == "workflow_state_age") ok = workflow_state_age();
  else if (name == "workflow_batch_register") ok = workflow_batch_register();
  else if (name == "workflow_valid_path") ok = workflow_valid_path();
  else if (name == "workflow_throughput") ok = workflow_throughput();
  else if (name == "workflow_chain_length") ok = workflow_chain_length();
  else if (name == "workflow_merge_histories") ok = workflow_merge_histories();
  // Model tests
  else if (name == "model_urgency") ok = model_urgency();
  else if (name == "model_vessel_manifest") ok = model_vessel_manifest();
  else if (name == "model_batch_creation") ok = model_batch_creation();
  else if (name == "model_validation") ok = model_validation();
  else if (name == "model_classify_severity") ok = model_classify_severity();
  else if (name == "model_severity_label") ok = model_severity_label();
  else if (name == "model_weight_class") ok = model_weight_class();
  else if (name == "model_crew_estimation") ok = model_crew_estimation();
  else if (name == "model_hazmat_surcharge") ok = model_hazmat_surcharge();
  else if (name == "model_eta") ok = model_eta();
  // Contract tests
  else if (name == "contracts_exposed") ok = contracts_exposed();
  else if (name == "contracts_service_defs") ok = contracts_service_defs();
  else if (name == "contracts_url") ok = contracts_url();
  else if (name == "contracts_validation") ok = contracts_validation();
  else if (name == "contracts_topo_order") ok = contracts_topo_order();
  else if (name == "contracts_health_endpoint") ok = contracts_health_endpoint();
  else if (name == "contracts_dependency_depth") ok = contracts_dependency_depth();
  else if (name == "contracts_critical_path") ok = contracts_critical_path();
  else if (name == "contracts_port_collision") ok = contracts_port_collision();
  else if (name == "contracts_summary_format") ok = contracts_summary_format();
  // Config tests
  else if (name == "config_defaults") ok = config_defaults();
  else if (name == "config_validate") ok = config_validate();
  else if (name == "config_endpoint_validation") ok = config_endpoint_validation();
  else if (name == "config_env_normalization") ok = config_env_normalization();
  else if (name == "config_feature_flags") ok = config_feature_flags();
  else if (name == "config_priority_ordering") ok = config_priority_ordering();
  // Concurrency tests
  else if (name == "concurrency_barrier") ok = concurrency_barrier();
  else if (name == "concurrency_merge_counts") ok = concurrency_merge_counts();
  else if (name == "concurrency_partition") ok = concurrency_partition();
  else if (name == "concurrency_atomic_counter") ok = concurrency_atomic_counter();
  else if (name == "concurrency_registry") ok = concurrency_registry();
  else if (name == "concurrency_fan_out_merge") ok = concurrency_fan_out_merge();
  else if (name == "concurrency_cycle_detection") ok = concurrency_cycle_detection();
  else if (name == "concurrency_work_stealing") ok = concurrency_work_stealing();
  // Events tests
  else if (name == "events_time_sorting") ok = events_time_sorting();
  else if (name == "events_dedup") ok = events_dedup();
  else if (name == "events_time_window") ok = events_time_window();
  else if (name == "events_count_by_kind") ok = events_count_by_kind();
  else if (name == "events_log_eviction") ok = events_log_eviction();
  else if (name == "events_gap_detection") ok = events_gap_detection();
  else if (name == "events_batch_by_time") ok = events_batch_by_time();
  else if (name == "events_rate") ok = events_rate();
  // Telemetry tests
  else if (name == "telemetry_error_rate") ok = telemetry_error_rate();
  else if (name == "telemetry_latency_bucket") ok = telemetry_latency_bucket();
  else if (name == "telemetry_throughput") ok = telemetry_throughput();
  else if (name == "telemetry_health_score") ok = telemetry_health_score();
  else if (name == "telemetry_threshold_check") ok = telemetry_threshold_check();
  else if (name == "telemetry_aggregate") ok = telemetry_aggregate();
  else if (name == "telemetry_uptime") ok = telemetry_uptime();
  else if (name == "telemetry_alerting") ok = telemetry_alerting();
  // Integration tests
  else if (name == "flow_integration") ok = flow_integration();
  else if (name == "end_to_end_dispatch") ok = end_to_end_dispatch();
  else if (name == "config_registry_workflow") ok = config_registry_workflow();
  else if (name == "event_driven_workflow") ok = event_driven_workflow();
  else if (name == "telemetry_collection_flow") ok = telemetry_collection_flow();
  // Latent bug tests
  else if (name == "latent_accumulated_utilization") ok = latent_accumulated_utilization();
  else if (name == "latent_active_route_count") ok = latent_active_route_count();
  else if (name == "latent_transition_key") ok = latent_transition_key();
  else if (name == "latent_token_expiry_spread") ok = latent_token_expiry_spread();
  // Domain logic bug tests
  else if (name == "domain_berth_fee") ok = domain_berth_fee();
  else if (name == "domain_sla_breach") ok = domain_sla_breach();
  else if (name == "domain_weather_eta") ok = domain_weather_eta();
  else if (name == "domain_hazmat_crew") ok = domain_hazmat_crew();
  // Multi-step bug tests
  else if (name == "multistep_normalize_timestamps") ok = multistep_normalize_timestamps();
  else if (name == "multistep_event_bursts") ok = multistep_event_bursts();
  else if (name == "multistep_reliability_score") ok = multistep_reliability_score();
  else if (name == "multistep_select_reliable") ok = multistep_select_reliable();
  // State machine bug tests
  else if (name == "statemachine_escalation_cooldown") ok = statemachine_escalation_cooldown();
  else if (name == "statemachine_transition_sequence") ok = statemachine_transition_sequence();
  else if (name == "statemachine_circuit_breaker_recovery") ok = statemachine_circuit_breaker_recovery();
  // Concurrency bug tests
  else if (name == "concurrency_safe_counter_overflow") ok = concurrency_safe_counter_overflow();
  else if (name == "concurrency_parallel_merge") ok = concurrency_parallel_merge();
  else if (name == "concurrency_queue_merge") ok = concurrency_queue_merge();
  else if (name == "concurrency_event_trim") ok = concurrency_event_trim();
  // Integration bug tests
  else if (name == "integration_dispatch_route_score") ok = integration_dispatch_route_score();
  else if (name == "integration_policy_queue_limit") ok = integration_policy_queue_limit();
  else if (name == "integration_health_composite") ok = integration_health_composite();
  else if (name == "integration_checkpoint_replay") ok = integration_checkpoint_replay();
  else if (name == "integration_priority_aging") ok = integration_priority_aging();
  else if (name == "integration_cascade_depth") ok = integration_cascade_depth();
  // False-pass detection tests
  else if (name == "resilience_jitter_variance") ok = resilience_jitter_variance();
  else if (name == "resilience_retry_with_jitter") ok = resilience_retry_with_jitter();
  else if (name == "stats_ema_asymmetric") ok = stats_ema_asymmetric();
  else if (name == "telemetry_health_asymmetric") ok = telemetry_health_asymmetric();
  else if (name == "stats_normalize_boundary") ok = stats_normalize_boundary();
  else if (name == "contracts_depth_transitive") ok = contracts_depth_transitive();
  else if (name == "concurrency_fan_out_by_key") ok = concurrency_fan_out_by_key();
  else if (name == "events_count_duplicates") ok = events_count_duplicates();
  else if (name == "config_endpoint_strict") ok = config_endpoint_strict();
  else if (name == "model_vessel_load") ok = model_vessel_load();
  // Targeted reinforcement tests
  else if (name == "resilience_bulkhead_nonexact") ok = resilience_bulkhead_nonexact();
  else if (name == "workflow_batch_invalid_state") ok = workflow_batch_invalid_state();
  else if (name == "model_crew_tons_matter") ok = model_crew_tons_matter();
  else if (name == "contracts_port_collision_gap") ok = contracts_port_collision_gap();
  else if (name == "events_merge_streams_order") ok = events_merge_streams_order();
  else if (name == "allocator_weighted_with_zero") ok = allocator_weighted_with_zero();
  else if (name == "allocator_berth_util_occupied") ok = allocator_berth_util_occupied();
  else if (name == "allocator_round_ceiling") ok = allocator_round_ceiling();
  else if (name == "allocator_cost_unit_exact") ok = allocator_cost_unit_exact();
  else if (name == "allocator_normalize_urg_exact") ok = allocator_normalize_urg_exact();
  else if (name == "routing_best_route_min_lat") ok = routing_best_route_min_lat();
  else if (name == "routing_failover_filtered") ok = routing_failover_filtered();
  else if (name == "routing_penalty_positive_val") ok = routing_penalty_positive_val();
  else if (name == "routing_normalize_lat_exact") ok = routing_normalize_lat_exact();
  else if (name == "routing_fuel_eff_correct") ok = routing_fuel_eff_correct();
  else if (name == "policy_risk_multiply") ok = policy_risk_multiply();
  else if (name == "policy_retries_by_level") ok = policy_retries_by_level();
  else if (name == "policy_cooldown_by_levels") ok = policy_cooldown_by_levels();
  else if (name == "queue_shed_emergency_ratio") ok = queue_shed_emergency_ratio();
  else if (name == "queue_batch_depth_limit") ok = queue_batch_depth_limit();
  else if (name == "queue_boost_with_interval") ok = queue_boost_with_interval();
  else if (name == "queue_requeue_with_penalty") ok = queue_requeue_with_penalty();
  else if (name == "queue_weighted_wait_factor") ok = queue_weighted_wait_factor();
  else if (name == "queue_pressure_with_rates") ok = queue_pressure_with_rates();
  else if (name == "queue_drain_pct_correct") ok = queue_drain_pct_correct();
  else if (name == "security_token_order") ok = security_token_order();
  else if (name == "security_mask_first") ok = security_mask_first();
  else if (name == "security_rate_key_ip_first") ok = security_rate_key_ip_first();
  else if (name == "security_session_ms") ok = security_session_ms();
  else if (name == "security_header_cr") ok = security_header_cr();
  else if (name == "security_perms_subset") ok = security_perms_subset();
  else if (name == "resilience_idempotent_method") ok = resilience_idempotent_method();
  else if (name == "resilience_compact_last") ok = resilience_compact_last();
  else if (name == "resilience_recovery_correct") ok = resilience_recovery_correct();
  else if (name == "resilience_degradation_mult") ok = resilience_degradation_mult();
  else if (name == "resilience_fallback_primary") ok = resilience_fallback_primary();
  else if (name == "stats_weighted_mean_denom") ok = stats_weighted_mean_denom();
  else if (name == "stats_covariance_centered") ok = stats_covariance_centered();
  else if (name == "stats_correlation_bivariate") ok = stats_correlation_bivariate();
  else if (name == "stats_sum_sq_deviation") ok = stats_sum_sq_deviation();
  else if (name == "stats_rate_change_interval") ok = stats_rate_change_interval();
  else if (name == "workflow_transition_entity") ok = workflow_transition_entity();
  else if (name == "workflow_time_ms_to_hours") ok = workflow_time_ms_to_hours();
  else if (name == "workflow_parallel_active") ok = workflow_parallel_active();
  else if (name == "workflow_completion_correct") ok = workflow_completion_correct();
  else if (name == "workflow_throughput_rate") ok = workflow_throughput_rate();
  else if (name == "telemetry_error_ratio") ok = telemetry_error_ratio();
  else if (name == "telemetry_throughput_sec") ok = telemetry_throughput_sec();
  else if (name == "telemetry_uptime_calc") ok = telemetry_uptime_calc();
  else if (name == "telemetry_alert_direction") ok = telemetry_alert_direction();
  else if (name == "events_dedup_first") ok = events_dedup_first();
  else if (name == "events_window_inclusive") ok = events_window_inclusive();
  else if (name == "events_normalize_divisor") ok = events_normalize_divisor();
  // False-pass tightening tests (round 3)
  else if (name == "routing_score_quality") ok = routing_score_quality();
  else if (name == "routing_active_exact") ok = routing_active_exact();
  else if (name == "routing_weighted_cost") ok = routing_weighted_cost();
  else if (name == "resilience_trip_at_thresh") ok = resilience_trip_at_thresh();
  else if (name == "resilience_duration_diff") ok = resilience_duration_diff();
  else if (name == "resilience_window_check") ok = resilience_window_check();
  else if (name == "resilience_halfopen_scales") ok = resilience_halfopen_scales();
  else if (name == "resilience_ckpt_scales") ok = resilience_ckpt_scales();
  else if (name == "stats_z_zero_stddev") ok = stats_z_zero_stddev();
  // Hyper-matrix
  else if (name == "hyper_matrix") ok = hyper_matrix();
  else {
    std::cerr << "unknown test: " << name << std::endl;
    return 2;
  }

  return ok ? 0 : 1;
}
