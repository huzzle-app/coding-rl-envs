# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/policy/service'

class PolicyServiceTest < Minitest::Test
  def test_evaluate_policy_gate_allows_low_risk
    decision = OpalCommand::Services::Policy.evaluate_policy_gate(risk_score: 20, comms_degraded: false, has_mfa: true)
    assert decision.approved
    assert_equal 'allow', decision.action
  end

  def test_evaluate_policy_gate_denies_no_mfa
    decision = OpalCommand::Services::Policy.evaluate_policy_gate(risk_score: 20, comms_degraded: false, has_mfa: false)
    refute decision.approved
    assert_equal 'no_mfa', decision.reason
  end

  def test_risk_band_classification
    assert_equal 'critical', OpalCommand::Services::Policy.risk_band(95)
    assert_equal 'low', OpalCommand::Services::Policy.risk_band(15)
  end

  def test_compute_compliance_score
    score = OpalCommand::Services::Policy.compute_compliance_score(incidents_resolved: 90, incidents_total: 100, sla_met_pct: 85)
    assert_operator score, :>, 0
    assert_operator score, :<=, 1.0
  end
end
