# frozen_string_literal: true

require_relative '../test_helper'

class WorkflowTest < Minitest::Test
  def test_transition_allowed_enforces_graph
    assert ClearLedger::Core::Workflow.transition_allowed?(:drafted, :validated)
    refute ClearLedger::Core::Workflow.transition_allowed?(:drafted, :settled)
    assert ClearLedger::Core::Workflow.transition_allowed?(:risk_checked, :settled)
  end

  def test_next_state_for_events
    assert_equal :validated, ClearLedger::Core::Workflow.next_state_for(:validate)
    assert_equal :reported, ClearLedger::Core::Workflow.next_state_for(:publish)
    assert_equal :drafted, ClearLedger::Core::Workflow.next_state_for(:unknown)
  end
end
