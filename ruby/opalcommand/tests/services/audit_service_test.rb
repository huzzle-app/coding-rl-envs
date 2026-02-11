# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/audit/service'

class AuditServiceTest < Minitest::Test
  def test_audit_trail_append_and_size
    trail = OpalCommand::Services::Audit::AuditTrail.new
    entry = OpalCommand::Services::Audit::AuditEntry.new(entry_id: 'a1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: 'op1', detail: 'test')
    trail.append(entry)
    assert_equal 1, trail.size
  end

  def test_validate_audit_entry_requires_operator
    entry = OpalCommand::Services::Audit::AuditEntry.new(entry_id: 'a1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: nil, detail: 'test')
    refute OpalCommand::Services::Audit.validate_audit_entry(entry)
  end

  def test_summarize_trail
    trail = OpalCommand::Services::Audit::AuditTrail.new
    trail.append(OpalCommand::Services::Audit::AuditEntry.new(entry_id: 'a1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: 'op1', detail: 'x'))
    trail.append(OpalCommand::Services::Audit::AuditEntry.new(entry_id: 'a2', service: 'auth', action: 'update', timestamp: 1001, operator_id: 'op2', detail: 'y'))
    summary = OpalCommand::Services::Audit.summarize_trail(trail)
    assert_equal 2, summary[:total]
    assert_includes summary[:services], 'auth'
  end

  def test_is_compliant_checks_services
    trail = OpalCommand::Services::Audit::AuditTrail.new
    trail.append(OpalCommand::Services::Audit::AuditEntry.new(entry_id: 'a1', service: 'gateway', action: 'create', timestamp: 1000, operator_id: 'op1', detail: 'x'))
    result = OpalCommand::Services::Audit.is_compliant(trail, required_services: %w[gateway auth])
    refute result[:compliant]
  end
end
