# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/auth/service'

class AuthServiceTest < Minitest::Test
  def test_derive_context_creates_operator
    ctx = OpalCommand::Services::Auth.derive_context(operator_id: 'op1', name: 'Alice', roles: %w[admin], clearance: 5, mfa_done: true)
    assert_equal 'op1', ctx.operator_id
    assert_equal 5, ctx.clearance
  end

  def test_authorize_intent_requires_mfa
    ctx = OpalCommand::Services::Auth.derive_context(operator_id: 'op1', name: 'Bob', roles: %w[reader], clearance: 3, mfa_done: false)
    result = OpalCommand::Services::Auth.authorize_intent(ctx, required_clearance: 2)
    assert_equal false, result[:authorized]
    assert_equal 'no_mfa', result[:reason]
  end

  def test_has_role_checks_membership
    ctx = OpalCommand::Services::Auth.derive_context(operator_id: 'op1', name: 'Carol', roles: %w[admin auditor], clearance: 4, mfa_done: true)
    assert OpalCommand::Services::Auth.has_role(ctx, 'admin')
    refute OpalCommand::Services::Auth.has_role(ctx, 'superuser')
  end

  def test_list_permissions_includes_read
    ctx = OpalCommand::Services::Auth.derive_context(operator_id: 'op1', name: 'Dave', roles: %w[reader], clearance: 1, mfa_done: true)
    perms = OpalCommand::Services::Auth.list_permissions(ctx)
    assert_includes perms, 'read'
  end
end
