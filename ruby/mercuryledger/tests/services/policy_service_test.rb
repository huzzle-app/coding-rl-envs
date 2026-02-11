# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/policy/service'

class PolicyServiceTest < Minitest::Test
  def test_evaluate_policy_gate_deny_high_risk
    result = MercuryLedger::Services::Policy.evaluate_policy_gate(0.95, false, true, 3)
    assert_equal :deny, result
  end

  def test_enforce_dual_control_requires_different_ops
    assert MercuryLedger::Services::Policy.enforce_dual_control('alice', 'bob')
    refute MercuryLedger::Services::Policy.enforce_dual_control('alice', 'alice')
  end

  def test_risk_band_classification
    assert_equal :critical, MercuryLedger::Services::Policy.risk_band(0.95)
    assert_equal :high, MercuryLedger::Services::Policy.risk_band(0.75)
    assert_equal :minimal, MercuryLedger::Services::Policy.risk_band(0.1)
  end

  def test_compute_compliance_score_within_range
    score = MercuryLedger::Services::Policy.compute_compliance_score(80, 100, 0.9)
    assert_operator score, :>, 0
    assert_operator score, :<=, 2.0
  end
end
