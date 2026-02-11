# frozen_string_literal: true

require_relative '../test_helper'

class LatentBugsMatrixTest < Minitest::Test
  # --- Statistics.exponential_moving_average ---

  def test_ema_reacts_to_step_change
    values = [10, 10, 10, 100, 100, 100, 100]
    result = ClearLedger::Core::Statistics.exponential_moving_average(values, 0.9)
    assert_in_delta 91.0, result[3], 1e-6
  end

  def test_ema_alpha_high_weights_current
    values = [0, 100]
    result = ClearLedger::Core::Statistics.exponential_moving_average(values, 0.8)
    assert_in_delta 80.0, result[1], 1e-6
  end

  def test_ema_alpha_low_weights_history
    values = [100, 0]
    result = ClearLedger::Core::Statistics.exponential_moving_average(values, 0.2)
    assert_in_delta 80.0, result[1], 1e-6
  end

  def test_ema_convergence_toward_constant
    values = [100] + [50] * 6
    result = ClearLedger::Core::Statistics.exponential_moving_average(values, 0.5)
    assert result.last < 55.0, "EMA should converge toward 50, got #{result.last}"
    assert result.last > 48.0, "EMA should be near 50, got #{result.last}"
  end

  def test_ema_preserves_length
    values = [1, 2, 3, 4, 5]
    result = ClearLedger::Core::Statistics.exponential_moving_average(values, 0.5)
    assert_equal 5, result.length
  end

  def test_ema_single_value
    result = ClearLedger::Core::Statistics.exponential_moving_average([42.0], 0.9)
    assert_equal [42.0], result
  end

  def test_ema_empty
    result = ClearLedger::Core::Statistics.exponential_moving_average([], 0.5)
    assert_equal [], result
  end

  def test_ema_trend_following
    values = [10, 20, 30, 40, 50]
    result = ClearLedger::Core::Statistics.exponential_moving_average(values, 0.9)
    assert_in_delta 19.0, result[1], 1e-6
    assert_in_delta 28.9, result[2], 1e-6
  end

  5.times do |i|
    define_method("test_ema_parametric_#{format('%03d', i)}") do
      alpha = 0.6 + i * 0.08
      values = [0] + [100] * 4
      result = ClearLedger::Core::Statistics.exponential_moving_average(values, alpha)
      assert_in_delta(alpha * 100, result[1], 1e-6)
    end
  end

  # --- Routing.route_health_composite ---

  def test_health_composite_normalized
    metrics = [
      { name: 'latency', value: 0.9, weight: 1.0 },
      { name: 'errors', value: 0.8, weight: 1.0 }
    ]
    score = ClearLedger::Core::Routing.route_health_composite(metrics)
    assert_in_delta 0.85, score, 1e-6
  end

  def test_health_composite_weighted
    metrics = [
      { name: 'latency', value: 1.0, weight: 3.0 },
      { name: 'errors', value: 0.5, weight: 1.0 }
    ]
    score = ClearLedger::Core::Routing.route_health_composite(metrics)
    assert_in_delta 0.875, score, 1e-6
  end

  def test_health_composite_single_metric
    metrics = [{ name: 'uptime', value: 0.95, weight: 2.0 }]
    score = ClearLedger::Core::Routing.route_health_composite(metrics)
    assert_in_delta 0.95, score, 1e-6
  end

  def test_health_composite_empty
    score = ClearLedger::Core::Routing.route_health_composite([])
    assert_in_delta 0.0, score, 1e-6
  end

  def test_health_composite_bounded
    metrics = [
      { name: 'a', value: 0.7, weight: 2.0 },
      { name: 'b', value: 0.3, weight: 2.0 },
      { name: 'c', value: 0.9, weight: 1.0 }
    ]
    score = ClearLedger::Core::Routing.route_health_composite(metrics)
    assert score <= 1.0, "Composite score #{score} exceeds 1.0"
    assert score >= 0.0
  end

  def test_health_composite_many_equal_metrics
    metrics = 10.times.map { |i| { name: "m#{i}", value: 0.8, weight: 1.0 } }
    score = ClearLedger::Core::Routing.route_health_composite(metrics)
    assert_in_delta 0.8, score, 1e-6
  end

  # --- AuditChain.verify_chain_integrity ---

  def test_chain_integrity_valid_chain
    chain = []
    h = 0
    3.times do |i|
      payload = "event-#{i}"
      new_h = ClearLedger::Core::AuditChain.append_hash(h, payload)
      chain << { hash: new_h, payload: payload, prev_hash: h }
      h = new_h
    end
    assert ClearLedger::Core::AuditChain.verify_chain_integrity(chain)
  end

  def test_chain_integrity_tampered_last_entry
    chain = []
    h = 0
    4.times do |i|
      payload = "event-#{i}"
      new_h = ClearLedger::Core::AuditChain.append_hash(h, payload)
      chain << { hash: new_h, payload: payload, prev_hash: h }
      h = new_h
    end
    chain[-1][:hash] = 99999
    refute ClearLedger::Core::AuditChain.verify_chain_integrity(chain)
  end

  def test_chain_integrity_tampered_middle_entry
    chain = []
    h = 0
    5.times do |i|
      payload = "event-#{i}"
      new_h = ClearLedger::Core::AuditChain.append_hash(h, payload)
      chain << { hash: new_h, payload: payload, prev_hash: h }
      h = new_h
    end
    chain[2][:hash] = 12345
    refute ClearLedger::Core::AuditChain.verify_chain_integrity(chain)
  end

  def test_chain_integrity_single_entry
    chain = [{ hash: 100, payload: 'only', prev_hash: 0 }]
    assert ClearLedger::Core::AuditChain.verify_chain_integrity(chain)
  end

  def test_chain_integrity_two_entries_valid
    h0 = ClearLedger::Core::AuditChain.append_hash(0, 'first')
    h1 = ClearLedger::Core::AuditChain.append_hash(h0, 'second')
    chain = [
      { hash: h0, payload: 'first', prev_hash: 0 },
      { hash: h1, payload: 'second', prev_hash: h0 }
    ]
    assert ClearLedger::Core::AuditChain.verify_chain_integrity(chain)
  end

  def test_chain_integrity_two_entries_tampered
    h0 = ClearLedger::Core::AuditChain.append_hash(0, 'first')
    chain = [
      { hash: h0, payload: 'first', prev_hash: 0 },
      { hash: 99999, payload: 'second', prev_hash: h0 }
    ]
    refute ClearLedger::Core::AuditChain.verify_chain_integrity(chain)
  end

  # --- LedgerWindow.sliding_window_aggregate ---

  def test_sliding_window_no_double_count_at_boundaries
    events = [
      { ts: 0, value: 1.0 },
      { ts: 5, value: 2.0 },
      { ts: 10, value: 3.0 },
      { ts: 15, value: 4.0 }
    ]
    results = ClearLedger::Core::LedgerWindow.sliding_window_aggregate(events, 10, 10)
    first_window = results.find { |r| r[:start] == 0 }
    assert_equal 2, first_window[:count]
    assert_in_delta 3.0, first_window[:sum], 1e-6
  end

  def test_sliding_window_step_smaller_than_window
    events = [
      { ts: 0, value: 1.0 },
      { ts: 3, value: 2.0 },
      { ts: 6, value: 3.0 },
      { ts: 9, value: 4.0 }
    ]
    results = ClearLedger::Core::LedgerWindow.sliding_window_aggregate(events, 5, 3)
    assert results.length >= 2
  end

  def test_sliding_window_empty_events
    results = ClearLedger::Core::LedgerWindow.sliding_window_aggregate([], 10, 5)
    assert_equal [], results
  end
end
