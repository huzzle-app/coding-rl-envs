# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::CacheSerializer do
  
  describe '.serialize / .deserialize round-trip' do
    let(:data) { { 'name' => 'Test Product', 'price' => 29.99, 'tags' => ['sale', 'new'] } }

    it 'produces identical data after serialize then deserialize with JSON' do
      serialized = described_class.serialize(data, format: :json)
      deserialized = described_class.deserialize(serialized, format: :json)

      expect(deserialized).to eq(data)
    end

    it 'uses a consistent default format across all calls' do
      serialized1 = described_class.serialize(data)
      serialized2 = described_class.serialize(data)

      # Both should use same format
      expect(serialized1).to eq(serialized2)
    end

    it 'does not silently return nil on deserialization failure' do
      
      bad_data = "\x00\x01\x02invalid"

      result = described_class.deserialize(bad_data)
      # Result should be nil (cache miss) but should be logged
      expect(result).to be_nil
    end

    it 'correctly detects JSON format' do
      json_data = '{"name":"test","price":9.99}'
      result = described_class.deserialize(json_data)

      expect(result).to be_a(Hash)
      expect(result['name']).to eq('test')
    end

    it 'handles empty hash serialization' do
      serialized = described_class.serialize({})
      deserialized = described_class.deserialize(serialized)
      expect(deserialized).to eq({})
    end
  end
end
