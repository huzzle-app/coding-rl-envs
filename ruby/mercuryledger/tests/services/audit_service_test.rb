# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/audit/service'

class AuditServiceTest < Minitest::Test
  def test_validate_audit_entry_accepts_valid
    entry = MercuryLedger::Services::Audit::AuditEntry.new(
      service: 'gateway', action: 'deploy', severity: 3, timestamp: Time.now.to_i, details: 'ok'
    )
    assert MercuryLedger::Services::Audit.validate_audit_entry(entry)
  end

  def test_summarize_trail_counts_entries
    entries = [
      MercuryLedger::Services::Audit::AuditEntry.new(service: 'gw', action: 'a', severity: 2, timestamp: 1),
      MercuryLedger::Services::Audit::AuditEntry.new(service: 'rt', action: 'b', severity: 4, timestamp: 2)
    ]
    summary = MercuryLedger::Services::Audit.summarize_trail(entries)
    assert_equal 2, summary[:total]
    assert_equal 4, summary[:max_severity]
  end

  def test_is_compliant_checks_all_services
    entries = [
      MercuryLedger::Services::Audit::AuditEntry.new(service: 'gw', action: 'a', severity: 1, timestamp: 1)
    ]
    assert MercuryLedger::Services::Audit.is_compliant?(entries, ['gw'])
    refute MercuryLedger::Services::Audit.is_compliant?(entries, ['gw', 'rt'])
  end

  def test_filter_by_severity_applies_threshold
    entries = [
      MercuryLedger::Services::Audit::AuditEntry.new(service: 'a', action: 'x', severity: 2, timestamp: 1),
      MercuryLedger::Services::Audit::AuditEntry.new(service: 'b', action: 'y', severity: 4, timestamp: 2)
    ]
    filtered = MercuryLedger::Services::Audit.filter_by_severity(entries, 3)
    assert_equal 1, filtered.length
  end
end
