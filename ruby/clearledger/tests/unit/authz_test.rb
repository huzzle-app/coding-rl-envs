# frozen_string_literal: true

require_relative '../test_helper'

class AuthzTest < Minitest::Test
  def test_authz_role_matrix
    assert ClearLedger::Core::Authz.allowed?(:operator, :read)
    refute ClearLedger::Core::Authz.allowed?(:operator, :override)
    assert ClearLedger::Core::Authz.allowed?(:admin, :override)
  end

  def test_token_freshness_window
    assert ClearLedger::Core::Authz.token_fresh?(1000, 300, 1299)
    refute ClearLedger::Core::Authz.token_fresh?(1000, 300, 1301)
  end
end
