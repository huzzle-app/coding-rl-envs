# frozen_string_literal: true

require_relative '../test_helper'

class ReconciliationTest < Minitest::Test
  def test_mismatch_respects_tolerance
    refute ClearLedger::Core::Reconciliation.mismatch?(1000, 999.7, 5)
    assert ClearLedger::Core::Reconciliation.mismatch?(1000, 998.0, 5)
  end

  def test_replay_signature_is_normalized
    assert_equal 'batch-7:v13', ClearLedger::Core::Reconciliation.replay_signature('BATCH-7', 13)
  end

  def test_merge_snapshots_prefers_newer_version
    left = { version: 11, balance: 10 }
    right = { version: 12, balance: 11 }

    assert_equal right, ClearLedger::Core::Reconciliation.merge_snapshots(left, right)
  end
end
