# frozen_string_literal: true

require_relative '../test_helper'
require 'digest'
require_relative '../../shared/contracts/contracts'

class ExtendedTest < Minitest::Test
  # --- Domain / Order ---

  def test_severity_classify_critical
    assert_equal MercuryLedger::Core::Severity::CRITICAL, MercuryLedger::Core::Severity.classify('critical failure')
  end

  def test_severity_classify_default
    assert_equal MercuryLedger::Core::Severity::MEDIUM, MercuryLedger::Core::Severity.classify('routine task')
  end

  def test_severity_valid
    assert MercuryLedger::Core::Severity.valid?(3)
    refute MercuryLedger::Core::Severity.valid?(0)
    refute MercuryLedger::Core::Severity.valid?(6)
  end

  def test_severity_sla_for
    assert_equal 15, MercuryLedger::Core::Severity.sla_for(5)
    assert_equal 60, MercuryLedger::Core::Severity.sla_for(99)
  end

  def test_vessel_manifest_valid
    vm = MercuryLedger::Core::VesselManifest.new(vessel_id: 'V-1', name: 'Test Ship', cargo_tons: 45000)
    assert vm.valid?
    refute vm.heavy?
  end

  def test_vessel_manifest_heavy
    vm = MercuryLedger::Core::VesselManifest.new(vessel_id: 'V-2', name: 'Heavy Ship', cargo_tons: 60000)
    assert vm.heavy?
  end

  def test_order_factory_create_batch
    batch = MercuryLedger::Core::OrderFactory.create_batch(5)
    assert_equal 5, batch.length
    batch.each { |o| assert_kind_of MercuryLedger::Core::Order, o }
  end

  def test_order_factory_validate_order
    good = MercuryLedger::Core::Order.new(severity: 3, sla_minutes: 60)
    assert MercuryLedger::Core::OrderFactory.validate_order(good)
    refute MercuryLedger::Core::OrderFactory.validate_order('not_an_order')
  end

  # --- Dispatch ---

  def test_dispatch_batch_split
    orders = [
      { id: 'a', urgency: 5, eta: '10:00' },
      { id: 'b', urgency: 3, eta: '11:00' },
      { id: 'c', urgency: 1, eta: '12:00' }
    ]
    result = MercuryLedger::Core::Dispatch.dispatch_batch(orders, 2)
    assert_equal 2, result[:planned].length
    assert_equal 1, result[:rejected].length
    assert_equal 'a', result[:planned].first[:id]
  end

  def test_dispatch_estimate_cost
    orders = [{ urgency: 4 }, { urgency: 2 }]
    assert_equal 75.0, MercuryLedger::Core::Dispatch.estimate_cost(orders)
  end

  def test_dispatch_estimate_turnaround
    assert_equal 10.0, MercuryLedger::Core::Dispatch.estimate_turnaround(5000)
    assert_equal 0.0, MercuryLedger::Core::Dispatch.estimate_turnaround(-1)
  end

  def test_dispatch_check_capacity
    assert_equal :normal, MercuryLedger::Core::Dispatch.check_capacity(5, 100)
    assert_equal :critical, MercuryLedger::Core::Dispatch.check_capacity(100, 100)
    assert_equal :warning, MercuryLedger::Core::Dispatch.check_capacity(85, 100)
  end

  def test_dispatch_validate_batch
    valid = MercuryLedger::Core::Dispatch.validate_batch([
      { id: 'a', urgency: 5 },
      { id: nil, urgency: 3 },
      'bad'
    ])
    assert_equal 1, valid.length
  end

  def test_berth_slot_duration
    slot = MercuryLedger::Core::BerthSlot.new(berth_id: 'B-1', start_hour: 6, end_hour: 14)
    assert_equal 8, slot.duration
    assert slot.available?
  end

  def test_berth_planner_assign_release
    planner = MercuryLedger::Core::BerthPlanner.new
    planner.add_slot(MercuryLedger::Core::BerthSlot.new(berth_id: 'B-1', start_hour: 6, end_hour: 14))
    assert_equal 1, planner.available_slots.length
    assert planner.assign('B-1', 'V-1')
    assert_equal 0, planner.available_slots.length
    assert planner.release('B-1')
    assert_equal 1, planner.available_slots.length
  end

  def test_rolling_window_scheduler
    sched = MercuryLedger::Core::RollingWindowScheduler.new(window_size: 10)
    sched.submit(100, 'ord-1')
    sched.submit(105, 'ord-2')
    assert_equal 2, sched.count(110)
    assert_equal 1, sched.count(111)
  end

  # --- Routing ---

  def test_channel_score
    route = { channel: 'alpha', latency: 10, reliability: 0.5 }
    assert_equal 20.0, MercuryLedger::Core::Routing.channel_score(route)
  end

  def test_estimate_transit_time
    assert_equal 100.0, MercuryLedger::Core::Routing.estimate_transit_time(1400, speed_knots: 14.0)
    assert_equal 0.0, MercuryLedger::Core::Routing.estimate_transit_time(-10)
  end

  def test_plan_multi_leg
    wps = [{ name: 'A', nm: 0 }, { name: 'B', nm: 200 }, { name: 'C', nm: 50 }]
    plan = MercuryLedger::Core::Routing.plan_multi_leg(wps)
    assert_equal 2, plan[:legs].length
    leg_sum = plan[:legs].sum { |l| l[:distance_nm] }
    assert_in_delta leg_sum, plan[:total_distance], 0.01,
      'Total distance must equal sum of legs (350), not crow-flies (50)'
  end

  def test_corridor_table
    table = MercuryLedger::Core::CorridorTable.new
    table.add('alpha', { channel: 'alpha', latency: 5 })
    table.add('beta', { channel: 'beta', latency: 3, active: false })
    assert_equal 2, table.count
    assert_equal 1, table.active.length
  end

  # --- Policy ---

  def test_previous_policy
    assert_equal 'normal', MercuryLedger::Core::Policy.previous_policy('watch')
    assert_equal 'normal', MercuryLedger::Core::Policy.previous_policy('normal')
  end

  def test_should_deescalate
    assert MercuryLedger::Core::Policy.should_deescalate?('watch', 5)
    refute MercuryLedger::Core::Policy.should_deescalate?('watch', 2)
    refute MercuryLedger::Core::Policy.should_deescalate?('normal', 100)
  end

  def test_check_sla_compliance
    assert_equal :compliant, MercuryLedger::Core::Policy.check_sla_compliance(20, 60)
    assert_equal :at_risk, MercuryLedger::Core::Policy.check_sla_compliance(50, 60)
    assert_equal :breached, MercuryLedger::Core::Policy.check_sla_compliance(70, 60)
  end

  def test_sla_percentage
    assert_equal 50.0, MercuryLedger::Core::Policy.sla_percentage(30, 60)
  end

  def test_policy_engine_escalate
    engine = MercuryLedger::Core::PolicyEngine.new
    assert_equal 'normal', engine.current
    engine.escalate(3)
    assert_equal 'watch', engine.current
    assert_equal 1, engine.history.length
  end

  # --- Queue ---

  def test_estimate_wait_time
    assert_equal 5.0, MercuryLedger::Core::Queue.estimate_wait_time(50, 10)
    assert_equal 0.0, MercuryLedger::Core::Queue.estimate_wait_time(0, 10)
  end

  def test_queue_health
    health = MercuryLedger::Core::QueueMonitor.queue_health(30, 100)
    assert_equal :healthy, health.status
    danger = MercuryLedger::Core::QueueMonitor.queue_health(85, 100)
    assert_equal :danger, danger.status
  end

  def test_priority_queue
    pq = MercuryLedger::Core::PriorityQueue.new
    pq.enqueue('low', 1)
    pq.enqueue('high', 10)
    pq.enqueue('mid', 5)
    assert_equal 'high', pq.peek
    assert_equal 'high', pq.dequeue
    assert_equal 2, pq.size
  end

  def test_rate_limiter
    limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 2, refill_rate: 0.0)
    assert limiter.allow?
    assert limiter.allow?
    refute limiter.allow?
  end

  # --- Security ---

  def test_sign_and_verify_manifest
    sig = MercuryLedger::Core::Security.sign_manifest('V-1', 45000, 'secret')
    assert MercuryLedger::Core::Security.verify_manifest('V-1', 45000, 'secret', sig)
    refute MercuryLedger::Core::Security.verify_manifest('V-1', 45000, 'wrong', sig)
  end

  def test_sanitise_path
    assert_equal 'data/file.txt', MercuryLedger::Core::Security.sanitise_path('../../data/file.txt')
    assert_equal '.', MercuryLedger::Core::Security.sanitise_path('..')
  end

  def test_allowed_origin
    assert MercuryLedger::Core::Security.allowed_origin?('https://mercury.internal')
    refute MercuryLedger::Core::Security.allowed_origin?('https://evil.com')
  end

  def test_token_store
    store = MercuryLedger::Core::TokenStore.new
    store.store('t-1', 'hash', 3600)
    assert store.valid?('t-1')
    assert store.revoke('t-1')
    refute store.valid?('t-1')
  end

  # --- Resilience ---

  def test_deduplicate
    events = [
      { id: 'a', sequence: 1 },
      { id: 'a', sequence: 1 },
      { id: 'b', sequence: 2 }
    ]
    deduped = MercuryLedger::Core::Resilience.deduplicate(events)
    assert_equal 2, deduped.length
  end

  def test_replay_converges
    a = [{ id: 'x', sequence: 1 }, { id: 'x', sequence: 2 }]
    b = [{ id: 'x', sequence: 2 }, { id: 'x', sequence: 1 }]
    assert MercuryLedger::Core::Resilience.replay_converges?(a, b)
  end

  def test_checkpoint_manager
    mgr = MercuryLedger::Core::CheckpointManager.new
    mgr.record('cp-1', 100, 999)
    cp = mgr.get('cp-1')
    assert_equal 100, cp.sequence
    assert mgr.should_checkpoint?(200)
    refute mgr.should_checkpoint?(150)
  end

  def test_circuit_breaker_closed_to_open
    cb = MercuryLedger::Core::CircuitBreaker.new(failure_threshold: 3)
    assert_equal MercuryLedger::Core::Resilience::CB_CLOSED, cb.state
    3.times { cb.record_failure }
    assert_equal MercuryLedger::Core::Resilience::CB_OPEN, cb.state
    refute cb.allow_request?
  end

  # --- Statistics ---

  def test_mean
    assert_equal 3.0, MercuryLedger::Core::Statistics.mean([1, 2, 3, 4, 5])
  end

  def test_variance_and_stddev
    v = MercuryLedger::Core::Statistics.variance([2, 4, 4, 4, 5, 5, 7, 9])
    assert_in_delta 4.571, v, 0.01,
      'Sample variance of [2,4,4,4,5,5,7,9] should use Bessel correction (n-1)'
    s = MercuryLedger::Core::Statistics.stddev([2, 4, 4, 4, 5, 5, 7, 9])
    assert_in_delta Math.sqrt(4.571), s, 0.01
  end

  def test_median
    assert_equal 3.0, MercuryLedger::Core::Statistics.median([1, 3, 5])
    assert_equal 2.5, MercuryLedger::Core::Statistics.median([1, 2, 3, 4])
  end

  def test_moving_average
    result = MercuryLedger::Core::Statistics.moving_average([1, 2, 3, 4, 5], 3)
    assert_equal 3, result.length
    assert_equal 2.0, result[0]
  end

  def test_response_time_tracker
    tracker = MercuryLedger::Core::ResponseTimeTracker.new
    [10, 20, 30, 40, 50].each { |t| tracker.record(t) }
    assert_equal 5, tracker.count
    assert_operator tracker.p50, :>, 0
  end

  def test_heatmap_generator
    events = [{ row: 0, col: 0, value: 3.0 }, { row: 1, col: 1, value: 5.0 }]
    cells = MercuryLedger::Core::HeatmapGenerator.generate(events, 3, 3)
    assert_equal 2, cells.length
  end

  # --- Workflow ---

  def test_is_terminal_state
    assert MercuryLedger::Core::Workflow.is_terminal_state?(:arrived)
    assert MercuryLedger::Core::Workflow.is_terminal_state?(:cancelled)
    refute MercuryLedger::Core::Workflow.is_terminal_state?(:queued)
  end

  def test_shortest_path
    path = MercuryLedger::Core::Workflow.shortest_path(:queued, :arrived)
    assert_equal [:queued, :allocated, :departed, :arrived], path
  end

  def test_workflow_engine_lifecycle
    engine = MercuryLedger::Core::WorkflowEngine.new
    assert engine.register('E-1')
    assert_equal :queued, engine.get_state('E-1')
    result = engine.transition('E-1', :allocated)
    assert result.success
    assert_equal 1, engine.active_count
    engine.transition('E-1', :departed)
    engine.transition('E-1', :arrived)
    assert engine.is_terminal?('E-1')
    assert_equal 0, engine.active_count
    assert_equal 3, engine.audit_log.length
  end

  # --- Contracts ---

  def test_service_registry_url
    registry = MercuryLedger::Contracts::ServiceRegistry.new
    url = registry.get_service_url(:gateway)
    assert_equal 'http://localhost:8110', url
  end

  def test_service_registry_validate
    registry = MercuryLedger::Contracts::ServiceRegistry.new
    assert registry.validate_contract(:routing)
    assert registry.validate_contract(:gateway)
  end

  def test_service_registry_topological_order
    registry = MercuryLedger::Contracts::ServiceRegistry.new
    order = registry.topological_order
    assert_kind_of Array, order
    assert_operator order.length, :>=, 8
    audit_idx = order.index(:audit)
    resilience_idx = order.index(:resilience)
    assert_operator audit_idx, :<, resilience_idx
  end
end
