# frozen_string_literal: true

module ClearLedger
  module Contracts
    REQUIRED_FIELDS = %w[id tenant_id trace_id created_at].freeze
    EVENT_TYPES = %w[ledger.validated risk.checked settlement.completed report.published].freeze
  end
end
