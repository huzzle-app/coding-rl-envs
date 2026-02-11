# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/gateway/service'
require_relative '../../services/auth/service'
require_relative '../../services/intake/service'
require_relative '../../services/ledger/service'
require_relative '../../services/settlement/service'
require_relative '../../services/reconcile/service'
require_relative '../../services/policy/service'
require_relative '../../services/risk/service'
require_relative '../../services/audit/service'
require_relative '../../services/analytics/service'
require_relative '../../services/notifications/service'
require_relative '../../services/reporting/service'
require 'digest'

class AdvancedIntegrationTest < Minitest::Test
  # --- Gateway: weighted_admission ---

  def test_gateway_weighted_admission_rejects_risk_70
    result = OpalCommand::Services::Gateway.weighted_admission(
      current_load: 10, max_capacity: 100, risk_score: 75, priority: :normal
    )
    refute result[:admitted], "Risk score 75 should be denied (threshold should be 70)"
  end

  def test_gateway_weighted_admission_float_truncation
    result = OpalCommand::Services::Gateway.weighted_admission(
      current_load: 10, max_capacity: 100, risk_score: 79.9, priority: :normal
    )
    refute result[:admitted],
      "Risk score 79.9 should be denied at threshold 70, not pass due to integer truncation"
  end

  def test_gateway_weighted_admission_safe
    result = OpalCommand::Services::Gateway.weighted_admission(
      current_load: 10, max_capacity: 100, risk_score: 50, priority: :normal
    )
    assert result[:admitted], "Risk score 50 should be admitted"
  end

  def test_gateway_risk_boundary_at_80
    result = OpalCommand::Services::Gateway.weighted_admission(
      current_load: 10, max_capacity: 100, risk_score: 80, priority: :normal
    )
    refute result[:admitted], "Risk score of exactly 80 should be denied"
  end

  # --- Gateway: load_balanced_select ---

  def test_gateway_load_balanced_least_loaded_selects_highest_capacity
    nodes = [
      OpalCommand::Services::Gateway::RouteNode.new(id: 'n1', region: 'us', latency_ms: 10, capacity: 30, active: true),
      OpalCommand::Services::Gateway::RouteNode.new(id: 'n2', region: 'us', latency_ms: 50, capacity: 90, active: true),
      OpalCommand::Services::Gateway::RouteNode.new(id: 'n3', region: 'eu', latency_ms: 20, capacity: 60, active: true)
    ]
    selected = OpalCommand::Services::Gateway.load_balanced_select(nodes, strategy: :least_loaded)
    refute_nil selected
    max_cap = nodes.max_by(&:capacity)
    assert_equal max_cap.id, selected.id,
      "least_loaded should select node with highest available capacity"
  end

  # --- Gateway: select_primary_node ---

  def test_gateway_select_primary_highest_score
    nodes = [
      OpalCommand::Services::Gateway::RouteNode.new(id: 'slow', region: 'us', latency_ms: 200, capacity: 50, active: true),
      OpalCommand::Services::Gateway::RouteNode.new(id: 'fast', region: 'us', latency_ms: 10, capacity: 100, active: true),
      OpalCommand::Services::Gateway::RouteNode.new(id: 'mid', region: 'eu', latency_ms: 50, capacity: 80, active: true)
    ]
    primary = OpalCommand::Services::Gateway.select_primary_node(nodes)
    refute_nil primary
    assert_equal 'fast', primary.id,
      "Primary node should have the highest score (lowest latency, highest capacity)"
  end

  # --- Gateway: admission_control boundary ---

  def test_gateway_admission_at_threshold
    result = OpalCommand::Services::Gateway.admission_control(
      current_load: 85, max_capacity: 100, priority: :normal
    )
    refute result[:admitted],
      "Load at exactly the threshold (85/100 = 85% >= 85%) should be denied"
  end

  # --- Settlement: berth penalty ---

  def test_settlement_berth_penalty_formula
    penalty = OpalCommand::Services::Settlement.compute_berth_penalty(300, 200, 3)
    excess = 300 - 200
    expected = (excess * 15.0) + (3 * 50.0)
    assert_in_delta expected, penalty, 0.01,
      "Berth penalty should be: excess_length * 15 + overstay_hours * 50"
  end

  def test_settlement_berth_penalty_scales_with_hours
    penalty_2h = OpalCommand::Services::Settlement.compute_berth_penalty(250, 200, 2)
    penalty_4h = OpalCommand::Services::Settlement.compute_berth_penalty(250, 200, 4)
    assert_operator penalty_4h, :>, penalty_2h, "Longer overstay should incur higher penalty"
    expected_2h = (50 * 15.0) + (2 * 50.0)
    assert_in_delta expected_2h, penalty_2h, 0.01, "2h penalty: excess*15 + hours*50"
  end

  # --- Settlement: can_berth? with tide ---

  def test_settlement_can_berth_with_tide
    result = OpalCommand::Services::Settlement.can_berth?(12.0, 10.0, tide_level_m: 3.0)
    assert result,
      "Vessel with 12m draft should fit in 10m berth when tide adds 3m (effective depth 13m)"
  end

  def test_settlement_cannot_berth_without_tide
    result = OpalCommand::Services::Settlement.can_berth?(12.0, 10.0, tide_level_m: 0.0)
    refute result, "12m draft should not fit in 10m berth without tide"
  end

  # --- Settlement: estimate_laden_fuel ---

  def test_settlement_laden_fuel_vs_ballast
    laden = OpalCommand::Services::Settlement.estimate_laden_fuel(100, 1000, laden: true)
    ballast = OpalCommand::Services::Settlement.estimate_laden_fuel(100, 1000, laden: false)
    assert_operator laden, :>, ballast,
      "Laden fuel should be higher than ballast fuel"
  end

  # --- Settlement: compute_voyage_cost precision ---

  def test_settlement_voyage_cost_precision
    legs = [
      { distance_nm: 33.33 },
      { distance_nm: 33.33 },
      { distance_nm: 33.34 }
    ]
    result = OpalCommand::Services::Settlement.compute_voyage_cost(legs, fuel_rate_per_nm: 0.35)
    expected = ((33.33 + 33.33 + 33.34) * 0.35).round(2)
    assert_in_delta expected, result, 0.01,
      "Voyage cost should sum all distances then apply rate"
  end

  # --- Settlement: multi_berth_schedule ---

  def test_settlement_multi_berth_largest_first
    berths = [{ id: 'b-s', capacity: 50 }, { id: 'b-l', capacity: 300 }, { id: 'b-m', capacity: 150 }]
    vessels = [{ id: 'v-huge', length: 350 }, { id: 'v-tiny', length: 80 }]
    schedule = OpalCommand::Services::Settlement.multi_berth_schedule(berths, vessels)
    huge_assignment = schedule.find { |a| a[:vessel_id] == 'v-huge' }
    assert_equal 'b-l', huge_assignment[:berth_id],
      "Largest vessel should get berth with highest capacity"
  end

  # --- Risk: aggregate ---

  def test_risk_aggregate_recent_weighted_higher
    scores = [20, 50, 80]
    agg = OpalCommand::Services::Risk.aggregate_risk(scores)
    assert_equal 80, agg[:max]
    assert_operator agg[:overall], :>, 50.0,
      "Most recent score (80) should have highest weight, pulling average above 50"
  end

  def test_risk_aggregate_max
    scores = [20, 50, 80, 30]
    agg = OpalCommand::Services::Risk.aggregate_risk(scores)
    assert_equal 80, agg[:max], "aggregate_risk max should be the highest score"
  end

  def test_risk_trend_analysis
    scores = [10, 20, 30, 40, 50]
    trends = OpalCommand::Services::Risk.risk_trend(scores, window: 3)
    assert_equal 3, trends.length
    assert_equal :increasing, trends.first[:trend]
  end

  # --- Reconcile: cascading budget integrity ---

  def test_reconcile_cascading_budget_integrity
    deltas = [5.0, 10.0, 15.0, 20.0]
    result = OpalCommand::Services::Reconcile.cascading_reconcile(deltas, available_budget: 200.0)
    total = result[:total_spent] + result[:remaining_budget]
    assert_in_delta 200.0, total, 0.01,
      "Total spent + remaining should equal original budget (precision matters)"
  end

  def test_reconcile_cascading_small_deltas_precision
    deltas = [0.33, 0.33, 0.34]
    result = OpalCommand::Services::Reconcile.cascading_reconcile(deltas, available_budget: 10.0)
    total = result[:total_spent] + result[:remaining_budget]
    assert_in_delta 10.0, total, 0.01,
      "Budget integrity should hold even with fractional deltas"
  end

  # --- Reconcile: priority order ---

  def test_reconcile_priority_order_descending
    items = [
      { id: 'a', delta_ratio: 0.3 },
      { id: 'b', delta_ratio: 0.8 },
      { id: 'c', delta_ratio: 0.1 }
    ]
    ordered = OpalCommand::Services::Reconcile.reconcile_priority_order(items)
    assert_equal 'b', ordered.first[:id],
      "reconcile_priority_order should sort by highest delta_ratio first"
  end

  # --- Notifications: cascade order ---

  def test_notifications_cascade_step_order
    result = OpalCommand::Services::Notifications.cascade_notifications(
      operators: ['op1'], base_severity: 2, message: 'alert', escalation_steps: 3
    )
    assert_equal 3, result.length
    severities = result.map { |n| n[:severity] }
    assert_equal [2, 3, 4], severities,
      "Cascade should escalate severity in order: 2 -> 3 -> 4"
  end

  def test_notifications_cascade_with_multiple_operators
    result = OpalCommand::Services::Notifications.cascade_notifications(
      operators: %w[op1 op2], base_severity: 1, message: 'test', escalation_steps: 3
    )
    expected_count = 2 * 3
    assert_equal expected_count, result.length,
      "2 operators x 3 steps = 6 notifications"
    severities = result.each_slice(2).map { |pair| pair.first[:severity] }
    assert_equal [1, 2, 3], severities, "Severity should escalate each step"
  end

  # --- Notifications: priority_dispatch channels ---

  def test_notifications_priority_dispatch_channel_limit
    notifs = [
      { operator_id: 'a', severity: 3, channels: %w[log email sms pager] }
    ]
    dispatched = OpalCommand::Services::Notifications.priority_dispatch(notifs, max_channels: 2)
    assert_equal 2, dispatched.first[:channels].length,
      "priority_dispatch with max_channels=2 should return exactly 2 channels"
  end

  def test_notifications_priority_dispatch_descending
    notifs = [
      { operator_id: 'a', severity: 2, channels: %w[log email] },
      { operator_id: 'b', severity: 5, channels: %w[log email sms pager] },
      { operator_id: 'c', severity: 1, channels: %w[log] }
    ]
    dispatched = OpalCommand::Services::Notifications.priority_dispatch(notifs)
    assert_equal 5, dispatched.first[:severity],
      "priority_dispatch should put highest severity first"
  end

  # --- Notifications: severity 5 channels ---

  def test_notifications_severity_5_includes_pager
    channels = OpalCommand::Services::Notifications::SEVERITY_CHANNELS[5]
    assert_includes channels, 'pager',
      "Severity 5 (highest) should include pager channel"
  end

  # --- Notifications: escalate_severity cap ---

  def test_notifications_escalate_severity_cap
    result = OpalCommand::Services::Notifications.escalate_severity(4)
    assert_equal 5, result, "escalate_severity(4) should reach 5 (the maximum)"
  end

  # --- Analytics: fleet_trend anomaly index ---

  def test_analytics_fleet_trend_anomaly_index_alignment
    values = [10, 10, 10, 10, 100, 10, 10, 10]
    result = OpalCommand::Services::Analytics.fleet_trend_with_anomalies(values, window: 3, threshold_z: 1.5)
    refute_empty result[:anomalies][:anomalies], "Should detect anomaly at index 4 (value=100)"
    anomaly_indices = result[:anomalies][:anomalies].map { |a| a[:index] }
    assert_includes anomaly_indices, 4, "Anomaly at original index 4"
    assert_operator result[:flagged_trends].length, :>=, 1,
      "At least one trend window should be flagged as containing an anomaly"
  end

  def test_analytics_health_quartiles
    vessels = (1..20).map { |i| { id: "v-#{i}", health_score: i * 5 } }
    quartiles = OpalCommand::Services::Analytics.health_quartiles(vessels)
    assert_operator quartiles[:q1], :<, quartiles[:q2]
    assert_operator quartiles[:q2], :<, quartiles[:q3]
  end

  # --- Ledger ---

  def test_ledger_merge_preserves_all_events
    a = OpalCommand::Services::Ledger::AuditLedger.new
    b = OpalCommand::Services::Ledger::AuditLedger.new
    a.append(OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e-1', service: 'svc-a', action: 'create', timestamp: 100, operator_id: 'op-1'))
    b.append(OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e-2', service: 'svc-b', action: 'update', timestamp: 200, operator_id: 'op-2'))
    merged = OpalCommand::Services::Ledger.merge_ledgers(a, b)
    assert_equal 2, merged.size
  end

  def test_ledger_compliance_gap_analysis
    ledger = OpalCommand::Services::Ledger::AuditLedger.new
    ledger.append(OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e-1', service: 'svc-a', action: 'create', timestamp: 100, operator_id: 'op-1'))
    result = OpalCommand::Services::Ledger.compliance_gap_analysis(
      ledger, required_services: %w[svc-a svc-b], required_actions: %w[create delete]
    )
    refute result[:compliant]
    assert_includes result[:missing_services], 'svc-b'
    assert_includes result[:missing_actions], 'delete'
  end

  # --- Auth ---

  def test_auth_session_health_integration
    ctx = OpalCommand::Services::Auth.derive_context(
      operator_id: 'op-1', name: 'Test', roles: %w[admin], clearance: 5, mfa_done: true
    )
    result = OpalCommand::Services::Auth.session_health(ctx, max_idle_s: 300, idle_s: 100)
    assert result[:valid]
  end

  def test_auth_effective_clearance_boost
    ctx = OpalCommand::Services::Auth.derive_context(
      operator_id: 'op-2', name: 'Test', roles: %w[viewer], clearance: 3, mfa_done: true
    )
    result = OpalCommand::Services::Auth.effective_clearance(ctx, context_boost: 2)
    assert_equal 5, result[:clearance], "Clearance 3 + boost 2 = 5"
    assert_equal 'privileged', result[:label]
    assert result[:boosted]
  end

  def test_auth_batch_authorize
    contexts = (1..3).map do |i|
      OpalCommand::Services::Auth.derive_context(
        operator_id: "op-#{i}", name: "Operator #{i}", roles: %w[admin],
        clearance: i + 2, mfa_done: i.odd?
      )
    end
    results = OpalCommand::Services::Auth.batch_authorize(contexts, required_clearance: 3)
    authorized_count = results.count { |r| r[:authorized] }
    assert_operator authorized_count, :>=, 1
  end

  # --- Audit ---

  def test_audit_cross_service_compliance
    trail1 = OpalCommand::Services::Audit::AuditTrail.new
    trail2 = OpalCommand::Services::Audit::AuditTrail.new
    trail1.append(OpalCommand::Services::Audit::AuditEntry.new(
      entry_id: 'a-1', service: 'gateway', action: 'route', timestamp: 100, operator_id: 'op-1'
    ))
    trail2.append(OpalCommand::Services::Audit::AuditEntry.new(
      entry_id: 'a-2', service: 'settlement', action: 'dock', timestamp: 200, operator_id: 'op-2'
    ))
    result = OpalCommand::Services::Audit.cross_service_audit([trail1, trail2], required_services: %w[gateway settlement risk])
    refute result[:compliant]
    assert_includes result[:missing], 'risk'
    assert_equal 2, result[:total_entries]
  end

  # --- Intake ---

  def test_intake_pipeline_integration
    commands = [
      { id: 'c1', type: 'scan', satellite: 'SAT-1', urgency: 5, payload: 'data1' },
      { id: 'c2', type: 'scan', satellite: 'SAT-2', urgency: 1, payload: 'data2' },
      { id: 'c3', type: 'scan', satellite: 'SAT-1', urgency: 8, payload: 'data3' },
      { id: nil, type: 'scan', satellite: 'SAT-3', urgency: 3, payload: 'data4' }
    ]
    result = OpalCommand::Services::Intake.intake_pipeline(commands, operator_id: 'op-1', urgency_threshold: 3)
    assert_equal 1, result[:dropped], "One invalid command (nil id) should be dropped"
    assert_equal 3, result[:total_processed]
    assert_operator result[:high].length, :>=, 1, "Commands with urgency > 3 should be in :high"
  end

  # --- Reporting ---

  def test_reporting_cross_service_report
    incidents = [
      { id: 'i-1', severity: 3, status: 'open' },
      { id: 'i-2', severity: 5, status: 'resolved' }
    ]
    report = OpalCommand::Services::Reporting.cross_service_report(
      incidents: incidents, fleet_health: 85, compliance_score: 0.95
    )
    assert_equal 'low', report[:risk_level]
    assert_equal 1, report[:open_incidents]
    assert_equal 1, report[:resolved_incidents]
  end

  def test_reporting_trend_report
    incidents = (1..10).map do |i|
      { id: "inc-#{i}", severity: (i % 5) + 1, status: i.even? ? 'resolved' : 'open' }
    end
    trends = OpalCommand::Services::Reporting.trend_report(incidents, window: 4)
    assert_operator trends.length, :>, 0
    trends.each do |t|
      assert_includes %i[worsening improving], t[:trend]
    end
  end

  # --- Multi-step: Workflow + Dispatch ---

  def test_workflow_dispatch_berth_allocation_chain
    engine = OpalCommand::Core::WorkflowEngine.new
    vessels = [
      { id: 'chain-v1', cargo_tons: 70000 },
      { id: 'chain-v2', cargo_tons: 20000 }
    ]
    berths = [
      { id: 'chain-b1', length: 350 },
      { id: 'chain-b2', length: 150 }
    ]

    vessels.each { |v| engine.register(v[:id]) }
    assignments = OpalCommand::Core::Dispatch.allocate_berths(vessels, berths)

    assignments.each do |a|
      result = engine.transition(a[:vessel_id], :allocated)
      assert result.success, "Vessel #{a[:vessel_id]} should transition to allocated"
    end

    heavy = assignments.find { |a| a[:vessel_id] == 'chain-v1' }
    assert_equal 'chain-b1', heavy[:berth_id],
      "Heavy vessel should get the longer berth in allocation chain"
  end

  # --- Concurrency: Workflow snapshot_and_advance ---

  def test_snapshot_and_advance_moves_all_active
    engine = OpalCommand::Core::WorkflowEngine.new
    5.times { |i| engine.register("snap-#{i}") }
    engine.transition('snap-0', :allocated)
    engine.transition('snap-0', :departed)
    engine.transition('snap-0', :arrived)

    results = engine.snapshot_and_advance(:allocated)
    successes = results.count(&:success)
    assert_equal 4, successes, "4 entities in :queued should be advanced to :allocated"
  end

  # --- Multi-step: Checkpoint + Workflow replay ---

  def test_checkpoint_workflow_state_replay
    engine = OpalCommand::Core::WorkflowEngine.new
    mgr = OpalCommand::Core::CheckpointManager.new

    engine.register('replay-1')
    engine.transition('replay-1', :allocated)
    mgr.record('replay-1', 1, Time.now.to_i)
    engine.transition('replay-1', :departed)
    mgr.record('replay-1', 2, Time.now.to_i)

    cp = mgr.get('replay-1')
    assert_equal 2, cp.sequence,
      "Checkpoint should reflect latest sequence after two transitions"
    assert_equal :departed, engine.get_state('replay-1')
  end

  # --- Integration: Risk + Gateway combined ---

  def test_risk_gateway_combined_flow
    risk = OpalCommand::Services::Risk.compute_risk_score(
      failed_attempts: 5, geo_anomaly: true, time_anomaly: false
    )
    admission = OpalCommand::Services::Gateway.weighted_admission(
      current_load: 10, max_capacity: 100, risk_score: risk, priority: :normal
    )
    if risk >= 70
      refute admission[:admitted], "High risk (#{risk}) should block admission"
    else
      assert admission[:admitted], "Moderate risk (#{risk}) should allow admission"
    end
  end
end
