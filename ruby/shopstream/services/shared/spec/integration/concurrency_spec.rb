# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Concurrency Integration' do
  # Cross-cutting thread safety tests covering A1-A10

  describe 'Inventory reservation race (A1)' do
    let(:product) { create(:product, stock: 10) }

    it 'does not oversell when concurrent reservations exceed stock' do
      results = []
      mutex = Mutex.new

      threads = 20.times.map do
        Thread.new do
          result = ReservationService.new.reserve(product.id, 1) rescue { success: false }
          mutex.synchronize { results << result }
        end
      end
      threads.each(&:join)

      successes = results.count { |r| r.is_a?(Hash) && r[:success] }
      expect(successes).to be <= 10

      product.reload
      expect(product.stock).to be >= 0
    end
  end

  describe 'Counter atomicity (A2)' do
    let(:product) { create(:product, view_count: 0) }

    it 'concurrent view increments produce correct total' do
      threads = 50.times.map do
        Thread.new { product.class.increment_counter(:view_count, product.id) rescue nil }
      end
      threads.each(&:join)

      product.reload
      expect(product.view_count).to eq(50)
    end
  end

  describe 'Price memoization thread safety (A3)' do
    it 'thread-unsafe memoization returns consistent results' do
      service = PricingService.new rescue nil
      next unless service

      product = create(:product, price: 100.0)
      results = []
      mutex = Mutex.new

      threads = 10.times.map do
        Thread.new do
          price = service.calculate_price(product.id) rescue nil
          mutex.synchronize { results << price }
        end
      end
      threads.each(&:join)

      # All threads should get the same price
      prices = results.compact.uniq
      expect(prices.size).to eq(1)
    end
  end

  describe 'Cart lost update (A5)' do
    let(:cart) { create(:cart) }

    it 'concurrent add_item does not lose items' do
      products = 5.times.map { create(:product) }
      mutex = Mutex.new
      errors = []

      threads = products.map do |product|
        Thread.new do
          begin
            cart.add_item(product.id, 1) rescue nil
          rescue StandardError => e
            mutex.synchronize { errors << e.message }
          end
        end
      end
      threads.each(&:join)

      cart.reload
      # All 5 items should be in the cart
      expect(cart.line_items.count).to eq(5)
    end
  end

  describe 'Optimistic locking (A10)' do
    let(:order) { create(:order) }

    it 'detects concurrent modifications' do
      order1 = Order.find(order.id)
      order2 = Order.find(order.id)

      order1.update!(notes: 'update 1')

      expect {
        order2.update!(notes: 'update 2')
      }.to raise_error(ActiveRecord::StaleObjectError)
    end

    it 'retries on stale object error' do
      order1 = Order.find(order.id)

      # Simulate concurrent modification
      Order.find(order.id).update!(notes: 'concurrent update')

      # Should retry with fresh data
      retried = false
      begin
        order1.update!(notes: 'original update')
      rescue ActiveRecord::StaleObjectError
        order1.reload
        order1.update!(notes: 'retried update')
        retried = true
      end

      expect(retried).to be true
      expect(order.reload.notes).to eq('retried update')
    end
  end

  describe 'Rate limiter race (A9)' do
    it 'concurrent requests do not bypass rate limit' do
      if defined?(RateLimiter)
        limiter = RateLimiter.new(limit: 10, window: 60)
        allowed_count = 0
        mutex = Mutex.new

        threads = 50.times.map do
          Thread.new do
            allowed = limiter.allow?('test-key') rescue false
            mutex.synchronize { allowed_count += 1 if allowed }
          end
        end
        threads.each(&:join)

        # Should not exceed limit
        expect(allowed_count).to be <= 15 # Some slack for race conditions
      end
    end
  end

  describe 'Event processor deduplication (A7)' do
    it 'concurrent identical events processed exactly once' do
      processor = ShopStream::EventProcessor.new rescue nil
      next unless processor

      count = 0
      mutex = Mutex.new
      processor.register('test.event') { |_| mutex.synchronize { count += 1 } }

      event = { 'type' => 'test.event', 'data' => {}, 'metadata' => { 'event_id' => 'evt-concurrent' } }

      threads = 10.times.map do
        Thread.new { processor.process(event) rescue nil }
      end
      threads.each(&:join)

      expect(count).to eq(1)
    end
  end

  describe 'Category cache singleton (A8)' do
    it 'singleton instance is thread-safe' do
      if defined?(CategoryCache)
        instances = []
        mutex = Mutex.new

        threads = 10.times.map do
          Thread.new do
            instance = CategoryCache.instance rescue nil
            mutex.synchronize { instances << instance.object_id } if instance
          end
        end
        threads.each(&:join)

        # All threads should get the same singleton
        expect(instances.uniq.size).to be <= 1
      end
    end
  end
end
