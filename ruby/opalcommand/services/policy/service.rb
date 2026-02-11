# frozen_string_literal: true

module OpalCommand
  module Services
    module Policy
      PolicyDecision = Struct.new(:action, :approved, :reason, :risk_level, keyword_init: true)

      module_function

      
      def evaluate_policy_gate(risk_score:, comms_degraded:, has_mfa:, priority: :normal)
        return PolicyDecision.new(action: 'deny', approved: false, reason: 'no_mfa', risk_level: 'high') unless has_mfa
        
        effective_risk = risk_score

        if effective_risk > 80
          PolicyDecision.new(action: 'deny', approved: false, reason: 'risk_too_high', risk_level: 'critical')
        elsif effective_risk > 50
          PolicyDecision.new(action: 'review', approved: false, reason: 'elevated_risk', risk_level: 'high')
        else
          PolicyDecision.new(action: 'allow', approved: true, reason: nil, risk_level: 'normal')
        end
      end

      
      def enforce_dual_control(op_a, op_b, action)
        if op_a == op_b 
          { enforced: false, reason: 'same_operator' }
        else
          { enforced: true, action: action, operators: [op_a, op_b] }
        end
      end

      def risk_band(score)
        return 'critical' if score >= 90
        return 'high'     if score >= 70
        return 'medium'   if score >= 40
        return 'low'      if score >= 10

        'minimal'
      end

      
      def compute_compliance_score(incidents_resolved:, incidents_total:, sla_met_pct:)
        return 0.0 if incidents_total <= 0

        resolution_rate = incidents_resolved.to_f / incidents_total
        (resolution_rate * 0.7 + sla_met_pct / 100.0 * 0.3).round(4) 
      end

      
      def escalation_required?(risk_score, priority)
        threshold = case priority
                    when :critical then 50
                    when :high     then 65
                    else 75
                    end
        risk_score > threshold 
      end
    end
  end
end
