# frozen_string_literal: true

require_relative '../test_helper'

class FaultInjectionTest < Minitest::Test
  def test_retry_backoff_grows_exponentially
    assert_equal 50, ClearLedger::Core::Resilience.retry_backoff_ms(1, 50)
    assert_equal 100, ClearLedger::Core::Resilience.retry_backoff_ms(2, 50)
    assert_equal 200, ClearLedger::Core::Resilience.retry_backoff_ms(3, 50)
  end

  def test_circuit_open_after_failure_burst
    refute ClearLedger::Core::Resilience.circuit_open?(4)
    assert ClearLedger::Core::Resilience.circuit_open?(5)
  end
end
