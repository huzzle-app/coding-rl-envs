# frozen_string_literal: true

module ShopStream
  # Event processor for handling incoming events
  
  class EventProcessor
    def initialize
      @handlers = {}
      @processed_events = Set.new
      
      # Concurrent processing can cause duplicates
    end

    def register(event_type, &handler)
      @handlers[event_type] = handler
    end

    def process(event)
      
      event_id = event['metadata']&.dig('event_id') || generate_event_id(event)
      event_type = event['type']

      
      # Thread 1: checks @processed_events.include?(event_id) -> false
      # Thread 2: checks @processed_events.include?(event_id) -> false
      # Both threads proceed to process the same event
      return if @processed_events.include?(event_id)

      handler = @handlers[event_type]
      return unless handler

      begin
        handler.call(event)
        @processed_events.add(event_id)
      rescue StandardError => e
        Rails.logger.error("Error processing event #{event_type}: #{e.message}")
        raise
      end
    end

    private

    def generate_event_id(event)
      # Fallback event ID generation
      Digest::SHA256.hexdigest("#{event['type']}-#{event['data']}-#{event['metadata']}")
    end

    # Correct implementation would use mutex or Redis for deduplication:
    # def process(event)
    #   event_id = event['metadata']&.dig('event_id')
    #
    #   @mutex.synchronize do
    #     return if @processed_events.include?(event_id)
    #     @processed_events.add(event_id)
    #   end
    #
    #   # Or use Redis SETNX for distributed deduplication:
    #   # return unless Redis.current.setnx("event:#{event_id}", 1)
    #   # Redis.current.expire("event:#{event_id}", 86400)
    #
    #   handler.call(event)
    # end
  end
end
