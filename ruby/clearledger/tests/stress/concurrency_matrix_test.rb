# frozen_string_literal: true

require_relative '../test_helper'

class ConcurrencyMatrixTest < Minitest::Test
  # --- Resilience.concurrent_replay ---
  # Bug: adds full snapshot.gross (includes base) instead of delta

  def test_concurrent_replay_two_batches
    batch_a = [
      ClearLedger::Core::Resilience::Event.new(version: 11, idempotency_key: 'a1', gross_delta: 10, net_delta: 5)
    ]
    batch_b = [
      ClearLedger::Core::Resilience::Event.new(version: 12, idempotency_key: 'b1', gross_delta: 20, net_delta: 8)
    ]
    result = ClearLedger::Core::Resilience.concurrent_replay(100.0, 50.0, 10, [batch_a, batch_b])
    assert_in_delta 130.0, result.gross, 1e-6
    assert_in_delta 63.0, result.net, 1e-6
  end

  def test_concurrent_replay_single_batch
    batch = [
      ClearLedger::Core::Resilience::Event.new(version: 11, idempotency_key: 'x', gross_delta: 5, net_delta: 3)
    ]
    result = ClearLedger::Core::Resilience.concurrent_replay(100.0, 50.0, 10, [batch])
    assert_in_delta 105.0, result.gross, 1e-6
    assert_in_delta 53.0, result.net, 1e-6
  end

  def test_concurrent_replay_empty_batches
    result = ClearLedger::Core::Resilience.concurrent_replay(100.0, 50.0, 10, [])
    assert_in_delta 100.0, result.gross, 1e-6
    assert_in_delta 50.0, result.net, 1e-6
  end

  def test_concurrent_replay_three_batches
    batches = 3.times.map do |i|
      [ClearLedger::Core::Resilience::Event.new(
        version: 11 + i, idempotency_key: "k#{i}", gross_delta: 10, net_delta: 5
      )]
    end
    result = ClearLedger::Core::Resilience.concurrent_replay(200.0, 100.0, 10, batches)
    assert_in_delta 230.0, result.gross, 1e-6
    assert_in_delta 115.0, result.net, 1e-6
  end

  def test_concurrent_replay_preserves_base_with_no_events
    batches = [[], []]
    result = ClearLedger::Core::Resilience.concurrent_replay(50.0, 25.0, 10, batches)
    assert_in_delta 50.0, result.gross, 1e-6
    assert_in_delta 25.0, result.net, 1e-6
  end

  def test_concurrent_replay_version_tracking
    batch_a = [
      ClearLedger::Core::Resilience::Event.new(version: 15, idempotency_key: 'a', gross_delta: 1, net_delta: 1)
    ]
    batch_b = [
      ClearLedger::Core::Resilience::Event.new(version: 20, idempotency_key: 'b', gross_delta: 1, net_delta: 1)
    ]
    result = ClearLedger::Core::Resilience.concurrent_replay(10.0, 5.0, 10, [batch_a, batch_b])
    assert_equal 20, result.version
  end

  def test_concurrent_replay_applied_count
    batch_a = [
      ClearLedger::Core::Resilience::Event.new(version: 11, idempotency_key: 'a1', gross_delta: 1, net_delta: 1),
      ClearLedger::Core::Resilience::Event.new(version: 12, idempotency_key: 'a2', gross_delta: 1, net_delta: 1)
    ]
    batch_b = [
      ClearLedger::Core::Resilience::Event.new(version: 13, idempotency_key: 'b1', gross_delta: 1, net_delta: 1)
    ]
    result = ClearLedger::Core::Resilience.concurrent_replay(10.0, 5.0, 10, [batch_a, batch_b])
    assert_equal 3, result.applied
  end

  5.times do |i|
    define_method("test_concurrent_replay_parametric_#{format('%03d', i)}") do
      n_batches = i + 2
      batches = n_batches.times.map do |j|
        [ClearLedger::Core::Resilience::Event.new(
          version: 11 + j, idempotency_key: "p#{j}", gross_delta: 10, net_delta: 5
        )]
      end
      result = ClearLedger::Core::Resilience.concurrent_replay(100.0, 50.0, 10, batches)
      expected_gross = 100.0 + n_batches * 10
      expected_net = 50.0 + n_batches * 5
      assert_in_delta expected_gross, result.gross, 1e-6
      assert_in_delta expected_net, result.net, 1e-6
    end
  end

  # --- Statistics.parallel_aggregate ---
  # Bug: averages partition means instead of computing global mean from totals

  def test_parallel_aggregate_equal_partitions
    partitions = [{ sum: 100.0, count: 10 }, { sum: 200.0, count: 10 }]
    result = ClearLedger::Core::Statistics.parallel_aggregate(partitions)
    assert_in_delta 15.0, result, 1e-6
  end

  def test_parallel_aggregate_unequal_partitions
    partitions = [{ sum: 100.0, count: 100 }, { sum: 20.0, count: 2 }]
    result = ClearLedger::Core::Statistics.parallel_aggregate(partitions)
    expected = 120.0 / 102
    assert_in_delta expected, result, 1e-6
  end

  def test_parallel_aggregate_single_partition
    partitions = [{ sum: 50.0, count: 5 }]
    result = ClearLedger::Core::Statistics.parallel_aggregate(partitions)
    assert_in_delta 10.0, result, 1e-6
  end

  def test_parallel_aggregate_empty
    result = ClearLedger::Core::Statistics.parallel_aggregate([])
    assert_in_delta 0.0, result, 1e-6
  end

  def test_parallel_aggregate_large_vs_small
    partitions = [
      { sum: 1_000_000.0, count: 1_000_000 },
      { sum: 100.0, count: 1 }
    ]
    result = ClearLedger::Core::Statistics.parallel_aggregate(partitions)
    expected = 1_000_100.0 / 1_000_001
    assert_in_delta expected, result, 0.001
  end

  def test_parallel_aggregate_three_partitions
    partitions = [
      { sum: 30.0, count: 3 },
      { sum: 40.0, count: 4 },
      { sum: 50.0, count: 5 }
    ]
    result = ClearLedger::Core::Statistics.parallel_aggregate(partitions)
    assert_in_delta 10.0, result, 1e-6
  end

  # --- QueuePolicy.concurrent_admit_batch ---
  # Bug: uses initial_inflight for all checks instead of current_inflight

  def test_concurrent_admit_respects_capacity
    requests = [:a, :b, :c, :d, :e]
    admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, 5, 0, 8)
    assert_equal 3, admitted.length
  end

  def test_concurrent_admit_full_queue_rejects_all
    requests = [:a, :b, :c]
    admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, 8, 0, 8)
    assert_equal 0, admitted.length
  end

  def test_concurrent_admit_empty_queue_admits_up_to_max
    requests = [:a, :b, :c, :d, :e, :f, :g, :h, :i, :j]
    admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, 0, 0, 5)
    assert_equal 5, admitted.length
  end

  def test_concurrent_admit_preserves_order
    requests = [:first, :second, :third]
    admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, 0, 0, 10)
    assert_equal [:first, :second, :third], admitted
  end

  def test_concurrent_admit_with_queue_depth
    requests = [:a, :b, :c, :d]
    admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, 3, 2, 8)
    assert_equal 3, admitted.length
  end

  def test_concurrent_admit_single_slot
    requests = [:a, :b, :c]
    admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, 4, 0, 5)
    assert_equal 1, admitted.length
  end

  5.times do |i|
    define_method("test_concurrent_admit_parametric_#{format('%03d', i)}") do
      initial = i * 2
      max = 10
      available = [max - initial, 0].max
      requests = (available + 5).times.map { |j| "req-#{j}" }
      admitted = ClearLedger::Core::QueuePolicy.concurrent_admit_batch(requests, initial, 0, max)
      assert_equal available, admitted.length
    end
  end
end
