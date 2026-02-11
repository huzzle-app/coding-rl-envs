# frozen_string_literal: true

module ShopStream
  # Dead Letter Queue processor
  
  class DLQProcessor
    DLQ_TOPIC = 'shopstream.dlq'
    MAX_RETRIES = 3

    class << self
      def send_to_dlq(message, error)
        dlq_message = {
          original_topic: message.topic,
          original_key: message.key,
          original_value: message.value,
          error: error.message,
          error_class: error.class.name,
          retry_count: 0,
          failed_at: Time.now.iso8601
        }

        KafkaProducer.publish(DLQ_TOPIC, dlq_message)
      end

      def start_processor
        
        # DLQ messages accumulate but are never retried
        # This method exists but is never called

        consumer = KafkaConsumer.new(
          topics: [DLQ_TOPIC],
          group_id: 'dlq-processor'
        )

        consumer.subscribe(DLQ_TOPIC) do |message|
          process_dlq_message(message)
        end

        consumer.start
      end

      private

      def process_dlq_message(message)
        retry_count = message['retry_count'] || 0

        if retry_count >= MAX_RETRIES
          
          # Should be stored for manual review
          Rails.logger.error("Message exceeded max retries: #{message}")
          return
        end

        # Attempt to reprocess
        original_topic = message['original_topic']
        original_value = message['original_value']

        begin
          # Re-publish to original topic
          KafkaProducer.publish(
            original_topic,
            JSON.parse(original_value),
            key: message['original_key']
          )
        rescue StandardError => e
          # Increment retry count and send back to DLQ
          message['retry_count'] = retry_count + 1
          message['last_error'] = e.message
          KafkaProducer.publish(DLQ_TOPIC, message)
        end
      end
    end

    # Correct implementation would:
    # 1. Start DLQ processor on application boot
    # 2. Store permanent failures in database for manual review
    # 3. Add monitoring/alerting on DLQ depth
    # 4. Implement circuit breaker for repeated failures
  end
end
