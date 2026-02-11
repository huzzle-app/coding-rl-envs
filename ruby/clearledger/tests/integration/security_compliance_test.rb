# frozen_string_literal: true

require_relative '../test_helper'

class SecurityComplianceTest < Minitest::Test
  def test_privileged_action_requires_admin_and_override_approval
    role = :admin
    token_ok = ClearLedger::Core::Authz.token_fresh?(1_000, 600, 1_550)
    can_override = ClearLedger::Core::Compliance.override_allowed?('documented emergency operational exception', 2, 90)

    assert token_ok
    assert can_override
    assert ClearLedger::Core::CommandRouter.guard_action?(role, :override)
  end

  def test_operator_cannot_issue_override_even_with_fresh_token
    token_ok = ClearLedger::Core::Authz.token_fresh?(1_000, 600, 1_200)

    assert token_ok
    refute ClearLedger::Core::CommandRouter.guard_action?(:operator, :override)
  end
end
