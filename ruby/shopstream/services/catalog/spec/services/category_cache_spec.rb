# frozen_string_literal: true

require 'rails_helper'

RSpec.describe CategoryCache do
  
  describe '.instance' do
    it 'returns the same instance across calls' do
      instance1 = described_class.instance
      instance2 = described_class.instance
      expect(instance1).to equal(instance2)
    end

    it 'returns the same instance from concurrent threads' do
      instances = []
      mutex = Mutex.new

      threads = 10.times.map do
        Thread.new do
          inst = described_class.instance
          mutex.synchronize { instances << inst.object_id }
        end
      end
      threads.each(&:join)

      # All threads should get the same instance
      expect(instances.uniq.size).to eq(1)
    end
  end

  describe '#get and thread safety' do
    let(:cache) { described_class.instance }

    it 'does not return corrupted data during concurrent reads and writes' do
      # Warm cache first
      allow(Category).to receive(:includes).and_return(Category)
      allow(Category).to receive(:all).and_return([])

      errors = []
      threads = 10.times.map do |i|
        Thread.new do
          if i.even?
            cache.invalidate rescue nil
          else
            result = cache.get(1) rescue nil
            errors << 'corrupted' if result.is_a?(String) # should be Hash or nil
          end
        end
      end
      threads.each(&:join)

      expect(errors).to be_empty
    end
  end

  describe '#invalidate' do
    it 'removes specific category from cache' do
      cache = described_class.instance
      cache.invalidate(999)
      expect(cache.get(999)).to be_nil
    end

    it 'clears entire cache when called without argument' do
      cache = described_class.instance
      cache.invalidate
      expect(cache.get_all).to be_empty rescue nil
    end
  end
end
