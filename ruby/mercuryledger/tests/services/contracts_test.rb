# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../shared/contracts/contracts'

class ContractsTest < Minitest::Test
  def test_contracts_expose_required_keys
    contracts = MercuryLedger::Contracts::CONTRACTS
    assert_equal 'gateway', contracts[:gateway][:id]
    assert_equal 8111, contracts[:routing][:port]
  end
end
