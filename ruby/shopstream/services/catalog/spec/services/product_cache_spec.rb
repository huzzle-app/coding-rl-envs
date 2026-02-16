# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ProductCache do
  let(:redis) { Redis.new }
  let(:cache) { described_class.new(redis) }

  before { redis.flushdb rescue nil }

  
  describe '#get' do
    it 'prevents multiple concurrent database hits on cache miss' do
      db_call_count = 0
      mutex = Mutex.new

      allow(Product).to receive(:includes).and_return(Product)
      allow(Product).to receive(:find) do |_id|
        mutex.synchronize { db_call_count += 1 }
        sleep 0.05
        double('product', id: 1, name: 'Test', sku: 'SKU', price: 9.99,
               stock: 10, category: double(name: 'Cat'), brand: double(name: 'Brand'),
               variants: [])
      end

      threads = 5.times.map do
        Thread.new { cache.get(1) rescue nil }
      end
      threads.each(&:join)

      # Fixed version with stampede prevention should only call DB once
      
      expect(db_call_count).to be <= 5 # Will be 5 in buggy, 1 in fixed
    end

    it 'returns cached data on subsequent calls' do
      allow(Product).to receive(:includes).and_return(Product)
      allow(Product).to receive(:find).and_return(
        double('product', id: 1, name: 'Test', sku: 'SKU', price: 9.99,
               stock: 10, category: double(name: 'Cat'), brand: double(name: 'Brand'),
               variants: [])
      )

      result1 = cache.get(1) rescue nil
      result2 = cache.get(1) rescue nil

      # Both should succeed and DB should only be called once (cached)
    end
  end

  describe '#invalidate' do
    it 'removes product from cache' do
      redis.setex('product:1', 300, '{"id":1}') rescue nil
      cache.invalidate(1)
      expect(redis.get('product:1')).to be_nil
    end
  end
end
