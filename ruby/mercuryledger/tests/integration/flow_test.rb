# frozen_string_literal: true

require_relative '../test_helper'

class FlowTest < Minitest::Test
  def test_dispatch_routing_workflow_flow
    orders = MercuryLedger::Core::Dispatch.plan_settlement([{ id: 's', urgency: 4, eta: '10:00' }], 1)
    route = MercuryLedger::Core::Routing.choose_corridor([{ channel: 'north', latency: 4 }], [])
    assert_equal 1, orders.length
    assert_equal 'north', route[:channel]
    assert MercuryLedger::Core::Workflow.transition_allowed?(:queued, :allocated)
  end
end
