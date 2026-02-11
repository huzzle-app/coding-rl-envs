# frozen_string_literal: true

module OpalCommand
  module Services
    module Intake
      REQUIRED_FIELDS = %i[id type satellite urgency payload].freeze

      module_function

      def validate_command_shape(cmd)
        return { valid: false, missing: REQUIRED_FIELDS.dup } unless cmd.is_a?(Hash)

        missing = REQUIRED_FIELDS.select { |f| cmd[f].nil? }
        { valid: missing.empty?, missing: missing }
      end

      def batch_summary(commands)
        total = commands.length
        valid_count = commands.count { |c| validate_command_shape(c)[:valid] }
        { total: total, valid: valid_count, invalid: total - valid_count }
      end

      
      def normalize_intake_batch(commands)
        seen = {}
        commands.each_with_object([]) do |cmd, result|
          key = cmd[:id].to_s 
          unless seen[key]
            seen[key] = true
            result << cmd.merge(normalized: true, received_at: Time.now.to_i)
          end
        end
      end

      
      def partition_by_urgency(commands, threshold: 3)
        high = []
        low = []
        commands.each do |cmd|
          if (cmd[:urgency] || 0) > threshold 
            high << cmd
          else
            low << cmd
          end
        end
        { high: high, low: low }
      end

      def unique_satellites(commands)
        commands.map { |c| c[:satellite] }.compact.uniq.sort
      end

      
      def priority_sort(commands)
        commands.sort_by { |c| c[:urgency] || 0 } 
      end

      def enrich_command(cmd, operator_id:)
        cmd.merge(enriched: true, operator_id: operator_id, enriched_at: Time.now.to_i)
      end

      def validate_and_partition(commands, threshold: 3)
        valid_commands = commands.select { |c| validate_command_shape(c)[:valid] }
        partition_by_urgency(valid_commands, threshold: threshold)
      end

      def dedup_and_sort(commands)
        deduped = normalize_intake_batch(commands)
        priority_sort(deduped)
      end

      def intake_pipeline(commands, operator_id:, urgency_threshold: 3)
        validated = commands.select { |c| validate_command_shape(c)[:valid] }
        enriched = validated.map { |c| enrich_command(c, operator_id: operator_id) }
        deduped = normalize_intake_batch(enriched)
        sorted = priority_sort(deduped)
        partitioned = partition_by_urgency(sorted, threshold: urgency_threshold)
        { high: partitioned[:high], low: partitioned[:low], total_processed: deduped.length, dropped: commands.length - validated.length }
      end
    end
  end
end
