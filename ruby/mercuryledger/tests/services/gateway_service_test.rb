# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/gateway/service'

class GatewayServiceTest < Minitest::Test
  def test_score_node_lower_load_scores_higher
    low_load = { id: 'n1', load: 0.1, latency_ms: 50, healthy: true }
    high_load = { id: 'n2', load: 0.9, latency_ms: 50, healthy: true }
    score_lo = MercuryLedger::Services::Gateway.score_node(low_load)
    score_hi = MercuryLedger::Services::Gateway.score_node(high_load)
    assert_operator score_lo, :>, score_hi,
      'Lower load node must score higher than higher load node'
  end

  def test_select_primary_node_returns_best_scored
    nodes = [
      { id: 'n1', load: 0.9, latency_ms: 200, healthy: true },
      { id: 'n2', load: 0.1, latency_ms: 10, healthy: true },
      { id: 'n3', load: 0.5, latency_ms: 100, healthy: true }
    ]
    best = MercuryLedger::Services::Gateway.select_primary_node(nodes)
    assert_equal 'n2', best[:id],
      'Primary node must be the one with lowest load and latency'
  end

  def test_build_route_chain_limits_hops
    nodes = Array.new(10) { |i| { id: "n#{i}", load: i * 0.1, latency_ms: i * 10, healthy: true } }
    chain = MercuryLedger::Services::Gateway.build_route_chain(nodes, 3)
    assert_operator chain.length, :<=, 3
  end

  def test_admission_control_rejects_at_capacity
    result = MercuryLedger::Services::Gateway.admission_control(100, 100, 1)
    assert_equal :reject, result
  end
end
