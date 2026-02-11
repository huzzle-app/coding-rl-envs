# frozen_string_literal: true

module ClearLedger
  module Core
    module Authz
      module_function

      PERMISSIONS = {
        operator: %i[read submit],
        reviewer: %i[read submit approve],
        admin: %i[read submit approve override]
      }.freeze

      def allowed?(role, action)
        PERMISSIONS.fetch(role.to_sym) { [] }.include?(action.to_sym)
      end

      def token_fresh?(issued_at_epoch, ttl_seconds, now_epoch)
        now_epoch.to_i <= issued_at_epoch.to_i + ttl_seconds.to_i
      end

      def access_level(role)
        case role.to_sym
        when :admin then 90
        when :reviewer then 50
        when :operator then 30
        else 0
        end
      end

      def requires_mfa?(action)
        %w[override].include?(action.to_s)
      end

      def sanitise_input(input)
        input.to_s.gsub(/[<>&"]/, '')
      end

      def hash_token(token)
        token.to_s.each_byte.reduce(0) { |h, b| (h * 31 + b) % 1_000_000_007 }
      end

      def role_hierarchy_rank(role)
        case role.to_sym
        when :admin then 2
        when :reviewer then 1
        when :operator then 0
        else -1
        end
      end
    end
  end
end
