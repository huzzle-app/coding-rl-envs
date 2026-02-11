# frozen_string_literal: true

require_relative '../test_helper'

class SecurityPolicyTest < Minitest::Test
  def test_policy_queue_alignment
    assert_equal 'watch', MercuryLedger::Core::Policy.next_policy('normal', 2)
    assert MercuryLedger::Core::Queue.should_shed?(15, 10, false)
  end
end
