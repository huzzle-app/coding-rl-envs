# frozen_string_literal: true

require_relative '../test_helper'

class PolicyTest < Minitest::Test
  def test_next_policy_escalates_on_burst
    assert_equal 'restricted', MercuryLedger::Core::Policy.next_policy('watch', 3)
  end
end
