# frozen_string_literal: true

require_relative '../test_helper'
require 'set'

class ComplexBugsMatrixTest < Minitest::Test
  # ==========================================================================
  # Settlement.process_settlement_pipeline
  # ==========================================================================

  def test_pipeline_rejected_entry_should_not_affect_risk
    entries = [
      { account: 'A', delta: 0 },     # invalid: delta must be non-zero
      { account: 'B', delta: 100.0 }   # valid
    ]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.1, 5.0, fee_tiers)
    settled = result[:entries].select { |e| e[:status] == :settled }
    assert_equal 1, settled.length, 'Valid entry should be settled'
    assert_in_delta 100.0, settled.first[:running_gross], 1e-6
  end

  def test_pipeline_rejected_entry_gross_not_inflated
    entries = [
      { account: 'X' },                # missing delta -> rejected
      { account: 'Y', delta: 50.0 }
    ]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.0, 10.0, fee_tiers)
    assert_in_delta 50.0, result[:final_gross], 1e-6
  end

  def test_pipeline_all_valid_entries
    entries = [
      { account: 'A', delta: 100.0 },
      { account: 'B', delta: 200.0 }
    ]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.0, 100.0, fee_tiers)
    settled = result[:entries].select { |e| e[:status] == :settled }
    assert_equal 2, settled.length
  end

  def test_pipeline_risk_block_with_high_leverage
    entries = [
      { account: 'A', delta: 1000.0 },
      { account: 'A', delta: 1000.0 }
    ]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.0, 0.5, fee_tiers)
    blocked = result[:entries].count { |e| e[:status] == :risk_blocked }
    assert blocked >= 1, 'At least one entry should be risk-blocked with tight leverage cap'
  end

  def test_pipeline_fee_calculation_correct
    entries = [{ account: 'A', delta: 5000.0 }]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.0, 100.0, fee_tiers)
    settled = result[:entries].first
    assert_equal :settled, settled[:status]
    assert_in_delta 5.0, settled[:fee], 1e-6
  end

  def test_pipeline_reserve_applied
    entries = [{ account: 'A', delta: 1000.0 }]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.1, 100.0, fee_tiers)
    settled = result[:entries].first
    assert_equal :settled, settled[:status]
    assert_in_delta 900.0, settled[:net], 1e-6
  end

  def test_pipeline_rejected_does_not_corrupt_final_net
    entries = [
      { account: 'A', delta: 0 },      # rejected
      { account: 'A', delta: 500.0 }    # valid
    ]
    fee_tiers = [{ limit: 10_000, rate: 0.001 }]
    result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.0, 100.0, fee_tiers)
    assert_in_delta 500.0, result[:final_net]['A'], 1e-6
  end

  5.times do |i|
    define_method("test_pipeline_parametric_rejected_corruption_#{format('%03d', i)}") do
      valid_delta = 100.0
      entries = [
        { account: 'X', delta: 0 },           # rejected (zero delta)
        { account: 'Y', delta: valid_delta }
      ]
      fee_tiers = [{ limit: 100_000, rate: 0.001 }]
      result = ClearLedger::Core::Settlement.process_settlement_pipeline(entries, 0.0, 100.0, fee_tiers)
      assert_in_delta valid_delta, result[:final_gross], 1e-6
    end
  end

  # ==========================================================================
  # Reconciliation.windowed_reconciliation
  # ==========================================================================

  def test_windowed_recon_no_double_match
    # Two expected entries for the same account/amount, but only one observed.
    # After matching the first expected, the observed entry should be consumed.
    expected = [
      { ts: 100, account: 'A', amount: 1000.0 },
      { ts: 200, account: 'A', amount: 1000.0 }
    ]
    observed = [
      { ts: 150, account: 'A', amount: 1000.0 }
    ]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 10_000, 100)
    bucket = result.values.first
    assert_equal 1, bucket[:matches], 'Only 1 observed entry available for matching'
    assert_equal 1, bucket[:breaks], 'Second expected has no observed counterpart'
    assert_equal 0, bucket[:unmatched_observed]
  end

  def test_windowed_recon_unmatched_observed_after_match
    expected = [{ ts: 100, account: 'A', amount: 1000.0 }]
    observed = [{ ts: 105, account: 'A', amount: 1000.0 }]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 1000, 100)
    bucket = result.values.first
    assert_equal 1, bucket[:matches]
    assert_equal 0, bucket[:unmatched_observed], 'Matched observed entry should be consumed'
  end

  def test_windowed_recon_mismatch
    expected = [{ ts: 100, account: 'A', amount: 1000.0 }]
    observed = [{ ts: 105, account: 'A', amount: 500.0 }]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 1000, 10)
    bucket = result.values.first
    assert_equal 0, bucket[:matches]
    assert_equal 1, bucket[:breaks]
    assert_equal 1, bucket[:unmatched_observed]
  end

  def test_windowed_recon_multiple_matches_consumed
    expected = [
      { ts: 100, account: 'A', amount: 1000.0 },
      { ts: 200, account: 'B', amount: 2000.0 }
    ]
    observed = [
      { ts: 150, account: 'A', amount: 1000.0 },
      { ts: 250, account: 'B', amount: 2000.0 }
    ]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 1000, 100)
    bucket = result.values.first
    assert_equal 2, bucket[:matches]
    assert_equal 0, bucket[:breaks]
    assert_equal 0, bucket[:unmatched_observed], 'Both observed should be consumed'
  end

  def test_windowed_recon_three_expected_one_observed
    expected = [
      { ts: 100, account: 'A', amount: 500.0 },
      { ts: 200, account: 'A', amount: 500.0 },
      { ts: 300, account: 'A', amount: 500.0 }
    ]
    observed = [
      { ts: 150, account: 'A', amount: 500.0 }
    ]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 10_000, 100)
    bucket = result.values.first
    assert_equal 1, bucket[:matches]
    assert_equal 2, bucket[:breaks]
  end

  def test_windowed_recon_missing_observed
    expected = [{ ts: 100, account: 'A', amount: 1000.0 }]
    observed = []
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 1000, 100)
    bucket = result.values.first
    assert_equal 0, bucket[:matches]
    assert_equal 1, bucket[:breaks]
  end

  def test_windowed_recon_extra_observed
    expected = []
    observed = [{ ts: 100, account: 'A', amount: 1000.0 }]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 1000, 100)
    bucket = result.values.first
    assert_equal 0, bucket[:matches]
    assert_equal 0, bucket[:breaks]
    assert_equal 1, bucket[:unmatched_observed]
  end

  def test_windowed_recon_cross_bucket_consumed
    expected = [
      { ts: 100, account: 'A', amount: 500.0 },
      { ts: 1100, account: 'B', amount: 600.0 }
    ]
    observed = [
      { ts: 150, account: 'A', amount: 500.0 },
      { ts: 1150, account: 'B', amount: 600.0 }
    ]
    result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 1000, 100)
    assert_equal 2, result.keys.length
    result.each_value do |bucket|
      assert_equal 1, bucket[:matches]
      assert_equal 0, bucket[:breaks]
      assert_equal 0, bucket[:unmatched_observed]
    end
  end

  5.times do |i|
    define_method("test_windowed_recon_parametric_consumption_#{format('%03d', i)}") do
      n = i + 2
      # N expected entries, all same account/amount. N observed entries.
      # Each expected should consume exactly one observed entry.
      expected = n.times.map { |j| { ts: j * 10, account: 'X', amount: 500.0 } }
      observed = n.times.map { |j| { ts: j * 10 + 5, account: 'X', amount: 500.0 } }
      result = ClearLedger::Core::Reconciliation.windowed_reconciliation(expected, observed, 100_000, 100)
      total_matches = result.values.sum { |b| b[:matches] }
      total_unmatched = result.values.sum { |b| b[:unmatched_observed] }
      assert_equal n, total_matches
      assert_equal 0, total_unmatched, 'All observed entries should be consumed by matching'
    end
  end

  # ==========================================================================
  # Routing.counterparty_exposure_chain
  # ==========================================================================

  def test_exposure_chain_depth_one
    graph = { 'A' => ['B'] }
    amounts = { 'B' => 1000.0 }
    exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(graph, 'A', amounts, 0.5, 3)
    assert_in_delta 500.0, exposure, 1e-6
  end

  def test_exposure_chain_depth_two_exponential
    graph = { 'A' => ['B'], 'B' => ['C'] }
    amounts = { 'B' => 1000.0, 'C' => 1000.0 }
    # B at depth 1: 1000 * 0.5^1 = 500
    # C at depth 2: 1000 * 0.5^2 = 250
    exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(graph, 'A', amounts, 0.5, 3)
    assert_in_delta 750.0, exposure, 1e-6
  end

  def test_exposure_chain_depth_three
    graph = { 'A' => ['B'], 'B' => ['C'], 'C' => ['D'] }
    amounts = { 'B' => 1000.0, 'C' => 1000.0, 'D' => 1000.0 }
    exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(graph, 'A', amounts, 0.5, 5)
    assert_in_delta 875.0, exposure, 1e-6
  end

  def test_exposure_chain_max_depth_limit
    graph = { 'A' => ['B'], 'B' => ['C'], 'C' => ['D'] }
    amounts = { 'B' => 1000.0, 'C' => 1000.0, 'D' => 1000.0 }
    exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(graph, 'A', amounts, 0.5, 1)
    assert_in_delta 500.0, exposure, 1e-6
  end

  def test_exposure_chain_no_neighbors
    graph = { 'A' => [] }
    amounts = { 'B' => 1000.0 }
    exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(graph, 'A', amounts, 0.5, 3)
    assert_in_delta 0.0, exposure, 1e-6
  end

  def test_exposure_chain_branching_graph
    graph = { 'A' => ['B', 'C'], 'B' => ['D'], 'C' => ['D'] }
    amounts = { 'B' => 1000.0, 'C' => 2000.0, 'D' => 500.0 }
    exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(graph, 'A', amounts, 0.5, 3)
    assert_in_delta 1625.0, exposure, 1e-6
  end

  5.times do |i|
    define_method("test_exposure_chain_parametric_depth_#{format('%03d', i)}") do
      depth = i + 2
      nodes = (0..depth).map { |d| "N#{d}" }
      graph = {}
      amounts = {}
      nodes.each_with_index do |n, idx|
        graph[n] = idx < nodes.length - 1 ? [nodes[idx + 1]] : []
        amounts[n] = 1000.0 if idx > 0
      end
      attenuation = 0.5
      expected = (1..depth).sum { |d| 1000.0 * (attenuation ** d) }
      exposure = ClearLedger::Core::Routing.counterparty_exposure_chain(
        graph, nodes.first, amounts, attenuation, depth + 1
      )
      assert_in_delta expected, exposure, 1e-3
    end
  end

  # ==========================================================================
  # Resilience.event_sourced_reconstruct
  # ==========================================================================

  def test_reconstruct_no_double_count_same_version
    # Snapshot at v10 already incorporates v10 events.
    # Passing a v10 event should NOT double-count it.
    snapshots = [
      { version: 5, gross: 100.0, net: 50.0 },
      { version: 10, gross: 200.0, net: 100.0 }
    ]
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 10, idempotency_key: 'already_included', gross_delta: 50, net_delta: 25),
      ClearLedger::Core::Resilience::Event.new(version: 11, idempotency_key: 'new_event', gross_delta: 10, net_delta: 5)
    ]
    result = ClearLedger::Core::Resilience.event_sourced_reconstruct(snapshots, events)
    # Only the v11 event should be applied on top of v10 snapshot
    assert_in_delta 210.0, result.gross, 1e-6
    assert_in_delta 105.0, result.net, 1e-6
    assert_equal 1, result.applied
  end

  def test_reconstruct_applied_count_excludes_old
    snapshots = [
      { version: 10, gross: 500.0, net: 250.0 }
    ]
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 8, idempotency_key: 'old1', gross_delta: 100, net_delta: 50),
      ClearLedger::Core::Resilience::Event.new(version: 10, idempotency_key: 'at_snap', gross_delta: 100, net_delta: 50),
      ClearLedger::Core::Resilience::Event.new(version: 12, idempotency_key: 'new1', gross_delta: 20, net_delta: 10)
    ]
    result = ClearLedger::Core::Resilience.event_sourced_reconstruct(snapshots, events)
    # v8 < v10: skipped. v10 == v10: should be skipped (already in snapshot).
    # Only v12 applied.
    assert_in_delta 520.0, result.gross, 1e-6
    assert_equal 1, result.applied
  end

  def test_reconstruct_single_snapshot_no_overlap
    snapshots = [{ version: 5, gross: 100.0, net: 50.0 }]
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 6, idempotency_key: 'e1', gross_delta: 20, net_delta: 10)
    ]
    result = ClearLedger::Core::Resilience.event_sourced_reconstruct(snapshots, events)
    assert_in_delta 120.0, result.gross, 1e-6
    assert_in_delta 60.0, result.net, 1e-6
  end

  def test_reconstruct_three_snapshots_picks_latest
    snapshots = [
      { version: 1, gross: 10.0, net: 5.0 },
      { version: 5, gross: 50.0, net: 25.0 },
      { version: 10, gross: 100.0, net: 50.0 }
    ]
    events = []
    result = ClearLedger::Core::Resilience.event_sourced_reconstruct(snapshots, events)
    assert_in_delta 100.0, result.gross, 1e-6
    assert_equal 10, result.version
  end

  def test_reconstruct_empty_snapshots
    result = ClearLedger::Core::Resilience.event_sourced_reconstruct([], [])
    assert_in_delta 0.0, result.gross, 1e-6
    assert_equal 0, result.version
  end

  def test_reconstruct_multiple_same_version_events
    snapshots = [
      { version: 10, gross: 1000.0, net: 500.0 }
    ]
    events = [
      ClearLedger::Core::Resilience::Event.new(version: 10, idempotency_key: 'a', gross_delta: 100, net_delta: 50),
      ClearLedger::Core::Resilience::Event.new(version: 10, idempotency_key: 'b', gross_delta: 200, net_delta: 100),
      ClearLedger::Core::Resilience::Event.new(version: 11, idempotency_key: 'c', gross_delta: 10, net_delta: 5)
    ]
    result = ClearLedger::Core::Resilience.event_sourced_reconstruct(snapshots, events)
    # v10 events already in snapshot — only v11 should apply
    assert_in_delta 1010.0, result.gross, 1e-6
    assert_in_delta 505.0, result.net, 1e-6
    assert_equal 1, result.applied
  end

  5.times do |i|
    define_method("test_reconstruct_parametric_double_count_#{format('%03d', i)}") do
      snap_version = 10 + i * 5
      snapshots = [
        { version: 1, gross: 10.0, net: 5.0 },
        { version: snap_version, gross: 1000.0 * (i + 1), net: 500.0 * (i + 1) }
      ]
      # Include an event at the snapshot's exact version (should not be applied)
      # and one newer event (should be applied)
      events = [
        ClearLedger::Core::Resilience::Event.new(
          version: snap_version, idempotency_key: "overlap_#{i}", gross_delta: 999, net_delta: 999
        ),
        ClearLedger::Core::Resilience::Event.new(
          version: snap_version + 1, idempotency_key: "new_#{i}", gross_delta: 10, net_delta: 5
        )
      ]
      result = ClearLedger::Core::Resilience.event_sourced_reconstruct(snapshots, events)
      expected_gross = 1000.0 * (i + 1) + 10.0
      assert_in_delta expected_gross, result.gross, 1e-6
      assert_equal 1, result.applied
    end
  end

  # ==========================================================================
  # Workflow.saga_compensate
  # ==========================================================================

  def test_saga_intermediate_balance_after_each_step
    steps = [
      { action: 'debit', account: 'A', delta: 100.0 },
      { action: 'credit', account: 'B', delta: 200.0 }
    ]
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 1000.0)
    # Reverse order: credit (200) first, then debit (100)
    # After compensating credit: 1000 - 200 = 800
    assert_in_delta 800.0, result[:log][0][:balance_after], 1e-6
    # After compensating debit: 800 - 100 = 700
    assert_in_delta 700.0, result[:log][1][:balance_after], 1e-6
    assert_in_delta 700.0, result[:final_balance], 1e-6
  end

  def test_saga_compensation_order_is_reversed
    steps = [
      { action: 'step1', account: 'A', delta: 10.0 },
      { action: 'step2', account: 'B', delta: 20.0 },
      { action: 'step3', account: 'C', delta: 30.0 }
    ]
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 500.0)
    actions = result[:log].map { |l| l[:action] }
    assert_equal 'compensate_step3', actions[0]
    assert_equal 'compensate_step2', actions[1]
    assert_equal 'compensate_step1', actions[2]
  end

  def test_saga_three_step_intermediate_balances
    steps = [
      { action: 'a', account: 'X', delta: 100.0 },
      { action: 'b', account: 'Y', delta: 50.0 },
      { action: 'c', account: 'Z', delta: 75.0 }
    ]
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 1000.0)
    # Reverse: c (75), b (50), a (100)
    assert_in_delta 925.0, result[:log][0][:balance_after], 1e-6
    assert_in_delta 875.0, result[:log][1][:balance_after], 1e-6
    assert_in_delta 775.0, result[:log][2][:balance_after], 1e-6
  end

  def test_saga_single_step_balance_after
    steps = [{ action: 'deposit', account: 'A', delta: 500.0 }]
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 1000.0)
    assert_in_delta 500.0, result[:log][0][:balance_after], 1e-6
    assert_in_delta 500.0, result[:final_balance], 1e-6
    assert_equal 1, result[:steps_compensated]
  end

  def test_saga_empty_steps
    result = ClearLedger::Core::Workflow.saga_compensate([], 1000.0)
    assert_in_delta 1000.0, result[:final_balance], 1e-6
    assert_equal 0, result[:steps_compensated]
  end

  def test_saga_negative_delta_balance_after
    steps = [{ action: 'withdraw', account: 'A', delta: -200.0 }]
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 1000.0)
    # Compensating -200 means subtracting -200 = adding 200
    assert_in_delta 1200.0, result[:log][0][:balance_after], 1e-6
    assert_in_delta 1200.0, result[:final_balance], 1e-6
  end

  def test_saga_delta_signs_in_log
    steps = [{ action: 'op', account: 'A', delta: 300.0 }]
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 1000.0)
    # Compensation log should record negative delta
    assert_in_delta(-300.0, result[:log][0][:delta], 1e-6)
  end

  def test_saga_count_matches_steps
    steps = 4.times.map { |i| { action: "s#{i}", account: 'A', delta: 10.0 } }
    result = ClearLedger::Core::Workflow.saga_compensate(steps, 100.0)
    assert_equal 4, result[:steps_compensated]
  end

  5.times do |i|
    define_method("test_saga_parametric_balance_trace_#{format('%03d', i)}") do
      n = i + 2
      steps = n.times.map { |j| { action: "op#{j}", account: 'A', delta: 50.0 * (j + 1) } }
      result = ClearLedger::Core::Workflow.saga_compensate(steps, 5000.0)
      # Verify each intermediate balance_after is correct
      expected_balance = 5000.0
      result[:log].each_with_index do |entry, idx|
        # Reversed: steps are compensated from last to first
        original_idx = n - 1 - idx
        expected_balance -= 50.0 * (original_idx + 1)
        assert_in_delta expected_balance, entry[:balance_after], 1e-6,
                        "Intermediate balance at compensation step #{idx} should be #{expected_balance}"
      end
    end
  end

  # ==========================================================================
  # Compliance.temporal_approval_chain
  # ==========================================================================

  def test_temporal_chain_requires_all_levels
    approvals = [
      { role: :operator, approved: true, ts: 100 },
      { role: :admin, approved: true, ts: 200 }
    ]
    refute ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 2)
  end

  def test_temporal_chain_complete_chain_passes
    approvals = [
      { role: :operator, approved: true, ts: 100 },
      { role: :reviewer, approved: true, ts: 200 },
      { role: :admin, approved: true, ts: 300 }
    ]
    assert ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 2)
  end

  def test_temporal_chain_must_be_ascending
    approvals = [
      { role: :operator, approved: true, ts: 100 },
      { role: :operator, approved: true, ts: 200 },
      { role: :reviewer, approved: true, ts: 300 },
      { role: :admin, approved: true, ts: 400 }
    ]
    refute ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 2)
  end

  def test_temporal_chain_descending_order_fails
    approvals = [
      { role: :admin, approved: true, ts: 100 },
      { role: :operator, approved: true, ts: 200 }
    ]
    refute ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 1)
  end

  def test_temporal_chain_level_zero_only
    approvals = [{ role: :operator, approved: true, ts: 100 }]
    assert ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 0)
  end

  def test_temporal_chain_unapproved_not_counted
    approvals = [
      { role: :operator, approved: true, ts: 100 },
      { role: :reviewer, approved: false, ts: 200 },
      { role: :admin, approved: true, ts: 300 }
    ]
    refute ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 2)
  end

  def test_temporal_chain_empty_approvals
    refute ClearLedger::Core::Compliance.temporal_approval_chain([], 1)
  end

  5.times do |i|
    define_method("test_temporal_chain_parametric_gap_#{format('%03d', i)}") do
      all_roles = [:operator, :reviewer, :admin]
      gap_idx = i % 3
      approvals = all_roles.each_with_index.map do |role, idx|
        next nil if idx == gap_idx
        { role: role, approved: true, ts: (idx + 1) * 100 }
      end.compact
      refute ClearLedger::Core::Compliance.temporal_approval_chain(approvals, 2),
             "Chain with gap at level #{gap_idx} should fail"
    end
  end

  # ==========================================================================
  # QueuePolicy.priority_drain_with_fairness
  # ==========================================================================

  def test_priority_drain_high_priority_first
    queues = [
      { priority: 1, items: [:low_a, :low_b] },
      { priority: 3, items: [:high_a, :high_b] },
      { priority: 2, items: [:med_a, :med_b] }
    ]
    drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, 3, 1)
    assert_equal :high_a, drained[0]
    assert_equal :med_a, drained[1]
    assert_equal :low_a, drained[2]
  end

  def test_priority_drain_respects_budget
    queues = [
      { priority: 1, items: Array.new(10) { |i| "item_#{i}" } }
    ]
    drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, 3, 5)
    assert_equal 3, drained.length
  end

  def test_priority_drain_per_queue_max
    queues = [
      { priority: 2, items: [:a, :b, :c, :d, :e] },
      { priority: 1, items: [:f, :g, :h] }
    ]
    drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, 10, 2)
    assert_equal 8, drained.length
  end

  def test_priority_drain_empty_queues
    queues = [
      { priority: 1, items: [] },
      { priority: 2, items: [] }
    ]
    drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, 10, 5)
    assert_empty drained
  end

  def test_priority_drain_single_high_priority
    queues = [
      { priority: 1, items: [:low] },
      { priority: 10, items: [:critical] }
    ]
    drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, 1, 1)
    assert_equal [:critical], drained
  end

  def test_priority_drain_fairness_round_robin
    queues = [
      { priority: 3, items: [:h1, :h2, :h3, :h4] },
      { priority: 2, items: [:m1, :m2, :m3, :m4] }
    ]
    drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, 4, 2)
    assert_equal [:h1, :h2, :m1, :m2], drained
  end

  5.times do |i|
    define_method("test_priority_drain_parametric_#{format('%03d', i)}") do
      queues = [
        { priority: 1, items: (i + 1).times.map { |j| "low_#{j}" } },
        { priority: 5, items: (i + 1).times.map { |j| "high_#{j}" } }
      ]
      drained = ClearLedger::Core::QueuePolicy.priority_drain_with_fairness(queues, i + 1, 10)
      assert_equal "high_0", drained.first
    end
  end

  # ==========================================================================
  # AuditChain.merkle_audit_verify
  # ==========================================================================

  def test_merkle_two_leaves
    leaves = [100, 200]
    root = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)
    expected = ClearLedger::Core::AuditChain.append_hash(100, '200')
    assert_equal expected, root
  end

  def test_merkle_single_leaf
    root = ClearLedger::Core::AuditChain.merkle_audit_verify([42])
    assert_equal 42, root
  end

  def test_merkle_empty
    root = ClearLedger::Core::AuditChain.merkle_audit_verify([])
    assert_equal 0, root
  end

  def test_merkle_three_leaves_odd
    leaves = [10, 20, 30]
    h1 = ClearLedger::Core::AuditChain.append_hash(10, '20')
    h2 = ClearLedger::Core::AuditChain.append_hash(30, '30')
    expected = ClearLedger::Core::AuditChain.append_hash(h1, h2.to_s)
    root = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)
    assert_equal expected, root
  end

  def test_merkle_four_leaves_even
    leaves = [10, 20, 30, 40]
    h1 = ClearLedger::Core::AuditChain.append_hash(10, '20')
    h2 = ClearLedger::Core::AuditChain.append_hash(30, '40')
    expected = ClearLedger::Core::AuditChain.append_hash(h1, h2.to_s)
    root = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)
    assert_equal expected, root
  end

  def test_merkle_five_leaves_odd
    leaves = [1, 2, 3, 4, 5]
    h12 = ClearLedger::Core::AuditChain.append_hash(1, '2')
    h34 = ClearLedger::Core::AuditChain.append_hash(3, '4')
    h55 = ClearLedger::Core::AuditChain.append_hash(5, '5')
    h_l = ClearLedger::Core::AuditChain.append_hash(h12, h34.to_s)
    h_r = ClearLedger::Core::AuditChain.append_hash(h55, h55.to_s)
    expected = ClearLedger::Core::AuditChain.append_hash(h_l, h_r.to_s)
    root = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)
    assert_equal expected, root
  end

  def test_merkle_deterministic
    leaves = [100, 200, 300]
    r1 = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)
    r2 = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)
    assert_equal r1, r2
  end

  def test_merkle_order_matters
    r1 = ClearLedger::Core::AuditChain.merkle_audit_verify([10, 20, 30])
    r2 = ClearLedger::Core::AuditChain.merkle_audit_verify([30, 20, 10])
    refute_equal r1, r2
  end

  5.times do |i|
    define_method("test_merkle_parametric_odd_#{format('%03d', i)}") do
      n = 2 * i + 3  # 3, 5, 7, 9, 11 leaves
      leaves = n.times.map { |j| (j + 1) * 100 }
      root = ClearLedger::Core::AuditChain.merkle_audit_verify(leaves)

      level = leaves.map(&:to_i)
      while level.length > 1
        next_level = []
        level.each_slice(2) do |pair|
          if pair.length == 2
            next_level << ClearLedger::Core::AuditChain.append_hash(pair[0], pair[1].to_s)
          else
            next_level << ClearLedger::Core::AuditChain.append_hash(pair[0], pair[0].to_s)
          end
        end
        level = next_level
      end
      assert_equal level.first, root
    end
  end

  # ==========================================================================
  # Cross-Module Interaction Tests
  # Each test exercises 2-3 bugs across different modules, preventing
  # single-module fixes from flipping these tests.
  # ==========================================================================

  def test_cross_settlement_riskgate_ratio_precision
    # Settlement.netting_ratio + RiskGate.exposure_ratio: both have integer division
    netting = ClearLedger::Core::Settlement.netting_ratio(100.0, 75.0)
    exposure = ClearLedger::Core::RiskGate.exposure_ratio(75.0, 10.0)
    assert_in_delta 0.75, netting, 1e-9
    assert_in_delta 7.5, exposure, 1e-9
  end

  def test_cross_workflow_terminal_and_pending
    # Workflow.terminal_state? + pending_count: both broken for :canceled
    assert ClearLedger::Core::Workflow.terminal_state?(:canceled)
    entities = [:drafted, :canceled, :reported, :validated]
    pending = ClearLedger::Core::Workflow.pending_count(entities)
    assert_equal 2, pending, ':canceled and :reported should not be counted as pending'
  end

  def test_cross_resilience_health_and_audit_score
    # Resilience.health_score + AuditChain.audit_score: both have integer division
    health = ClearLedger::Core::Resilience.health_score(7, 3)
    audit = ClearLedger::Core::AuditChain.audit_score(7, 10)
    assert_in_delta 0.7, health, 1e-9
    assert_in_delta 0.7, audit, 1e-9
  end

  def test_cross_compliance_sla_percentage_consistency
    # Compliance.compliance_score + SLA.sla_compliance_rate: both return ratio not percentage
    comp_rate = ClearLedger::Core::Compliance.compliance_score(80, 100)
    sla_rate = ClearLedger::Core::SLA.sla_compliance_rate(80, 100)
    assert_in_delta 80.0, comp_rate, 1e-9
    assert_in_delta 80.0, sla_rate, 1e-9
  end

  def test_cross_age_calculations_positive
    # Reconciliation.age_seconds + Resilience.checkpoint_age + AuditChain.entry_age: all inverted
    recon_age = ClearLedger::Core::Reconciliation.age_seconds(1000, 1100)
    checkpoint_age = ClearLedger::Core::Resilience.checkpoint_age(1000, 2000)
    entry_age = ClearLedger::Core::AuditChain.entry_age(1000, 2000)
    assert_equal 100, recon_age
    assert_equal 1000, checkpoint_age
    assert_equal 1000, entry_age
  end

  def test_cross_routing_queue_admission
    # Routing.congestion_score + QueuePolicy.should_throttle?: inverted division + boundary
    congestion = ClearLedger::Core::Routing.congestion_score(80, 100)
    should_throttle = ClearLedger::Core::QueuePolicy.should_throttle?(100.0, 100.0)
    assert_in_delta 0.8, congestion, 1e-9
    assert should_throttle, 'Should throttle at full capacity'
  end

  def test_cross_window_sla_boundary
    # LedgerWindow.event_in_window? + SLA.sla_met?: both have boundary bugs
    refute ClearLedger::Core::LedgerWindow.event_in_window?(150, 50, 150),
           'Event at window_end should be outside half-open window [50, 150)'
    assert ClearLedger::Core::SLA.sla_met?(60, 60),
           'SLA at exactly deadline should be met'
  end

  def test_cross_statistics_median_and_ema
    # Statistics.median + exponential_moving_average: two different stats bugs
    med = ClearLedger::Core::Statistics.median([1, 2, 3, 4])
    ema = ClearLedger::Core::Statistics.exponential_moving_average([0, 100], 0.8)
    assert_in_delta 2.5, med, 1e-9
    assert_in_delta 80.0, ema[1], 1e-6
  end

  def test_cross_command_auth_requirements
    # CommandRouter + Authz: all missing-case bugs
    settle_priority = ClearLedger::Core::CommandRouter.command_priority('settle')
    needs_audit = ClearLedger::Core::CommandRouter.requires_audit?('reconcile')
    needs_mfa = ClearLedger::Core::Authz.requires_mfa?('approve')
    assert_equal 3, settle_priority
    assert needs_audit, 'reconcile command should require audit'
    assert needs_mfa, 'approve action should require MFA'
  end

  def test_cross_resilience_routing_healthy_paths
    # Resilience.failover_candidates + Routing.feasible_routes: both have inverted filter logic
    failover = ClearLedger::Core::Resilience.failover_candidates(%w[a b c], %w[b])
    routes = { 'a' => 50, 'b' => 150, 'c' => 200 }
    feasible = ClearLedger::Core::Routing.feasible_routes(routes, 100)
    assert_equal %w[a c], failover
    assert feasible.key?('a'), 'Route under max_latency should be feasible'
    refute feasible.key?('c'), 'Route over max_latency should not be feasible'
  end

  def test_cross_settlement_fee_and_priority
    # Settlement.settlement_fee + priority_settlement?: wrong constant + boundary
    fee = ClearLedger::Core::Settlement.settlement_fee(10_000, 'premium')
    is_priority = ClearLedger::Core::Settlement.priority_settlement?(3, 100_001)
    assert_in_delta 20.0, fee, 1e-9
    assert is_priority, 'urgency 3 with amount > 100k should be priority'
  end

  def test_cross_compliance_authz_thresholds
    # Compliance.override_allowed? + escalation_needed? + Authz.role_hierarchy_rank: threshold bugs
    override_ok = ClearLedger::Core::Compliance.override_allowed?('short reas', 2, 90)
    escalate = ClearLedger::Core::Compliance.escalation_needed?(3, 2)
    rank = ClearLedger::Core::Authz.role_hierarchy_rank(:admin)
    assert override_ok, 'Valid override with 10-char reason + 2 approvals should be allowed'
    assert escalate, 'Severity 3 with failures 2 should trigger escalation'
    assert_equal 3, rank
  end
end
