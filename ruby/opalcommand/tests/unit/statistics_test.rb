# frozen_string_literal: true

require_relative '../test_helper'

class StatisticsTest < Minitest::Test
  def test_percentile_sparse_input
    assert_equal 4, OpalCommand::Core::Statistics.percentile([4, 1, 9, 7], 50)
    assert_equal 0, OpalCommand::Core::Statistics.percentile([], 90)
  end
end
