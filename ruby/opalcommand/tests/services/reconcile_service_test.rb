# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/reconcile/service'

class ReconcileServiceTest < Minitest::Test
  def test_build_reconcile_sequence_returns_steps
    result = OpalCommand::Services::Reconcile.build_reconcile_sequence(delta_required: 10.0, available_budget: 100.0)
    assert result[:budget_ok]
    assert_operator result[:steps].length, :>, 0
  end

  def test_validate_budget_over
    result = OpalCommand::Services::Reconcile.validate_budget(total_delta: 200.0, budget: 100.0)
    refute result[:valid]
    assert_equal 'over_budget', result[:reason]
  end

  def test_estimate_timeline_hours
    hours = OpalCommand::Services::Reconcile.estimate_timeline_hours(8, spacing_minutes: 30)
    assert_equal 4.0, hours
  end

  def test_reconcile_summary
    steps = [{ delta: 5.0 }, { delta: 3.0 }]
    summary = OpalCommand::Services::Reconcile.reconcile_summary(steps)
    assert_equal 2, summary[:step_count]
    assert_equal 8.0, summary[:total_delta]
  end
end
