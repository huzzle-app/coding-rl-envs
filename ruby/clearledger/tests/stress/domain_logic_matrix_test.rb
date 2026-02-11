# frozen_string_literal: true

require_relative '../test_helper'

class DomainLogicMatrixTest < Minitest::Test
  # --- Settlement.bilateral_net ---

  def test_bilateral_net_basic_addition
    a = [{ account: 'X', delta: 100.0 }]
    b = [{ account: 'X', delta: 50.0 }]
    result = ClearLedger::Core::Settlement.bilateral_net(a, b)
    assert_in_delta 150.0, result['X'], 1e-6
  end

  def test_bilateral_net_offsetting_positions
    a = [{ account: 'X', delta: 100.0 }]
    b = [{ account: 'X', delta: -100.0 }]
    result = ClearLedger::Core::Settlement.bilateral_net(a, b)
    assert_in_delta 0.0, result['X'], 1e-6
  end

  def test_bilateral_net_multiple_accounts
    a = [{ account: 'X', delta: 50.0 }, { account: 'Y', delta: 30.0 }]
    b = [{ account: 'X', delta: 20.0 }, { account: 'Y', delta: -10.0 }]
    result = ClearLedger::Core::Settlement.bilateral_net(a, b)
    assert_in_delta 70.0, result['X'], 1e-6
    assert_in_delta 20.0, result['Y'], 1e-6
  end

  def test_bilateral_net_disjoint_accounts
    a = [{ account: 'X', delta: 100.0 }]
    b = [{ account: 'Y', delta: 200.0 }]
    result = ClearLedger::Core::Settlement.bilateral_net(a, b)
    assert_in_delta 100.0, result['X'], 1e-6
    assert_in_delta 200.0, result['Y'], 1e-6
  end

  def test_bilateral_net_empty_one_side
    a = [{ account: 'X', delta: 100.0 }]
    result = ClearLedger::Core::Settlement.bilateral_net(a, [])
    assert_in_delta 100.0, result['X'], 1e-6
  end

  def test_bilateral_net_both_negative
    a = [{ account: 'X', delta: -30.0 }]
    b = [{ account: 'X', delta: -20.0 }]
    result = ClearLedger::Core::Settlement.bilateral_net(a, b)
    assert_in_delta(-50.0, result['X'], 1e-6)
  end

  def test_bilateral_net_is_commutative
    a = [{ account: 'X', delta: 40.0 }]
    b = [{ account: 'X', delta: 60.0 }]
    result_ab = ClearLedger::Core::Settlement.bilateral_net(a, b)
    result_ba = ClearLedger::Core::Settlement.bilateral_net(b, a)
    assert_in_delta result_ab['X'], result_ba['X'], 1e-6
  end

  5.times do |i|
    define_method("test_bilateral_net_parametric_#{format('%03d', i)}") do
      delta_a = 10.0 * (i + 1)
      delta_b = 5.0 * (i + 1)
      a = [{ account: 'Z', delta: delta_a }]
      b = [{ account: 'Z', delta: delta_b }]
      result = ClearLedger::Core::Settlement.bilateral_net(a, b)
      assert_in_delta(delta_a + delta_b, result['Z'], 1e-6)
    end
  end

  # --- Settlement.tiered_fee ---

  def test_tiered_fee_single_tier
    tiers = [{ limit: 10_000, rate: 0.001 }]
    fee = ClearLedger::Core::Settlement.tiered_fee(5_000, tiers)
    assert_in_delta 5.0, fee, 1e-6
  end

  def test_tiered_fee_two_tiers_in_first_band
    tiers = [{ limit: 10_000, rate: 0.001 }, { limit: 50_000, rate: 0.003 }]
    fee = ClearLedger::Core::Settlement.tiered_fee(5_000, tiers)
    assert_in_delta 5.0, fee, 1e-6
  end

  def test_tiered_fee_two_tiers_crosses_bands
    tiers = [{ limit: 10_000, rate: 0.001 }, { limit: 50_000, rate: 0.003 }]
    fee = ClearLedger::Core::Settlement.tiered_fee(30_000, tiers)
    # First 10,000 at 0.001 = 10.0, next 20,000 at 0.003 = 60.0 → total 70.0
    assert_in_delta 70.0, fee, 1e-6
  end

  def test_tiered_fee_exceeds_all_tiers
    tiers = [{ limit: 10_000, rate: 0.001 }, { limit: 50_000, rate: 0.003 }]
    fee = ClearLedger::Core::Settlement.tiered_fee(80_000, tiers)
    # First 10,000 at 0.001 = 10.0, next 40,000 at 0.003 = 120.0, last 30,000 at 0.003 = 90.0 → 220.0
    assert_in_delta 220.0, fee, 1e-6
  end

  def test_tiered_fee_three_tiers
    tiers = [
      { limit: 1_000, rate: 0.01 },
      { limit: 10_000, rate: 0.005 },
      { limit: 100_000, rate: 0.001 }
    ]
    fee = ClearLedger::Core::Settlement.tiered_fee(15_000, tiers)
    # First 1,000 at 0.01 = 10.0, next 9,000 at 0.005 = 45.0, next 5,000 at 0.001 = 5.0 → 60.0
    assert_in_delta 60.0, fee, 1e-6
  end

  # --- Reconciliation.progressive_reconcile ---

  def test_progressive_reconcile_tightening_tolerance
    pairs = [[1000.0, 990.0], [1000.0, 990.0], [1000.0, 990.0]]
    results = ClearLedger::Core::Reconciliation.progressive_reconcile(pairs, 150, 50)
    assert results[0]
    assert results[1]
    refute results[2]
  end

  def test_progressive_reconcile_all_pass_loose
    pairs = [[100.0, 99.0], [100.0, 99.0]]
    results = ClearLedger::Core::Reconciliation.progressive_reconcile(pairs, 200, 10)
    assert results.all?
  end

  def test_progressive_reconcile_immediate_fail_tight
    pairs = [[100.0, 90.0]]
    results = ClearLedger::Core::Reconciliation.progressive_reconcile(pairs, 500, 100)
    refute results[0]
  end

  def test_progressive_reconcile_decay_makes_later_stricter
    pairs = [[1000.0, 995.0]] * 5
    results = ClearLedger::Core::Reconciliation.progressive_reconcile(pairs, 80, 20)
    assert results[0]
    assert results[1]
    refute results[2]
  end

  def test_progressive_reconcile_empty
    results = ClearLedger::Core::Reconciliation.progressive_reconcile([], 100, 10)
    assert_equal [], results
  end

  # --- Routing.adaptive_route ---

  def test_adaptive_route_high_decay_favors_current
    hub = ClearLedger::Core::Routing.adaptive_route(
      { 'fast' => 10.0, 'slow' => 60.0 },
      { 'fast' => 80.0, 'slow' => 60.0 },
      0.8
    )
    assert_equal 'fast', hub
  end

  def test_adaptive_route_step_change_detection
    hub = ClearLedger::Core::Routing.adaptive_route(
      { 'improved' => 5.0, 'stable' => 50.0 },
      { 'improved' => 200.0, 'stable' => 50.0 },
      0.9
    )
    assert_equal 'improved', hub
  end

  def test_adaptive_route_no_history_uses_current
    hub = ClearLedger::Core::Routing.adaptive_route(
      { 'a' => 20.0, 'b' => 30.0 },
      {},
      0.5
    )
    assert_equal 'a', hub
  end

  def test_adaptive_route_recent_spike_detected
    hub = ClearLedger::Core::Routing.adaptive_route(
      { 'spiked' => 500.0, 'normal' => 40.0 },
      { 'spiked' => 20.0, 'normal' => 40.0 },
      0.7
    )
    assert_equal 'normal', hub
  end

  # --- LedgerWindow.late_event_policy ---

  def test_late_event_within_grace_period
    result = ClearLedger::Core::LedgerWindow.late_event_policy(105, 100, 10)
    assert_equal :accept, result
  end

  def test_late_event_beyond_grace_period
    result = ClearLedger::Core::LedgerWindow.late_event_policy(115, 100, 10)
    assert_equal :reject, result
  end

  def test_late_event_exactly_at_grace_boundary
    result = ClearLedger::Core::LedgerWindow.late_event_policy(110, 100, 10)
    assert_equal :accept, result
  end

  def test_early_event_always_accepted
    result = ClearLedger::Core::LedgerWindow.late_event_policy(95, 100, 10)
    assert_equal :accept, result
  end

  def test_late_event_at_watermark
    result = ClearLedger::Core::LedgerWindow.late_event_policy(100, 100, 10)
    assert_equal :accept, result
  end

  def test_late_event_zero_grace_rejects_late
    result = ClearLedger::Core::LedgerWindow.late_event_policy(101, 100, 0)
    assert_equal :reject, result
  end

  def test_late_event_large_grace_accepts
    result = ClearLedger::Core::LedgerWindow.late_event_policy(200, 100, 200)
    assert_equal :accept, result
  end

  5.times do |i|
    define_method("test_late_event_parametric_#{format('%03d', i)}") do
      watermark = 1000
      grace = 50 + i * 20
      late_ts = watermark + grace - 5
      result = ClearLedger::Core::LedgerWindow.late_event_policy(late_ts, watermark, grace)
      assert_equal :accept, result
    end
  end
end
