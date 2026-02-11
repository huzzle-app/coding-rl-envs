# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::DLQProcessor do
  
  describe '.start_processor' do
    it 'exists and can be called to start DLQ processing' do
      expect(described_class).to respond_to(:start_processor)
    end

    it 'starts consuming from the DLQ topic' do
      consumer_double = double('consumer', subscribe: nil, start: nil)
      allow(ShopStream::KafkaConsumer).to receive(:new).and_return(consumer_double)

      expect(consumer_double).to receive(:subscribe).with('shopstream.dlq')
      described_class.start_processor rescue nil
    end
  end

  describe '.send_to_dlq' do
    it 'publishes failed message to DLQ topic with error details' do
      message = double('message', topic: 'orders', key: 'key-1', value: '{}')
      error = StandardError.new('processing failed')

      expect(ShopStream::KafkaProducer).to receive(:publish).with(
        'shopstream.dlq',
        hash_including(
          original_topic: 'orders',
          error: 'processing failed',
          error_class: 'StandardError'
        )
      )

      described_class.send_to_dlq(message, error)
    end

    it 'includes retry count starting at zero' do
      message = double('message', topic: 'orders', key: nil, value: '{}')
      error = StandardError.new('fail')

      expect(ShopStream::KafkaProducer).to receive(:publish).with(
        'shopstream.dlq',
        hash_including(retry_count: 0)
      )

      described_class.send_to_dlq(message, error)
    end
  end
end
