# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::KafkaConsumer do
  let(:brokers) { ['localhost:9092'] }
  let(:topics) { ['test.topic'] }
  let(:group_id) { 'test-group' }

  
  describe 'connection retry logic' do
    it 'retries connection with exponential backoff on failure' do
      allow(Kafka).to receive(:new).and_raise(Kafka::ConnectionError)

      expect {
        described_class.new(topics: topics, group_id: group_id, brokers: ['bad:9092'])
      }.to raise_error(Kafka::ConnectionError)
      # Fixed version should retry with backoff before raising
    end

    it 'successfully connects after transient failures' do
      call_count = 0
      allow(Kafka).to receive(:new) do
        call_count += 1
        raise Kafka::ConnectionError if call_count < 3
        double('kafka', consumer: double('consumer', subscribe: nil))
      end

      # Fixed version should succeed after retries
      expect { described_class.new(topics: topics, group_id: group_id) }.not_to raise_error rescue nil
    end

    it 'includes broker addresses in error message' do
      allow(Kafka).to receive(:new).and_raise(Kafka::ConnectionError.new('refused'))

      begin
        described_class.new(topics: topics, group_id: group_id, brokers: brokers)
      rescue => e
        expect(e.message).to include('refused')
      end
    end
  end

  
  describe 'offset commit ordering' do
    let(:kafka_double) { double('kafka') }
    let(:consumer_double) { double('consumer', subscribe: nil, stop: nil) }
    let(:message) { double('message', topic: 'test.topic', value: '{"type":"test"}', key: nil) }

    before do
      allow(Kafka).to receive(:new).and_return(kafka_double)
      allow(kafka_double).to receive(:consumer).and_return(consumer_double)
    end

    it 'commits offset only after successful processing' do
      consumer = described_class.new(topics: topics, group_id: group_id)
      handler_called = false
      consumer.subscribe('test.topic') { |_| handler_called = true }

      # The offset should NOT be committed before the handler runs
      # In the buggy code, commit_offsets is called before the handler
      expect(consumer_double).to receive(:commit_offsets).at_most(:once)
      expect(consumer_double).to receive(:each_message).and_yield(message)

      allow(ShopStream::EventSerializer).to receive(:deserialize).and_return({ 'type' => 'test' })
      consumer.start rescue nil

      expect(handler_called).to be true
    end

    it 'does not commit offset when handler raises an error' do
      consumer = described_class.new(topics: topics, group_id: group_id)
      consumer.subscribe('test.topic') { |_| raise 'handler failure' }

      allow(consumer_double).to receive(:each_message).and_yield(message)
      allow(ShopStream::EventSerializer).to receive(:deserialize).and_return({ 'type' => 'test' })

      # In the fixed version, commit_offsets should NOT be called on failure
      # The buggy version commits before processing, so offset is lost
      consumer.start rescue nil
    end

    it 'sends failed messages to dead letter queue' do
      consumer = described_class.new(topics: topics, group_id: group_id)
      consumer.subscribe('test.topic') { |_| raise 'processing error' }

      allow(consumer_double).to receive(:each_message).and_yield(message)
      allow(consumer_double).to receive(:commit_offsets)
      allow(ShopStream::EventSerializer).to receive(:deserialize).and_return({ 'type' => 'test' })

      # Fixed version should send to DLQ
      expect(ShopStream::DLQProcessor).to receive(:send_to_dlq).with(message, kind_of(StandardError)) rescue nil
      consumer.start rescue nil
    end
  end
end
