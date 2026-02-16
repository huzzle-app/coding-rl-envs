# frozen_string_literal: true

require 'digest'
require_relative '../test_helper'
require_relative '../../services/gateway/service'
require_relative '../../services/audit/service'
require_relative '../../services/analytics/service'
require_relative '../../services/notifications/service'
require_relative '../../services/policy/service'
require_relative '../../services/resilience/service'
require_relative '../../services/routing/service'
require_relative '../../services/security/service'
require_relative '../../shared/contracts/contracts'

# =============================================================================
# ServiceMeshMatrixTest — 2168 tests across 8 service modules.
# Each test has bug-detecting assertions that fail when the corresponding
# service has incorrect logic and pass when the bug is fixed.
# =============================================================================
class ServiceMeshMatrixTest < Minitest::Test
  TOTAL_CASES = 2168

  TOTAL_CASES.times do |idx|
    define_method("test_service_mesh_#{format('%05d', idx)}") do
      bucket = idx % 8

      case bucket
      when 0
        # ----- Gateway: score_node weight validation -----
        low_load = { id: "n-lo-#{idx}", load: 0.1, latency_ms: 50, healthy: true }
        high_load = { id: "n-hi-#{idx}", load: 0.9, latency_ms: 50, healthy: true }
        score_lo = MercuryLedger::Services::Gateway.score_node(low_load)
        score_hi = MercuryLedger::Services::Gateway.score_node(high_load)
        assert_operator score_lo, :>, score_hi,
          'Lower load node must score higher than higher load node'

        # select_primary_node should pick the best
        nodes = [high_load, low_load]
        best = MercuryLedger::Services::Gateway.select_primary_node(nodes)
        assert_equal low_load[:id], best[:id],
          'Primary node must be the one with highest score (lowest load)'

        # build_route_chain must respect max_hops limit
        many_nodes = Array.new(10) { |i| { id: "n#{i}", load: i * 0.08, latency_ms: 20, healthy: true } }
        chain = MercuryLedger::Services::Gateway.build_route_chain(many_nodes, 3)
        assert_operator chain.length, :<=, 3,
          'Route chain must not exceed max_hops'

        # admission_control at capacity with low priority must reject
        result = MercuryLedger::Services::Gateway.admission_control(100, 100, 1)
        assert_equal :reject, result

      when 1
        # ----- Audit: severity validation, trail summary -----
        entry = MercuryLedger::Services::Audit::AuditEntry.new(
          service: "svc-#{idx % 4}", action: 'check',
          severity: (idx % 5) + 1, timestamp: Time.now.to_i
        )
        assert MercuryLedger::Services::Audit.validate_audit_entry(entry),
          'Valid audit entry must pass validation'

        invalid_entry = MercuryLedger::Services::Audit::AuditEntry.new(
          service: nil, action: 'check', severity: 3, timestamp: 1
        )
        refute MercuryLedger::Services::Audit.validate_audit_entry(invalid_entry),
          'Entry with nil service must fail validation'

        entries = Array.new(3) { |i|
          MercuryLedger::Services::Audit::AuditEntry.new(
            service: "svc-#{i}", action: 'op', severity: i + 1, timestamp: i
          )
        }
        summary = MercuryLedger::Services::Audit.summarize_trail(entries)
        assert_equal 3, summary[:total]
        assert_equal 3, summary[:max_severity]
        assert_equal 3, summary[:services].length

      when 2
        # ----- Analytics: moving_metric should average, not sum -----
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        window = 3
        metric = MercuryLedger::Services::Analytics.moving_metric(values, window)
        # If moving_metric averages: [20.0, 30.0, 40.0]
        # If moving_metric sums: [60.0, 90.0, 120.0]
        refute_empty metric
        assert_operator metric[0], :<=, 30.0,
          'moving_metric should return averages, not sums'

        # Fleet health should be ratio of healthy active vessels
        vessels = [
          { active: true, healthy: true },
          { active: true, healthy: false },
          { active: true, healthy: true }
        ]
        health = MercuryLedger::Services::Analytics.compute_fleet_health(vessels)
        assert_in_delta 0.6667, health, 0.01,
          'Fleet health = 2 healthy / 3 active'

        # anomaly_report should detect outliers
        data = Array.new(20) { |i| 10.0 + (i == 10 ? 100 : 0) }
        anomalies = MercuryLedger::Services::Analytics.anomaly_report(data, 2.0)
        assert_operator anomalies.length, :>=, 1,
          'Should detect the outlier at index 10'

      when 3
        # ----- Notifications: format includes severity prefix -----
        msg1 = MercuryLedger::Services::Notifications.format_notification('deploy', 1, 'msg')
        assert_includes msg1, '[INFO]',
          'Severity 1 should format as [INFO], not [UNKNOWN]'

        # Channels should include sms for severity >= 4
        channels = MercuryLedger::Services::Notifications.plan_channels(4)
        assert_includes channels, 'sms',
          'Severity 4 must include sms channel'
        assert_includes channels, 'slack'
        assert_includes channels, 'email'
        assert_includes channels, 'log'

        # Severity 1 should only have log
        channels1 = MercuryLedger::Services::Notifications.plan_channels(1)
        assert_equal ['log'], channels1,
          'Severity 1 should only have log channel'

        # Escalation delay
        assert_equal 0, MercuryLedger::Services::Notifications.escalation_delay(5)
        assert_operator MercuryLedger::Services::Notifications.escalation_delay(1), :>, 0

      when 4
        # ----- Policy: evaluate_policy_gate should consider degraded flag -----
        # High risk should deny even with MFA
        result = MercuryLedger::Services::Policy.evaluate_policy_gate(0.95, false, true, 3)
        assert_equal :deny, result

        # When degraded and mid-risk, should deny (not just allow with MFA)
        degraded_result = MercuryLedger::Services::Policy.evaluate_policy_gate(0.5, true, true, 3)
        assert_equal :deny, degraded_result,
          'Degraded system with mid-risk should deny, not allow'

        # compliance score in expected range
        score = MercuryLedger::Services::Policy.compute_compliance_score(80, 100, 0.9)
        expected = (80.0 / 100 * 0.6 + 0.9 * 0.4).round(4)
        assert_in_delta expected, score, 0.001

        # policy_summary counts
        gates = [:allow, :deny, :review, :allow]
        summary = MercuryLedger::Services::Policy.policy_summary(gates)
        assert_equal 4, summary[:total]
        assert_equal 2, summary[:allowed]
        assert_equal 1, summary[:denied]

      when 5
        # ----- Resilience: replay plan and coverage -----
        plan = MercuryLedger::Services::Resilience.build_replay_plan(100, 60, 4)
        assert_operator plan[:batches], :>, 0
        assert_equal 240, plan[:budget],
          'Budget should be timeout * parallel'

        # classify_replay_mode boundary checks
        assert_equal :complete, MercuryLedger::Services::Resilience.classify_replay_mode(10, 10)
        assert_equal :idle, MercuryLedger::Services::Resilience.classify_replay_mode(10, 0)
        assert_equal :active, MercuryLedger::Services::Resilience.classify_replay_mode(10, 5)

        # failover_priority: primary > secondary > tertiary
        p_primary = MercuryLedger::Services::Resilience.failover_priority('primary', false, 10)
        p_secondary = MercuryLedger::Services::Resilience.failover_priority('secondary', false, 10)
        p_tertiary = MercuryLedger::Services::Resilience.failover_priority('tertiary', false, 10)
        assert_operator p_primary, :>, p_secondary
        assert_operator p_secondary, :>, p_tertiary

        # degraded penalty should reduce priority
        p_degraded = MercuryLedger::Services::Resilience.failover_priority('primary', true, 10)
        assert_operator p_primary, :>, p_degraded,
          'Degraded region should have lower priority'

      when 6
        # ----- Routing: channel_health_score and optimal path -----
        # Higher reliability with same latency should give higher score
        score_hi = MercuryLedger::Services::Routing.channel_health_score(50, 0.95)
        score_lo = MercuryLedger::Services::Routing.channel_health_score(50, 0.5)
        assert_operator score_hi, :>, score_lo,
          'Higher reliability should yield higher health score'

        # optimal path: sorted by distance + risk
        legs = [
          MercuryLedger::Services::Routing::Leg.new(from: 'A', to: 'B', distance: 200, risk: 0.5),
          MercuryLedger::Services::Routing::Leg.new(from: 'B', to: 'C', distance: 50, risk: 0.1)
        ]
        sorted = MercuryLedger::Services::Routing.compute_optimal_path(legs)
        assert_equal 'B', sorted[0].from,
          'Lowest combined distance+risk leg should be first'

        # total_distance
        assert_equal 250.0, MercuryLedger::Services::Routing.total_distance(legs)

        # estimate_arrival_time
        time = MercuryLedger::Services::Routing.estimate_arrival_time(500, 20, 1.2)
        assert_in_delta 30.0, time, 0.01

      when 7
        # ----- Security: secret strength, risk score, command auth -----
        # 8-char secret with all character types should be valid
        assert MercuryLedger::Services::Security.validate_secret_strength('Abcdefg1'),
          '8-char secret with upper/lower/digit should be valid'

        # Short secret should fail
        refute MercuryLedger::Services::Security.validate_secret_strength('Ab1'),
          'Too-short secret must fail'

        # Command auth with correct sig
        cmd = "cmd-#{idx}"
        secret = 'test-secret-key'
        sig = Digest::SHA256.hexdigest("#{secret}:#{cmd}")
        assert MercuryLedger::Services::Security.validate_command_auth(cmd, sig, secret)

        # Wrong sig
        refute MercuryLedger::Services::Security.validate_command_auth(cmd, 'wrong', secret)

        # Path traversal
        assert MercuryLedger::Services::Security.check_path_traversal('../../etc/passwd')
        refute MercuryLedger::Services::Security.check_path_traversal('safe/path/file.txt')

        # Risk score capped and computed
        risk = MercuryLedger::Services::Security.compute_risk_score(4, true, true)
        assert_operator risk, :<=, 1.05,
          'Risk score must not exceed 1.05'
        assert_operator risk, :>, 0.4,
          'High failed attempts + geo + off-hours should give significant risk'

        # Rate limit check
        assert_equal :blocked, MercuryLedger::Services::Security.rate_limit_check(100, 100, 60)
        assert_equal :ok, MercuryLedger::Services::Security.rate_limit_check(10, 100, 60)
        result = MercuryLedger::Services::Security.rate_limit_check(85, 100, 60)
        assert_equal :warn, result,
          'At 85% of limit should warn (threshold 0.8), not ok'
      end
    end
  end
end
