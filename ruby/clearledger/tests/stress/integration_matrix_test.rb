# frozen_string_literal: true

require_relative '../test_helper'

class IntegrationBugsMatrixTest < Minitest::Test
  # --- CommandRouter.route_with_risk_and_compliance ---
  # Bug: checks :submit permission for override instead of :override

  def test_operator_blocked_from_override
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'eu', 200_000, :operator, 100_000
    )
    assert_equal :blocked, result[:status]
    assert_equal 'override_not_authorized', result[:reason]
  end

  def test_admin_can_override
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'eu', 200_000, :admin, 100_000
    )
    assert_equal :routed, result[:status]
  end

  def test_no_override_needed_under_floor
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'us', 50_000, :operator, 100_000
    )
    assert_equal :routed, result[:status]
  end

  def test_reviewer_blocked_from_override
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'eu', 500_000, :reviewer, 100_000
    )
    assert_equal :blocked, result[:status]
  end

  def test_non_settle_action_no_override
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'reconcile', 'us', 999_999, :operator, 100_000
    )
    assert_equal :routed, result[:status]
  end

  def test_route_destination_correct_eu
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'eu', 50_000, :operator, 100_000
    )
    assert_equal 'settlement-eu', result[:destination]
  end

  def test_route_destination_correct_us
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'us', 50_000, :operator, 100_000
    )
    assert_equal 'settlement-us', result[:destination]
  end

  def test_exactly_at_override_floor_no_override
    result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
      'settle', 'eu', 100_000, :operator, 100_000
    )
    assert_equal :routed, result[:status]
  end

  5.times do |i|
    define_method("test_override_parametric_#{format('%03d', i)}") do
      amount = 100_001 + i * 50_000
      result = ClearLedger::Core::CommandRouter.route_with_risk_and_compliance(
        'settle', 'eu', amount, :operator, 100_000
      )
      assert_equal :blocked, result[:status]
    end
  end

  # --- AuditChain.audit_with_compliance ---
  # Bug: reject { |a| !found.include?(a) } keeps FOUND items instead of missing

  def test_audit_compliance_all_present
    entries = [{ action: 'settle' }, { action: 'override' }, { action: 'report' }]
    required = ['settle', 'override', 'report']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    assert result[:complete]
    assert_empty result[:missing]
  end

  def test_audit_compliance_one_missing
    entries = [{ action: 'settle' }, { action: 'report' }]
    required = ['settle', 'override', 'report']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    refute result[:complete]
    assert_equal ['override'], result[:missing]
  end

  def test_audit_compliance_all_missing
    entries = [{ action: 'other' }]
    required = ['settle', 'override']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    refute result[:complete]
    assert_includes result[:missing], 'settle'
    assert_includes result[:missing], 'override'
  end

  def test_audit_compliance_score_partial
    entries = [{ action: 'settle' }]
    required = ['settle', 'override']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    assert_in_delta 0.5, result[:score], 1e-6
  end

  def test_audit_compliance_score_full
    entries = [{ action: 'settle' }, { action: 'report' }]
    required = ['settle', 'report']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    assert_in_delta 1.0, result[:score], 1e-6
  end

  def test_audit_compliance_empty_entries
    entries = []
    required = ['settle']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    refute result[:complete]
    assert_equal ['settle'], result[:missing]
  end

  def test_audit_compliance_extra_entries_ignored
    entries = [{ action: 'settle' }, { action: 'report' }, { action: 'extra' }]
    required = ['settle', 'report']
    result = ClearLedger::Core::AuditChain.audit_with_compliance(entries, required)
    assert result[:complete]
  end

  # --- Compliance.multi_jurisdiction_check ---
  # Bug: uses any? instead of all? — entry passes if ANY jurisdiction passes

  def test_multi_jurisdiction_all_must_pass
    rules = {
      'EU' => [lambda { |e| e[:amount] < 10_000 }],
      'US' => [lambda { |e| e[:amount] < 5_000 }]
    }
    entry = { amount: 7_000 }
    refute ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
  end

  def test_multi_jurisdiction_all_pass
    rules = {
      'EU' => [lambda { |e| e[:amount] < 10_000 }],
      'US' => [lambda { |e| e[:amount] < 10_000 }]
    }
    entry = { amount: 5_000 }
    assert ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
  end

  def test_multi_jurisdiction_all_fail
    rules = {
      'EU' => [lambda { |e| e[:amount] < 100 }],
      'US' => [lambda { |e| e[:amount] < 100 }]
    }
    entry = { amount: 5_000 }
    refute ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
  end

  def test_multi_jurisdiction_single_jurisdiction
    rules = {
      'EU' => [lambda { |e| e[:amount] < 10_000 }]
    }
    entry = { amount: 5_000 }
    assert ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
  end

  def test_multi_jurisdiction_multiple_rules_per_jurisdiction
    rules = {
      'EU' => [
        lambda { |e| e[:amount] < 10_000 },
        lambda { |e| e[:currency] == 'EUR' }
      ]
    }
    entry = { amount: 5_000, currency: 'USD' }
    refute ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
  end

  def test_multi_jurisdiction_three_jurisdictions_one_fails
    rules = {
      'EU' => [lambda { |e| e[:amount] < 10_000 }],
      'US' => [lambda { |e| e[:amount] < 10_000 }],
      'UK' => [lambda { |e| e[:amount] < 1_000 }]
    }
    entry = { amount: 5_000 }
    refute ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
  end

  5.times do |i|
    define_method("test_multi_jurisdiction_parametric_#{format('%03d', i)}") do
      threshold_eu = 10_000
      threshold_us = 5_000 - i * 500
      amount = 4_500
      rules = {
        'EU' => [lambda { |e| e[:amount] < threshold_eu }],
        'US' => [lambda { |e| e[:amount] < threshold_us }]
      }
      entry = { amount: amount }
      if amount < threshold_us
        assert ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
      else
        refute ClearLedger::Core::Compliance.multi_jurisdiction_check(rules, entry)
      end
    end
  end
end
