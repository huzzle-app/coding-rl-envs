# frozen_string_literal: true

require_relative '../test_helper'

class SettlementTest < Minitest::Test
  def test_net_positions_aggregates_accounts
    entries = [
      { account: 'A', delta: 12.5 },
      { account: 'A', delta: -2.0 },
      { account: 'B', delta: 4.0 }
    ]

    result = ClearLedger::Core::Settlement.net_positions(entries)
    assert_in_delta 10.5, result['A'], 1e-9
    assert_in_delta 4.0, result['B'], 1e-9
  end

  def test_apply_reserve_reduces_exposure
    net = { 'A' => 100.0, 'B' => -80.0 }
    result = ClearLedger::Core::Settlement.apply_reserve(net, 0.10)

    assert_in_delta 90.0, result['A'], 1e-9
    assert_in_delta(-88.0, result['B'], 1e-9)
  end

  def test_eligible_for_settlement_when_under_threshold
    assert ClearLedger::Core::Settlement.eligible_for_settlement?(9.99, 10)
    refute ClearLedger::Core::Settlement.eligible_for_settlement?(10.01, 10)
  end
end
