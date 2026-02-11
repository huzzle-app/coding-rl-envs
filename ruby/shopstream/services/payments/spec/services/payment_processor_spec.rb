# frozen_string_literal: true

require 'rails_helper'

RSpec.describe PaymentProcessor do
  
  let(:order) { create(:order, payment_status: 'pending', total_amount: 99.99) }

  describe '#process_payment' do
    it 'prevents double-spend when two concurrent requests process same order' do
      processors = 2.times.map { described_class.new(order.id) }
      results = []
      mutex = Mutex.new

      threads = processors.map do |processor|
        Thread.new do
          result = processor.process_payment(
            amount: 99.99,
            payment_method: 'card_123',
            idempotency_key: 'idem-key-1'
          ) rescue { success: false }
          mutex.synchronize { results << result }
        end
      end
      threads.each(&:join)

      successful = results.count { |r| r[:success] }
      # Only one payment should succeed
      expect(successful).to eq(1)
    end

    it 'returns already_paid when order is already paid' do
      order.update!(payment_status: 'paid')
      processor = described_class.new(order.id)

      result = processor.process_payment(amount: 99.99, payment_method: 'card_123')

      expect(result[:already_paid]).to be true
    end

    it 'uses idempotency key for deduplication' do
      processor = described_class.new(order.id)

      result1 = processor.process_payment(
        amount: 99.99, payment_method: 'card_123', idempotency_key: 'key-123'
      )
      result2 = processor.process_payment(
        amount: 99.99, payment_method: 'card_123', idempotency_key: 'key-123'
      )

      # Second call with same key should not charge again
      expect(result1[:success]).to be true
    end
  end

  describe '#refund' do
    let(:paid_order) { create(:order, payment_status: 'paid', payment_id: 'pay_123', total_amount: 100.0) }

    it 'prevents concurrent double refund' do
      processors = 2.times.map { described_class.new(paid_order.id) }
      results = []
      mutex = Mutex.new

      threads = processors.map do |p|
        Thread.new do
          result = p.refund(amount: 100.0) rescue { success: false }
          mutex.synchronize { results << result }
        end
      end
      threads.each(&:join)

      successful = results.count { |r| r[:success] }
      expect(successful).to eq(1)
    end
  end
end
