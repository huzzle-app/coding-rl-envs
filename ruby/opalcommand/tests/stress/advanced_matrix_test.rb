# frozen_string_literal: true

require 'digest'
require_relative '../test_helper'
require_relative '../../shared/contracts/contracts'
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

class AdvancedMatrixTest < Minitest::Test
  TOTAL_CASES = 1500

  TOTAL_CASES.times do |idx|
    define_method("test_advanced_matrix_#{format('%05d', idx)}") do
      bucket = idx % 15

      case bucket
      when 0
        # Checkpoint record should always update on re-record
        mgr = OpalCommand::Core::CheckpointManager.new
        mgr.record('cp-alpha', 10, 1000)
        mgr.record('cp-alpha', 20 + idx, 2000 + idx)
        cp = mgr.get('cp-alpha')
        assert_equal 20 + idx, cp.sequence, "Checkpoint should update to higher sequence #{20 + idx}"

        # latest_sequence should return max across all checkpoints
        mgr.record('cp-beta', 5, 500)
        mgr.record('cp-gamma', 30 + (idx % 20), 3000)
        latest = mgr.latest_sequence
        assert_operator latest, :>=, 20 + idx, "latest_sequence should be the maximum across all checkpoints"

      when 1
        # Checkpoint merge should compare by sequence, not timestamp
        mgr_a = OpalCommand::Core::CheckpointManager.new
        mgr_b = OpalCommand::Core::CheckpointManager.new
        mgr_a.record("m-#{idx}", 10, 9000)
        mgr_b.record("m-#{idx}", 50 + idx, 1000)
        other_cps = mgr_b.all
        mgr_a.merge(other_cps)
        merged = mgr_a.get("m-#{idx}")
        assert_equal 50 + idx, merged.sequence, "Merge should keep higher sequence (50+#{idx}), not compare by timestamp"

        # Merge of disjoint sets should add new entries
        mgr_a.record("extra-#{idx}", 100, 9000)
        mgr_c = OpalCommand::Core::CheckpointManager.new
        mgr_c.record("other-#{idx}", 200, 9500)
        mgr_a.merge(mgr_c.all)
        assert_equal 200, mgr_a.get("other-#{idx}").sequence

      when 2
        # reconstruct_event_stream should return events AFTER checkpoint
        mgr = OpalCommand::Core::CheckpointManager.new
        checkpoint_seq = 10 + (idx % 30)
        events = (1..40).map { |i| { id: "e#{i}", sequence: i } }
        result = mgr.reconstruct_event_stream(events, checkpoint_seq)
        result.each do |e|
          assert_operator e[:sequence], :>, checkpoint_seq,
            "Event seq #{e[:sequence]} should be > checkpoint #{checkpoint_seq}"
        end
        expected_count = events.count { |e| e[:sequence] > checkpoint_seq }
        assert_equal expected_count, result.length

      when 3
        # Workflow reopen should record correct from_state in history
        engine = OpalCommand::Core::WorkflowEngine.new
        engine.register("re-#{idx}")
        engine.transition("re-#{idx}", :allocated)
        engine.transition("re-#{idx}", :departed)
        engine.transition("re-#{idx}", :arrived)
        assert engine.is_terminal?("re-#{idx}")

        result = engine.reopen("re-#{idx}", :queued)
        assert result.success, "reopen should succeed on terminal entity"
        assert_equal :queued, engine.get_state("re-#{idx}")

        history = engine.history("re-#{idx}")
        reopen_record = history.last
        assert_equal :arrived, reopen_record.from_state,
          "reopen should record from_state as :arrived (the previous terminal state)"
        assert_equal :queued, reopen_record.to_state

      when 4
        # batch_transition should support cascading within same batch
        engine = OpalCommand::Core::WorkflowEngine.new
        engine.register("bt-#{idx}")
        result = engine.batch_transition([
          ["bt-#{idx}", :allocated],
          ["bt-#{idx}", :departed]
        ])
        assert_equal 2, result[:success_count],
          "Second transition should see first's result (queued->allocated->departed)"
        assert_equal :departed, engine.get_state("bt-#{idx}")

      when 5
        # reconstruct_state should return to_state of last transition
        engine = OpalCommand::Core::WorkflowEngine.new
        engine.register("rs-#{idx}")
        engine.transition("rs-#{idx}", :allocated)
        engine.transition("rs-#{idx}", :departed)
        state = engine.reconstruct_state("rs-#{idx}")
        assert_equal :departed, state,
          "reconstruct_state should return current state (:departed), not from_state"

      when 6
        # PriorityQueue batch_dequeue should return highest priority first
        pq = OpalCommand::Core::PriorityQueue.new
        items = (1..(10 + idx % 20)).to_a
        items.each { |i| pq.enqueue("item-#{i}", i) }
        dequeued = pq.batch_dequeue(5)
        assert_equal 5, dequeued.length
        # Items should be in descending priority order
        expected = items.sort.reverse.first(5).map { |i| "item-#{i}" }
        assert_equal expected, dequeued,
          "batch_dequeue should return items in descending priority order"

      when 7
        # PriorityQueue merge should not destroy source queue
        pq_a = OpalCommand::Core::PriorityQueue.new
        pq_b = OpalCommand::Core::PriorityQueue.new
        pq_a.enqueue("a-#{idx}", 5)
        pq_b.enqueue("b1-#{idx}", 10)
        pq_b.enqueue("b2-#{idx}", 15)
        size_before = pq_b.size
        pq_a.merge(pq_b)
        assert_equal size_before, pq_b.size,
          "merge should not clear the source queue"
        assert_equal 3, pq_a.size

      when 8
        # TokenStore validate_token_chain should check ALL tokens
        store = OpalCommand::Core::TokenStore.new
        store.store("tc-#{idx}-1", 'h', 3600)
        store.store("tc-#{idx}-3", 'h', 3600)
        result = store.validate_token_chain(["tc-#{idx}-1", "tc-#{idx}-2", "tc-#{idx}-3"])
        assert_equal ["tc-#{idx}-1"], result[:valid]
        assert_equal 2, result[:invalid].length,
          "Should report both invalid tokens, not stop at first"
        assert_includes result[:invalid], "tc-#{idx}-2"
        assert_includes result[:invalid], "tc-#{idx}-3"

      when 9
        # Dispatch allocate_berths should assign heaviest to longest
        vessels = [
          { id: "v-light-#{idx}", cargo_tons: 1000 },
          { id: "v-heavy-#{idx}", cargo_tons: 80000 },
          { id: "v-mid-#{idx}", cargo_tons: 30000 }
        ]
        berths = [
          { id: 'b-short', length: 100 },
          { id: 'b-long', length: 400 },
          { id: 'b-mid', length: 200 }
        ]
        assignments = OpalCommand::Core::Dispatch.allocate_berths(vessels, berths)
        heavy_assignment = assignments.find { |a| a[:vessel_id] == "v-heavy-#{idx}" }
        assert_equal 'b-long', heavy_assignment[:berth_id], "Heaviest vessel should get longest berth"

      when 10
        # Dispatch optimal_schedule: highest urgency to earliest slot
        orders = [
          { id: "o-#{idx}-1", urgency: 10 },
          { id: "o-#{idx}-2", urgency: 5 },
          { id: "o-#{idx}-3", urgency: 20 }
        ]
        slots = [
          { start_hour: 6, end_hour: 10 },
          { start_hour: 10, end_hour: 14 },
          { start_hour: 14, end_hour: 18 }
        ]
        schedule = OpalCommand::Core::Dispatch.optimal_schedule(orders, slots)
        assert_equal 3, schedule.length
        assert_equal 20, schedule.first[:urgency], "Highest urgency order should get the earliest slot"

        # Fuel consumption: laden should differ from ballast
        laden = OpalCommand::Core::Dispatch.estimate_fuel_consumption(100, 1000, laden: true)
        ballast = OpalCommand::Core::Dispatch.estimate_fuel_consumption(100, 1000, laden: false)
        assert_operator laden, :>, ballast, "Laden fuel > ballast fuel"

      when 11
        # Gateway weighted_admission should reject at risk >= 70
        result = OpalCommand::Services::Gateway.weighted_admission(
          current_load: 10, max_capacity: 100, risk_score: 75 + (idx % 5), priority: :normal
        )
        assert_equal false, result[:admitted], "Risk score #{75 + idx % 5} should be denied (threshold 70)"

        # load_balanced_select least_loaded: pick highest capacity
        nodes = Array.new(4) do |i|
          OpalCommand::Services::Gateway::RouteNode.new(
            id: "lb-#{idx}-#{i}", region: "r#{i}", latency_ms: 10 + i * 5,
            capacity: 30 + (i * 20), active: true
          )
        end
        selected = OpalCommand::Services::Gateway.load_balanced_select(nodes, strategy: :least_loaded)
        refute_nil selected
        max_cap = nodes.max_by(&:capacity)
        assert_equal max_cap.id, selected.id, "least_loaded should select node with highest available capacity"

      when 12
        # Settlement: berth penalty, can_berth? with tide, laden fuel
        penalty_2h = OpalCommand::Services::Settlement.compute_berth_penalty(250, 200, 2)
        penalty_4h = OpalCommand::Services::Settlement.compute_berth_penalty(250, 200, 4)
        assert_operator penalty_4h, :>, penalty_2h
        expected_2h = (50 * 15.0) + (2 * 50.0)
        assert_in_delta expected_2h, penalty_2h, 0.01, "Penalty formula: excess_length * 15 + hours * 50"

        # can_berth? should consider tide
        result = OpalCommand::Services::Settlement.can_berth?(12.0, 10.0, tide_level_m: 3.0)
        assert result, "12m draft should fit in 10m berth + 3m tide"

        # laden fuel should differ from ballast
        laden = OpalCommand::Services::Settlement.estimate_laden_fuel(100, 1000, laden: true)
        ballast = OpalCommand::Services::Settlement.estimate_laden_fuel(100, 1000, laden: false)
        assert_operator laden, :>, ballast, "Laden fuel > ballast"

      when 13
        # Risk aggregate: recent scores weighted higher
        scores = [10, 30, 70 + (idx % 20)]
        agg = OpalCommand::Services::Risk.aggregate_risk(scores)
        assert_equal scores.max, agg[:max]
        assert_operator agg[:overall], :>, scores.first.to_f,
          "Most recent score should pull average above first score"

        # Notifications cascade: step order
        notifications = OpalCommand::Services::Notifications.cascade_notifications(
          operators: ["op-#{idx}"], base_severity: 2, message: "test alert", escalation_steps: 3
        )
        assert_equal 3, notifications.length
        severities = notifications.map { |n| n[:severity] }
        assert_equal [2, 3, 4], severities, "Severity should escalate in order: 2 -> 3 -> 4"

      when 14
        # Reconcile cascading budget integrity
        deltas = [10.0, 20.0, 30.0]
        result = OpalCommand::Services::Reconcile.cascading_reconcile(deltas, available_budget: 100.0)
        assert_operator result[:remaining_budget], :>=, 0
        assert_in_delta 100.0, result[:total_spent] + result[:remaining_budget], 0.01,
          "Spent + remaining should equal original budget"

        # Notifications priority_dispatch: max_channels should be respected
        notifs = [
          { operator_id: "op-#{idx}", severity: 3, channels: %w[log email sms pager] }
        ]
        dispatched = OpalCommand::Services::Notifications.priority_dispatch(notifs, max_channels: 2)
        assert_equal 2, dispatched.first[:channels].length,
          "max_channels=2 should limit channels to exactly 2"

        # Severity 5 should include pager
        channels_5 = OpalCommand::Services::Notifications::SEVERITY_CHANNELS[5]
        assert_includes channels_5, 'pager', "Severity 5 should include pager"

        # escalate_severity should reach 5
        capped = OpalCommand::Services::Notifications.escalate_severity(4)
        assert_equal 5, capped, "escalate_severity(4) should reach 5"
      end
    end
  end
end
