# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ApiKeyService do
  

  let(:redis) { Redis.new }

  describe '#generate' do
    it 'returns a key with proper prefix' do
      service = described_class.new(redis)
      result = service.generate(1, name: 'test-key', permissions: ['read'])

      expect(result[:key]).to start_with('sk_')
      expect(result[:name]).to eq('test-key')
    end

    it 'stores hashed key, not plaintext' do
      service = described_class.new(redis)
      result = service.generate(1, name: 'test-key')

      # The stored data should not contain the raw key
      stored = redis.hgetall('api_keys:1')
      stored.keys.each do |stored_hash|
        expect(stored_hash).not_to eq(result[:key])
      end
    end
  end

  describe '#validate' do
    it 'validates a correct API key' do
      service = described_class.new(redis)
      result = service.generate(1, name: 'my-key', permissions: ['read', 'write'])
      key = result[:key]

      validated = service.validate(key)

      expect(validated).not_to be_nil
      expect(validated['user_id']).to eq('1')
      expect(validated['name']).to eq('my-key')
    end

    it 'returns nil for invalid key' do
      service = described_class.new(redis)
      validated = service.validate('sk_invalid_key_here')

      expect(validated).to be_nil
    end

    it 'returns nil for nil key' do
      service = described_class.new(redis)
      expect(service.validate(nil)).to be_nil
    end

    it 'uses constant-time comparison to prevent timing attack' do
      service = described_class.new(redis)
      service.generate(1, name: 'target-key')

      # Validation time should not vary significantly based on key content
      # This tests the principle: use ActiveSupport::SecurityUtils.secure_compare
      # or hash-based lookup (O(1)) instead of iterating through all keys
      times = 10.times.map do
        key = "sk_#{SecureRandom.hex(32)}"
        start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
        service.validate(key)
        Process.clock_gettime(Process::CLOCK_MONOTONIC) - start
      end

      # Standard deviation should be small (no linear scan dependency)
      avg = times.sum / times.size
      variance = times.map { |t| (t - avg)**2 }.sum / times.size
      std_dev = Math.sqrt(variance)

      expect(std_dev).to be < avg * 0.5
    end

    it 'uses O(1) lookup, not O(n) scan of all users' do
      service = described_class.new(redis)

      # Create keys for many users
      100.times { |i| service.generate(i, name: "key-#{i}") }

      target = service.generate(50, name: 'target')

      # Should use hash index for O(1) lookup
      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      result = service.validate(target[:key])
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start

      expect(result).not_to be_nil
      # O(1) should be fast; O(n) scanning 100 users would be noticeably slower
      expect(elapsed).to be < 0.1
    end
  end

  describe '#revoke' do
    it 'revokes key by name' do
      service = described_class.new(redis)
      result = service.generate(1, name: 'to-revoke')

      expect(service.revoke(1, 'to-revoke')).to be true
      expect(service.validate(result[:key])).to be_nil
    end

    it 'returns false for non-existent key name' do
      service = described_class.new(redis)
      expect(service.revoke(1, 'nonexistent')).to be false
    end
  end

  describe '#list_keys' do
    it 'lists all keys for a user without exposing raw key values' do
      service = described_class.new(redis)
      service.generate(1, name: 'key-a', permissions: ['read'])
      service.generate(1, name: 'key-b', permissions: ['write'])

      keys = service.list_keys(1)

      expect(keys.size).to eq(2)
      names = keys.map { |k| k[:name] }
      expect(names).to include('key-a', 'key-b')

      # Should not expose raw key values
      keys.each do |k|
        expect(k).not_to have_key(:key)
        expect(k).not_to have_key('key')
      end
    end
  end
end
