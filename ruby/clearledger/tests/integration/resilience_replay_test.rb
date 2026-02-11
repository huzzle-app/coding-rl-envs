# frozen_string_literal: true

require_relative '../test_helper'

class ResilienceReplayTest < Minitest::Test
  def test_ordered_and_shuffled_replay_converges
    ordered = [
      ClearLedger::Core::Resilience::Event.new(version: 11, idempotency_key: 'k1', gross_delta: 12.0, net_delta: 8.0),
      ClearLedger::Core::Resilience::Event.new(version: 12, idempotency_key: 'k2', gross_delta: -3.0, net_delta: -2.0),
      ClearLedger::Core::Resilience::Event.new(version: 13, idempotency_key: 'k3', gross_delta: 1.0, net_delta: 0.5)
    ]
    shuffled = [ordered[2], ordered[0], ordered[1]]

    a = ClearLedger::Core::Resilience.replay_state(100.0, 70.0, 10, ordered)
    b = ClearLedger::Core::Resilience.replay_state(100.0, 70.0, 10, shuffled)

    assert_in_delta a.gross, b.gross, 1e-9
    assert_in_delta a.net, b.net, 1e-9
    assert_equal a.version, b.version
  end

  def test_stale_versions_are_ignored
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 9, idempotency_key: 'old', gross_delta: 100, net_delta: 100),
      ClearLedger::Core::Resilience::Event.new(version: 10, idempotency_key: 'eq', gross_delta: 2, net_delta: 1)
    ]

    snapshot = ClearLedger::Core::Resilience.replay_state(20.0, 10.0, 10, events)
    assert_equal 1, snapshot.applied
    assert_in_delta 22.0, snapshot.gross, 1e-9
    assert_in_delta 11.0, snapshot.net, 1e-9
  end

  def test_stale_duplicate_does_not_shadow_fresh_event
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 9, idempotency_key: 'dup', gross_delta: 100, net_delta: 100),
      ClearLedger::Core::Resilience::Event.new(version: 12, idempotency_key: 'dup', gross_delta: 4, net_delta: 3)
    ]

    snapshot = ClearLedger::Core::Resilience.replay_state(50.0, 30.0, 10, events)
    assert_equal 1, snapshot.applied
    assert_in_delta 54.0, snapshot.gross, 1e-9
    assert_in_delta 33.0, snapshot.net, 1e-9
  end
end
