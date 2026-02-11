# frozen_string_literal: true

require_relative '../test_helper'

class WorkflowTest < Minitest::Test
  def test_transition_graph_enforced
    assert MercuryLedger::Core::Workflow.transition_allowed?(:queued, :allocated)
    refute MercuryLedger::Core::Workflow.transition_allowed?(:queued, :arrived)
  end
end
