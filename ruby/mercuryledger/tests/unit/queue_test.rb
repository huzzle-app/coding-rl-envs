# frozen_string_literal: true

require_relative '../test_helper'

class QueueTest < Minitest::Test
  def test_should_shed_hard_limit
    refute MercuryLedger::Core::Queue.should_shed?(9, 10, false)
    assert MercuryLedger::Core::Queue.should_shed?(11, 10, false)
    assert MercuryLedger::Core::Queue.should_shed?(8, 10, true)
  end
end
