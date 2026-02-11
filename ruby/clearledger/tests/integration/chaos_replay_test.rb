# frozen_string_literal: true

require_relative '../test_helper'

class ChaosReplayTest < Minitest::Test
  def test_replay_idempotency_collision_applies_once
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 21, idempotency_key: 'dup', gross_delta: 3, net_delta: 1),
      ClearLedger::Core::Resilience::Event.new(version: 22, idempotency_key: 'dup', gross_delta: 50, net_delta: 20),
      ClearLedger::Core::Resilience::Event.new(version: 23, idempotency_key: 'ok', gross_delta: -2, net_delta: 0)
    ]

    snapshot = ClearLedger::Core::Resilience.replay_state(40, 20, 20, events)
    assert_equal 2, snapshot.applied
  end

  def test_replay_accepts_equal_version
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 20, idempotency_key: 'eq', gross_delta: 1, net_delta: 1)
    ]

    snapshot = ClearLedger::Core::Resilience.replay_state(10, 5, 20, events)
    assert_equal 1, snapshot.applied
    assert_equal 20, snapshot.version
  end
end
