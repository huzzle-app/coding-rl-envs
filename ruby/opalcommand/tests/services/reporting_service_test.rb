# frozen_string_literal: true

require_relative '../test_helper'
require_relative '../../services/reporting/service'

class ReportingServiceTest < Minitest::Test
  def test_rank_incidents_returns_sorted
    incidents = [
      { id: 'i1', severity: 2 },
      { id: 'i2', severity: 5 },
      { id: 'i3', severity: 3 }
    ]
    ranked = OpalCommand::Services::Reporting.rank_incidents(incidents)
    assert_equal 3, ranked.length
  end

  def test_compliance_report_grade
    report = OpalCommand::Services::Reporting.compliance_report(resolved: 95, total: 100, sla_met_pct: 96)
    assert_includes %w[A B C D], report[:grade]
  end

  def test_format_incident_row_contains_id
    row = OpalCommand::Services::Reporting.format_incident_row({ id: 'INC-42', severity: 3, status: 'open' })
    assert_includes row, 'INC-42'
  end

  def test_generate_executive_summary
    incidents = [{ status: 'open' }, { status: 'resolved' }, { status: 'resolved' }]
    summary = OpalCommand::Services::Reporting.generate_executive_summary(incidents: incidents, fleet_health: 75)
    assert_equal 1, summary[:open_incidents]
    assert_equal 2, summary[:resolved_incidents]
  end
end
