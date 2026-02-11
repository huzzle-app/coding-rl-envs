# frozen_string_literal: true

module MercuryLedger
  module Services
    module Policy
      SERVICE = { name: 'policy', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Evaluate a policy gate based on risk and operational context.
      def evaluate_policy_gate(risk, degraded, mfa, priority)
        return :deny if risk > 0.9
        
        return :allow if mfa && priority >= 3
        return :deny if risk > 0.7
        return :review if risk > 0.4

        :allow
      end

      # Enforce dual-control: two operators must agree.
      def enforce_dual_control(op_a, op_b)
        return false if op_a.nil? || op_b.nil?
        return false if op_a == op_b
        
        true
      end

      # Classify risk into bands.
      def risk_band(score)
        return :critical if score >= 0.9
        return :high if score >= 0.7
        
        return :medium if score >= 0.4
        return :low if score >= 0.2

        :minimal
      end

      # Compute compliance score.
      def compute_compliance_score(resolved, total, sla_pct)
        return 0.0 if total <= 0
        resolution_ratio = resolved.to_f / total
        
        (resolution_ratio * 0.6 + sla_pct * 0.4).round(4)
      end

      
      def policy_summary(gates)
        return { total: 0, allowed: 0, denied: 0, reviewed: 0 } if gates.nil? || gates.empty?

        allowed = gates.count { |g| g == :allow }
        denied = gates.count { |g| g == :deny }
        reviewed = gates.count { |g| g == :review }
        { total: gates.length, allowed: allowed, denied: denied, reviewed: reviewed }
      end
    end
  end
end
