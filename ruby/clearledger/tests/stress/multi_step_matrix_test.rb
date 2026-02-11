# frozen_string_literal: true

require_relative '../test_helper'
require 'set'

class MultiStepMatrixTest < Minitest::Test
  # --- Reconciliation.detect_systematic_bias ---
  # Two bugs: (1) direction labels swapped, (2) count uses min instead of max

  def test_bias_direction_when_expected_exceeds_observed
    expected = [100, 100, 100, 100, 100]
    observed = [90, 90, 90, 90, 90]
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias(expected, observed)
    assert_equal :under_observed, result[:direction]
  end

  def test_bias_direction_when_observed_exceeds_expected
    expected = [50, 50, 50]
    observed = [70, 70, 70]
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias(expected, observed)
    assert_equal :over_observed, result[:direction]
  end

  def test_bias_count_reports_dominant_direction
    expected = [100, 100, 100, 100, 100]
    observed = [90, 90, 90, 90, 90]
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias(expected, observed)
    assert_equal 5, result[:count]
  end

  def test_bias_count_mixed_directions
    expected = [100, 100, 50, 100]
    observed = [90, 90, 60, 90]
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias(expected, observed)
    assert_equal 3, result[:count]
  end

  def test_bias_magnitude
    expected = [100, 200, 300]
    observed = [90, 190, 290]
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias(expected, observed)
    assert_in_delta 10.0, result[:bias], 1e-6
  end

  def test_bias_empty_input
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias([], [])
    assert_equal :none, result[:direction]
    assert_equal 0, result[:count]
  end

  def test_bias_no_bias_zero_diffs
    expected = [100, 100, 100]
    observed = [100, 100, 100]
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias(expected, observed)
    assert_in_delta 0.0, result[:bias], 1e-6
  end

  def test_bias_single_pair_positive
    result = ClearLedger::Core::Reconciliation.detect_systematic_bias([100], [80])
    assert_equal :under_observed, result[:direction]
    assert_equal 1, result[:count]
  end

  # --- Workflow.detect_cycle ---
  # Two bugs: (1) missing rec_stack.delete on backtrack, (2) returns true instead of false

  def test_detect_cycle_acyclic_linear
    graph = { a: [:b], b: [:c], c: [] }
    refute ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  def test_detect_cycle_simple_cycle
    graph = { a: [:b], b: [:a] }
    assert ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  def test_detect_cycle_self_loop
    graph = { a: [:a] }
    assert ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  def test_detect_cycle_diamond_no_cycle
    graph = { a: [:b, :c], b: [:d], c: [:d], d: [] }
    refute ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  def test_detect_cycle_longer_cycle
    graph = { a: [:b], b: [:c], c: [:d], d: [:a] }
    assert ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  def test_detect_cycle_disconnected_no_cycle
    graph = { a: [:b], b: [], c: [:d], d: [] }
    refute ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  def test_detect_cycle_empty_graph
    refute ClearLedger::Core::Workflow.detect_cycle({})
  end

  def test_detect_cycle_single_node_no_edges
    graph = { a: [] }
    refute ClearLedger::Core::Workflow.detect_cycle(graph)
  end

  # --- Compliance.cascading_approval ---
  # Bug: uses any? instead of checking all levels exist in chain

  def test_cascading_approval_requires_full_chain
    approvers = [{ role: :admin, approved: true }]
    refute ClearLedger::Core::Compliance.cascading_approval(approvers, 2)
  end

  def test_cascading_approval_missing_middle_level
    approvers = [
      { role: :operator, approved: true },
      { role: :admin, approved: true }
    ]
    refute ClearLedger::Core::Compliance.cascading_approval(approvers, 2)
  end

  def test_cascading_approval_complete_chain
    approvers = [
      { role: :operator, approved: true },
      { role: :reviewer, approved: true },
      { role: :admin, approved: true }
    ]
    assert ClearLedger::Core::Compliance.cascading_approval(approvers, 2)
  end

  def test_cascading_approval_unapproved_not_counted
    approvers = [
      { role: :operator, approved: true },
      { role: :reviewer, approved: false },
      { role: :admin, approved: true }
    ]
    refute ClearLedger::Core::Compliance.cascading_approval(approvers, 2)
  end

  def test_cascading_approval_level_zero_only
    approvers = [{ role: :operator, approved: true }]
    assert ClearLedger::Core::Compliance.cascading_approval(approvers, 0)
  end

  def test_cascading_approval_reviewer_chain
    approvers = [
      { role: :operator, approved: true },
      { role: :reviewer, approved: true }
    ]
    assert ClearLedger::Core::Compliance.cascading_approval(approvers, 1)
  end

  def test_cascading_approval_no_approvals
    approvers = [
      { role: :operator, approved: false },
      { role: :reviewer, approved: false }
    ]
    refute ClearLedger::Core::Compliance.cascading_approval(approvers, 1)
  end

  def test_cascading_approval_higher_than_available
    approvers = [{ role: :operator, approved: true }]
    refute ClearLedger::Core::Compliance.cascading_approval(approvers, 2)
  end
end
