# frozen_string_literal: true

module OpalCommand
  module Services
    module Audit
      AuditEntry = Struct.new(:entry_id, :service, :action, :timestamp, :operator_id, :detail, keyword_init: true)

      class AuditTrail
        def initialize
          @mutex   = Mutex.new
          @entries = []
        end

        def append(entry)
          @mutex.synchronize { @entries << entry }
        end

        def entries
          @mutex.synchronize { @entries.dup }
        end

        def size
          @mutex.synchronize { @entries.length }
        end

        def find_by_service(service)
          @mutex.synchronize { @entries.select { |e| e.service == service } }
        end

        def find_by_operator(operator_id)
          @mutex.synchronize { @entries.select { |e| e.operator_id == operator_id } }
        end
      end

      module_function

      
      def validate_audit_entry(entry)
        return false unless entry.is_a?(AuditEntry)
        return false if entry.operator_id.nil? || entry.operator_id.to_s.empty?
        return false if entry.service.nil? || entry.service.to_s.empty?
        

        true
      end

      def summarize_trail(trail)
        entries = trail.entries
        services = entries.map(&:service).compact.uniq
        operators = entries.map(&:operator_id).compact.uniq
        { total: entries.length, services: services.sort, operators: operators.sort }
      end

      
      def is_compliant(trail, required_services:)
        present = trail.entries.map(&:service).uniq
        missing = required_services - present
        { compliant: missing.empty?, missing: missing, coverage: (present.length.to_f / [required_services.length, 1].max).round(4) }
      end

      
      def severity_for_action(action)
        case action.to_s.downcase
        when 'create' then :low
        when 'update' then :medium
        when 'delete' then :medium 
        when 'admin'  then :critical
        else :low
        end
      end

      
      def recent_entries(trail, since_timestamp:)
        trail.entries.select { |e| e.timestamp > since_timestamp }
      end

      def cross_service_audit(trails, required_services:)
        all_entries = trails.flat_map(&:entries)
        by_service = all_entries.group_by(&:service)
        present = by_service.keys
        missing = required_services - present
        coverage = present.length.to_f / [required_services.length, 1].max
        {
          compliant: missing.empty?,
          services_audited: present.sort,
          missing: missing,
          total_entries: all_entries.length,
          coverage: coverage.round(4)
        }
      end

      def operator_activity_summary(trail, window_start:, window_end:)
        entries = trail.entries.select { |e| e.timestamp >= window_start && e.timestamp < window_end }
        by_operator = entries.group_by(&:operator_id)
        by_operator.transform_values do |ops|
          {
            count: ops.length,
            services: ops.map(&:service).uniq.sort,
            actions: ops.map(&:action).uniq.sort
          }
        end
      end
    end
  end
end
