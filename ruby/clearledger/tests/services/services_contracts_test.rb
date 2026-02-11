# frozen_string_literal: true

require_relative '../test_helper'

class ServicesContractsTest < Minitest::Test
  EXPECTED_SERVICES = %w[
    analytics audit auth gateway intake ledger notifications policy reconcile reporting risk settlement
  ].freeze

  def test_services_expose_contract_constants
    services_root = File.expand_path('../../services', __dir__)
    service_files = Dir[File.join(services_root, '*/service.rb')]

    assert_equal 12, service_files.length

    names = service_files.map { |p| File.basename(File.dirname(p)) }.sort
    assert_equal EXPECTED_SERVICES, names

    service_files.each do |path|
      content = File.read(path)
      assert_includes content, 'SERVICE_NAME'
      assert_includes content, 'API_VERSION'
    end
  end

  def test_shared_contract_has_required_fields
    assert_includes ClearLedger::Contracts::REQUIRED_FIELDS, 'trace_id'
    assert_includes ClearLedger::Contracts::EVENT_TYPES, 'settlement.completed'
  end

  def test_contract_event_types_are_unique
    uniq = ClearLedger::Contracts::EVENT_TYPES.uniq
    assert_equal uniq.length, ClearLedger::Contracts::EVENT_TYPES.length
  end
end
