# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/resilience/service'

class ResilienceServiceTest < Minitest::Test
  def test_build_replay_plan_budget_is_timeout_times_parallel
    plan = MercuryLedger::Services::Resilience.build_replay_plan(100, 60, 4)
    assert_operator plan[:batches], :>, 0
    assert_equal 240, plan[:budget],
      'Budget must equal timeout * parallel (60 * 4 = 240)'
  end

  def test_classify_replay_mode_complete
    mode = MercuryLedger::Services::Resilience.classify_replay_mode(10, 10)
    assert_equal :complete, mode
  end

  def test_failover_priority_primary_highest
    primary = MercuryLedger::Services::Resilience.failover_priority('primary', false, 10)
    secondary = MercuryLedger::Services::Resilience.failover_priority('secondary', false, 10)
    assert_operator primary, :>, secondary
  end

  def test_recovery_time_estimate_positive
    est = MercuryLedger::Services::Resilience.recovery_time_estimate(5, 10.0)
    assert_operator est, :>, 0
  end
end
