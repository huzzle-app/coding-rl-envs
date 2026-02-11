# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/gateway/service'

class GatewayServiceTest < Minitest::Test
  def test_score_node_returns_positive_for_active
    node = { id: 'n1', load: 0.3, latency_ms: 50, healthy: true }
    score = MercuryLedger::Services::Gateway.score_node(node)
    assert_operator score, :>, 0
  end

  def test_select_primary_node_returns_highest
    nodes = [
      { id: 'n1', load: 0.9, latency_ms: 200, healthy: true },
      { id: 'n2', load: 0.1, latency_ms: 10, healthy: true },
      { id: 'n3', load: 0.5, latency_ms: 100, healthy: true }
    ]
    best = MercuryLedger::Services::Gateway.select_primary_node(nodes)
    refute_nil best
  end

  def test_build_route_chain_limits_hops
    nodes = Array.new(10) { |i| { id: "n#{i}", load: i * 0.1, latency_ms: i * 10, healthy: true } }
    chain = MercuryLedger::Services::Gateway.build_route_chain(nodes, 3)
    assert_operator chain.length, :<=, 5
  end

  def test_admission_control_rejects_at_capacity
    result = MercuryLedger::Services::Gateway.admission_control(100, 100, 1)
    assert_equal :reject, result
  end
end
