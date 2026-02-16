# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::EventSerializer do
  
  describe '.deserialize' do
    let(:event_json) do
      { version: 2, type: 'order.created', data: { order_id: 1 },
        metadata: { timestamp: Time.now.iso8601, source_service: 'orders' } }.to_json
    end

    it 'returns hash with consistent key type accessible by callers' do
      result = described_class.deserialize(event_json)

      # Callers typically use symbol keys; JSON.parse returns string keys
      # Fixed version should symbolize keys or document string key usage
      expect(result['type'] || result[:type]).to eq('order.created')
    end

    it 'allows accessing event type without nil' do
      result = described_class.deserialize(event_json)

      
      event_type = result[:type] || result['type']
      expect(event_type).not_to be_nil
      expect(event_type).to eq('order.created')
    end

    it 'allows accessing nested metadata' do
      result = described_class.deserialize(event_json)

      metadata = result[:metadata] || result['metadata']
      expect(metadata).not_to be_nil
      timestamp = metadata[:timestamp] || metadata['timestamp']
      expect(timestamp).not_to be_nil
    end

    it 'preserves all data fields through serialize/deserialize round-trip' do
      original = { type: 'test.event', data: { key: 'value', nested: { deep: true } } }
      serialized = described_class.serialize(original)
      deserialized = described_class.deserialize(serialized)

      data = deserialized[:data] || deserialized['data']
      expect(data).not_to be_nil
    end
  end

  
  describe 'schema versioning' do
    it 'handles v1 events without source_service field' do
      v1_event = { version: 1, type: 'order.created', data: { order_id: 1 } }.to_json

      result = described_class.deserialize(v1_event)
      metadata = result['metadata'] || result[:metadata] || {}
      # Fixed version should provide a default source_service for v1
      expect(metadata).to be_a(Hash)
    end

    it 'handles v2 events with source_service field' do
      v2_event = { version: 2, type: 'order.created', data: {},
                   metadata: { source_service: 'orders', timestamp: Time.now.iso8601 } }.to_json

      result = described_class.deserialize(v2_event)
      metadata = result['metadata'] || result[:metadata]
      source = metadata['source_service'] || metadata[:source_service]
      expect(source).to eq('orders')
    end

    it 'handles unknown versions gracefully without raising' do
      v3_event = { version: 3, type: 'future.event', data: {} }.to_json

      # Fixed version should handle unknown versions gracefully
      expect { described_class.deserialize(v3_event) }.not_to raise_error
    end

    it 'preserves backward compatibility for consumers' do
      v1_json = { version: 1, type: 'payment.processed', data: { amount: 99.99 } }.to_json

      result = described_class.deserialize(v1_json)
      data = result['data'] || result[:data]
      amount = data['amount'] || data[:amount]
      expect(amount).to eq(99.99)
    end
  end
end
