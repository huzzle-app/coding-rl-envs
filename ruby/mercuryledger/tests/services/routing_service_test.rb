# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/routing/service'

class RoutingServiceTest < Minitest::Test
  def test_compute_optimal_path_sorts
    legs = [
      MercuryLedger::Services::Routing::Leg.new(from: 'A', to: 'B', distance: 100, risk: 0.5),
      MercuryLedger::Services::Routing::Leg.new(from: 'B', to: 'C', distance: 50, risk: 0.1)
    ]
    sorted = MercuryLedger::Services::Routing.compute_optimal_path(legs)
    assert_equal 2, sorted.length
  end

  def test_channel_health_score_positive
    score = MercuryLedger::Services::Routing.channel_health_score(50, 0.95)
    assert_operator score, :>, 0
  end

  def test_estimate_arrival_time_positive
    time = MercuryLedger::Services::Routing.estimate_arrival_time(500, 20, 1.2)
    assert_operator time, :>, 0
  end

  def test_total_distance_sums_legs
    legs = [
      MercuryLedger::Services::Routing::Leg.new(from: 'A', to: 'B', distance: 100, risk: 0.1),
      MercuryLedger::Services::Routing::Leg.new(from: 'B', to: 'C', distance: 200, risk: 0.2)
    ]
    assert_equal 300.0, MercuryLedger::Services::Routing.total_distance(legs)
  end
end
