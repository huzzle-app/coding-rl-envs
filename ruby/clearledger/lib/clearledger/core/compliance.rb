# frozen_string_literal: true

module ClearLedger
  module Core
    module Compliance
      module_function

      def override_allowed?(reason, approvals, ttl_minutes)
        reason.to_s.strip.length >= 12 && approvals.to_i >= 2 && ttl_minutes.to_i <= 120
      end

      def retention_bucket(days)
        case days.to_i
        when 0..30 then :hot
        when 31..365 then :warm
        else :cold
        end
      end

      def policy_version_supported?(version)
        version.to_i >= 3
      end

      def audit_required?(action)
        %w[settle override].include?(action.to_s)
      end

      def compliance_score(passed, total)
        return 0.0 if total.to_i <= 0
        passed.to_f / total.to_f
      end

      def max_retention_days(bucket)
        case bucket.to_sym
        when :hot then 30
        when :warm then 365
        when :cold then 3650
        else 30
        end
      end

      def escalation_needed?(severity, failures)
        severity.to_i >= 4 || failures.to_i >= 3
      end

      def policy_compatible?(v1, v2)
        v1.to_i <= v2.to_i
      end

      def cascading_approval(approvers, required_level)
        levels = approvers.select { |a| a[:approved] }
                          .map { |a| ClearLedger::Core::Authz.role_hierarchy_rank(a[:role]) }
                          .sort
        levels.any? { |l| l >= required_level }
      end

      def multi_jurisdiction_check(rules_by_jurisdiction, entry)
        results = {}
        rules_by_jurisdiction.each do |jurisdiction, rules|
          passed = rules.all? { |rule| rule.call(entry) }
          results[jurisdiction] = passed
        end
        results.values.any?
      end

      # Validates a temporal approval chain: approvals must form a strictly
      # ascending sequence of levels (0 -> 1 -> 2 -> ... -> required_level),
      # with each approval's timestamp later than the previous one.
      # All levels from 0 to required_level must be present and approved.
      def temporal_approval_chain(approvals, required_level)
        approved = approvals.select { |a| a[:approved] }
                            .map { |a|
                              {
                                level: ClearLedger::Core::Authz.role_hierarchy_rank(a[:role]),
                                ts: a[:ts].to_i
                              }
                            }
                            .sort_by { |a| a[:ts] }

        return false if approved.empty?

        present_levels = approved.map { |a| a[:level] }.uniq
        return false unless present_levels.max >= required_level

        prev_level = -1
        approved.each do |a|
          return false unless a[:level] >= prev_level
          prev_level = a[:level]
        end

        true
      end
    end
  end
end
