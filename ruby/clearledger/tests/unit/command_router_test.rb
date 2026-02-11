# frozen_string_literal: true

require_relative '../test_helper'

class CommandRouterTest < Minitest::Test
  def test_route_command
    assert_equal 'settlement-eu', ClearLedger::Core::CommandRouter.route_command('settle', 'eu')
    assert_equal 'reconcile-core', ClearLedger::Core::CommandRouter.route_command('reconcile', 'us')
    assert_equal 'control-plane', ClearLedger::Core::CommandRouter.route_command('other', 'apac')
  end

  def test_requires_override
    assert ClearLedger::Core::CommandRouter.requires_override?('settle', 200_000, 150_000)
    refute ClearLedger::Core::CommandRouter.requires_override?('reconcile', 200_000, 150_000)
  end

  def test_guard_action_uses_authz_matrix
    assert ClearLedger::Core::CommandRouter.guard_action?(:admin, :override)
    refute ClearLedger::Core::CommandRouter.guard_action?(:operator, :override)
  end
end
