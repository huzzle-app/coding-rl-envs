# frozen_string_literal: true

require_relative '../test_helper'

class ExtendedTest < Minitest::Test
  def test_netting_ratio_as_float
    ratio = ClearLedger::Core::Settlement.netting_ratio(100.0, 75.0)
    assert_in_delta 0.75, ratio, 1e-9
  end

  def test_settlement_fee_premium_rate
    assert_in_delta 20.0, ClearLedger::Core::Settlement.settlement_fee(10_000, 'premium'), 1e-9
  end

  def test_priority_settlement_boundary
    assert ClearLedger::Core::Settlement.priority_settlement?(3, 100_001)
  end

  def test_break_count_finds_mismatches
    assert_equal 2, ClearLedger::Core::Reconciliation.break_count([1, 2, 3, 4, 5], [1, 2, 6, 4, 7])
  end

  def test_age_seconds_positive
    assert_equal 100, ClearLedger::Core::Reconciliation.age_seconds(1000, 1100)
  end

  def test_compliance_score_as_percentage
    assert_in_delta 80.0, ClearLedger::Core::Compliance.compliance_score(80, 100), 1e-9
  end

  def test_max_retention_warm_is_180
    assert_equal 180, ClearLedger::Core::Compliance.max_retention_days(:warm)
  end

  def test_exposure_ratio_as_float
    assert_in_delta 7.5, ClearLedger::Core::RiskGate.exposure_ratio(75.0, 10.0), 1e-9
  end

  def test_risk_tier_boundary
    assert_equal :high, ClearLedger::Core::RiskGate.risk_tier(5.0)
  end

  def test_concentration_risk_as_ratio
    assert_in_delta 0.5, ClearLedger::Core::RiskGate.concentration_risk([10, 30, 20]), 1e-9
  end

  def test_terminal_state_includes_canceled
    assert ClearLedger::Core::Workflow.terminal_state?(:canceled)
    assert ClearLedger::Core::Workflow.terminal_state?(:reported)
  end

  def test_pending_count_excludes_terminal
    entities = [:reported, :canceled, :drafted, :validated]
    assert_equal 2, ClearLedger::Core::Workflow.pending_count(entities)
  end

  def test_health_score_as_float
    assert_in_delta 0.7, ClearLedger::Core::Resilience.health_score(7, 3), 1e-9
  end

  def test_partition_impact_ratio
    assert_in_delta 0.3, ClearLedger::Core::Resilience.partition_impact(3, 10), 1e-9
  end

  def test_failover_excludes_degraded
    assert_equal %w[a c], ClearLedger::Core::Resilience.failover_candidates(%w[a b c], %w[b])
  end

  def test_access_level_reviewer
    assert_equal 60, ClearLedger::Core::Authz.access_level(:reviewer)
  end

  def test_requires_mfa_for_approve
    assert ClearLedger::Core::Authz.requires_mfa?('approve')
  end

  def test_sanitise_input_removes_single_quotes
    assert_equal 'hello world', ClearLedger::Core::Authz.sanitise_input("hello' world")
  end

  def test_role_hierarchy_admin_is_3
    assert_equal 3, ClearLedger::Core::Authz.role_hierarchy_rank(:admin)
  end

  def test_backpressure_level_high
    assert_equal 'high', ClearLedger::Core::QueuePolicy.backpressure_level(80, 100)
  end

  def test_should_throttle_at_limit
    assert ClearLedger::Core::QueuePolicy.should_throttle?(100.0, 100.0)
  end

  def test_drain_batch_exact_count
    assert_equal [1, 2, 3], ClearLedger::Core::QueuePolicy.drain_batch([1, 2, 3, 4, 5], 3)
  end

  def test_sla_buffer_adds_time
    assert_equal 120, ClearLedger::Core::SLA.sla_buffer(100)
  end

  def test_sla_met_at_boundary
    assert ClearLedger::Core::SLA.sla_met?(60, 60)
  end

  def test_median_even_length
    assert_in_delta 2.5, ClearLedger::Core::Statistics.median([1, 2, 3, 4]), 1e-9
  end

  def test_audit_score_as_float
    assert_in_delta 0.7, ClearLedger::Core::AuditChain.audit_score(7, 10), 1e-9
  end
end
