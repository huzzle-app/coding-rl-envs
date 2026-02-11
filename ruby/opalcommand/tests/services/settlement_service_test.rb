# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/settlement/service'

class SettlementServiceTest < Minitest::Test
  def test_compute_docking_period_positive
    period = OpalCommand::Services::Settlement.compute_docking_period(200)
    assert_operator period, :>, 0
  end

  def test_berth_decay_rate_positive
    rate = OpalCommand::Services::Settlement.berth_decay_rate(150, area_m2: 5000, mass_kg: 40_000)
    assert_operator rate, :>, 0
  end

  def test_predict_congestion_risk
    risk = OpalCommand::Services::Settlement.predict_congestion_risk(100, 60)
    assert_includes %i[high medium low], risk
  end

  def test_zone_band_classification
    assert_equal 'alpha', OpalCommand::Services::Settlement.zone_band(50)
    assert_equal 'delta', OpalCommand::Services::Settlement.zone_band(500)
  end
end
