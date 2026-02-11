# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/analytics/service'

class AnalyticsServiceTest < Minitest::Test
  def test_compute_fleet_health_returns_score
    vessels = [
      { id: 'v1', health_score: 80, active: true },
      { id: 'v2', health_score: 60, active: true },
      { id: 'v3', health_score: 40, active: false }
    ]
    result = OpalCommand::Services::Analytics.compute_fleet_health(vessels)
    assert_operator result[:score], :>, 0
    assert_equal 2, result[:active]
  end

  def test_trend_analysis_returns_trends
    values = [10, 20, 30, 25, 15]
    trends = OpalCommand::Services::Analytics.trend_analysis(values, window: 3)
    assert_equal 3, trends.length
    assert_includes %i[up down flat], trends[0][:trend]
  end

  def test_vessel_ranking_returns_sorted
    vessels = [
      { id: 'v1', health_score: 30 },
      { id: 'v2', health_score: 90 },
      { id: 'v3', health_score: 60 }
    ]
    ranked = OpalCommand::Services::Analytics.vessel_ranking(vessels)
    assert_equal 3, ranked.length
  end

  def test_fleet_summary_counts
    vessels = [
      { id: 'v1', health_score: 80, active: true },
      { id: 'v2', health_score: 40, active: false }
    ]
    summary = OpalCommand::Services::Analytics.fleet_summary(vessels)
    assert_equal 2, summary[:total]
    assert_equal 1, summary[:active]
  end
end
