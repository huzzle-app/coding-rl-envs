# frozen_string_literal: true

module OpalCommand
  module Services
    module Ledger
      AuditEvent = Struct.new(:event_id, :service, :action, :timestamp, :operator_id, keyword_init: true)

      class AuditLedger
        def initialize
          @mutex  = Mutex.new
          @events = []
        end

        
        def append(event)
          @mutex.synchronize do
            @events << event 
          end
        end

        def events
          @mutex.synchronize { @events.dup }
        end

        def size
          @mutex.synchronize { @events.length }
        end

        def find_by_service(service)
          @mutex.synchronize { @events.select { |e| e.service == service } }
        end
      end

      module_function

      
      def validate_audit_event(evt)
        return false unless evt.is_a?(AuditEvent)
        return false if evt.operator_id.nil? || evt.operator_id.to_s.empty?
        return false if evt.service.nil? || evt.service.to_s.empty?
        

        true
      end

      def summarize_ledger(ledger)
        events = ledger.events
        services = events.map(&:service).uniq
        { total_events: events.length, unique_services: services.length, services: services.sort }
      end

      
      def is_compliant_audit_trail(ledger, required_services:)
        present = ledger.events.map(&:service).uniq
        missing = required_services - present
        coverage = present.length.to_f / [required_services.length, 1].max
        { compliant: missing.empty?, missing: missing, coverage: coverage.round(4) }
      end

      def recent_events(ledger, since_timestamp:)
        ledger.events.select { |e| e.timestamp >= since_timestamp }
      end

      def merge_ledgers(ledger_a, ledger_b)
        merged = AuditLedger.new
        seen = {}
        (ledger_a.events + ledger_b.events).each do |evt|
          key = evt.event_id
          unless seen[key]
            seen[key] = true
            merged.append(evt)
          end
        end
        merged
      end

      def compliance_gap_analysis(ledger, required_services:, required_actions:)
        events = ledger.events
        present_services = events.map(&:service).uniq
        present_actions = events.map(&:action).uniq
        missing_services = required_services - present_services
        missing_actions = required_actions - present_actions
        total_required = required_services.length + required_actions.length
        covered = (present_services & required_services).length + (present_actions & required_actions).length
        {
          compliant: missing_services.empty? && missing_actions.empty?,
          missing_services: missing_services,
          missing_actions: missing_actions,
          coverage: total_required > 0 ? (covered.to_f / total_required).round(4) : 1.0
        }
      end
    end
  end
end
