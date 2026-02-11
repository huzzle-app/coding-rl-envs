# frozen_string_literal: true

require_relative '../test_helper'

# =============================================================================
# Advanced bug detection tests — Latent, Domain, Multi-step, State Machine,
# Concurrency, and Integration categories.
# =============================================================================

class LatentWorkflowAuditPollutionTest < Minitest::Test
  # Bug 1: WorkflowEngine.transition records FAILED transitions in history,
  # polluting the audit log with phantom entries.

  def setup
    @engine = MercuryLedger::Core::WorkflowEngine.new
  end

  def test_failed_transition_does_not_appear_in_history
    @engine.register('ship-1')
    result = @engine.transition('ship-1', :completed) # queued->completed is invalid
    refute result.success
    assert_equal 0, @engine.history('ship-1').length,
      'Failed transitions must not be recorded in history'
  end

  def test_audit_log_excludes_rejected_transitions
    @engine.register('ship-2')
    @engine.transition('ship-2', :completed)
    @engine.transition('ship-2', :arrived)
    assert @engine.audit_log.all? { |line| !line.include?('completed') || line.include?('arrived') },
      'Audit log should only contain successful transitions'
  end

  def test_history_length_matches_successful_transitions_only
    @engine.register('v1')
    @engine.transition('v1', :allocated)   # valid
    @engine.transition('v1', :completed)   # invalid (allocated->completed)
    @engine.transition('v1', :departed)    # valid
    history = @engine.history('v1')
    assert_equal 2, history.length,
      'History should contain exactly 2 successful transitions, not include failed ones'
  end

  def test_multiple_failed_transitions_no_history_growth
    @engine.register('v2')
    5.times { @engine.transition('v2', :completed) }
    assert_equal 0, @engine.history('v2').length,
      'Repeated failed transitions must not accumulate in history'
  end

  def test_audit_log_count_equals_successful_transition_count
    @engine.register('a1')
    @engine.transition('a1', :allocated)
    @engine.transition('a1', :completed) # invalid
    @engine.transition('a1', :departed)
    assert_equal 2, @engine.audit_log.length,
      'Audit log count must equal number of successful transitions'
  end

  def test_history_from_state_matches_actual_state_at_time
    @engine.register('a2')
    @engine.transition('a2', :allocated)
    @engine.transition('a2', :arrived) # invalid skip
    @engine.transition('a2', :departed)
    history = @engine.history('a2')
    assert_equal :queued, history[0].from_state
    assert_equal :allocated, history[1].from_state
  end

  def test_entity_not_found_transition_no_history
    result = @engine.transition('nonexistent', :allocated)
    refute result.success
    assert_equal 0, @engine.history.length
  end

  def test_full_lifecycle_history_exactly_four_records
    @engine.register('lc1')
    @engine.transition('lc1', :allocated)
    @engine.transition('lc1', :departed)
    @engine.transition('lc1', :arrived)
    @engine.transition('lc1', :completed)
    assert_equal 4, @engine.history('lc1').length
  end

  def test_interleaved_valid_invalid_history_integrity
    @engine.register('m1')
    @engine.transition('m1', :allocated)  # valid
    @engine.transition('m1', :queued)     # invalid (backward)
    @engine.transition('m1', :departed)   # valid
    @engine.transition('m1', :queued)     # invalid
    @engine.transition('m1', :arrived)    # valid
    assert_equal 3, @engine.history('m1').length
  end
end

class LatentCircuitBreakerCounterTest < Minitest::Test
  # Bug 2: CircuitBreaker.record_success in CLOSED state resets @success_count
  # instead of @failure_count. Failures accumulate silently across windows.

  def setup
    @cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 3, success_threshold: 2, timeout: 1)
  end

  def test_success_resets_failure_count_in_closed_state
    3.times { @cb.record_failure }
    assert_equal 'closed', @cb.state
    @cb.record_success
    3.times { @cb.record_failure }
    assert_equal 'closed', @cb.state,
      'Success in closed state should reset failure counter; breaker tripped prematurely'
  end

  def test_success_prevents_cumulative_failure_counting
    2.times { @cb.record_failure }
    @cb.record_success
    2.times { @cb.record_failure }
    @cb.record_success
    2.times { @cb.record_failure }
    assert_equal 'closed', @cb.state,
      'Failures should not accumulate across success resets'
  end

  def test_alternating_failure_success_stays_closed
    10.times do
      3.times { @cb.record_failure }
      @cb.record_success
    end
    assert_equal 'closed', @cb.state,
      'Periodic successes should prevent breaker from ever opening'
  end

  def test_closed_success_does_not_affect_success_counter
    cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 1, success_threshold: 10, timeout: 1)
    20.times { cb.record_success }
    assert_equal 'closed', cb.state
  end

  def test_failure_burst_after_long_success_streak
    50.times { @cb.record_success }
    4.times { @cb.record_failure }
    assert_equal 'open', @cb.state,
      'Exactly threshold+1 failures after successes should open breaker'
  end
end

class LatentAllocateCostsTruncationTest < Minitest::Test
  # Bug 3: allocate_costs uses floor truncation (share * 100).to_i / 100.0
  # instead of rounding. This causes systematic under-allocation (penny loss).

  def test_cost_allocation_sums_to_budget
    orders = (1..3).map { |i| { id: i, urgency: 1 } }
    result = MercuryLedger::Core::Dispatch.allocate_costs(orders, 100.0)
    total = result.sum { |o| o[:allocated] }
    assert_in_delta 100.0, total, 0.02,
      'Total allocated costs should sum to budget within rounding tolerance'
  end

  def test_thirds_allocation_rounds_correctly
    orders = [{ id: 1, urgency: 1 }, { id: 2, urgency: 1 }, { id: 3, urgency: 1 }]
    result = MercuryLedger::Core::Dispatch.allocate_costs(orders, 100.0)
    assert_equal 33.33, result[0][:allocated],
      'One-third of 100 should round to 33.33, not truncate to 33.33'
  end

  def test_allocation_rounding_not_truncating
    orders = [{ id: 1, urgency: 1 }, { id: 2, urgency: 2 }]
    result = MercuryLedger::Core::Dispatch.allocate_costs(orders, 10.0)
    assert_equal 6.67, result[1][:allocated],
      'Two-thirds of 10 should round UP to 6.67, not truncate to 6.66'
  end

  def test_small_budget_rounding_accuracy
    orders = [{ id: 1, urgency: 3 }, { id: 2, urgency: 7 }]
    result = MercuryLedger::Core::Dispatch.allocate_costs(orders, 1.0)
    assert_equal 0.3, result[0][:allocated]
    assert_equal 0.7, result[1][:allocated]
  end

  def test_asymmetric_urgency_round_vs_truncate
    orders = [{ id: 1, urgency: 1 }, { id: 2, urgency: 5 }, { id: 3, urgency: 6 }]
    result = MercuryLedger::Core::Dispatch.allocate_costs(orders, 100.0)
    share_5 = result.find { |o| o[:id] == 2 }[:allocated]
    assert_equal 41.67, share_5,
      'Should round 41.666... to 41.67, not truncate to 41.66'
  end

  def test_large_budget_penny_loss
    orders = (1..7).map { |i| { id: i, urgency: 1 } }
    result = MercuryLedger::Core::Dispatch.allocate_costs(orders, 1000.0)
    total = result.sum { |o| o[:allocated] }
    assert_in_delta 1000.0, total, 0.07,
      'Large budget should not lose significant pennies through truncation'
  end
end

class DomainBerthConflictBoundaryTest < Minitest::Test
  # Bug 4: has_conflict? uses <= instead of <, making adjacent
  # (non-overlapping) berth windows falsely report conflicts.

  def test_adjacent_berth_windows_no_conflict
    slot_a = { berth: 'B1', start_hour: 0, end_hour: 8 }
    slot_b = { berth: 'B1', start_hour: 8, end_hour: 16 }
    refute MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b),
      'Adjacent windows (end=8, start=8) must not conflict; vessel departed before next arrives'
  end

  def test_adjacent_windows_reverse_order_no_conflict
    slot_a = { berth: 'B1', start_hour: 8, end_hour: 16 }
    slot_b = { berth: 'B1', start_hour: 0, end_hour: 8 }
    refute MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b),
      'Adjacent windows must not conflict regardless of comparison order'
  end

  def test_overlapping_windows_still_conflict
    slot_a = { berth: 'B1', start_hour: 0, end_hour: 10 }
    slot_b = { berth: 'B1', start_hour: 9, end_hour: 16 }
    assert MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b)
  end

  def test_zero_duration_adjacent_no_conflict
    slot_a = { berth: 'B1', start_hour: 5, end_hour: 5 }
    slot_b = { berth: 'B1', start_hour: 5, end_hour: 10 }
    refute MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b),
      'Zero-duration window touching another should not conflict'
  end

  def test_tight_schedule_three_adjacent_no_conflicts
    slots = [
      { berth: 'B1', start_hour: 0, end_hour: 8 },
      { berth: 'B1', start_hour: 8, end_hour: 16 },
      { berth: 'B1', start_hour: 16, end_hour: 24 }
    ]
    slots.each_cons(2) do |a, b|
      refute MercuryLedger::Core::Dispatch.has_conflict?(a, b),
        "Adjacent slots #{a[:start_hour]}-#{a[:end_hour]} and #{b[:start_hour]}-#{b[:end_hour]} must not conflict"
    end
  end

  def test_different_berths_never_conflict
    slot_a = { berth: 'B1', start_hour: 0, end_hour: 24 }
    slot_b = { berth: 'B2', start_hour: 0, end_hour: 24 }
    refute MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b)
  end

  def test_fully_contained_window_conflicts
    slot_a = { berth: 'B1', start_hour: 0, end_hour: 24 }
    slot_b = { berth: 'B1', start_hour: 5, end_hour: 10 }
    assert MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b)
  end
end

class DomainManifestSignatureProtocolTest < Minitest::Test
  # Bug 5: sign_manifest constructs "cargo_tons:vessel_id" instead of
  # "vessel_id:cargo_tons". Self-consistent but cross-system incompatible.

  def test_manifest_signature_field_order
    secret = 'test-secret-key'
    sig = MercuryLedger::Core::Security.sign_manifest('VESSEL-001', 5000, secret)
    expected = Digest::SHA256.hexdigest("#{secret}:VESSEL-001:5000")
    assert_equal expected, sig,
      'Manifest signature must follow vessel_id:cargo_tons field ordering protocol'
  end

  def test_verify_manifest_with_canonical_ordering
    secret = 'my-secret'
    vessel = 'MV-ATLANTIC'
    tons = 12000
    sig = MercuryLedger::Core::Security.sign_manifest(vessel, tons, secret)
    assert MercuryLedger::Core::Security.verify_manifest(vessel, tons, secret, sig),
      'verify_manifest should validate signatures produced by sign_manifest'
  end

  def test_manifest_signature_changes_with_vessel_id
    secret = 'k'
    sig1 = MercuryLedger::Core::Security.sign_manifest('A', 100, secret)
    sig2 = MercuryLedger::Core::Security.sign_manifest('B', 100, secret)
    refute_equal sig1, sig2
  end

  def test_manifest_signature_distinguishes_field_swap
    secret = 'k'
    sig1 = MercuryLedger::Core::Security.sign_manifest('100', 200, secret)
    sig2 = MercuryLedger::Core::Security.sign_manifest('200', 100, secret)
    refute_equal sig1, sig2,
      'Swapping vessel_id and cargo_tons must produce different signatures'
  end

  def test_cross_system_verification
    secret = 'shared-secret'
    vessel = 'CARGO-7'
    tons = 3500
    external_sig = Digest::SHA256.hexdigest("#{secret}:#{vessel}:#{tons}")
    assert MercuryLedger::Core::Security.verify_manifest(vessel, tons, secret, external_sig),
      'External system using vessel_id:cargo_tons ordering should pass verification'
  end

  def test_numeric_vessel_id_not_confused_with_tonnage
    secret = 's'
    sig = MercuryLedger::Core::Security.sign_manifest('5000', 3000, secret)
    expected = Digest::SHA256.hexdigest("#{secret}:5000:3000")
    assert_equal expected, sig,
      'Numeric vessel_id should be in first position of data string'
  end
end

class DomainSampleVarianceTest < Minitest::Test
  # Bug 6: variance uses population formula (/ n) instead of sample (/ n-1).

  def test_sample_variance_two_elements
    values = [2.0, 4.0]
    result = MercuryLedger::Core::Statistics.variance(values)
    assert_in_delta 2.0, result, 0.001,
      'Sample variance of [2,4] should be 2.0 (Bessel correction: divide by n-1)'
  end

  def test_sample_variance_three_elements
    values = [2.0, 4.0, 6.0]
    result = MercuryLedger::Core::Statistics.variance(values)
    assert_in_delta 4.0, result, 0.001,
      'Sample variance of [2,4,6] should be 4.0'
  end

  def test_stddev_uses_sample_variance
    values = [10.0, 20.0]
    result = MercuryLedger::Core::Statistics.stddev(values)
    expected = Math.sqrt(50.0)
    assert_in_delta expected, result, 0.001,
      'Standard deviation should use sample variance (n-1 denominator)'
  end

  def test_variance_known_dataset
    values = [4, 7, 13, 2, 1]
    mean = values.sum.to_f / values.length
    expected = values.sum { |v| (v - mean)**2 }.to_f / (values.length - 1)
    result = MercuryLedger::Core::Statistics.variance(values)
    assert_in_delta expected, result, 0.001,
      'Variance must use Bessel-corrected (n-1) denominator'
  end

  def test_variance_single_element_returns_zero
    assert_equal 0.0, MercuryLedger::Core::Statistics.variance([5])
  end

  def test_variance_identical_values_is_zero
    values = [3.0, 3.0, 3.0, 3.0]
    assert_in_delta 0.0, MercuryLedger::Core::Statistics.variance(values), 0.001
  end

  def test_population_vs_sample_distinction
    values = [1, 2, 3, 4, 5]
    sample_var = MercuryLedger::Core::Statistics.variance(values)
    pop_var = values.sum { |v| (v - 3.0)**2 }.to_f / values.length
    assert sample_var > pop_var,
      'Sample variance (n-1) must be larger than population variance (n) for n>1'
  end
end

class MultiStepCircuitBreakerCascadeTest < Minitest::Test
  # Bug 7: CircuitBreaker handles half_open->open on failure, but doesn't
  # reset failure_count. Combined with Bug 2 (success resets wrong counter),
  # this creates a cascading hyper-sensitivity problem.

  def test_half_open_failure_resets_to_open
    cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 2, success_threshold: 2, timeout: 0)
    4.times { cb.record_failure }
    assert_equal 'open', cb.state
    sleep(0.01)
    assert_equal 'half_open', cb.state
    cb.record_failure
    assert_equal 'open', cb.state
  end

  def test_half_open_recovery_requires_fresh_failure_count
    cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 5, success_threshold: 2, timeout: 0)
    6.times { cb.record_failure }
    assert_equal 'open', cb.state
    sleep(0.01)
    assert_equal 'half_open', cb.state
    2.times { cb.record_success }
    assert_equal 'closed', cb.state
    5.times { cb.record_failure }
    assert_equal 'closed', cb.state,
      'After recovery, failure count must be reset; old failures should not carry over'
    cb.record_failure
    assert_equal 'open', cb.state
  end

  def test_repeated_open_halfopen_cycles_dont_accumulate
    cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 3, success_threshold: 1, timeout: 0)
    3.times do
      4.times { cb.record_failure }
      assert_equal 'open', cb.state
      sleep(0.01)
      cb.record_success
      assert_equal 'closed', cb.state
    end
    3.times { cb.record_failure }
    assert_equal 'closed', cb.state,
      'Failure count must not accumulate across open/halfopen/closed cycles'
  end

  def test_half_open_single_failure_goes_to_open_not_beyond
    cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 100, success_threshold: 1, timeout: 0)
    101.times { cb.record_failure }
    assert_equal 'open', cb.state
    sleep(0.01)
    assert_equal 'half_open', cb.state
    cb.record_failure
    assert_equal 'open', cb.state
  end
end

class MultiStepTotalDistanceMismatchTest < Minitest::Test
  # Bug 8: plan_multi_leg computes total_distance as crow-flies (first to last
  # waypoint) instead of summing individual leg distances. Individual legs are
  # correct, but total is wrong for any non-linear route.

  def test_zigzag_total_equals_sum_of_legs
    waypoints = [
      { name: 'A', nm: 0 },
      { name: 'B', nm: 100 },
      { name: 'C', nm: 30 },
      { name: 'D', nm: 200 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    leg_sum = result[:legs].sum { |l| l[:distance_nm] }
    assert_in_delta leg_sum, result[:total_distance], 0.01,
      'Total distance must equal sum of leg distances, not crow-flies distance'
  end

  def test_backtrack_route_total_exceeds_point_to_point
    waypoints = [
      { name: 'A', nm: 0 },
      { name: 'B', nm: 500 },
      { name: 'C', nm: 100 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    # Legs: A->B = 500, B->C = 400. Total should be 900.
    # Point-to-point: |100-0| = 100 (WRONG)
    assert_in_delta 900.0, result[:total_distance], 0.01,
      'Backtracking route total must be sum of legs (900), not point-to-point (100)'
  end

  def test_round_trip_total_is_double
    waypoints = [
      { name: 'Home', nm: 0 },
      { name: 'Dest', nm: 200 },
      { name: 'Home2', nm: 0 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    # Round trip: 200 + 200 = 400. Point-to-point: |0-0| = 0
    assert_in_delta 400.0, result[:total_distance], 0.01,
      'Round trip total must be 400, not 0 (point-to-point)'
  end

  def test_detour_route_total
    waypoints = [
      { name: 'A', nm: 0 },
      { name: 'B', nm: 300 },
      { name: 'C', nm: 50 },
      { name: 'D', nm: 100 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    # A->B: 300, B->C: 250, C->D: 50. Total: 600
    # Point-to-point: |100-0| = 100
    assert_in_delta 600.0, result[:total_distance], 0.01,
      'Detour route: total should be 600 (sum), not 100 (point-to-point)'
  end

  def test_linear_route_total_matches_both_methods
    # For monotonically increasing waypoints, both methods give the same answer
    waypoints = [
      { name: 'A', nm: 0 },
      { name: 'B', nm: 50 },
      { name: 'C', nm: 150 },
      { name: 'D', nm: 300 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    leg_sum = result[:legs].sum { |l| l[:distance_nm] }
    assert_in_delta 300.0, result[:total_distance], 0.01
    assert_in_delta leg_sum, result[:total_distance], 0.01
  end

  def test_individual_legs_correct_despite_total_bug
    waypoints = [
      { name: 'A', nm: 200 },
      { name: 'B', nm: 50 },
      { name: 'C', nm: 300 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    assert_equal 150.0, result[:legs][0][:distance_nm]
    assert_equal 250.0, result[:legs][1][:distance_nm]
    assert_in_delta 400.0, result[:total_distance], 0.01,
      'Total should be 400 (150+250), not 100 (point-to-point)'
  end

  def test_single_waypoint_oscillation
    waypoints = [
      { name: 'A', nm: 0 },
      { name: 'B', nm: 100 },
      { name: 'A2', nm: 0 },
      { name: 'B2', nm: 100 },
      { name: 'A3', nm: 0 }
    ]
    result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
    # Each leg: 100nm, 4 legs = 400nm. Point-to-point: 0
    assert_in_delta 400.0, result[:total_distance], 0.01,
      'Oscillating route total must be 400, not 0'
  end
end

class StateMachineDeescalationTypoTest < Minitest::Test
  # Bug 9: DEESCALATION_THRESHOLDS has 'watching' key instead of 'watch',
  # so the 'watch' level can never de-escalate.

  def test_watch_level_can_deescalate
    result = MercuryLedger::Core::Policy.should_deescalate?('watch', 4)
    assert result, 'Watch policy with 4 consecutive successes should allow de-escalation'
  end

  def test_watch_deescalation_threshold_exists
    threshold = MercuryLedger::Core::Policy::DEESCALATION_THRESHOLDS['watch']
    refute_nil threshold,
      "DEESCALATION_THRESHOLDS must contain 'watch' key (not 'watching')"
  end

  def test_watch_deescalation_requires_4_successes
    refute MercuryLedger::Core::Policy.should_deescalate?('watch', 3),
      '3 successes should not be enough to de-escalate from watch'
    assert MercuryLedger::Core::Policy.should_deescalate?('watch', 4),
      '4 successes should de-escalate from watch'
  end

  def test_policy_engine_deescalates_from_watch
    engine = MercuryLedger::Core::PolicyEngine.new(initial: 'watch')
    result = engine.deescalate(4)
    assert_equal 'normal', result,
      'PolicyEngine should de-escalate from watch to normal with sufficient streak'
  end

  def test_full_escalation_deescalation_cycle
    engine = MercuryLedger::Core::PolicyEngine.new
    engine.escalate(5)
    assert_equal 'watch', engine.current
    engine.deescalate(4)
    assert_equal 'normal', engine.current,
      'Full escalation->de-escalation cycle should return to normal'
  end

  def test_restricted_deescalation_still_works
    assert MercuryLedger::Core::Policy.should_deescalate?('restricted', 7)
  end

  def test_halted_deescalation_still_works
    assert MercuryLedger::Core::Policy.should_deescalate?('halted', 10)
  end

  def test_all_deescalation_levels_have_thresholds
    %w[watch restricted halted].each do |level|
      threshold = MercuryLedger::Core::Policy::DEESCALATION_THRESHOLDS[level]
      refute_nil threshold, "De-escalation threshold missing for '#{level}'"
    end
  end
end

class StateMachineShortestPathSelfTest < Minitest::Test
  # Bug 10: Workflow.shortest_path removes the from==to early return, so
  # self-paths return nil instead of [from]. This breaks any code checking
  # "am I already at the destination?" since the DAG has no self-loops.

  def test_self_path_returns_single_element
    result = MercuryLedger::Core::Workflow.shortest_path(:queued, :queued)
    assert_equal [:queued], result,
      'shortest_path from a state to itself must return [state]'
  end

  def test_self_path_not_nil
    result = MercuryLedger::Core::Workflow.shortest_path(:completed, :completed)
    refute_nil result,
      'Self-path for terminal state must not be nil'
  end

  def test_all_states_have_self_paths
    MercuryLedger::Core::Workflow::GRAPH.each_key do |state|
      path = MercuryLedger::Core::Workflow.shortest_path(state, state)
      refute_nil path, "Self-path for #{state} must not be nil"
      assert_equal [state], path, "Self-path for #{state} must be [#{state}]"
    end
  end

  def test_self_path_terminal_state_completed
    path = MercuryLedger::Core::Workflow.shortest_path(:completed, :completed)
    assert_equal [:completed], path,
      'Completed state self-path must return [:completed], not nil'
  end

  def test_self_path_terminal_state_cancelled
    path = MercuryLedger::Core::Workflow.shortest_path(:cancelled, :cancelled)
    assert_equal [:cancelled], path,
      'Cancelled state (no outgoing edges) self-path must return [:cancelled]'
  end

  def test_normal_path_still_works
    path = MercuryLedger::Core::Workflow.shortest_path(:queued, :completed)
    refute_nil path
    assert_equal :queued, path.first
    assert_equal :completed, path.last
  end

  def test_unreachable_path_returns_nil
    path = MercuryLedger::Core::Workflow.shortest_path(:completed, :queued)
    assert_nil path, 'Backward path should still be nil'
  end

  def test_self_path_length_is_one
    path = MercuryLedger::Core::Workflow.shortest_path(:arrived, :arrived)
    refute_nil path, 'Self-path must not be nil'
    assert_equal 1, path&.length,
      'Self-path length must be exactly 1'
  end
end

class ConcurrencyActiveFilterTruthinessTest < Minitest::Test
  # Bug 11: CorridorTable#active uses `r[:active] == true` instead of
  # `r[:active] != false`. Routes without an explicit :active key are
  # silently excluded (Ruby truthiness: nil != false is true, nil == true is false).

  def test_route_without_active_key_is_active_by_default
    table = MercuryLedger::Core::CorridorTable.new
    table.add('ch1', { channel: 'ch1', latency: 10 })
    active = table.active
    assert_equal 1, active.length,
      'Routes without :active key should be considered active by default'
  end

  def test_explicitly_active_route_is_active
    table = MercuryLedger::Core::CorridorTable.new
    table.add('ch1', { channel: 'ch1', latency: 10, active: true })
    assert_equal 1, table.active.length
  end

  def test_explicitly_inactive_route_excluded
    table = MercuryLedger::Core::CorridorTable.new
    table.add('ch1', { channel: 'ch1', latency: 10, active: false })
    assert_equal 0, table.active.length,
      'Routes with active: false must be excluded'
  end

  def test_mixed_routes_with_and_without_active_key
    table = MercuryLedger::Core::CorridorTable.new
    table.add('ch1', { channel: 'ch1', latency: 10 })                    # no key (default active)
    table.add('ch2', { channel: 'ch2', latency: 20, active: true })       # explicit true
    table.add('ch3', { channel: 'ch3', latency: 30, active: false })      # explicit false
    table.add('ch4', { channel: 'ch4', latency: 40 })                    # no key (default active)
    active = table.active
    assert_equal 3, active.length,
      'Should include routes without :active key and routes with active: true'
  end

  def test_nil_active_treated_as_active
    table = MercuryLedger::Core::CorridorTable.new
    table.add('ch1', { channel: 'ch1', latency: 10, active: nil })
    active = table.active
    assert_equal 1, active.length,
      'Route with active: nil should be treated as active (only false deactivates)'
  end

  def test_active_count_matches_convention
    table = MercuryLedger::Core::CorridorTable.new
    5.times { |i| table.add("ch#{i}", { channel: "ch#{i}", latency: i }) }
    table.add('disabled', { channel: 'disabled', latency: 99, active: false })
    assert_equal 5, table.active.length,
      'Only routes with explicit active: false should be excluded from active list'
  end

  def test_all_vs_active_difference_is_only_false_routes
    table = MercuryLedger::Core::CorridorTable.new
    table.add('ch1', { channel: 'ch1', latency: 5 })
    table.add('ch2', { channel: 'ch2', latency: 10, active: false })
    assert_equal 2, table.all.length
    assert_equal 1, table.active.length,
      'Difference between all and active should only be routes with active: false'
  end
end

class ConcurrencyRateLimiterFractionalTokenTest < Minitest::Test
  # Bug 12: RateLimiter.allow? uses `<= 0` instead of `< 1.0`, allowing
  # requests through with fractional tokens (0 < tokens < 1).

  def test_no_fractional_token_consumption
    limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 1, refill_rate: 0.0)
    assert limiter.allow?
    refute limiter.allow?,
      'Zero tokens remaining must deny request'
  end

  def test_slow_refill_below_one_token_denies
    t = Time.now.to_f
    limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 1, refill_rate: 0.5)
    assert limiter.allow?(t)
    refute limiter.allow?(t + 1.0),
      'Half a token (0.5) is not enough; should deny request'
  end

  def test_exact_one_token_allows
    t = Time.now.to_f
    limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 1, refill_rate: 1.0)
    assert limiter.allow?(t)
    assert limiter.allow?(t + 1.0),
      'Exactly 1.0 tokens should allow the request'
  end

  def test_fractional_token_not_usable
    t = Time.now.to_f
    limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 2, refill_rate: 0.1)
    assert limiter.allow?(t)
    assert limiter.allow?(t)
    refute limiter.allow?(t + 5.0),
      'Fractional token (0.5) must not allow a request'
  end

  def test_token_count_reflects_whole_tokens
    t = Time.now.to_f
    limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 5, refill_rate: 0.0)
    5.times { limiter.allow?(t) }
    assert_equal 0, limiter.tokens
  end
end

class IntegrationReplayLastWriteWinsTest < Minitest::Test
  # Bug 13: replay uses `>` instead of `>=` for sequence comparison, changing
  # from "last write wins" to "first write wins" for same-sequence events.
  # This breaks event sourcing semantics where the latest event at the same
  # sequence should supersede earlier ones.

  def test_last_event_with_same_sequence_wins
    events = [
      { id: 'order', sequence: 5, status: 'pending' },
      { id: 'order', sequence: 5, status: 'confirmed' }
    ]
    result = MercuryLedger::Core::Resilience.replay(events)
    assert_equal 1, result.length
    assert_equal 'confirmed', result[0][:status],
      'Last event with same sequence must win (last-write-wins semantics)'
  end

  def test_later_duplicate_overrides_earlier
    events = [
      { id: 'x', sequence: 1, value: 'original' },
      { id: 'x', sequence: 1, value: 'corrected' }
    ]
    result = MercuryLedger::Core::Resilience.replay(events)
    assert_equal 'corrected', result[0][:value],
      'Correction event at same sequence must override original'
  end

  def test_replay_convergence_with_same_sequence_duplicates
    events_a = [
      { id: 'a', sequence: 3, val: 'first' },
      { id: 'a', sequence: 3, val: 'second' }
    ]
    events_b = [
      { id: 'a', sequence: 3, val: 'second' },
      { id: 'a', sequence: 3, val: 'first' }
    ]
    # With last-write-wins: events_a gives 'second', events_b gives 'first'
    # With first-write-wins: events_a gives 'first', events_b gives 'second'
    # Either way convergence should be consistent for same-order inputs
    result_a = MercuryLedger::Core::Resilience.replay(events_a)
    assert_equal 'second', result_a[0][:val],
      'Last-write-wins: second event should supersede first'
  end

  def test_higher_sequence_still_wins_over_equal
    events = [
      { id: 'x', sequence: 1, val: 'v1' },
      { id: 'x', sequence: 2, val: 'v2' },
      { id: 'x', sequence: 2, val: 'v2-corrected' }
    ]
    result = MercuryLedger::Core::Resilience.replay(events)
    assert_equal 'v2-corrected', result[0][:val],
      'Latest event at highest sequence should win'
  end

  def test_replay_ordering_ascending
    events = [
      { id: 'a', sequence: 3 },
      { id: 'b', sequence: 1 },
      { id: 'c', sequence: 2 }
    ]
    result = MercuryLedger::Core::Resilience.replay(events)
    sequences = result.map { |e| e[:sequence] }
    assert_equal [1, 2, 3], sequences,
      'Replay must return events in ascending sequence order'
  end

  def test_event_correction_pattern
    # Simulates a real-world event correction scenario:
    # An event is recorded, then a corrected version arrives at the same sequence
    events = [
      { id: 'shipment-42', sequence: 10, tons: 1000, status: 'loaded' },
      { id: 'shipment-42', sequence: 10, tons: 1050, status: 'loaded-corrected' },
      { id: 'shipment-43', sequence: 11, tons: 500, status: 'loaded' }
    ]
    result = MercuryLedger::Core::Resilience.replay(events)
    shipment42 = result.find { |e| e[:id] == 'shipment-42' }
    assert_equal 1050, shipment42[:tons],
      'Corrected event (same sequence) must replace original in replay'
  end
end

class IntegrationTokenCleanupUnionTest < Minitest::Test
  # Bug 14: TokenStore.cleanup uses `&&` instead of `||`, requiring tokens to
  # be BOTH revoked AND expired to be cleaned up. This means:
  # - Revoked-but-fresh tokens linger (security risk)
  # - Expired-but-not-revoked tokens linger (memory leak)

  def test_revoked_fresh_token_cleaned
    store = MercuryLedger::Core::TokenStore.new
    store.store('tok-1', 'hash1', 3600)
    store.revoke('tok-1')
    removed = store.cleanup(Time.now.to_i)
    assert_equal 1, removed,
      'Revoked token must be cleaned even if not yet expired'
    assert_equal 0, store.count
  end

  def test_expired_unrevoked_token_cleaned
    store = MercuryLedger::Core::TokenStore.new
    now = Time.now.to_i
    store.store('tok-2', 'hash2', 60)
    removed = store.cleanup(now + 120)
    assert_equal 1, removed,
      'Expired token must be cleaned even if not revoked'
    assert_equal 0, store.count
  end

  def test_both_revoked_and_expired_cleaned
    store = MercuryLedger::Core::TokenStore.new
    now = Time.now.to_i
    store.store('tok-3', 'hash3', 30)
    store.revoke('tok-3')
    removed = store.cleanup(now + 60)
    assert_equal 1, removed
    assert_equal 0, store.count
  end

  def test_fresh_unrevoked_token_preserved
    store = MercuryLedger::Core::TokenStore.new
    store.store('tok-4', 'hash4', 3600)
    removed = store.cleanup(Time.now.to_i + 10)
    assert_equal 0, removed,
      'Fresh, non-revoked token must not be cleaned'
    assert_equal 1, store.count
  end

  def test_mixed_cleanup_scenario
    store = MercuryLedger::Core::TokenStore.new
    now = Time.now.to_i
    store.store('fresh', 'h1', 3600)      # fresh, not revoked -> keep
    store.store('expired', 'h2', 30)       # expired, not revoked -> clean
    store.store('revoked-fresh', 'h3', 3600) # revoked, not expired -> clean
    store.revoke('revoked-fresh')
    store.store('revoked-expired', 'h4', 30) # revoked and expired -> clean
    store.revoke('revoked-expired')
    removed = store.cleanup(now + 60)
    assert_equal 3, removed,
      'Should clean expired OR revoked tokens (union), keeping only fresh unrevoked'
    assert_equal 1, store.count
  end

  def test_revoked_token_security_cleanup
    store = MercuryLedger::Core::TokenStore.new
    # Simulate revoking a compromised token that hasn't expired yet
    store.store('compromised', 'hash', 86400) # 24-hour TTL
    store.revoke('compromised')
    removed = store.cleanup(Time.now.to_i)
    assert_equal 1, removed,
      'Compromised/revoked tokens must be cleaned immediately, not linger until expiry'
  end

  def test_mass_expiry_cleanup
    store = MercuryLedger::Core::TokenStore.new
    now = Time.now.to_i
    10.times { |i| store.store("expired-#{i}", "h#{i}", 30) }
    5.times { |i| store.store("fresh-#{i}", "h#{i}", 3600) }
    removed = store.cleanup(now + 30)
    assert_equal 10, removed,
      'All expired tokens must be cleaned in bulk'
    assert_equal 5, store.count
  end

  def test_cleanup_at_exact_ttl_boundary
    store = MercuryLedger::Core::TokenStore.new
    now = Time.now.to_i
    store.store('boundary', 'hash', 60)
    removed = store.cleanup(now + 60)
    assert_equal 1, removed,
      'Token at exact TTL boundary must be cleaned'
  end
end

# =============================================================================
# Parameterized matrix tests for broader coverage
# =============================================================================

class BugMatrixCoverageTest < Minitest::Test

  # --- Berth conflict boundary matrix ---
  [
    [0, 8, 8, 16, false, 'adjacent-touching'],
    [0, 8, 7, 16, true,  'overlapping-by-one'],
    [0, 10, 10, 20, false, 'exactly-adjacent'],
    [5, 5, 5, 10, false, 'zero-duration-touching'],
    [0, 24, 12, 36, true, 'partial-overlap'],
    [0, 0, 0, 0, false, 'zero-zero-adjacent'],
  ].each_with_index do |(s1, e1, s2, e2, expected, label), idx|
    define_method("test_berth_conflict_matrix_#{idx}_#{label}") do
      a = { berth: 'B1', start_hour: s1, end_hour: e1 }
      b = { berth: 'B1', start_hour: s2, end_hour: e2 }
      if expected
        assert MercuryLedger::Core::Dispatch.has_conflict?(a, b), "Expected conflict for #{label}"
      else
        refute MercuryLedger::Core::Dispatch.has_conflict?(a, b), "Expected no conflict for #{label}"
      end
    end
  end

  # --- Variance correctness matrix ---
  [
    [[1, 2], 0.5],
    [[1, 2, 3], 1.0],
    [[10, 10, 10], 0.0],
    [[2, 4, 4, 4, 5, 5, 7, 9], 4.571],
    [[100, 200], 5000.0],
  ].each_with_index do |(values, expected_var), idx|
    define_method("test_variance_matrix_#{idx}") do
      result = MercuryLedger::Core::Statistics.variance(values)
      assert_in_delta expected_var, result, 0.01,
        "Variance of #{values.inspect} should be #{expected_var}"
    end
  end

  # --- Multi-leg total-vs-legs consistency matrix ---
  [
    [[0, 100, 50, 200], 300.0, 'zigzag'],
    [[0, 500, 100], 900.0, 'backtrack'],
    [[0, 200, 0], 400.0, 'round-trip'],
    [[100, 0, 100], 200.0, 'bounce'],
    [[0, 100, 0, 100, 0], 400.0, 'oscillating'],
    [[50, 200, 50, 200], 450.0, 'repeated-backtrack'],
  ].each_with_index do |(nms, expected_total, label), idx|
    define_method("test_multileg_total_consistency_#{idx}_#{label}") do
      waypoints = nms.each_with_index.map { |nm, i| { name: "P#{i}", nm: nm } }
      result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
      assert_in_delta expected_total, result[:total_distance], 0.01,
        "Total distance for #{label}: expected #{expected_total} (sum of legs)"
    end
  end

  # --- Cost allocation rounding matrix ---
  [
    [3, 100.0, 33.33],
    [3, 10.0, 3.33],
    [7, 100.0, 14.29],
    [6, 100.0, 16.67],
  ].each_with_index do |(n_orders, budget, expected_each), idx|
    define_method("test_cost_allocation_rounding_matrix_#{idx}") do
      orders = (1..n_orders).map { |i| { id: i, urgency: 1 } }
      result = MercuryLedger::Core::Dispatch.allocate_costs(orders, budget)
      actual = result[0][:allocated]
      assert_equal expected_each, actual,
        "#{budget}/#{n_orders} = #{budget.to_f / n_orders} should round to #{expected_each}"
    end
  end

  # --- Manifest signature protocol matrix ---
  [
    ['SHIP-1', 1000, 'secret1'],
    ['VESSEL-ABC', 50000, 'key-xyz'],
    ['123', 456, 'numeric-id'],
    ['A', 1, 'minimal'],
  ].each_with_index do |(vessel, tons, secret), idx|
    define_method("test_manifest_protocol_matrix_#{idx}") do
      sig = MercuryLedger::Core::Security.sign_manifest(vessel, tons, secret)
      canonical = Digest::SHA256.hexdigest("#{secret}:#{vessel}:#{tons}")
      assert_equal canonical, sig,
        "Manifest for #{vessel}/#{tons} must match canonical vessel_id:cargo_tons format"
    end
  end

  # --- Circuit breaker success-reset matrix ---
  [2, 3, 5, 10].each_with_index do |threshold, idx|
    define_method("test_cb_success_resets_failure_count_threshold_#{threshold}") do
      cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: threshold, success_threshold: 1, timeout: 1)
      threshold.times { cb.record_failure }
      cb.record_success
      threshold.times { cb.record_failure }
      assert_equal 'closed', cb.state,
        "Threshold=#{threshold}: success should reset failures; breaker tripped prematurely"
    end
  end

  # --- Shortest path self-path matrix ---
  MercuryLedger::Core::Workflow::GRAPH.each_key do |state|
    define_method("test_shortest_self_path_#{state}") do
      path = MercuryLedger::Core::Workflow.shortest_path(state, state)
      refute_nil path, "Self-path for #{state} must not be nil"
      assert_equal [state], path
    end
  end

  # --- Active filter truthiness matrix ---
  [
    [nil, true, 'nil-active-defaults-to-included'],
    [true, true, 'explicit-true-included'],
    [false, false, 'explicit-false-excluded'],
  ].each_with_index do |(active_val, should_include, label), idx|
    define_method("test_active_filter_truthiness_#{idx}_#{label}") do
      table = MercuryLedger::Core::CorridorTable.new
      route = { channel: 'test', latency: 10 }
      route[:active] = active_val unless active_val.nil? && label.include?('nil')
      # For the nil test, don't set the key at all
      if label.include?('nil')
        route.delete(:active)
      end
      table.add('test', route)
      if should_include
        assert_equal 1, table.active.length, "Route with active=#{active_val.inspect} should be included"
      else
        assert_equal 0, table.active.length, "Route with active=#{active_val.inspect} should be excluded"
      end
    end
  end

  # --- Replay last-write-wins matrix ---
  [
    ['original', 'correction', 'correction', 'same-sequence-correction'],
    ['v1', 'v2', 'v2', 'sequential-updates'],
    ['old-data', 'new-data', 'new-data', 'data-replacement'],
  ].each_with_index do |(first_val, second_val, expected, label), idx|
    define_method("test_replay_last_write_wins_#{idx}_#{label}") do
      events = [
        { id: 'e', sequence: 1, val: first_val },
        { id: 'e', sequence: 1, val: second_val }
      ]
      result = MercuryLedger::Core::Resilience.replay(events)
      assert_equal expected, result[0][:val],
        "Last-write-wins for #{label}: expected '#{expected}'"
    end
  end

  # --- Token cleanup union-vs-intersection matrix ---
  [
    [true, true, true, 'revoked-and-expired'],
    [true, false, true, 'revoked-only'],
    [false, true, true, 'expired-only'],
    [false, false, false, 'fresh-and-valid'],
  ].each_with_index do |(revoked, expired, should_clean, label), idx|
    define_method("test_token_cleanup_union_#{idx}_#{label}") do
      store = MercuryLedger::Core::TokenStore.new
      now = Time.now.to_i
      ttl = expired ? 30 : 3600
      store.store('tok', 'hash', ttl)
      store.revoke('tok') if revoked
      cleanup_time = expired ? now + 60 : now + 10
      removed = store.cleanup(cleanup_time)
      if should_clean
        assert_equal 1, removed, "#{label}: token should be cleaned"
      else
        assert_equal 0, removed, "#{label}: token should be preserved"
      end
    end
  end

  # --- Watch de-escalation matrix ---
  (1..6).each do |streak|
    define_method("test_watch_deescalation_streak_#{streak}") do
      result = MercuryLedger::Core::Policy.should_deescalate?('watch', streak)
      if streak >= 4
        assert result, "Watch with streak=#{streak} should de-escalate"
      else
        refute result, "Watch with streak=#{streak} should NOT de-escalate"
      end
    end
  end
end
