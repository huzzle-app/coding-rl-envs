# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/gateway/service'

class GatewayServiceTest < Minitest::Test
  def test_score_node_positive_for_active
    node = OpalCommand::Services::Gateway::RouteNode.new(id: 'n1', region: 'us-east', latency_ms: 10, capacity: 80, active: true)
    score = OpalCommand::Services::Gateway.score_node(node)
    assert_operator score, :>, 0
  end

  def test_select_primary_node_returns_best
    nodes = [
      OpalCommand::Services::Gateway::RouteNode.new(id: 'n1', region: 'us-east', latency_ms: 50, capacity: 90, active: true),
      OpalCommand::Services::Gateway::RouteNode.new(id: 'n2', region: 'eu-west', latency_ms: 10, capacity: 90, active: true)
    ]
    primary = OpalCommand::Services::Gateway.select_primary_node(nodes)
    refute_nil primary
    assert_kind_of OpalCommand::Services::Gateway::RouteNode, primary
  end

  def test_build_route_chain_limits_hops
    nodes = Array.new(10) { |i| OpalCommand::Services::Gateway::RouteNode.new(id: "n#{i}", region: 'us', latency_ms: i + 1, capacity: 50, active: true) }
    chain = OpalCommand::Services::Gateway.build_route_chain(nodes, max_hops: 3)
    assert_equal 3, chain[:hops]
  end

  def test_admission_control_rejects_over_capacity
    result = OpalCommand::Services::Gateway.admission_control(current_load: 100, max_capacity: 100, priority: :normal)
    assert_equal false, result[:admitted]
  end
end
