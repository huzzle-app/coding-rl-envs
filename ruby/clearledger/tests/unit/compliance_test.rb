# frozen_string_literal: true

require_relative '../test_helper'

class ComplianceTest < Minitest::Test
  def test_override_allowed_requires_reason_and_approvals
    assert ClearLedger::Core::Compliance.override_allowed?('risk accepted by committee', 2, 90)
    refute ClearLedger::Core::Compliance.override_allowed?('too short', 2, 90)
    refute ClearLedger::Core::Compliance.override_allowed?('risk accepted by committee', 1, 90)
    refute ClearLedger::Core::Compliance.override_allowed?('risk accepted by committee', 2, 180)
  end

  def test_retention_bucket
    assert_equal :hot, ClearLedger::Core::Compliance.retention_bucket(14)
    assert_equal :warm, ClearLedger::Core::Compliance.retention_bucket(90)
    assert_equal :cold, ClearLedger::Core::Compliance.retention_bucket(500)
  end

  def test_policy_version_supported
    refute ClearLedger::Core::Compliance.policy_version_supported?(2)
    assert ClearLedger::Core::Compliance.policy_version_supported?(3)
  end
end
