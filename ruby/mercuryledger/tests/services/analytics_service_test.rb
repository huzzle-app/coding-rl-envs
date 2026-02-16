# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/analytics/service'

class AnalyticsServiceTest < Minitest::Test
  def test_compute_fleet_health_active_vessels
    vessels = [
      { active: true, healthy: true },
      { active: true, healthy: false },
      { active: false, healthy: true }
    ]
    health = MercuryLedger::Services::Analytics.compute_fleet_health(vessels)
    assert_operator health, :>, 0
    assert_operator health, :<=, 1.0
  end

  def test_moving_metric_returns_averages_not_sums
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    metric = MercuryLedger::Services::Analytics.moving_metric(values, 3)
    refute_empty metric
    assert_in_delta 20.0, metric[0], 0.01,
      'moving_metric should return averages (20.0), not sums (60.0)'
  end

  def test_anomaly_report_detects_outliers
    values = [10, 10, 10, 10, 100, 10, 10]
    anomalies = MercuryLedger::Services::Analytics.anomaly_report(values, 2.0)
    assert_operator anomalies.length, :>=, 1
  end

  def test_fleet_summary_totals
    vessels = [
      { active: true, healthy: true, load: 0.5 },
      { active: false, healthy: false, load: 0.1 }
    ]
    summary = MercuryLedger::Services::Analytics.fleet_summary(vessels)
    assert_equal 2, summary[:total]
    assert_equal 1, summary[:active]
  end
end
