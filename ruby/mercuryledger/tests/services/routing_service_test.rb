# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/routing/service'

class RoutingServiceTest < Minitest::Test
  def test_compute_optimal_path_sorts_by_combined_cost
    legs = [
      MercuryLedger::Services::Routing::Leg.new(from: 'A', to: 'B', distance: 100, risk: 0.5),
      MercuryLedger::Services::Routing::Leg.new(from: 'B', to: 'C', distance: 50, risk: 0.1)
    ]
    sorted = MercuryLedger::Services::Routing.compute_optimal_path(legs)
    assert_equal 'B', sorted[0].from,
      'Leg with lowest distance+risk should be first'
  end

  def test_channel_health_score_higher_reliability_wins
    score_hi = MercuryLedger::Services::Routing.channel_health_score(50, 0.95)
    score_lo = MercuryLedger::Services::Routing.channel_health_score(50, 0.5)
    assert_operator score_hi, :>, score_lo,
      'Higher reliability must yield higher health score'
  end

  def test_estimate_arrival_time_value
    time = MercuryLedger::Services::Routing.estimate_arrival_time(500, 20, 1.2)
    assert_in_delta 30.0, time, 0.01,
      '500/20 * 1.2 = 30.0'
  end

  def test_total_distance_sums_legs
    legs = [
      MercuryLedger::Services::Routing::Leg.new(from: 'A', to: 'B', distance: 100, risk: 0.1),
      MercuryLedger::Services::Routing::Leg.new(from: 'B', to: 'C', distance: 200, risk: 0.2)
    ]
    assert_equal 300.0, MercuryLedger::Services::Routing.total_distance(legs)
  end
end
