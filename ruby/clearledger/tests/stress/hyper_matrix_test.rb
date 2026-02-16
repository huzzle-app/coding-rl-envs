# frozen_string_literal: true

require_relative '../test_helper'
require 'set'

class HyperMatrixTest < Minitest::Test
  TOTAL_CASES = 1160

  # 40 distinct bug-detecting assertion buckets.
  # Each test picks ONE bucket via idx % 40, so each bug is tested ~29 times.
  # This prevents fixing a single shallow bug from flipping 1000+ tests.

  TOTAL_CASES.times do |idx|
    define_method("test_hyper_matrix_#{format('%05d', idx)}") do
      delta_a = 10.0 + (idx % 40)
      delta_b = -(5.0 + (idx % 20))

      entries = [
        { account: "acct-#{idx % 7}", delta: delta_a },
        { account: "acct-#{(idx * 3) % 7}", delta: delta_b }
      ]

      # --- Common regression guards (these pass with current code) ---
      net = ClearLedger::Core::Settlement.net_positions(entries)
      assert_kind_of Hash, net

      reserved = ClearLedger::Core::Settlement.apply_reserve(net, 0.05)
      reserved.each_value { |v| assert_kind_of Float, v }

      gross = ClearLedger::Core::Settlement.gross_exposure(entries)
      assert gross >= 0.0

      sig = ClearLedger::Core::Reconciliation.replay_signature("batch-#{idx}", idx)
      assert sig.include?(':v')

      from = idx % 2 == 0 ? :drafted : :validated
      to = from == :drafted ? :validated : :risk_checked
      assert ClearLedger::Core::Workflow.transition_allowed?(from, to)
      refute ClearLedger::Core::Workflow.transition_allowed?(:reported, :drafted)

      reachable = ClearLedger::Core::Workflow.reachable_states(:drafted)
      assert reachable.include?(:reported)

      backoff = ClearLedger::Core::Resilience.retry_backoff_ms(1 + (idx % 4), 50)
      assert backoff >= 50

      part = ClearLedger::Core::Routing.deterministic_partition("tenant-#{idx}", 8)
      assert part >= 0 && part < 8

      policy = ClearLedger::Core::QueuePolicy.next_policy(idx % 8)
      assert policy.key?(:max_inflight)

      # --- Bug-detecting assertion: one per bucket (40 buckets) ---
      bucket = idx % 40

      case bucket
      when 0  # Settlement.netting_ratio: integer division → should be float
        assert_in_delta 0.75, ClearLedger::Core::Settlement.netting_ratio(100.0, 75.0), 1e-9
      when 1  # Reconciliation.break_count: returns matches instead of mismatches
        assert_equal 2, ClearLedger::Core::Reconciliation.break_count([1, 2, 3, 4, 5], [1, 2, 6, 4, 7])
      when 2  # Compliance.compliance_score: ratio instead of percentage
        assert_in_delta 80.0, ClearLedger::Core::Compliance.compliance_score(80, 100), 1e-9
      when 3  # Compliance.max_retention_days: warm returns 365 instead of 180
        assert_equal 180, ClearLedger::Core::Compliance.max_retention_days(:warm)
      when 4  # RiskGate.exposure_ratio: integer division
        assert_in_delta 7.5, ClearLedger::Core::RiskGate.exposure_ratio(75.0, 10.0), 1e-9
      when 5  # RiskGate.risk_tier: boundary error (> vs >=)
        assert_equal :high, ClearLedger::Core::RiskGate.risk_tier(5.0)
      when 6  # Workflow.terminal_state?: missing :canceled
        assert ClearLedger::Core::Workflow.terminal_state?(:canceled)
      when 7  # Workflow.pending_count: doesn't exclude :canceled
        entities = [:reported, :canceled, :drafted, :validated]
        assert_equal 2, ClearLedger::Core::Workflow.pending_count(entities)
      when 8  # Resilience.failover_candidates: selects degraded instead of healthy
        assert_equal %w[a c], ClearLedger::Core::Resilience.failover_candidates(%w[a b c], %w[b])
      when 9  # Authz.access_level: reviewer returns 50 instead of 60
        assert_equal 60, ClearLedger::Core::Authz.access_level(:reviewer)
      when 10 # Authz.requires_mfa?: missing 'approve'
        assert ClearLedger::Core::Authz.requires_mfa?('approve')
      when 11 # Authz.sanitise_input: missing single quote removal
        assert_equal 'hello world', ClearLedger::Core::Authz.sanitise_input("hello' world")
      when 12 # Authz.role_hierarchy_rank: admin returns 2 instead of 3
        assert_equal 3, ClearLedger::Core::Authz.role_hierarchy_rank(:admin)
      when 13 # QueuePolicy.drain_batch: off-by-one (batch_size + 1)
        assert_equal [1, 2, 3], ClearLedger::Core::QueuePolicy.drain_batch([1, 2, 3, 4, 5], 3)
      when 14 # SLA.sla_compliance_rate: ratio instead of percentage
        assert_in_delta 80.0, ClearLedger::Core::SLA.sla_compliance_rate(80, 100), 1e-9
      when 15 # SLA.sla_buffer: multiplies by 0.8 instead of 1.2
        assert_equal 120, ClearLedger::Core::SLA.sla_buffer(100)
      when 16 # SLA.sla_met?: < instead of <=
        assert ClearLedger::Core::SLA.sla_met?(60, 60)
      when 17 # AuditChain.audit_score: integer division
        assert_in_delta 0.7, ClearLedger::Core::AuditChain.audit_score(7, 10), 1e-9
      when 18 # LedgerWindow.event_in_window?: second condition wrong
        assert ClearLedger::Core::LedgerWindow.event_in_window?(100, 50, 150)
        refute ClearLedger::Core::LedgerWindow.event_in_window?(150, 50, 150)
      when 19 # CommandRouter.command_priority: missing 'settle' case
        assert_equal 3, ClearLedger::Core::CommandRouter.command_priority('settle')
      when 20 # Reconciliation.age_seconds: inverted subtraction
        age = ClearLedger::Core::Reconciliation.age_seconds(1000, 1100)
        assert age >= 0, "age_seconds should return positive value, got #{age}"
        assert_equal 100, age
      when 21 # Resilience.health_score: integer division
        hs = ClearLedger::Core::Resilience.health_score(7, 3)
        assert_in_delta 0.7, hs, 1e-9
      when 22 # Resilience.partition_impact: inverted division
        impact = ClearLedger::Core::Resilience.partition_impact(3, 10)
        assert_in_delta 0.3, impact, 1e-9
      when 23 # Routing.congestion_score: inverted division
        congestion = ClearLedger::Core::Routing.congestion_score(80, 100)
        assert_in_delta 0.8, congestion, 1e-9
      when 24 # QueuePolicy.backpressure_level: wrong threshold for critical
        assert_equal 'high', ClearLedger::Core::QueuePolicy.backpressure_level(80, 100)
      when 25 # QueuePolicy.should_throttle?: > instead of >=
        assert ClearLedger::Core::QueuePolicy.should_throttle?(100.0, 100.0)
      when 26 # Resilience.checkpoint_age: inverted subtraction
        age = ClearLedger::Core::Resilience.checkpoint_age(1000, 2000)
        assert_equal 1000, age
      when 27 # AuditChain.entry_age: inverted subtraction
        age = ClearLedger::Core::AuditChain.entry_age(1000, 2000)
        assert_equal 1000, age
      when 28 # Routing.feasible_routes: selects infeasible routes
        routes = { 'a' => 50, 'b' => 150, 'c' => 200 }
        feasible = ClearLedger::Core::Routing.feasible_routes(routes, 100)
        assert feasible.key?('a'), 'Route under max_latency should be feasible'
        refute feasible.key?('c'), 'Route over max_latency should not be feasible'
      when 29 # Settlement.settlement_fee: wrong premium rate
        assert_in_delta 20.0, ClearLedger::Core::Settlement.settlement_fee(10_000, 'premium'), 1e-9
      when 30 # Settlement.priority_settlement?: boundary error (> vs >=)
        assert ClearLedger::Core::Settlement.priority_settlement?(3, 100_001)
      when 31 # RiskGate.concentration_risk: returns max instead of ratio
        assert_in_delta 0.5, ClearLedger::Core::RiskGate.concentration_risk([10, 30, 20]), 1e-9
      when 32 # Compliance.escalation_needed?: severity boundary (>= 4 vs >= 3)
        assert ClearLedger::Core::Compliance.escalation_needed?(3, 2)
      when 33 # Statistics.median: doesn't average for even-length
        assert_in_delta 2.5, ClearLedger::Core::Statistics.median([1, 2, 3, 4]), 1e-9
      when 34 # Statistics.exponential_moving_average: alpha weights wrong direction
        result = ClearLedger::Core::Statistics.exponential_moving_average([0, 100], 0.8)
        assert_in_delta 80.0, result[1], 1e-6
      when 35 # CommandRouter.requires_audit?: missing 'reconcile'
        assert ClearLedger::Core::CommandRouter.requires_audit?('reconcile')
      when 36 # Compliance.override_allowed?: threshold too strict (>= 12 vs >= 10)
        assert ClearLedger::Core::Compliance.override_allowed?('short reas', 2, 90)
      when 37 # LedgerWindow.late_event_policy: inverted grace period
        result = ClearLedger::Core::LedgerWindow.late_event_policy(105, 100, 10)
        assert_equal :accept, result
      when 38 # Routing.route_health_composite: missing normalization
        metrics = [
          { name: 'latency', value: 0.9, weight: 1.0 },
          { name: 'errors', value: 0.8, weight: 1.0 }
        ]
        score = ClearLedger::Core::Routing.route_health_composite(metrics)
        assert_in_delta 0.85, score, 1e-6
      when 39 # Workflow.shortest_path: finds longest instead of shortest
        path = ClearLedger::Core::Workflow.shortest_path(:drafted, :canceled)
        assert_equal [:drafted, :canceled], path
      end
    end
  end
end
