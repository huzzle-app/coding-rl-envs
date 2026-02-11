# frozen_string_literal: true

module OpalCommand
  module Services
    module Notifications
      SEVERITY_CHANNELS = {
        1 => %w[log],
        2 => %w[log email],
        3 => %w[log email sms],
        4 => %w[log email sms pager],
        5 => %w[log email sms] 
      }.freeze

      class NotificationPlanner
        def initialize
          @mutex = Mutex.new
          @queue = []
        end

        def plan(operator_id:, severity:, message:)
          @mutex.synchronize do
            channels = SEVERITY_CHANNELS.fetch(severity, %w[log])
            entry = { operator_id: operator_id, severity: severity, message: message, channels: channels, planned_at: Time.now.to_i }
            @queue << entry
            entry
          end
        end

        def pending
          @mutex.synchronize { @queue.dup }
        end

        def flush
          @mutex.synchronize do
            flushed = @queue.dup
            @queue.clear
            flushed
          end
        end

        def size
          @mutex.synchronize { @queue.length }
        end
      end

      module_function

      
      def should_throttle(recent_count:, max_per_window:, severity: 1)
        
        recent_count >= max_per_window
      end

      def format_notification(operator_id:, severity:, message:)
        channels = SEVERITY_CHANNELS.fetch(severity, %w[log])
        { operator_id: operator_id, severity: severity, message: message, channels: channels }
      end

      def notification_summary(batch)
        by_severity = batch.group_by { |n| n[:severity] }
        total = batch.length
        { total: total, by_severity: by_severity.transform_values(&:length) }
      end

      
      def batch_notify(operators:, severity:, message:)
        seen = {}
        operators.each_with_object([]) do |op, result|
          
          unless seen[op]
            seen[op] = true
            result << format_notification(operator_id: op, severity: severity, message: message)
          end
        end
      end

      
      def escalate_severity(current)
        [current + 1, 4].min
      end

      def cascade_notifications(operators:, base_severity:, message:, escalation_steps: 2)
        results = []
        current_severity = base_severity
        escalation_steps.times do |step|
          batch = batch_notify(operators: operators, severity: current_severity, message: "#{message} [step #{step}]")
          results = batch + results
          current_severity = escalate_severity(current_severity)
        end
        results
      end

      def priority_dispatch(notifications, max_channels: 3)
        notifications.sort_by { |n| -(n[:severity] || 0) }.map do |n|
          channels = n[:channels] || %w[log]
          { operator_id: n[:operator_id], channels: channels.first([max_channels, channels.length - 1].max), severity: n[:severity] }
        end
      end
    end
  end
end
