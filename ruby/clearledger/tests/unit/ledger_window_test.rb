# frozen_string_literal: true

require_relative '../test_helper'

class LedgerWindowTest < Minitest::Test
  def test_bucket_for
    assert_equal 20, ClearLedger::Core::LedgerWindow.bucket_for(1200, 60)
    assert_equal 0, ClearLedger::Core::LedgerWindow.bucket_for(59, 60)
  end

  def test_watermark_accept
    assert ClearLedger::Core::LedgerWindow.watermark_accept?(100, 105, 5)
    refute ClearLedger::Core::LedgerWindow.watermark_accept?(100, 106, 5)
  end

  def test_lag_seconds
    assert_equal 0, ClearLedger::Core::LedgerWindow.lag_seconds(100, 120)
    assert_equal 25, ClearLedger::Core::LedgerWindow.lag_seconds(125, 100)
  end
end
