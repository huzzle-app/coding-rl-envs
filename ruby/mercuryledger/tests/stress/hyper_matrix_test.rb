# frozen_string_literal: true

require 'digest'
require_relative '../test_helper'
require_relative '../../shared/contracts/contracts'

# =============================================================================
# HyperMatrixTest — 7000 parameterized tests distributed across 14 bug buckets.
# Each bucket targets a specific source-code bug so that fixing one module
# yields proportional reward improvement (~500 tests per bug).
# =============================================================================
class HyperMatrixTest < Minitest::Test
  TOTAL_CASES = 7000
  NUM_BUCKETS = 14

  TOTAL_CASES.times do |idx|
    define_method("test_hyper_matrix_#{format('%05d', idx)}") do
      bucket = idx % NUM_BUCKETS

      case bucket

      # ----- Bug 1: plan_settlement sorts ascending (should sort descending) -----
      when 0
        high_urg = 50 + (idx % 50)
        low_urg = 1 + (idx % 10)
        planned = MercuryLedger::Core::Dispatch.plan_settlement(
          [
            { id: "lo-#{idx}", urgency: low_urg, eta: '09:00' },
            { id: "hi-#{idx}", urgency: high_urg, eta: '10:00' }
          ], 1
        )
        assert_equal 1, planned.length
        assert_equal "hi-#{idx}", planned[0][:id],
          'plan_settlement must select highest urgency order'

      # ----- Bug 2: has_conflict? uses <= instead of < (adjacent = conflict) -----
      when 1
        s1 = idx % 20
        e1 = s1 + 4 + (idx % 6)
        s2 = e1  # adjacent: starts exactly when first ends
        e2 = s2 + 3 + (idx % 5)
        slot_a = { berth: 'B1', start_hour: s1, end_hour: e1 }
        slot_b = { berth: 'B1', start_hour: s2, end_hour: e2 }
        refute MercuryLedger::Core::Dispatch.has_conflict?(slot_a, slot_b),
          "Adjacent berth windows (end=#{e1}, start=#{s2}) must not conflict"

      # ----- Bug 3: allocate_costs truncates instead of rounding -----
      when 2
        # Budget ≡ 1 mod 3 ensures 2/3 share always has .X667 pattern
        # so truncation (X.66) differs from rounding (X.67)
        budget = ((idx / NUM_BUCKETS) % 100 + 10) * 3.0 + 1.0
        orders = [{ id: 1, urgency: 1 }, { id: 2, urgency: 2 }]
        result = MercuryLedger::Core::Dispatch.allocate_costs(orders, budget)
        share_2 = result.find { |o| o[:id] == 2 }[:allocated]
        expected = (budget * 2.0 / 3.0).round(2)
        assert_equal expected, share_2,
          "2/3 of #{budget} should round to #{expected}, not truncate"

      # ----- Bug 4: sign_manifest uses cargo:vessel instead of vessel:cargo -----
      when 3
        vessel = "SHIP-#{idx}"
        tons = 1000 + (idx * 7) % 9000
        secret = "secret-#{idx % 100}"
        sig = MercuryLedger::Core::Security.sign_manifest(vessel, tons, secret)
        canonical = Digest::SHA256.hexdigest("#{secret}:#{vessel}:#{tons}")
        assert_equal canonical, sig,
          'Manifest signature must use vessel_id:cargo_tons field order'

      # ----- Bug 5: variance uses population (n) instead of sample (n-1) -----
      when 4
        base = (idx % 20) + 1
        values = [base.to_f, (base + 2).to_f]
        result = MercuryLedger::Core::Statistics.variance(values)
        # Sample variance of [x, x+2]: mean = x+1, sum_sq = 2, n-1 = 1 => 2.0
        assert_in_delta 2.0, result, 0.001,
          'Variance must use Bessel correction (n-1 denominator)'

      # ----- Bug 6: replay uses > instead of >= (first-write-wins bug) -----
      when 5
        events = [
          { id: "evt-#{idx}", sequence: 1, value: 'original' },
          { id: "evt-#{idx}", sequence: 1, value: 'corrected' }
        ]
        replayed = MercuryLedger::Core::Resilience.replay(events)
        assert_equal 1, replayed.length
        assert_equal 'corrected', replayed[0][:value],
          'Last event at same sequence must win (last-write-wins)'

      # ----- Bug 7: TokenStore.cleanup uses && instead of || -----
      when 6
        store = MercuryLedger::Core::TokenStore.new
        store.store("tok-#{idx}", 'hash', 3600)
        store.revoke("tok-#{idx}")
        removed = store.cleanup(Time.now.to_i + 10)
        assert_equal 1, removed,
          'Revoked token must be cleaned even if not yet expired'

      # ----- Bug 8: DEESCALATION_THRESHOLDS has "watching" instead of "watch" -----
      when 7
        streak = 4 + (idx % 10)
        result = MercuryLedger::Core::Policy.should_deescalate?('watch', streak)
        assert result,
          "Watch with streak=#{streak} should allow de-escalation"

      # ----- Bug 9: shortest_path missing from==to early return -----
      when 8
        states = MercuryLedger::Core::Workflow::GRAPH.keys
        state = states[idx % states.length]
        path = MercuryLedger::Core::Workflow.shortest_path(state, state)
        refute_nil path, "Self-path for #{state} must not be nil"
        assert_equal [state], path,
          "Self-path for #{state} must be [#{state}]"

      # ----- Bug 10: CorridorTable#active uses == true instead of != false -----
      when 9
        table = MercuryLedger::Core::CorridorTable.new
        # Route without :active key should default to active
        table.add("ch-#{idx}", { channel: "ch-#{idx}", latency: 10 + (idx % 50) })
        active = table.active
        assert_equal 1, active.length,
          'Route without :active key should be considered active by default'

      # ----- Bug 11: CircuitBreaker success resets wrong counter in closed state -----
      when 10
        threshold = 3 + (idx % 5)
        cb = MercuryLedger::Core::CircuitBreaker.new(
          failure_threshold: threshold, success_threshold: 1, timeout: 600
        )
        threshold.times { cb.record_failure }
        cb.record_success
        threshold.times { cb.record_failure }
        assert_equal 'closed', cb.state,
          "Success must reset failure counter; threshold=#{threshold}"

      # ----- Bug 12: plan_multi_leg uses crow-flies instead of leg sum -----
      when 11
        offset = idx % 500
        waypoints = [
          { name: 'A', nm: 0 },
          { name: 'B', nm: 200 + offset },
          { name: 'C', nm: 50 + (offset / 2) }
        ]
        result = MercuryLedger::Core::Routing.plan_multi_leg(waypoints)
        leg_sum = result[:legs].sum { |l| l[:distance_nm] }
        assert_in_delta leg_sum, result[:total_distance], 0.01,
          'Total distance must equal sum of legs, not crow-flies'

      # ----- Bug 13: RateLimiter allows fractional tokens -----
      when 12
        t = Time.now.to_f + idx
        limiter = MercuryLedger::Core::RateLimiter.new(max_tokens: 1, refill_rate: 0.5)
        assert limiter.allow?(t)
        # After 1 second, refills 0.5 tokens — fractional, must deny
        refute limiter.allow?(t + 1.0),
          'Fractional token (0.5) must not allow a request'

      # ----- Bug 14: TERMINAL_STATES missing :arrived -----
      when 13
        assert MercuryLedger::Core::Workflow.is_terminal_state?(:arrived),
          ':arrived must be a terminal state'
        engine = MercuryLedger::Core::WorkflowEngine.new
        engine.register("e-#{idx}")
        engine.transition("e-#{idx}", :allocated)
        engine.transition("e-#{idx}", :departed)
        engine.transition("e-#{idx}", :arrived)
        assert engine.is_terminal?("e-#{idx}"),
          'Entity at :arrived must be terminal'
      end
    end
  end
end
