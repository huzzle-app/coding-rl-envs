# frozen_string_literal: true

require_relative '../test_helper'

class MigrationsTest < Minitest::Test
  def test_core_migration_contains_table
    sql = File.read(File.expand_path('../../migrations/001_core.sql', __dir__))
    assert_includes sql, 'CREATE TABLE IF NOT EXISTS settlement_orders'
  end
end
