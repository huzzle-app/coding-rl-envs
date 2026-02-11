# frozen_string_literal: true

require_relative '../test_helper'

class StatisticsTest < Minitest::Test
  def test_percentile
    assert_in_delta 5.0, ClearLedger::Core::Statistics.percentile([1, 3, 5, 7, 9], 0.50), 1e-9
    assert_in_delta 9.0, ClearLedger::Core::Statistics.percentile([1, 3, 5, 7, 9], 1.0), 1e-9
  end

  def test_moving_average
    out = ClearLedger::Core::Statistics.moving_average([2, 4, 6, 8], 2)
    assert_equal [2.0, 3.0, 5.0, 7.0], out
  end

  def test_bounded_ratio
    assert_in_delta 0.0, ClearLedger::Core::Statistics.bounded_ratio(3, 0), 1e-9
    assert_in_delta 0.4, ClearLedger::Core::Statistics.bounded_ratio(2, 5), 1e-9
    assert_in_delta 1.0, ClearLedger::Core::Statistics.bounded_ratio(8, 5), 1e-9
  end
end
