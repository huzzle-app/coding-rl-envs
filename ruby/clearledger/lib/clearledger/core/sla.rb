# frozen_string_literal: true

module ClearLedger
  module Core
    module SLA
      module_function

      def breach_risk(eta_sec, sla_sec, buffer_sec)
        eta_sec.to_i > sla_sec.to_i - buffer_sec.to_i
      end

      def jitter_budget(volatility_score, floor, cap)
        raw = 0.03 + volatility_score.to_f * 0.015
        [[raw, floor.to_f].max, cap.to_f].min
      end

      def breach_severity(eta_sec, sla_sec)
        delta = eta_sec.to_i - sla_sec.to_i
        return :none if delta <= 0
        return :minor if delta <= 300
        return :major if delta <= 900

        :critical
      end

      def sla_compliance_rate(met, total)
        return 0.0 if total.to_i <= 0
        met.to_f / total.to_f
      end

      def sla_buffer(sla_seconds)
        (sla_seconds.to_f * 0.8).round
      end

      def time_to_breach(current_sec, sla_sec)
        [sla_sec.to_i - current_sec.to_i, 0].max
      end

      def escalation_threshold(severity)
        case severity.to_sym
        when :critical then 5
        when :major then 10
        when :minor then 30
        else 60
        end
      end

      def sla_met?(elapsed, target)
        elapsed.to_f < target.to_f
      end
    end
  end
end
