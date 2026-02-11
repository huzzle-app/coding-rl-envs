# frozen_string_literal: true

require_relative '../test_helper'

class RiskGateTest < Minitest::Test
  def test_limit_breached_uses_leverage_cap
    assert ClearLedger::Core::RiskGate.limit_breached?(120, 10, 10)
    refute ClearLedger::Core::RiskGate.limit_breached?(80, 10, 10)
  end

  def test_dynamic_buffer_clamps_floor_and_cap
    assert_in_delta 0.08, ClearLedger::Core::RiskGate.dynamic_buffer(1.5, 0.06, 0.20), 1e-9
    assert_in_delta 0.06, ClearLedger::Core::RiskGate.dynamic_buffer(-5, 0.06, 0.20), 1e-9
    assert_in_delta 0.20, ClearLedger::Core::RiskGate.dynamic_buffer(30, 0.06, 0.20), 1e-9
  end

  def test_throttle_required
    assert ClearLedger::Core::RiskGate.throttle_required?(9, 3, 12)
    refute ClearLedger::Core::RiskGate.throttle_required?(8, 3, 12)
  end
end
