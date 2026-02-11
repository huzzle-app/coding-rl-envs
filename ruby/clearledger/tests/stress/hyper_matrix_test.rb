# frozen_string_literal: true

require_relative '../test_helper'
require 'set'

class HyperMatrixTest < Minitest::Test
  TOTAL_CASES = 1160

  TOTAL_CASES.times do |idx|
    define_method("test_hyper_matrix_#{format('%05d', idx)}") do
      sev_a = (idx % 5) + 1
      sev_b = ((idx * 3) % 5) + 1
      delta_a = 10.0 + (idx % 40)
      delta_b = -(5.0 + (idx % 20))

      entries = [
        { account: "acct-#{idx % 7}", delta: delta_a },
        { account: "acct-#{(idx * 3) % 7}", delta: delta_b }
      ]
      net = ClearLedger::Core::Settlement.net_positions(entries)
      assert_kind_of Hash, net

      reserved = ClearLedger::Core::Settlement.apply_reserve(net, 0.05)
      reserved.each_value { |v| assert_kind_of Float, v }

      gross = ClearLedger::Core::Settlement.gross_exposure(entries)
      assert gross >= 0.0

      fee = ClearLedger::Core::Settlement.settlement_fee(delta_a * 100, 'standard')
      assert fee >= 0.0

      netting = ClearLedger::Core::Settlement.netting_ratio(gross, net.values.sum.abs)
      assert netting >= 0.0

      tolerance = 5 + (idx % 20)
      mismatch = ClearLedger::Core::Reconciliation.mismatch?(delta_a, delta_a * 0.999, tolerance)
      refute mismatch if tolerance >= 15

      sig = ClearLedger::Core::Reconciliation.replay_signature("batch-#{idx}", idx)
      assert sig.include?(':v')

      drift = ClearLedger::Core::Reconciliation.drift_score([1.0, 2.0, 3.0, 4.0])
      assert drift >= 0.0

      age = ClearLedger::Core::Reconciliation.age_seconds(1000, 1100)
      assert age >= 0

      from = idx % 2 == 0 ? :drafted : :validated
      to = from == :drafted ? :validated : :risk_checked
      assert ClearLedger::Core::Workflow.transition_allowed?(from, to)
      refute ClearLedger::Core::Workflow.transition_allowed?(:reported, :drafted)

      assert ClearLedger::Core::Workflow.terminal_state?(:reported)
      assert ClearLedger::Core::Workflow.terminal_state?(:canceled)
      refute ClearLedger::Core::Workflow.terminal_state?(:drafted)

      reachable = ClearLedger::Core::Workflow.reachable_states(:drafted)
      assert reachable.include?(:reported)

      backoff = ClearLedger::Core::Resilience.retry_backoff_ms(1 + (idx % 4), 50)
      assert backoff >= 50

      events = [
        ClearLedger::Core::Resilience::Event.new(version: 10 + idx % 5, idempotency_key: "k-#{idx % 13}", gross_delta: 3, net_delta: 1),
        ClearLedger::Core::Resilience::Event.new(version: 11 + idx % 5, idempotency_key: "k-#{(idx + 1) % 13}", gross_delta: -1, net_delta: 0)
      ]
      snap = ClearLedger::Core::Resilience.replay_state(100.0, 50.0, 10, events)
      assert snap.applied >= 1

      hs = ClearLedger::Core::Resilience.health_score(7, 3)
      assert hs >= 0.6 && hs <= 0.8

      impact = ClearLedger::Core::Resilience.partition_impact(3, 10)
      assert impact >= 0.2 && impact <= 0.4

      hub = ClearLedger::Core::Routing.best_hub({ 'east' => 10 + idx % 5, 'west' => 15 + idx % 3 })
      assert_kind_of String, hub

      part = ClearLedger::Core::Routing.deterministic_partition("tenant-#{idx}", 8)
      assert part >= 0 && part < 8

      congestion = ClearLedger::Core::Routing.congestion_score(80, 100)
      assert congestion >= 0.7 && congestion <= 0.9

      policy = ClearLedger::Core::QueuePolicy.next_policy(idx % 8)
      assert policy.key?(:max_inflight)

      bp = ClearLedger::Core::QueuePolicy.backpressure_level(80, 100)
      assert_equal 'high', bp

      throttle = ClearLedger::Core::QueuePolicy.should_throttle?(100.0, 100.0)
      assert throttle

      bucket = idx % 20

      if bucket == 0
        assert_in_delta 0.75, ClearLedger::Core::Settlement.netting_ratio(100.0, 75.0), 1e-9
      elsif bucket == 1
        assert_equal 2, ClearLedger::Core::Reconciliation.break_count([1, 2, 3, 4, 5], [1, 2, 6, 4, 7])
      elsif bucket == 2
        assert_in_delta 80.0, ClearLedger::Core::Compliance.compliance_score(80, 100), 1e-9
      elsif bucket == 3
        assert_equal 180, ClearLedger::Core::Compliance.max_retention_days(:warm)
      elsif bucket == 4
        ratio = ClearLedger::Core::RiskGate.exposure_ratio(75.0, 10.0)
        assert_in_delta 7.5, ratio, 1e-9
      elsif bucket == 5
        assert_equal :high, ClearLedger::Core::RiskGate.risk_tier(5.0)
      elsif bucket == 6
        assert ClearLedger::Core::Workflow.terminal_state?(:canceled)
      elsif bucket == 7
        entities = [:reported, :canceled, :drafted, :validated]
        assert_equal 2, ClearLedger::Core::Workflow.pending_count(entities)
      elsif bucket == 8
        candidates = ClearLedger::Core::Resilience.failover_candidates(%w[a b c], %w[b])
        assert_equal %w[a c], candidates
      elsif bucket == 9
        assert_equal 60, ClearLedger::Core::Authz.access_level(:reviewer)
      elsif bucket == 10
        assert ClearLedger::Core::Authz.requires_mfa?('approve')
      elsif bucket == 11
        assert_equal 'hello world', ClearLedger::Core::Authz.sanitise_input("hello' world")
      elsif bucket == 12
        assert_equal 3, ClearLedger::Core::Authz.role_hierarchy_rank(:admin)
      elsif bucket == 13
        assert_equal [1, 2, 3], ClearLedger::Core::QueuePolicy.drain_batch([1, 2, 3, 4, 5], 3)
      elsif bucket == 14
        assert_in_delta 80.0, ClearLedger::Core::SLA.sla_compliance_rate(80, 100), 1e-9
      elsif bucket == 15
        assert_equal 120, ClearLedger::Core::SLA.sla_buffer(100)
      elsif bucket == 16
        assert ClearLedger::Core::SLA.sla_met?(60, 60)
      elsif bucket == 17
        score = ClearLedger::Core::AuditChain.audit_score(7, 10)
        assert_in_delta 0.7, score, 1e-9
      elsif bucket == 18
        assert ClearLedger::Core::LedgerWindow.event_in_window?(100, 50, 150)
        refute ClearLedger::Core::LedgerWindow.event_in_window?(150, 50, 150)
      elsif bucket == 19
        assert_equal 3, ClearLedger::Core::CommandRouter.command_priority('settle')
      end
    end
  end
end
