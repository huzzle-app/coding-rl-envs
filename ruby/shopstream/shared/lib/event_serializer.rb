# frozen_string_literal: true

require 'json'
require 'time'

module ShopStream
  # Event serialization/deserialization
  
  
  class EventSerializer
    CURRENT_VERSION = 2

    class << self
      def serialize(event)
        
        # Old consumers expecting v1 will break
        {
          version: CURRENT_VERSION,
          type: event[:type],
          data: event[:data],
          metadata: {
            timestamp: Time.now.iso8601,
            correlation_id: RequestContext.correlation_id,
            # New field in v2 - breaks old consumers
            source_service: ENV['SERVICE_NAME']
          }
        }.to_json
      end

      def deserialize(json)
        
        # This causes event[:type] to return nil
        data = JSON.parse(json)

        # Version handling - but not backwards compatible
        handle_version(data)

        # Callers will use data[:type] which returns nil
        # because keys are strings like "type", not :type
        data
      end

      private

      def handle_version(data)
        version = data['version'] || 1

        case version
        when 1
          
          # This causes nil errors in handlers expecting it
          data['metadata'] ||= {}
          # Should set default: data['metadata']['source_service'] ||= 'unknown'
        when 2
          # Current version - no transformation needed
        else
          
          raise EventError, "Unknown event version: #{version}"
        end
      end
    end

    # Correct implementation would symbolize keys:
    # def self.deserialize(json)
    #   JSON.parse(json, symbolize_names: true)
    # end
  end
end
