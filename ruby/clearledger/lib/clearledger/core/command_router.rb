# frozen_string_literal: true

module ClearLedger
  module Core
    module CommandRouter
      module_function

      def route_command(action, region)
        key = [action.to_s.downcase, region.to_s.downcase]
        case key
        when ['settle', 'eu'] then 'settlement-eu'
        when ['settle', 'us'] then 'settlement-us'
        when ['reconcile', 'eu'], ['reconcile', 'us'] then 'reconcile-core'
        else 'control-plane'
        end
      end

      def requires_override?(action, amount_cents, override_floor_cents)
        action.to_s == 'settle' && amount_cents.to_i > override_floor_cents.to_i
      end

      def guard_action(role, action)
        ClearLedger::Core::Authz.allowed?(role, action)
      end

      def guard_action?(role, action)
        guard_action(role, action)
      end

      def command_priority(action)
        case action.to_s
        when 'reconcile' then 2
        when 'report' then 1
        else 0
        end
      end

      def region_routing_key(tenant_id, region)
        "#{tenant_id.to_s.downcase}:#{region.to_s.downcase}"
      end

      def batch_route(commands)
        commands.map { |c| route_command(c[:action], c[:region]) }
      end

      def requires_audit?(action)
        %w[settle].include?(action.to_s)
      end

      def route_with_risk_and_compliance(action, region, amount_cents, role, override_floor)
        destination = route_command(action, region)
        needs_override = requires_override?(action, amount_cents, override_floor)
        authorized = guard_action?(role, action == 'settle' ? :submit : action.to_sym)

        if needs_override
          override_authorized = guard_action?(role, :submit)
          return { destination: destination, status: :blocked, reason: 'override_not_authorized' } unless override_authorized
        end

        return { destination: destination, status: :blocked, reason: 'unauthorized' } unless authorized
        { destination: destination, status: :routed }
      end
    end
  end
end
