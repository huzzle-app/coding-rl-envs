# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/intake/service'

class IntakeServiceTest < Minitest::Test
  def test_validate_command_shape_valid
    cmd = { id: 'cmd1', type: 'nav', satellite: 'SAT-1', urgency: 3, payload: 'data' }
    result = OpalCommand::Services::Intake.validate_command_shape(cmd)
    assert result[:valid]
    assert_empty result[:missing]
  end

  def test_validate_command_shape_missing_fields
    cmd = { id: 'cmd1' }
    result = OpalCommand::Services::Intake.validate_command_shape(cmd)
    refute result[:valid]
    assert_operator result[:missing].length, :>=, 1
  end

  def test_batch_summary_counts
    commands = [
      { id: 'c1', type: 'nav', satellite: 'S1', urgency: 1, payload: 'x' },
      { id: 'c2' }
    ]
    summary = OpalCommand::Services::Intake.batch_summary(commands)
    assert_equal 2, summary[:total]
    assert_equal 1, summary[:valid]
  end

  def test_unique_satellites
    commands = [{ satellite: 'A' }, { satellite: 'B' }, { satellite: 'A' }]
    sats = OpalCommand::Services::Intake.unique_satellites(commands)
    assert_equal %w[A B], sats
  end
end
