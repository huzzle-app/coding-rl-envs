# frozen_string_literal: true

require_relative '../test_helper'

class OrderTest < Minitest::Test
  def test_order_urgency_score
    order = MercuryLedger::Core::Order.new(severity: 3, sla_minutes: 30)
    assert_equal 120, order.urgency_score
  end
end
