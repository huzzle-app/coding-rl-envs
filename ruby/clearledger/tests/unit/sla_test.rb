# frozen_string_literal: true

require_relative '../test_helper'

class SlaTest < Minitest::Test
  def test_breach_risk_with_buffer
    assert ClearLedger::Core::SLA.breach_risk(980, 1000, 30)
    refute ClearLedger::Core::SLA.breach_risk(940, 1000, 30)
  end

  def test_jitter_budget_is_clamped
    assert_in_delta 0.06, ClearLedger::Core::SLA.jitter_budget(2.0, 0.06, 0.20), 1e-9
    assert_in_delta 0.20, ClearLedger::Core::SLA.jitter_budget(30.0, 0.06, 0.20), 1e-9
  end

  def test_breach_severity_levels
    assert_equal :none, ClearLedger::Core::SLA.breach_severity(900, 1000)
    assert_equal :minor, ClearLedger::Core::SLA.breach_severity(1100, 1000)
    assert_equal :major, ClearLedger::Core::SLA.breach_severity(1700, 1000)
    assert_equal :critical, ClearLedger::Core::SLA.breach_severity(2200, 1000)
  end
end
