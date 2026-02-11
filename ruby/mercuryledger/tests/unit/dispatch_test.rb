# frozen_string_literal: true

require_relative '../test_helper'

class DispatchTest < Minitest::Test
  def test_plan_settlement_respects_capacity
    out = MercuryLedger::Core::Dispatch.plan_settlement([
                                                          { id: 'a', urgency: 1, eta: '09:30' },
                                                          { id: 'b', urgency: 3, eta: '10:00' },
                                                          { id: 'c', urgency: 3, eta: '08:30' }
                                                        ], 2)
    assert_equal %w[c b], out.map { |o| o[:id] }
  end
end
