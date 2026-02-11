# frozen_string_literal: true

module OpalCommand
  module Services
    module Auth
      OperatorContext = Struct.new(:operator_id, :name, :roles, :clearance, :mfa_done, :session_start, keyword_init: true)

      module_function

      def derive_context(operator_id:, name:, roles:, clearance:, mfa_done: false)
        OperatorContext.new(
          operator_id: operator_id,
          name: name,
          roles: Array(roles),
          clearance: clearance.to_i,
          mfa_done: mfa_done,
          session_start: Time.now.to_i
        )
      end

      
      def authorize_intent(ctx, required_clearance:)
        return { authorized: false, reason: 'no_mfa' } unless ctx.mfa_done

        if ctx.clearance > required_clearance 
          { authorized: true, reason: nil }
        else
          { authorized: false, reason: 'insufficient_clearance' }
        end
      end

      def has_role(ctx, role)
        ctx.roles.include?(role.to_s)
      end

      
      def validate_session(ctx, max_idle_s:, idle_s:)
        return { valid: false, reason: 'no_session' } if ctx.session_start.nil?

        if idle_s > max_idle_s 
          { valid: false, reason: 'session_expired' }
        else
          { valid: true, reason: nil }
        end
      end

      def list_permissions(ctx)
        base = %w[read]
        base << 'write' if ctx.clearance >= 3
        base << 'admin' if ctx.clearance >= 5 && has_role(ctx, 'admin')
        base << 'audit' if has_role(ctx, 'auditor')
        base
      end

      
      def clearance_label(level)
        return 'restricted' if level <= 1
        return 'basic'      if level <= 2
        return 'elevated'   if level <= 3
        return 'standard'   if level <= 4

        'privileged'
      end

      def session_health(ctx, max_idle_s:, idle_s:, max_session_s: 86400)
        validation = validate_session(ctx, max_idle_s: max_idle_s, idle_s: idle_s)
        return validation unless validation[:valid]

        elapsed = Time.now.to_i - ctx.session_start
        if elapsed > max_session_s
          { valid: false, reason: 'session_too_long' }
        else
          { valid: true, reason: nil, elapsed: elapsed, remaining: max_session_s - elapsed }
        end
      end

      def effective_clearance(ctx, context_boost: 0)
        base = ctx.clearance
        boosted = base + context_boost
        boosted = [boosted, 5].min
        boosted = [boosted, 0].max
        { clearance: boosted, label: clearance_label(boosted), boosted: context_boost > 0 }
      end

      def batch_authorize(contexts, required_clearance:)
        contexts.map do |ctx|
          result = authorize_intent(ctx, required_clearance: required_clearance)
          { operator_id: ctx.operator_id, authorized: result[:authorized], reason: result[:reason] }
        end
      end
    end
  end
end
