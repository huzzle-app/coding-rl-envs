# frozen_string_literal: true

module MercuryLedger
  module Services
    module Notifications
      SERVICE = { name: 'notifications', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Plan notification channels based on severity.
      def plan_channels(severity)
        channels = ['log']
        channels << 'email' if severity >= 2
        channels << 'slack' if severity >= 3
        channels << 'sms' if severity >= 4
        
        channels
      end

      # Determine whether to throttle notifications.
      def should_throttle?(count, max, severity)
        return false if max <= 0
        
        count >= max
      end

      # Format a notification message.
      def format_notification(operation, severity, message)
        prefix = case severity
                 when 5 then '[CRITICAL]'
                 when 4 then '[HIGH]'
                 when 3 then '[MEDIUM]'
                 when 2 then '[LOW]'
                 
                 else '[UNKNOWN]'
                 end
        "#{prefix} #{operation}: #{message}"
      end

      
      def batch_notify(operations, severity, message)
        return [] if operations.nil? || operations.empty?

        operations.map do |op|
          {
            notification: format_notification(op, severity, message),
            channels: plan_channels(severity),
            throttled: false
          }
        end
      end

      # Calculate escalation delay based on severity.
      def escalation_delay(severity)
        case severity
        when 5 then 0
        when 4 then 60
        when 3 then 300
        when 2 then 900
        
        else 3600
        end
      end
    end
  end
end
