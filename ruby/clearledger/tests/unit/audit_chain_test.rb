# frozen_string_literal: true

require_relative '../test_helper'

class AuditChainTest < Minitest::Test
  def test_fingerprint_normalizes_values
    fp = ClearLedger::Core::AuditChain.fingerprint('Tenant-A', 'Trace-7', 'Dispatch.Accepted')
    assert_equal 'tenant-a:trace-7:dispatch.accepted', fp
  end

  def test_append_hash_is_deterministic
    a = ClearLedger::Core::AuditChain.append_hash(17, 'payload-one')
    b = ClearLedger::Core::AuditChain.append_hash(17, 'payload-one')
    c = ClearLedger::Core::AuditChain.append_hash(17, 'payload-two')

    assert_equal a, b
    refute_equal a, c
  end

  def test_ordered_sequence
    assert ClearLedger::Core::AuditChain.ordered?([1, 2, 3, 8])
    refute ClearLedger::Core::AuditChain.ordered?([1, 2, 2, 4])
  end
end
