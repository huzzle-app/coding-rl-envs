# frozen_string_literal: true

require_relative '../test_helper'

class ReplayTest < Minitest::Test
  def test_ordered_and_shuffled_replay_converge
    a = MercuryLedger::Core::Resilience.replay([{ id: 'k', sequence: 1 }, { id: 'k', sequence: 2 }])
    b = MercuryLedger::Core::Resilience.replay([{ id: 'k', sequence: 2 }, { id: 'k', sequence: 1 }])
    assert_equal a, b
  end
end
