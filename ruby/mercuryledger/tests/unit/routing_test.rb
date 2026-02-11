# frozen_string_literal: true

require_relative '../test_helper'

class RoutingTest < Minitest::Test
  def test_choose_corridor_ignores_blocked
    route = MercuryLedger::Core::Routing.choose_corridor([
                                                           { channel: 'alpha', latency: 8 },
                                                           { channel: 'beta', latency: 2 }
                                                         ], ['beta'])
    assert_equal 'alpha', route[:channel]
  end
end
