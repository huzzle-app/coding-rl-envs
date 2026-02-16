# frozen_string_literal: true

require 'digest'
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

class ServiceMeshMatrixTest < Minitest::Test
  TOTAL_CASES = 2152

  TOTAL_CASES.times do |idx|
    define_method("test_service_mesh_matrix_#{format('%05d', idx)}") do
      bucket = idx % 8

      case bucket
      when 0
        # gateway + auth
        node = OpalCommand::Services::Gateway::RouteNode.new(
          id: "n-#{idx}", region: "region-#{idx % 4}", latency_ms: 5 + (idx % 50),
          capacity: 30 + (idx % 70), active: (idx % 7) != 0
        )
        score = OpalCommand::Services::Gateway.score_node(node)
        assert_operator score, :>=, 0

        nodes = Array.new(3) do |i|
          OpalCommand::Services::Gateway::RouteNode.new(
            id: "n-#{idx}-#{i}", region: "r#{i}", latency_ms: 10 + i * 5 + (idx % 20),
            capacity: 50 + (idx % 40), active: true
          )
        end
        primary = OpalCommand::Services::Gateway.select_primary_node(nodes)
        refute_nil primary

        # Bug: select_primary_node uses min_by instead of max_by
        best_score = nodes.map { |n| OpalCommand::Services::Gateway.score_node(n) }.max
        assert_equal best_score, OpalCommand::Services::Gateway.score_node(primary),
          "select_primary_node should pick the node with HIGHEST score"

        chain = OpalCommand::Services::Gateway.build_route_chain(nodes, max_hops: 2)
        assert_operator chain[:hops], :<=, 2

        ctx = OpalCommand::Services::Auth.derive_context(
          operator_id: "op-#{idx}", name: "Operator #{idx}", roles: %w[admin],
          clearance: 3 + (idx % 3), mfa_done: (idx % 3) != 0
        )
        assert_equal "op-#{idx}", ctx.operator_id

        # Bug: Auth.authorize_intent uses > instead of >= (clearance 3 with required 3 should pass)
        ctx_exact = OpalCommand::Services::Auth.derive_context(
          operator_id: "exact-#{idx}", name: "Exact", roles: %w[admin],
          clearance: 3, mfa_done: true
        )
        exact_result = OpalCommand::Services::Auth.authorize_intent(ctx_exact, required_clearance: 3)
        assert exact_result[:authorized],
          "clearance 3 with required_clearance 3 should be authorized (>= not >)"

      when 1
        # intake + ledger
        cmd = { id: "cmd-#{idx}", type: "type-#{idx % 4}", satellite: "SAT-#{idx % 10}", urgency: (idx % 5) + 1, payload: "data-#{idx}" }
        shape = OpalCommand::Services::Intake.validate_command_shape(cmd)
        assert shape[:valid]

        commands = Array.new(4) do |i|
          { id: "cmd-#{idx}-#{i}", type: "type-#{i % 3}", satellite: "SAT-#{i}", urgency: i + 1, payload: "p#{i}" }
        end
        summary = OpalCommand::Services::Intake.batch_summary(commands)
        assert_equal 4, summary[:total]

        # Bug: priority_sort sorts ascending instead of descending
        sorted = OpalCommand::Services::Intake.priority_sort(commands)
        assert_operator sorted.first[:urgency], :>=, sorted.last[:urgency],
          "priority_sort should return highest urgency first (descending)"

        # Bug: partition_by_urgency uses > instead of >= (threshold boundary)
        threshold_cmds = [
          { id: "t-#{idx}", type: "t", satellite: "S", urgency: 3, payload: "p" }
        ]
        partitioned = OpalCommand::Services::Intake.partition_by_urgency(threshold_cmds, threshold: 3)
        assert_equal 1, partitioned[:high].length,
          "urgency == threshold (3) should be in :high partition (>= not >)"

        ledger = OpalCommand::Services::Ledger::AuditLedger.new
        evt = OpalCommand::Services::Ledger::AuditEvent.new(
          event_id: "e-#{idx}", service: 'intake', action: 'ingest',
          timestamp: 1000 + idx, operator_id: "op-#{idx % 5}"
        )
        ledger.append(evt)
        assert_equal 1, ledger.size

        valid = OpalCommand::Services::Ledger.validate_audit_event(evt)
        assert valid

      when 2
        # settlement + reconcile
        period = OpalCommand::Services::Settlement.compute_docking_period(100 + (idx % 300))
        assert_operator period, :>, 0

        decay = OpalCommand::Services::Settlement.berth_decay_rate(
          150 + (idx % 200), area_m2: 3000 + (idx % 5000), mass_kg: 20_000 + (idx * 100 % 80_000)
        )
        assert_operator decay, :>, 0

        risk = OpalCommand::Services::Settlement.predict_congestion_risk(50 + (idx % 200), 10 + (idx % 30))
        assert_includes %i[high medium low unknown], risk

        zone = OpalCommand::Services::Settlement.zone_band(idx % 500)
        assert_includes %w[alpha bravo charlie delta], zone

        # Bug: can_berth? ignores tide_level_m
        can_fit = OpalCommand::Services::Settlement.can_berth?(12.0, 10.0, tide_level_m: 3.0)
        assert can_fit, "12m draft should fit in 10m berth + 3m tide (can_berth? must consider tide)"

        # Bug: compute_berth_penalty divides time_penalty by 24 erroneously
        penalty = OpalCommand::Services::Settlement.compute_berth_penalty(250, 200, 2)
        expected_penalty = (50 * 15.0) + (2 * 50.0)  # excess=50, excess*15=750, hours*50=100, total=850
        assert_in_delta expected_penalty, penalty, 0.01,
          "berth_penalty formula: excess_length * 15 + hours * 50 (no /24 divisor)"

        # Bug: estimate_laden_fuel ignores laden parameter
        laden_fuel = OpalCommand::Services::Settlement.estimate_laden_fuel(100, 1000, laden: true)
        ballast_fuel = OpalCommand::Services::Settlement.estimate_laden_fuel(100, 1000, laden: false)
        assert_operator laden_fuel, :>, ballast_fuel,
          "Laden fuel consumption should exceed ballast fuel"

        seq = OpalCommand::Services::Reconcile.build_reconcile_sequence(
          delta_required: 10.0 + (idx % 50), available_budget: 200.0 + (idx % 300)
        )
        assert seq.key?(:steps)

      when 3
        # policy + reporting
        decision = OpalCommand::Services::Policy.evaluate_policy_gate(
          risk_score: idx % 100, comms_degraded: (idx % 5) == 0, has_mfa: (idx % 4) != 0
        )
        refute_nil decision.action

        band = OpalCommand::Services::Policy.risk_band(idx % 100)
        assert_includes %w[critical high medium low minimal], band

        compliance = OpalCommand::Services::Policy.compute_compliance_score(
          incidents_resolved: 70 + (idx % 30), incidents_total: 100, sla_met_pct: 60 + (idx % 40)
        )
        assert_operator compliance, :>=, 0

        # Bug: escalation_required? uses > instead of >= at boundary
        esc_at_boundary = OpalCommand::Services::Policy.escalation_required?(75, :normal)
        assert esc_at_boundary,
          "risk_score == threshold (75 for :normal) should require escalation (>= not >)"

        # Bug: Reporting.rank_incidents sorts ascending instead of descending
        incidents_to_rank = [
          { id: "lo-#{idx}", severity: 1 },
          { id: "hi-#{idx}", severity: 5 },
          { id: "mid-#{idx}", severity: 3 }
        ]
        ranked = OpalCommand::Services::Reporting.rank_incidents(incidents_to_rank)
        assert_equal 5, ranked.first[:severity],
          "rank_incidents should return highest severity first (descending)"

        dual = OpalCommand::Services::Policy.enforce_dual_control("op-#{idx}", "op-#{idx + 1}", 'deploy')
        assert dual[:enforced]

      when 4
        # risk + audit
        secret = "secret-#{idx % 10}"
        command = "action-#{idx}"
        sig = Digest::SHA256.hexdigest("#{secret}:#{command}")
        auth_result = OpalCommand::Services::Risk.validate_command_auth(
          command: command, signature: sig, secret: secret,
          required_role: 'operator', user_roles: %w[operator viewer]
        )
        assert auth_result[:valid]

        path_result = OpalCommand::Services::Risk.check_path_traversal("data/file-#{idx}.txt")
        assert path_result[:safe]

        rate_result = OpalCommand::Services::Risk.rate_limit_check(request_count: idx % 20, limit: 20)
        refute_nil rate_result[:allowed]

        # Bug: sanitize_input truncates to max_length-1 instead of max_length
        input_str = "a" * 50
        sanitized = OpalCommand::Services::Risk.sanitize_input(input_str, max_length: 50)
        assert_equal 50, sanitized.length,
          "sanitize_input with max_length=50 should keep all 50 chars, not truncate to 49"

        trail = OpalCommand::Services::Audit::AuditTrail.new
        trail.append(OpalCommand::Services::Audit::AuditEntry.new(
          entry_id: "a-#{idx}", service: 'risk', action: 'validate',
          timestamp: 2000 + idx, operator_id: "op-#{idx % 8}", detail: 'check'
        ))
        assert_equal 1, trail.size

      when 5
        # analytics + notifications
        vessels = Array.new(5) do |i|
          { id: "v-#{idx}-#{i}", health_score: 40 + (idx + i * 7) % 60, active: (i % 3) != 0 }
        end
        health = OpalCommand::Services::Analytics.compute_fleet_health(vessels)
        assert_operator health[:score], :>, 0

        values = Array.new(8) { |i| (idx + i * 13) % 100 }
        trends = OpalCommand::Services::Analytics.trend_analysis(values, window: 3)
        assert_operator trends.length, :>, 0

        # Bug: vessel_ranking sorts ascending instead of descending
        ranked = OpalCommand::Services::Analytics.vessel_ranking(vessels)
        assert_equal 5, ranked.length
        assert_operator ranked.first[:health_score], :>=, ranked.last[:health_score],
          "vessel_ranking should return highest health_score first (descending)"

        # Bug: SEVERITY_CHANNELS[5] missing 'pager'
        channels_5 = OpalCommand::Services::Notifications::SEVERITY_CHANNELS[5]
        assert_includes channels_5, 'pager',
          "Severity 5 should include 'pager' in notification channels"

        planner = OpalCommand::Services::Notifications::NotificationPlanner.new
        planner.plan(operator_id: "op-#{idx}", severity: (idx % 5) + 1, message: "alert-#{idx}")
        assert_equal 1, planner.size

        throttled = OpalCommand::Services::Notifications.should_throttle(
          recent_count: idx % 15, max_per_window: 10, severity: (idx % 5) + 1
        )
        assert_includes [true, false], throttled

      when 6
        # reporting
        incidents = Array.new(6) do |i|
          { id: "inc-#{idx}-#{i}", severity: (i % 5) + 1, status: i.even? ? 'resolved' : 'open' }
        end
        ranked = OpalCommand::Services::Reporting.rank_incidents(incidents)
        assert_equal 6, ranked.length
        # Bug: rank_incidents sorts ascending instead of descending
        assert_operator ranked.first[:severity], :>=, ranked.last[:severity],
          "rank_incidents should return highest severity first"

        report = OpalCommand::Services::Reporting.compliance_report(
          resolved: 80 + (idx % 20), total: 100, sla_met_pct: 70 + (idx % 30)
        )
        assert_includes %w[A B C D], report[:grade]

        row = OpalCommand::Services::Reporting.format_incident_row(incidents.first)
        assert_includes row, "inc-#{idx}-0"

        # Bug: generate_executive_summary uses > instead of >= for 80 boundary
        summary_80 = OpalCommand::Services::Reporting.generate_executive_summary(
          incidents: incidents, fleet_health: 80
        )
        assert_equal 'excellent', summary_80[:fleet_status],
          "fleet_health == 80 should be 'excellent' (>= not >)"

        summary = OpalCommand::Services::Reporting.generate_executive_summary(
          incidents: incidents, fleet_health: 50 + (idx % 50)
        )
        assert_operator summary[:open_incidents], :>=, 0

        op_report = OpalCommand::Services::Reporting.operation_report(
          operation_id: "op-#{idx}", steps_executed: idx % 20,
          budget_remaining: 100.0 - (idx % 100), incidents: incidents.select { |i| i[:status] == 'open' }
        )
        refute_nil op_report[:status]

      when 7
        # cross-service: batch_notify + analytics + reporting
        operators = Array.new(3) { |i| "op-#{idx}-#{i}" }
        notifications = OpalCommand::Services::Notifications.batch_notify(
          operators: operators, severity: (idx % 4) + 1, message: "cross-#{idx}"
        )
        assert_operator notifications.length, :>=, 1

        # Bug: escalate_severity caps at 4 instead of 5
        esc = OpalCommand::Services::Notifications.escalate_severity(4)
        assert_equal 5, esc,
          "escalate_severity(4) should reach 5, not cap at 4"

        # Bug: cascade_notifications prepends instead of appending (reversed order)
        cascade = OpalCommand::Services::Notifications.cascade_notifications(
          operators: ["op-#{idx}"], base_severity: 2, message: "test", escalation_steps: 3
        )
        assert_equal 3, cascade.length
        severities = cascade.map { |n| n[:severity] }
        assert_equal [2, 3, 4], severities,
          "cascade should be in ascending severity order: [2, 3, 4]"

        # Bug: priority_dispatch uses channels.length-1 as min (drops a channel)
        test_notifs = [
          { operator_id: "op-#{idx}", severity: 3, channels: %w[log email sms pager] }
        ]
        dispatched = OpalCommand::Services::Notifications.priority_dispatch(test_notifs, max_channels: 2)
        assert_equal 2, dispatched.first[:channels].length,
          "max_channels=2 should limit to exactly 2 channels"

        # Bug: Gateway.weighted_admission threshold 80 instead of 70
        gw_result = OpalCommand::Services::Gateway.weighted_admission(
          current_load: 10, max_capacity: 100, risk_score: 75, priority: :normal
        )
        assert_equal false, gw_result[:admitted],
          "risk_score 75 (>= 70) should be denied by weighted_admission"

        vessels = Array.new(4) { |i| { id: "v-#{idx}-#{i}", health_score: 50 + (idx + i) % 50, active: true } }
        fleet = OpalCommand::Services::Analytics.fleet_summary(vessels)
        assert_equal 4, fleet[:total]

        incidents = [{ id: "i-#{idx}", severity: 3, status: 'open' }]
        exec_summary = OpalCommand::Services::Reporting.generate_executive_summary(
          incidents: incidents, fleet_health: fleet[:avg_health]
        )
        assert_equal 1, exec_summary[:open_incidents]

        # Exercise risk scoring and sanitization
        risk_score = OpalCommand::Services::Risk.compute_risk_score(
          failed_attempts: idx % 10, geo_anomaly: (idx % 3) == 0, time_anomaly: (idx % 5) == 0
        )
        assert_operator risk_score, :>=, 0

        sanitized = OpalCommand::Services::Risk.sanitize_input("user-input-#{idx}", max_length: 50)
        refute_nil sanitized
      end
    end
  end
end
