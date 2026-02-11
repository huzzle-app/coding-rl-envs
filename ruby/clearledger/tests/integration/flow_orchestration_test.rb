# frozen_string_literal: true

require_relative '../test_helper'

class FlowOrchestrationTest < Minitest::Test
  def test_risk_and_compliance_gate_release
    exposure = 90.0
    collateral = 15.0
    cap = 8.0

    refute ClearLedger::Core::RiskGate.limit_breached?(exposure, collateral, cap)
    assert ClearLedger::Core::Compliance.override_allowed?('committee approved emergency release', 2, 60)
    assert ClearLedger::Core::Workflow.transition_allowed?(:risk_checked, :settled)
  end

  def test_settlement_pipeline_produces_expected_net
    entries = [
      { account: 'maker', delta: 20.0 },
      { account: 'maker', delta: -3.0 },
      { account: 'taker', delta: -4.0 }
    ]

    net = ClearLedger::Core::Settlement.net_positions(entries)
    reserved = ClearLedger::Core::Settlement.apply_reserve(net, 0.10)

    assert_in_delta 15.3, reserved['maker'], 1e-9
    assert_in_delta(-4.4, reserved['taker'], 1e-9)
  end
end
