# frozen_string_literal: true

require_relative '../test_helper'

class QueuePolicyTest < Minitest::Test
  def test_next_policy_transitions
    assert_equal({ max_inflight: 32, drop_oldest: false }, ClearLedger::Core::QueuePolicy.next_policy(1))
    assert_equal({ max_inflight: 16, drop_oldest: true }, ClearLedger::Core::QueuePolicy.next_policy(3))
    assert_equal({ max_inflight: 8, drop_oldest: true }, ClearLedger::Core::QueuePolicy.next_policy(8))
  end

  def test_admit_guard
    assert ClearLedger::Core::QueuePolicy.admit?(4, 2, 8)
    refute ClearLedger::Core::QueuePolicy.admit?(4, 4, 8)
  end

  def test_penalty_score_scales_with_retries_and_latency
    assert_equal 2, ClearLedger::Core::QueuePolicy.penalty_score(1, 200)
    assert_equal 11, ClearLedger::Core::QueuePolicy.penalty_score(4, 750)
  end
end
