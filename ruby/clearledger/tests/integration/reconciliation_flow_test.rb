# frozen_string_literal: true

require_relative '../test_helper'

class ReconciliationFlowTest < Minitest::Test
  def test_reconciliation_flow_uses_window_watermark_and_mismatch
    bucket = ClearLedger::Core::LedgerWindow.bucket_for(3_600, 300)
    accepted = ClearLedger::Core::LedgerWindow.watermark_accept?(1_000, 1_003, 5)
    mismatch = ClearLedger::Core::Reconciliation.mismatch?(1_000.0, 996.0, 20)

    assert_equal 12, bucket
    assert accepted
    assert mismatch
  end

  def test_queue_policy_and_sla_work_together
    policy = ClearLedger::Core::QueuePolicy.next_policy(4)
    admitted = ClearLedger::Core::QueuePolicy.admit?(12, 5, policy[:max_inflight])
    risk = ClearLedger::Core::SLA.breach_risk(1_900, 2_000, 150)

    refute admitted
    assert risk
  end
end
