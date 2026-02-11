# frozen_string_literal: true

require_relative '../test_helper'
require 'digest'

class AdvancedCoreTest < Minitest::Test
  # --- Resilience: Checkpoint Record ---

  def test_checkpoint_record_updates_sequence
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('cp-1', 10, 1000)
    mgr.record('cp-1', 50, 2000)
    cp = mgr.get('cp-1')
    assert_equal 50, cp.sequence, "record should overwrite with newer sequence"
    assert_equal 2000, cp.timestamp, "record should overwrite timestamp too"
  end

  def test_checkpoint_record_updates_even_when_lower_sequence
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('cp-2', 100, 5000)
    mgr.record('cp-2', 50, 6000)
    cp = mgr.get('cp-2')
    assert_equal 50, cp.sequence, "record should always overwrite existing checkpoint"
  end

  def test_checkpoint_record_multiple_updates
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('cp-3', 1, 100)
    mgr.record('cp-3', 2, 200)
    mgr.record('cp-3', 3, 300)
    cp = mgr.get('cp-3')
    assert_equal 3, cp.sequence, "three successive records should result in sequence=3"
  end

  # --- Resilience: Checkpoint Merge ---

  def test_checkpoint_merge_keeps_higher_sequence
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('merge-1', 10, 1000)
    other = [OpalCommand::Core::Checkpoint.new(id: 'merge-1', sequence: 100, timestamp: 500)]
    mgr.merge(other)
    cp = mgr.get('merge-1')
    assert_equal 100, cp.sequence, "merge should keep the higher sequence (100 > 10)"
  end

  def test_checkpoint_merge_does_not_downgrade
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('merge-2', 100, 5000)
    other = [OpalCommand::Core::Checkpoint.new(id: 'merge-2', sequence: 5, timestamp: 9999)]
    mgr.merge(other)
    cp = mgr.get('merge-2')
    assert_equal 100, cp.sequence, "merge should not downgrade sequence from 100 to 5"
  end

  def test_checkpoint_merge_sequence_based_not_timestamp
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('merge-3', 50, 9000)
    other = [OpalCommand::Core::Checkpoint.new(id: 'merge-3', sequence: 80, timestamp: 1000)]
    mgr.merge(other)
    cp = mgr.get('merge-3')
    assert_equal 80, cp.sequence,
      "merge should compare by sequence (80 > 50), not timestamp"
  end

  # --- Resilience: latest_sequence ---

  def test_latest_sequence_returns_max
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('a', 10, 1000)
    mgr.record('b', 50, 2000)
    mgr.record('c', 30, 3000)
    assert_equal 50, mgr.latest_sequence, "latest_sequence should return the maximum sequence"
  end

  def test_latest_sequence_with_equal_timestamps
    mgr = OpalCommand::Core::CheckpointManager.new
    mgr.record('x', 5, 1000)
    mgr.record('y', 25, 1000)
    mgr.record('z', 15, 1000)
    assert_equal 25, mgr.latest_sequence, "latest_sequence should return max even with equal timestamps"
  end

  # --- Resilience: reconstruct_event_stream ---

  def test_reconstruct_event_stream_returns_events_after_checkpoint
    mgr = OpalCommand::Core::CheckpointManager.new
    events = [
      { id: 'e1', sequence: 5 },
      { id: 'e2', sequence: 10 },
      { id: 'e3', sequence: 15 },
      { id: 'e4', sequence: 20 }
    ]
    result = mgr.reconstruct_event_stream(events, 10)
    seqs = result.map { |e| e[:sequence] }
    assert seqs.all? { |s| s > 10 }, "Should only return events with sequence > checkpoint (10), got #{seqs}"
  end

  def test_reconstruct_event_stream_excludes_checkpoint_seq
    mgr = OpalCommand::Core::CheckpointManager.new
    events = (1..20).map { |i| { id: "e#{i}", sequence: i } }
    result = mgr.reconstruct_event_stream(events, 10)
    refute result.any? { |e| e[:sequence] == 10 }, "Should not include the checkpoint sequence itself"
    refute result.any? { |e| e[:sequence] < 10 }, "Should not include events before checkpoint"
  end

  # --- Workflow: register_at validation ---

  def test_register_at_rejects_invalid_state
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register_at('ent-1', :flying)
    state = engine.get_state('ent-1')
    assert OpalCommand::Core::Workflow.is_valid_state?(state),
      "register_at should only accept states in the GRAPH, but accepted :flying"
  end

  def test_register_at_valid_state_works
    engine = OpalCommand::Core::WorkflowEngine.new
    assert engine.register_at('ent-2', :allocated)
    assert_equal :allocated, engine.get_state('ent-2')
  end

  # --- Workflow: reopen history ---

  def test_reopen_records_correct_from_state
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('ent-3')
    engine.transition('ent-3', :allocated)
    engine.transition('ent-3', :departed)
    engine.transition('ent-3', :arrived)
    engine.reopen('ent-3', :queued)
    history = engine.history('ent-3')
    reopen_record = history.last
    assert_equal :arrived, reopen_record.from_state,
      "reopen history should record from_state as the previous terminal state (:arrived)"
    assert_equal :queued, reopen_record.to_state
  end

  def test_reopen_records_transition_count
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('ent-3b')
    engine.transition('ent-3b', :allocated)
    engine.transition('ent-3b', :departed)
    engine.transition('ent-3b', :arrived)
    before_count = engine.history('ent-3b').length
    engine.reopen('ent-3b', :queued)
    after_count = engine.history('ent-3b').length
    assert_equal before_count + 1, after_count,
      "reopen should add a transition record to history"
  end

  def test_reopen_fails_on_non_terminal
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('ent-5')
    result = engine.reopen('ent-5', :allocated)
    refute result.success
    assert_equal 'not_terminal', result.error
  end

  # --- Workflow: batch_transition snapshot isolation ---

  def test_batch_transition_cascading_within_batch
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('bt-chain')
    result = engine.batch_transition([
      ['bt-chain', :allocated],
      ['bt-chain', :departed]
    ])
    assert_equal 2, result[:success_count],
      "Second transition in batch should see first transition's result"
    assert_equal :departed, engine.get_state('bt-chain')
  end

  def test_batch_transition_simple
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('bt-1')
    engine.register('bt-2')
    engine.register('bt-3')
    result = engine.batch_transition([['bt-1', :allocated], ['bt-2', :allocated], ['bt-3', :cancelled]])
    assert_equal 3, result[:success_count], "All 3 transitions should succeed"
    assert_equal 3, result[:total]
  end

  def test_batch_transition_partial_failure
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('bt-4')
    result = engine.batch_transition([['bt-4', :allocated], ['bt-missing', :allocated]])
    assert_equal 1, result[:success_count]
    failed = result[:results].find { |r| r[:entity_id] == 'bt-missing' }
    assert_equal 'not_found', failed[:error]
  end

  # --- Workflow: reconstruct_state ---

  def test_reconstruct_state_returns_current
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('rs-1')
    engine.transition('rs-1', :allocated)
    engine.transition('rs-1', :departed)
    state = engine.reconstruct_state('rs-1')
    assert_equal :departed, state,
      "reconstruct_state should return the current state (to_state of last transition)"
  end

  def test_reconstruct_state_after_full_path
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('rs-2')
    engine.transition('rs-2', :allocated)
    engine.transition('rs-2', :departed)
    engine.transition('rs-2', :arrived)
    state = engine.reconstruct_state('rs-2')
    assert_equal :arrived, state, "After full path, reconstruct_state should return :arrived"
  end

  # --- Workflow: valid_transition_path? ---

  def test_valid_transition_path_checks_entity_current_state
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('vtp-1')
    engine.transition('vtp-1', :allocated)
    path_from_queued = [:queued, :allocated, :departed, :arrived]
    result = engine.valid_transition_path?(path_from_queued)
    assert result, "Path from queued through arrived should be valid edges"
  end

  # --- Queue: batch_dequeue ordering ---

  def test_batch_dequeue_returns_highest_priority_first
    pq = OpalCommand::Core::PriorityQueue.new
    pq.enqueue('low', 1)
    pq.enqueue('high', 10)
    pq.enqueue('mid', 5)
    pq.enqueue('top', 20)
    dequeued = pq.batch_dequeue(3)
    assert_equal 'top', dequeued[0], "First dequeued item should be highest priority (20)"
    assert_equal 'high', dequeued[1], "Second should be priority 10"
    assert_equal 'mid', dequeued[2], "Third should be priority 5"
  end

  def test_batch_dequeue_preserves_priority_order
    pq = OpalCommand::Core::PriorityQueue.new
    (1..10).each { |i| pq.enqueue("item-#{i}", i) }
    dequeued = pq.batch_dequeue(5)
    priorities_descending = dequeued == %w[item-10 item-9 item-8 item-7 item-6]
    assert priorities_descending,
      "batch_dequeue should return items in descending priority order, got #{dequeued}"
  end

  # --- Queue: merge side effect ---

  def test_merge_does_not_destroy_source_queue
    pq_a = OpalCommand::Core::PriorityQueue.new
    pq_b = OpalCommand::Core::PriorityQueue.new
    pq_a.enqueue('alpha', 5)
    pq_b.enqueue('beta', 10)
    pq_b.enqueue('gamma', 15)
    original_b_size = pq_b.size
    pq_a.merge(pq_b)
    assert_equal original_b_size, pq_b.size,
      "merge should not clear the source queue (pq_b should still have #{original_b_size} items)"
  end

  def test_priority_queue_merge_maintains_order
    pq_a = OpalCommand::Core::PriorityQueue.new
    pq_b = OpalCommand::Core::PriorityQueue.new
    pq_a.enqueue('alpha', 5)
    pq_a.enqueue('beta', 10)
    pq_b.enqueue('gamma', 15)
    pq_b.enqueue('delta', 1)
    pq_a.merge(pq_b)
    assert_equal 'gamma', pq_a.peek, "After merge, highest priority (15) should be at the front"
    assert_equal 'gamma', pq_a.dequeue
    assert_equal 'beta', pq_a.dequeue
    assert_equal 'alpha', pq_a.dequeue
    assert_equal 'delta', pq_a.dequeue
  end

  def test_priority_queue_top_n
    pq = OpalCommand::Core::PriorityQueue.new
    pq.enqueue('a', 1)
    pq.enqueue('b', 5)
    pq.enqueue('c', 3)
    top = pq.top_n(2)
    assert_equal 2, top.length
    assert_equal 'b', top[0]
    assert_equal 'c', top[1]
  end

  # --- Security: rotate_tokens ---

  def test_rotate_tokens_resets_issued_at
    store = OpalCommand::Core::TokenStore.new
    store.store('rot-1', 'hash1', 3600)
    store.rotate_tokens(10)
    refute store.valid?('rot-1', Time.now.to_i + 20),
      "After rotating to 10s TTL, token should be expired after 20s from issue time"
  end

  def test_rotate_tokens_makes_token_valid_within_new_ttl
    store = OpalCommand::Core::TokenStore.new
    store.store('rot-2', 'hash', 5)
    sleep(0.01)
    store.rotate_tokens(3600)
    assert store.valid?('rot-2'),
      "After rotating to 3600s TTL, recently-stored token should still be valid"
  end

  # --- Security: active_tokens boundary ---

  def test_active_tokens_at_boundary
    store = OpalCommand::Core::TokenStore.new
    now = Time.now.to_i
    store.store('boundary-1', 'hash', 60)
    active = store.active_tokens(now + 60)
    refute_includes active, 'boundary-1',
      "Token at exact TTL boundary should not be active"
  end

  def test_active_tokens_consistent_with_valid
    store = OpalCommand::Core::TokenStore.new
    now = Time.now.to_i
    store.store('consistency-1', 'hash', 60)
    check_time = now + 60
    active = store.active_tokens(check_time)
    is_valid = store.valid?('consistency-1', check_time)
    active_contains = active.include?('consistency-1')
    assert_equal is_valid, active_contains,
      "active_tokens and valid? should agree at boundary (active=#{active_contains}, valid=#{is_valid})"
  end

  # --- Security: transfer_token ---

  def test_transfer_token_atomicity
    store = OpalCommand::Core::TokenStore.new
    store.store('src-1', 'hash', 3600)
    assert store.valid?('src-1'), "Source token should be valid before transfer"
    result = store.transfer_token('src-1', 'dest-1', 'new_hash', 3600)
    assert result[:success]
    refute store.valid?('src-1'), "Source should be revoked after transfer"
    assert store.valid?('dest-1'), "Destination should be valid after transfer"
  end

  # --- Security: validate_token_chain ---

  def test_validate_token_chain_checks_all_tokens
    store = OpalCommand::Core::TokenStore.new
    store.store('chain-1', 'h', 3600)
    store.store('chain-3', 'h', 3600)
    result = store.validate_token_chain(%w[chain-1 chain-2 chain-3])
    assert_equal %w[chain-1], result[:valid]
    assert_equal %w[chain-2 chain-3], result[:invalid],
      "validate_token_chain should report all invalid tokens, not just the first"
  end

  def test_validate_token_chain_all_valid
    store = OpalCommand::Core::TokenStore.new
    store.store('ok-1', 'h', 3600)
    store.store('ok-2', 'h', 3600)
    store.store('ok-3', 'h', 3600)
    result = store.validate_token_chain(%w[ok-1 ok-2 ok-3])
    assert_equal 3, result[:valid].length
    assert_empty result[:invalid]
  end

  # --- Security: bulk_revoke ---

  def test_bulk_revoke
    store = OpalCommand::Core::TokenStore.new
    store.store('br-1', 'h', 3600)
    store.store('br-2', 'h', 3600)
    store.store('br-3', 'h', 3600)
    revoked = store.bulk_revoke(['br-1', 'br-3'])
    assert_equal 2, revoked
    refute store.valid?('br-1')
    assert store.valid?('br-2')
    refute store.valid?('br-3')
  end

  # --- Dispatch: allocate_berths ---

  def test_allocate_berths_heavy_to_long
    vessels = [
      { id: 'v-small', cargo_tons: 5000 },
      { id: 'v-large', cargo_tons: 90000 },
      { id: 'v-medium', cargo_tons: 40000 }
    ]
    berths = [
      { id: 'b-200', length: 200 },
      { id: 'b-400', length: 400 },
      { id: 'b-100', length: 100 }
    ]
    result = OpalCommand::Core::Dispatch.allocate_berths(vessels, berths)
    heavy = result.find { |a| a[:vessel_id] == 'v-large' }
    assert_equal 'b-400', heavy[:berth_id],
      "Heaviest vessel (90k tons) should be assigned to longest berth (400m)"
  end

  # --- Dispatch: optimal_schedule ---

  def test_optimal_schedule_highest_urgency_first
    orders = [
      { id: 'low', urgency: 1 },
      { id: 'high', urgency: 10 },
      { id: 'mid', urgency: 5 }
    ]
    slots = [{ start_hour: 6 }, { start_hour: 10 }, { start_hour: 14 }]
    schedule = OpalCommand::Core::Dispatch.optimal_schedule(orders, slots)
    assert_equal 'high', schedule.first[:order_id],
      "Highest urgency order should be scheduled first"
  end

  # --- Dispatch: estimate_fuel_consumption ---

  def test_estimate_fuel_consumption_laden_vs_ballast
    distance = 100
    deadweight = 1000
    laden_fuel = OpalCommand::Core::Dispatch.estimate_fuel_consumption(distance, deadweight, laden: true)
    ballast_fuel = OpalCommand::Core::Dispatch.estimate_fuel_consumption(distance, deadweight, laden: false)
    assert_operator laden_fuel, :>, ballast_fuel,
      "Laden fuel consumption should be higher than ballast"
  end

  # --- Dispatch: compute_voyage_cost precision ---

  def test_compute_voyage_cost_precision
    legs = [
      { distance_nm: 33.33 },
      { distance_nm: 33.33 },
      { distance_nm: 33.34 }
    ]
    result = OpalCommand::Core::Dispatch.compute_voyage_cost(legs, fuel_rate_per_nm: 0.35)
    expected = ((33.33 + 33.33 + 33.34) * 0.35).round(2)
    assert_in_delta expected, result, 0.01,
      "Voyage cost should sum distances first then apply rate, not round per-leg"
  end

  # --- Statistics: EWMA ---

  def test_ewma_tracker_weighting
    tracker = OpalCommand::Core::EWMATracker.new(alpha: 0.3)
    tracker.update(100)
    assert_in_delta 100.0, tracker.value, 0.01
    tracker.update(200)
    expected = 0.3 * 200.0 + 0.7 * 100.0
    assert_in_delta expected, tracker.value, 0.01,
      "EWMA should weight: alpha * new_value + (1-alpha) * old_value"
  end

  def test_ewma_tracker_responds_to_new_values
    tracker = OpalCommand::Core::EWMATracker.new(alpha: 0.3)
    tracker.update(100)
    tracker.update(200)
    assert_operator tracker.value, :>, 100.0,
      "After updating with 200, EWMA should be above initial 100"
  end

  # --- Statistics: Correlation consistency ---

  def test_correlation_tracker_perfect_positive
    ct = OpalCommand::Core::CorrelationTracker.new
    10.times { |i| ct.record(i, i) }
    corr = ct.correlation
    assert_in_delta 1.0, corr, 0.001, "Perfect positive correlation should be 1.0"
  end

  def test_correlation_tracker_perfect_negative
    ct = OpalCommand::Core::CorrelationTracker.new
    10.times { |i| ct.record(i, 10 - i) }
    corr = ct.correlation
    assert_in_delta(-1.0, corr, 0.001, "Perfect negative correlation should be -1.0")
  end

  def test_correlation_covariance_sample_vs_population
    ct = OpalCommand::Core::CorrelationTracker.new
    data = [[1, 2], [3, 4], [5, 6], [7, 8]]
    data.each { |x, y| ct.record(x, y) }
    cov = ct.covariance
    expected_sample = data.sum { |x, y| (x - 4.0) * (y - 5.0) } / (data.length - 1).to_f
    assert_in_delta expected_sample, cov, 0.001,
      "Covariance should use sample formula (n-1 divisor)"
  end

  # --- Policy: auto_adjust ---

  def test_policy_engine_auto_adjust_escalation
    engine = OpalCommand::Core::PolicyEngine.new
    result = engine.auto_adjust(5, 0)
    assert_equal 'watch', result, "5 failures should escalate from normal to watch"
  end

  def test_policy_engine_auto_adjust_no_immediate_deescalation
    engine = OpalCommand::Core::PolicyEngine.new
    result = engine.auto_adjust(5, 5)
    assert_equal 'watch', result,
      "auto_adjust with both failure_burst=5 and success_streak=5 should escalate and stay (not immediately deescalate)"
  end

  def test_policy_engine_auto_adjust_deescalation
    engine = OpalCommand::Core::PolicyEngine.new(initial: 'watch')
    result = engine.auto_adjust(0, 5)
    assert_equal 'normal', result, "5 successes from watch should deescalate to normal"
  end

  def test_policy_chain_most_severe
    chain = OpalCommand::Core::PolicyChain.new(%w[normal watch restricted])
    assert_equal 'restricted', chain.most_severe
  end

  def test_policy_chain_escalate_all
    chain = OpalCommand::Core::PolicyChain.new(%w[normal normal watch])
    chain.escalate_all(5)
    levels = chain.current_levels
    assert_includes levels, 'watch'
    assert_includes levels, 'restricted'
  end

  def test_policy_engine_severity_level
    engine = OpalCommand::Core::PolicyEngine.new(initial: 'restricted')
    assert_equal 2, engine.severity_level, "restricted is index 2 in ORDER"
  end

  # --- Workflow misc ---

  def test_entities_in_state
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('es-1')
    engine.register('es-2')
    engine.register('es-3')
    engine.transition('es-1', :allocated)
    queued = engine.entities_in_state(:queued)
    assert_equal 2, queued.length
    assert_includes queued, 'es-2'
    assert_includes queued, 'es-3'
  end

  def test_transition_count
    engine = OpalCommand::Core::WorkflowEngine.new
    engine.register('tc-1')
    engine.transition('tc-1', :allocated)
    engine.transition('tc-1', :departed)
    assert_equal 2, engine.transition_count('tc-1')
    assert_equal 2, engine.transition_count
  end
end
