# frozen_string_literal: true

require_relative '../test_helper'

class StateMachineMatrixTest < Minitest::Test
  # --- Workflow.apply_transition_batch ---
  # Bug: checks initial_state instead of current state for transitions

  def test_batch_sequential_transitions
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:validate, :risk_pass, :settle])
    assert_equal :settled, result[:final_state]
    assert result[:transitions].all? { |t| t[:status] == :applied }
  end

  def test_batch_second_transition_uses_updated_state
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:validate, :risk_pass])
    assert_equal :risk_checked, result[:final_state]
    assert_equal :applied, result[:transitions][1][:status]
  end

  def test_batch_rejects_invalid_from_initial
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:settle])
    assert_equal :rejected, result[:transitions][0][:status]
  end

  def test_batch_mixed_valid_and_invalid
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:validate, :settle])
    assert_equal :applied, result[:transitions][0][:status]
    assert_equal :rejected, result[:transitions][1][:status]
  end

  def test_batch_full_pipeline
    result = ClearLedger::Core::Workflow.apply_transition_batch(
      :drafted, [:validate, :risk_pass, :settle, :publish]
    )
    assert_equal :reported, result[:final_state]
    assert_equal 4, result[:transitions].count { |t| t[:status] == :applied }
  end

  def test_batch_cancel_from_drafted
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:cancel])
    assert_equal :canceled, result[:final_state]
    assert_equal :applied, result[:transitions][0][:status]
  end

  def test_batch_records_from_state_correctly
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:validate, :risk_pass])
    assert_equal :drafted, result[:transitions][0][:from]
    assert_equal :validated, result[:transitions][1][:from]
  end

  def test_batch_three_step_state_tracking
    result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, [:validate, :risk_pass, :settle])
    assert_equal :validated, result[:transitions][0][:to]
    assert_equal :risk_checked, result[:transitions][1][:to]
    assert_equal :settled, result[:transitions][2][:to]
    assert_equal :settled, result[:final_state]
  end

  5.times do |i|
    define_method("test_batch_parametric_pipeline_#{format('%03d', i)}") do
      events = [:validate, :risk_pass, :settle, :publish]
      subset = events[0..i]
      result = ClearLedger::Core::Workflow.apply_transition_batch(:drafted, subset)
      applied = result[:transitions].count { |t| t[:status] == :applied }
      assert_equal subset.length, applied
    end
  end

  # --- Workflow.guard_transition ---
  # Bug: uses :submit for all events, should require :approve for :cancel

  def test_guard_transition_operator_can_validate
    result = ClearLedger::Core::Workflow.guard_transition(:drafted, :validate, :operator)
    assert result[:allowed]
    assert_equal :validated, result[:next_state]
  end

  def test_guard_transition_operator_cannot_cancel
    result = ClearLedger::Core::Workflow.guard_transition(:drafted, :cancel, :operator)
    refute result[:allowed]
    assert_equal 'unauthorized', result[:reason]
  end

  def test_guard_transition_reviewer_can_cancel
    result = ClearLedger::Core::Workflow.guard_transition(:drafted, :cancel, :reviewer)
    assert result[:allowed]
    assert_equal :canceled, result[:next_state]
  end

  def test_guard_transition_admin_can_cancel
    result = ClearLedger::Core::Workflow.guard_transition(:validated, :cancel, :admin)
    assert result[:allowed]
  end

  def test_guard_transition_invalid_transition
    result = ClearLedger::Core::Workflow.guard_transition(:drafted, :settle, :admin)
    refute result[:allowed]
    assert_equal 'invalid_transition', result[:reason]
  end

  def test_guard_transition_operator_submit_settle
    result = ClearLedger::Core::Workflow.guard_transition(:risk_checked, :settle, :operator)
    assert result[:allowed]
  end

  def test_guard_transition_unknown_role
    result = ClearLedger::Core::Workflow.guard_transition(:drafted, :validate, :guest)
    refute result[:allowed]
  end

  5.times do |i|
    define_method("test_guard_cancel_parametric_#{format('%03d', i)}") do
      states = [:drafted, :validated, :risk_checked, :settled, :reported]
      state = states[i % states.length]
      result = ClearLedger::Core::Workflow.guard_transition(state, :cancel, :operator)
      refute result[:allowed], "Operator should not be able to cancel from #{state}"
    end
  end
end
