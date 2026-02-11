# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/ledger/service'

class LedgerServiceTest < Minitest::Test
  def test_audit_ledger_append_and_size
    ledger = OpalCommand::Services::Ledger::AuditLedger.new
    evt = OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: 'op1')
    ledger.append(evt)
    assert_equal 1, ledger.size
  end

  def test_validate_audit_event_requires_operator
    evt = OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: nil)
    refute OpalCommand::Services::Ledger.validate_audit_event(evt)
  end

  def test_summarize_ledger
    ledger = OpalCommand::Services::Ledger::AuditLedger.new
    ledger.append(OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: 'op1'))
    ledger.append(OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e2', service: 'auth', action: 'update', timestamp: 1001, operator_id: 'op2'))
    summary = OpalCommand::Services::Ledger.summarize_ledger(ledger)
    assert_equal 2, summary[:total_events]
    assert_equal 2, summary[:unique_services]
  end

  def test_is_compliant_audit_trail
    ledger = OpalCommand::Services::Ledger::AuditLedger.new
    ledger.append(OpalCommand::Services::Ledger::AuditEvent.new(event_id: 'e1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: 'op1'))
    result = OpalCommand::Services::Ledger.is_compliant_audit_trail(ledger, required_services: %w[gateway auth])
    refute result[:compliant]
    assert_includes result[:missing], 'auth'
  end
end
