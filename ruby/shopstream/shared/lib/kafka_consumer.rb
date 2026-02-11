# frozen_string_literal: true

require 'kafka'

module ShopStream
  # Kafka consumer for event-driven communication
  
  
  class KafkaConsumer
    attr_reader :topics, :group_id

    def initialize(topics:, group_id:, brokers: nil)
      @topics = Array(topics)
      @group_id = group_id
      @brokers = brokers || ENV.fetch('KAFKA_BROKERS', 'localhost:9092').split(',')
      @handlers = {}
      @running = false

      
      # Should have exponential backoff for connection failures
      @kafka = Kafka.new(@brokers)
      @consumer = @kafka.consumer(group_id: @group_id)
    end

    def subscribe(topic, &handler)
      @handlers[topic] = handler
      @consumer.subscribe(topic)
    end

    def start
      @running = true

      @consumer.each_message do |message|
        break unless @running

        topic = message.topic
        handler = @handlers[topic]

        if handler
          
          # If processing fails, message is lost
          @consumer.commit_offsets

          begin
            payload = EventSerializer.deserialize(message.value)
            handler.call(payload)
          rescue StandardError => e
            # Silent failure - should send to DLQ
            Rails.logger.error("Error processing message: #{e.message}")
          end
        end
      end
    end

    def stop
      @running = false
      @consumer.stop
    end

    # Correct implementation would be:
    # def start
    #   @running = true
    #   @consumer.each_message do |message|
    #     break unless @running
    #     begin
    #       payload = EventSerializer.deserialize(message.value)
    #       @handlers[message.topic]&.call(payload)
    #       @consumer.commit_offsets  # Commit AFTER processing
    #     rescue StandardError => e
    #       DLQProcessor.send_to_dlq(message, e)
    #     end
    #   end
    # end
  end
end
