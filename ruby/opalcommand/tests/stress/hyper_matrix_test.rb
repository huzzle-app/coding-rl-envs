# frozen_string_literal: true

require 'digest'
require_relative '../test_helper'
require_relative '../../shared/contracts/contracts'

class HyperMatrixTest < Minitest::Test
  TOTAL_CASES = 7000

  TOTAL_CASES.times do |idx|
    define_method("test_hyper_matrix_#{format('%05d', idx)}") do
      severity_a = (idx % 7) + 1
      severity_b = ((idx * 3) % 7) + 1
      sla_a = 20 + (idx % 90)
      sla_b = 20 + ((idx * 2) % 90)

      order_a = OpalCommand::Core::Order.new(severity: severity_a, sla_minutes: sla_a)
      order_b = OpalCommand::Core::Order.new(severity: severity_b, sla_minutes: sla_b)

      planned = OpalCommand::Core::Dispatch.plan_settlement(
        [
          { id: "a-#{idx}", urgency: order_a.urgency_score, eta: "0#{idx % 9}:1#{idx % 6}" },
          { id: "b-#{idx}", urgency: order_b.urgency_score, eta: "0#{(idx + 3) % 9}:2#{idx % 6}" },
          { id: "c-#{idx}", urgency: (idx % 50) + 2, eta: "1#{idx % 4}:0#{idx % 6}" }
        ],
        2
      )

      assert_operator planned.length, :>=, 1
      assert_operator planned.length, :<=, 2
      assert_operator planned[0][:urgency], :>=, planned[1][:urgency] if planned.length == 2

      # Exercise dispatch_batch
      batch = OpalCommand::Core::Dispatch.dispatch_batch(
        [{ id: "d-#{idx}", urgency: idx % 20 + 1, eta: "05:00" }, { id: "e-#{idx}", urgency: idx % 10 + 1, eta: "06:00" }], 1
      )
      assert_equal 1, batch[:planned].length

      blocked = (idx % 5).zero? ? ['beta'] : []
      route = OpalCommand::Core::Routing.choose_corridor(
        [
          { channel: 'alpha', latency: 2 + (idx % 9) },
          { channel: 'beta', latency: idx % 3 },
          { channel: 'gamma', latency: 4 + (idx % 4) }
        ],
        blocked
      )
      refute_nil route
      refute_equal 'beta', route[:channel] if blocked.include?('beta')

      # Exercise channel_score and transit_time
      score = OpalCommand::Core::Routing.channel_score({ latency: 10, reliability: 0.8 })
      assert_operator score, :>, 0
      tt = OpalCommand::Core::Routing.estimate_transit_time(1000 + idx)
      assert_operator tt, :>, 0

      src = (idx % 2).zero? ? :queued : :allocated
      dst = src == :queued ? :allocated : :departed
      assert OpalCommand::Core::Workflow.transition_allowed?(src, dst)
      refute OpalCommand::Core::Workflow.transition_allowed?(:arrived, :queued)

      # Exercise shortest_path and terminal state
      assert OpalCommand::Core::Workflow.is_terminal_state?(:arrived)
      path = OpalCommand::Core::Workflow.shortest_path(:queued, :arrived)
      assert_operator path.length, :>=, 2 if path

      pol = OpalCommand::Core::Policy.next_policy((idx % 2).zero? ? 'normal' : 'watch', 2 + (idx % 2))
      assert_includes %w[watch restricted halted], pol

      # Exercise previous_policy and SLA
      prev = OpalCommand::Core::Policy.previous_policy(pol)
      refute_nil prev
      sla_status = OpalCommand::Core::Policy.check_sla_compliance(idx % 120, 60)
      assert_includes %i[compliant at_risk breached], sla_status

      depth = (idx % 30) + 1
      refute OpalCommand::Core::Queue.should_shed?(depth, 40, false)
      assert OpalCommand::Core::Queue.should_shed?(41, 40, false)

      # Exercise queue health and wait time
      health = OpalCommand::Core::QueueMonitor.queue_health(depth, 40)
      refute_nil health.status
      wt = OpalCommand::Core::Queue.estimate_wait_time(depth, 5)
      assert_operator wt, :>=, 0

      replayed = OpalCommand::Core::Resilience.replay([
        { id: "k-#{idx % 17}", sequence: 1 },
        { id: "k-#{idx % 17}", sequence: 2 },
        { id: "z-#{idx % 13}", sequence: 1 }
      ])
      assert_operator replayed.length, :>=, 2
      assert_operator replayed.last[:sequence], :>=, 1

      # Exercise deduplicate and converges
      deduped = OpalCommand::Core::Resilience.deduplicate([
        { id: "d-#{idx}", sequence: 1 }, { id: "d-#{idx}", sequence: 1 }
      ])
      assert_equal 1, deduped.length

      p50 = OpalCommand::Core::Statistics.percentile([idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11], 50)
      assert_kind_of Integer, p50

      # Exercise mean and moving_average
      avg = OpalCommand::Core::Statistics.mean([idx % 10 + 1, (idx * 3) % 10 + 1])
      assert_operator avg, :>, 0
      ma = OpalCommand::Core::Statistics.moving_average([1, 2, 3, 4], 2)
      assert_equal 3, ma.length

      # Exercise severity classify
      sev = OpalCommand::Core::Severity.classify((idx % 3).zero? ? 'critical' : 'routine')
      assert OpalCommand::Core::Severity.valid?(sev)

      # Exercise estimate_cost
      cost = OpalCommand::Core::Dispatch.estimate_cost([{ urgency: idx % 5 + 1 }])
      assert_operator cost, :>=, 0

      # Exercise service registry
      if (idx % 100).zero?
        registry = OpalCommand::Contracts::ServiceRegistry.new
        url = registry.get_service_url(:gateway)
        assert_includes url, '8110'
        assert registry.validate_contract(:routing)
      end

      next unless (idx % 17).zero?

      payload = "manifest:#{idx}"
      digest = Digest::SHA256.hexdigest(payload)
      assert OpalCommand::Core::Security.verify_signature(payload, digest, digest)
      refute OpalCommand::Core::Security.verify_signature(payload, digest[1..], digest)

      # Exercise sign/verify manifest
      sig = OpalCommand::Core::Security.sign_manifest('V-1', 45000, 'key')
      assert OpalCommand::Core::Security.verify_manifest('V-1', 45000, 'key', sig)

      # Exercise sanitise_path
      safe = OpalCommand::Core::Security.sanitise_path("../../etc/passwd")
      refute_includes safe, '..'
    end
  end
end
