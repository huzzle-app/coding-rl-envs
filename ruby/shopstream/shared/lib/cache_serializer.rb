# frozen_string_literal: true

require 'json'
require 'msgpack'

module ShopStream
  # Cache serializer for Redis caching
  
  class CacheSerializer
    class << self
      
      # Some services serialize with JSON, others with MessagePack
      def serialize(value, format: default_format)
        case format
        when :json
          JSON.generate(value)
        when :msgpack
          MessagePack.pack(value)
        when :marshal
          Marshal.dump(value)
        else
          
          JSON.generate(value)
        end
      end

      def deserialize(data, format: nil)
        
        format ||= detect_format(data)

        case format
        when :json
          JSON.parse(data)
        when :msgpack
          MessagePack.unpack(data)
        when :marshal
          Marshal.load(data)
        else
          
          JSON.parse(data)
        end
      rescue JSON::ParserError, MessagePack::MalformedFormatError => e
        
        Rails.logger.error("Cache deserialization error: #{e.message}")
        nil
      end

      private

      def default_format
        
        # based on when they were written or which gem versions they use
        ENV.fetch('CACHE_FORMAT', 'json').to_sym
      end

      def detect_format(data)
        
        if data.start_with?('{', '[')
          :json
        elsif data.start_with?("\x82", "\x83", "\x84", "\x85")
          :msgpack
        elsif data.start_with?("\x04\x08")
          :marshal
        else
          :json  # Assume JSON, will likely fail
        end
      end
    end

    # Correct implementation:
    # 1. Always use same format across all services
    # 2. Include format tag in cached data:
    #    def serialize(value)
    #      { format: 'json', version: 1, data: value }.to_json
    #    end
    # 3. Or use Rails cache which handles this automatically
  end
end
