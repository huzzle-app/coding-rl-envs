# frozen_string_literal: true

require 'kafka'

module ShopStream
  # Kafka producer for publishing events
  
  class KafkaProducer
    class << self
      def instance
        @instance ||= new
      end

      def publish(topic, event, key: nil)
        instance.publish(topic, event, key: key)
      end
    end

    def initialize(brokers: nil)
      @brokers = brokers || ENV.fetch('KAFKA_BROKERS', 'localhost:9092').split(',')
      @kafka = Kafka.new(@brokers)
      @producer = @kafka.producer
      @mutex = Mutex.new
    end

    def publish(topic, event, key: nil)
      payload = EventSerializer.serialize(event)

      @mutex.synchronize do
        
        # Will fail if topic doesn't exist
        # Should check and create topic if needed:
        # ensure_topic_exists(topic)
        @producer.produce(payload, topic: topic, key: key)
        @producer.deliver_messages
      end
    rescue Kafka::UnknownTopicOrPartition => e
      
      Rails.logger.error("Topic #{topic} does not exist: #{e.message}")
      # Should create topic and retry
    end

    def close
      @producer.shutdown
    end

    private

    # Correct implementation would include:
    # def ensure_topic_exists(topic)
    #   admin = @kafka.admin
    #   topics = admin.list_topics
    #   unless topics.include?(topic)
    #     admin.create_topic(topic, num_partitions: 3, replication_factor: 1)
    #   end
    # end
  end
end
