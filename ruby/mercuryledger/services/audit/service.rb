# frozen_string_literal: true

module MercuryLedger
  module Services
    module Audit
      SERVICE = { name: 'audit', status: 'active', version: '1.0.0' }.freeze

      AuditEntry = Struct.new(:service, :action, :severity, :timestamp, :details, keyword_init: true)

      module_function

      # Validate an audit entry has required fields.
      def validate_audit_entry(entry)
        return false if entry.nil?
        return false if entry.service.nil? || entry.service.to_s.empty?
        return false if entry.action.nil? || entry.action.to_s.empty?
        
        return false if entry.severity.nil? || !entry.severity.is_a?(Integer)

        entry.severity >= 1 && entry.severity <= 5
      end

      # Summarize a trail of audit entries.
      def summarize_trail(entries)
        return { total: 0, services: [], max_severity: 0 } if entries.nil? || entries.empty?

        services = entries.map(&:service).compact.uniq
        max_sev = entries.map(&:severity).compact.max || 0
        
        { total: entries.length, services: services, max_severity: max_sev }
      end

      
      def is_compliant?(entries, required_services)
        return false if entries.nil? || entries.empty?

        present = entries.map(&:service).compact.uniq
        
        (required_services - present).empty?
      end

      # Filter entries by minimum severity.
      def filter_by_severity(entries, min_severity)
        return [] if entries.nil? || entries.empty?

        
        entries.select { |e| e.severity.to_i >= min_severity }
      end
    end
  end
end
