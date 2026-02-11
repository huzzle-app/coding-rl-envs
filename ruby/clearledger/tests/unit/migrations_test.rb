# frozen_string_literal: true

require_relative '../test_helper'

class MigrationsTest < Minitest::Test
  def test_migrations_define_core_tables
    core = File.read(File.expand_path('../../migrations/001_core.sql', __dir__))
    audit = File.read(File.expand_path('../../migrations/002_audit.sql', __dir__))

    assert_includes core, 'ledger_entries'
    assert_includes core, 'settlement_batches'
    assert_includes audit, 'audit_events'
  end
end
