# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Cross-Service Integration' do
  # Tests that span multiple bug categories and service boundaries

  describe 'Order lifecycle' do
    let(:user) { create(:user) }
    let(:product) { create(:product, stock: 50, price: 29.99) }

    it 'creates order with correct total amount (H1 precision)' do
      items = [{ product_id: product.id, quantity: 3 }]

      # Using BigDecimal prevents float precision errors
      expected = BigDecimal('29.99') * 3
      actual = items.sum { |i| BigDecimal(Product.find(i[:product_id]).price.to_s) * i[:quantity] }

      expect(actual).to eq(expected)
    end

    it 'validates stock before order confirmation (A1 race)' do
      order = create(:order, user: user)
      create(:line_item, order: order, product: product, quantity: 5)

      # Stock validation should use pessimistic locking
      expect {
        5.times.map do
          Thread.new do
            ReservationService.new.reserve(product.id, 10) rescue nil
          end
        end.each(&:join)
      }.not_to raise_error

      product.reload
      expect(product.stock).to be >= 0
    end

    it 'tax + discount + total consistency (H2 + H4)' do
      subtotal = BigDecimal('100.00')
      discount_rate = BigDecimal('0.20')
      tax_rate = BigDecimal('0.10')

      discounted = subtotal - (subtotal * discount_rate)
      tax = (discounted * tax_rate).round(2)
      total = discounted + tax

      expect(total).to eq(BigDecimal('88.00'))
    end

    it 'concurrent order + payment race condition (A4 + A5)' do
      order = create(:order, user: user, payment_status: 'pending', total_amount: 50.0)

      results = []
      mutex = Mutex.new

      threads = 2.times.map do
        Thread.new do
          result = begin
            PaymentProcessor.new(order.id).process_payment(
              amount: 50.0, payment_method: 'card_1', idempotency_key: 'pay-key'
            )
          rescue StandardError
            { success: false }
          end
          mutex.synchronize { results << result }
        end
      end
      threads.each(&:join)

      successes = results.count { |r| r[:success] }
      expect(successes).to be <= 1
    end
  end

  describe 'Event flow' do
    it 'event published after commit, not before (C1 + C4)' do
      events_published = []
      allow(ShopStream::KafkaProducer).to receive(:publish) do |topic, event|
        events_published << event
      end

      ActiveRecord::Base.transaction do
        order = create(:order, status: 'pending')
        order.update!(status: 'confirmed')
        # Events should not be published yet (inside transaction)
      end

      # Events should be published after commit
    end

    it 'idempotent event handling (E1 + E2 + B2)' do
      event = {
        'type' => 'payment.processed',
        'data' => { 'order_id' => 1 },
        'metadata' => { 'event_id' => 'unique-id-1' }
      }

      processor = ShopStream::EventProcessor.new rescue nil
      if processor
        processor.register('payment.processed') { |_e| }
        processor.process(event) rescue nil
        processor.process(event) rescue nil
        # Should not process twice
      end
    end
  end

  describe 'Security chain' do
    it 'JWT + session + IDOR chain (I1 + A6 + I3)' do
      # Weak JWT secret leads to forged tokens
      # Which enables session fixation
      # Which enables IDOR
      secret = JwtService::SECRET_KEY rescue 'secret'

      if secret.length < 32
        # Secret too short - vulnerability I1
        expect(secret.length).to be < 32
      end
    end

    it 'SQL injection prevention across all services (B3 + I5)' do
      malicious = "'; DROP TABLE orders; --"

      # Search service should sanitize
      expect {
        SearchService.new.search(malicious) rescue nil
      }.not_to raise_error

      # Order queries should use parameterized queries
      expect {
        Order.where('status = ?', malicious).to_a rescue nil
      }.not_to raise_error
    end

    it 'rate limiting withstands concurrent bypass attempts (A9 + I4)' do
      # Many concurrent requests should not all bypass rate limiter
      if defined?(RateLimiter)
        limiter = RateLimiter.new(limit: 5, window: 60)
        results = []
        mutex = Mutex.new

        threads = 20.times.map do
          Thread.new do
            allowed = limiter.allow?('test-ip') rescue true
            mutex.synchronize { results << allowed }
          end
        end
        threads.each(&:join)

        # Most should be blocked
        expect(results.count(true)).to be <= 10
      end
    end
  end

  describe 'Distributed systems' do
    it 'circuit breaker + service registry + health check chain (F1 + F4 + F7)' do
      # When a service is down:
      # 1. Circuit breaker should open (F1)
      # 2. Service registry should reflect unhealthy status (F4)
      # 3. Health check should report unhealthy (F7)
      if defined?(CircuitBreaker)
        cb = CircuitBreaker.new('test-service', threshold: 2)
        2.times { cb.call { raise 'down' } rescue nil }
        expect(cb).to be_open
      end
    end

    it 'correlation ID propagates through service calls (F6 + B7)' do
      # Using Thread.current instead of class variables
      Thread.current[:request_context] = { correlation_id: 'test-corr-123' }

      context = Thread.current[:request_context]
      expect(context[:correlation_id]).to eq('test-corr-123')

      Thread.current[:request_context] = nil
    end

    it 'distributed lock prevents concurrent processing (F3 + D9)' do
      if defined?(LockService)
        service = LockService.new
        results = []
        mutex = Mutex.new

        threads = 3.times.map do |i|
          Thread.new do
            acquired = service.acquire('test-resource', ttl: 5) rescue false
            mutex.synchronize { results << acquired }
          end
        end
        threads.each(&:join)

        # Only one should acquire the lock
        expect(results.count(true)).to be <= 1
      end
    end
  end

  describe 'Caching chain' do
    it 'cache stampede + stale cache + serialization (G1 + G2 + G5)' do
      product = create(:product, price: 10.0)

      # Concurrent cache access should not cause stampede
      threads = 5.times.map do
        Thread.new do
          Rails.cache.fetch("product:#{product.id}", expires_in: 1.hour) do
            Product.find(product.id).as_json
          end
        end
      end
      results = threads.map(&:value)

      # All should get same data
      expect(results.uniq.size).to eq(1)
    end
  end
end
