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

      # === Bug-detecting assertions (bucketed by idx % 14) ===
      # Placed FIRST so all 14 buckets fire regardless of idx parity
      bug_bucket = idx % 14
      case bug_bucket
      when 0
        # Bug: Resilience.replay keeps LOWER sequence (uses < instead of >)
        replay_result = OpalCommand::Core::Resilience.replay([
          { id: "dup-#{idx}", sequence: 1 },
          { id: "dup-#{idx}", sequence: 2 + (idx % 10) }
        ])
        latest_for_dup = replay_result.find { |e| e[:id] == "dup-#{idx}" }
        assert_equal 2 + (idx % 10), latest_for_dup[:sequence],
          "replay should keep HIGHEST sequence for dup-#{idx}, not lowest"

      when 1
        # Bug: choose_corridor uses max_by latency (picks slowest route)
        corridors = [
          { channel: "fast-#{idx}", latency: 1 },
          { channel: "slow-#{idx}", latency: 100 }
        ]
        chosen = OpalCommand::Core::Routing.choose_corridor(corridors, [])
        assert_equal "fast-#{idx}", chosen[:channel],
          "choose_corridor should pick LOWEST latency route"

      when 2
        # Bug: urgency_score uses severity * 8 instead of * 10
        order_check = OpalCommand::Core::Order.new(severity: 5, sla_minutes: 120)
        expected_urgency = (5 * 10) + [120 - 120, 0].max
        assert_equal expected_urgency, order_check.urgency_score,
          "urgency_score should use severity * 10, not * 8"

      when 3
        # Bug: should_shed uses > instead of >= (boundary error)
        result_at_limit = OpalCommand::Core::Queue.should_shed?(40, 40, false)
        assert result_at_limit,
          "should_shed?(40, 40) should be true: depth >= hard_limit"

      when 4
        # Bug: check_sla_compliance uses > instead of >= at 80% boundary
        elapsed_at_80 = (60 * 0.8).to_i  # 48
        sla_result = OpalCommand::Core::Policy.check_sla_compliance(elapsed_at_80, 60)
        assert_equal :at_risk, sla_result,
          "elapsed == sla * 0.8 should be :at_risk, not :compliant"

      when 5
        # Bug: EWMA formula inverted (weights current instead of new value)
        ewma = OpalCommand::Core::EWMATracker.new(alpha: 0.3)
        ewma.update(100.0)  # initial
        ewma.update(0.0)    # if correct: 0.3*0 + 0.7*100 = 70; if buggy: 0.3*100 + 0.7*0 = 30
        val = ewma.value
        assert_operator val, :>, 50.0,
          "EWMA after update(100) then update(0) with alpha=0.3 should be 70, not 30 (formula inverted)"

      when 6
        # Bug: validate_token_chain breaks on first invalid instead of checking all
        store = OpalCommand::Core::TokenStore.new
        store.store("vc-#{idx}-1", 'h', 3600)
        store.store("vc-#{idx}-3", 'h', 3600)
        chain_result = store.validate_token_chain(["vc-#{idx}-1", "vc-#{idx}-2", "vc-#{idx}-3"])
        assert_equal 1, chain_result[:valid].length,
          "validate_token_chain: only token 1 should be valid (token 3 expired after break)"
        assert_equal 2, chain_result[:invalid].length,
          "validate_token_chain should check ALL tokens, not stop at first invalid"

      when 7
        # Bug: PriorityQueue batch_dequeue returns in wrong order (reversed)
        pq = OpalCommand::Core::PriorityQueue.new
        pq.enqueue("low-#{idx}", 1)
        pq.enqueue("high-#{idx}", 100)
        pq.enqueue("mid-#{idx}", 50)
        batch = pq.batch_dequeue(3)
        assert_equal "high-#{idx}", batch.first,
          "batch_dequeue should return highest priority first"

      when 8
        # Bug: PriorityQueue merge clears source queue
        pq_src = OpalCommand::Core::PriorityQueue.new
        pq_dest = OpalCommand::Core::PriorityQueue.new
        pq_src.enqueue("src-#{idx}", 10)
        pq_src.enqueue("src2-#{idx}", 20)
        src_size_before = pq_src.size
        pq_dest.merge(pq_src)
        assert_equal src_size_before, pq_src.size,
          "merge should NOT clear the source queue"

      when 9
        # Bug: WorkflowEngine batch_transition reads from snapshot (no cascading)
        engine = OpalCommand::Core::WorkflowEngine.new
        engine.register("bt-#{idx}")
        result = engine.batch_transition([
          ["bt-#{idx}", :allocated],
          ["bt-#{idx}", :departed]
        ])
        assert_equal 2, result[:success_count],
          "batch_transition should cascade: queued->allocated->departed in same batch"
        assert_equal :departed, engine.get_state("bt-#{idx}")

      when 10
        # Bug: reconstruct_state returns from_state instead of to_state
        engine = OpalCommand::Core::WorkflowEngine.new
        engine.register("rs-#{idx}")
        engine.transition("rs-#{idx}", :allocated)
        engine.transition("rs-#{idx}", :departed)
        state = engine.reconstruct_state("rs-#{idx}")
        assert_equal :departed, state,
          "reconstruct_state should return to_state (:departed), not from_state"

      when 11
        # Bug: reopen records wrong from_state (records to_state instead of current)
        engine = OpalCommand::Core::WorkflowEngine.new
        engine.register("ro-#{idx}")
        engine.transition("ro-#{idx}", :allocated)
        engine.transition("ro-#{idx}", :departed)
        engine.transition("ro-#{idx}", :arrived)
        engine.reopen("ro-#{idx}", :queued)
        history = engine.history("ro-#{idx}")
        reopen_entry = history.last
        assert_equal :arrived, reopen_entry.from_state,
          "reopen from_state should be :arrived (old terminal), not :queued"

      when 12
        # Bug: CheckpointManager.record uses ||= (never updates)
        mgr = OpalCommand::Core::CheckpointManager.new
        mgr.record("cp-#{idx}", 10, 1000)
        mgr.record("cp-#{idx}", 50 + idx, 2000)
        cp = mgr.get("cp-#{idx}")
        assert_equal 50 + idx, cp.sequence,
          "record should UPDATE checkpoint to newer sequence, not keep first"

      when 13
        # Bug: reconstruct_event_stream uses <= (returns AT checkpoint, not AFTER)
        mgr = OpalCommand::Core::CheckpointManager.new
        checkpoint_seq = 5 + (idx % 20)
        events = (1..30).map { |i| { id: "ev#{i}", sequence: i } }
        result = mgr.reconstruct_event_stream(events, checkpoint_seq)
        result.each do |e|
          assert_operator e[:sequence], :>, checkpoint_seq,
            "reconstruct_event_stream should return events AFTER checkpoint (seq #{checkpoint_seq}), not at/before"
        end
      end

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
