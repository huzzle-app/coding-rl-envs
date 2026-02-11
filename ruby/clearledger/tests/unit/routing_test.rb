# frozen_string_literal: true

require_relative '../test_helper'

class RoutingTest < Minitest::Test
  def test_best_hub_prefers_lowest_latency_then_lexical
    hub = ClearLedger::Core::Routing.best_hub({ 'west' => 19.0, 'east' => 17.0, 'alpha' => 17.0 })
    assert_equal 'alpha', hub
  end

  def test_deterministic_partition_is_stable
    a = ClearLedger::Core::Routing.deterministic_partition('tenant-a', 11)
    b = ClearLedger::Core::Routing.deterministic_partition('tenant-a', 11)
    c = ClearLedger::Core::Routing.deterministic_partition('tenant-b', 11)

    assert_equal a, b
    refute_equal a, c
  end

  def test_churn_rate
    prev = { 'job-1' => 'r1', 'job-2' => 'r2', 'job-3' => 'r3' }
    cur = { 'job-1' => 'r1', 'job-2' => 'r4', 'job-3' => 'r3' }
    assert_in_delta 1.0 / 3.0, ClearLedger::Core::Routing.churn_rate(prev, cur), 1e-9
  end
end
