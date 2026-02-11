# frozen_string_literal: true

module OpalCommand
  module Services
    module Reporting
      module_function

      
      def rank_incidents(incidents)
        incidents.sort_by { |i| i[:severity] || 0 } 
      end

      
      def compliance_report(resolved:, total:, sla_met_pct:)
        resolution_rate = total > 0 ? (resolved.to_f / total * 100.0).round(2) : 0.0
        grade = if resolution_rate >= 95 && sla_met_pct >= 95
                  'A'
                elsif resolution_rate >= 80 && sla_met_pct >= 80
                  'B'
                elsif resolution_rate >= 60
                  'C' 
                else
                  'D'
                end
        { resolution_rate: resolution_rate, sla_met_pct: sla_met_pct, grade: grade }
      end

      def format_incident_row(incident)
        id = incident[:id] || 'unknown'
        sev = incident[:severity] || 0
        status = incident[:status] || 'open'
        "#{id} | severity=#{sev} | status=#{status}"
      end

      
      def generate_executive_summary(incidents:, fleet_health:)
        open_count = incidents.count { |i| i[:status] == 'open' }
        resolved_count = incidents.count { |i| i[:status] == 'resolved' }
        fleet_status = if fleet_health >= 80
                         'excellent' 
                       elsif fleet_health >= 50
                         'fair'
                       else
                         'poor'
                       end
        { open_incidents: open_count, resolved_incidents: resolved_count, fleet_status: fleet_status, fleet_health: fleet_health }
      end

      def operation_report(operation_id:, steps_executed:, budget_remaining:, incidents:)
        incident_count = incidents.length
        status = budget_remaining > 0 && incident_count.zero? ? 'nominal' : 'attention_required'
        { operation_id: operation_id, steps_executed: steps_executed, budget_remaining: budget_remaining.round(2),
          incident_count: incident_count, status: status }
      end

      
      def severity_distribution(incidents)
        return {} if incidents.empty?

        grouped = incidents.group_by { |i| i[:severity] || 0 }
        grouped.transform_values { |v| v.length.to_f / incidents.length }
      end

      def trend_report(incidents, window: 5)
        return [] if incidents.length < window

        incidents.each_cons(window).map do |batch|
          open_count = batch.count { |i| i[:status] == 'open' }
          resolved_count = batch.count { |i| i[:status] == 'resolved' }
          { open_rate: (open_count.to_f / batch.length).round(4),
            resolved_rate: (resolved_count.to_f / batch.length).round(4),
            trend: open_count > resolved_count ? :worsening : :improving }
        end
      end

      def cross_service_report(incidents:, fleet_health:, compliance_score:)
        exec_summary = generate_executive_summary(incidents: incidents, fleet_health: fleet_health)
        risk_level = if compliance_score >= 0.9 && fleet_health >= 80
                       'low'
                     elsif compliance_score >= 0.7
                       'medium'
                     else
                       'high'
                     end
        exec_summary.merge(risk_level: risk_level, compliance_score: compliance_score)
      end
    end
  end
end
