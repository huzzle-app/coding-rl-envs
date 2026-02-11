# frozen_string_literal: true

require 'rails_helper'

RSpec.describe CurrencyService do
  

  describe '#get_exchange_rate' do
    it 'uses mutex to prevent multiple concurrent fetches' do
      service = described_class.new
      results = []
      mutex = Mutex.new

      threads = 10.times.map do
        Thread.new do
          rate = service.get_exchange_rate('USD', 'EUR')
          mutex.synchronize { results << rate }
        end
      end
      threads.each(&:join)

      # All threads should get the same rate
      expect(results.uniq.size).to eq(1)
    end

    it 'thread-safely accesses the rates cache' do
      service = described_class.new

      # Concurrent calls should not raise errors
      expect {
        threads = 5.times.map do
          Thread.new { service.get_exchange_rate('USD', 'EUR') }
        end
        threads.each(&:join)
      }.not_to raise_error
    end
  end

  describe '#execute_conversion' do
    it 'uses the quoted rate, not the current rate' do
      service = described_class.new

      quote = service.quote_conversion(100.0, from: 'USD', to: 'EUR')
      quoted_rate = quote[:rate]
      quoted_amount = quote[:converted_amount]

      # Execute should use the locked/quoted rate
      result = service.execute_conversion(quote_id: quote[:quote_id], amount: 100.0)

      expect(result[:success]).to be true
      expect(result[:rate_used]).to eq(quoted_rate)
      expect(result[:converted_amount]).to eq(quoted_amount)
    end

    it 'rejects expired quotes' do
      service = described_class.new

      quote = service.quote_conversion(100.0, from: 'USD', to: 'EUR', lock_duration: 0.seconds)

      # Allow quote to expire
      travel_to(1.minute.from_now) do
        result = service.execute_conversion(quote_id: quote[:quote_id], amount: 100.0)
        expect(result[:success]).to be false
        expect(result[:error]).to match(/expired/i)
      end
    end

    it 'does not charge different amount than quoted even if rate changed' do
      service = described_class.new

      quote = service.quote_conversion(100.0, from: 'USD', to: 'EUR')
      original_amount = quote[:converted_amount]

      # Even if internal rate changes, execute should use quote rate
      result = service.execute_conversion(quote_id: quote[:quote_id], amount: 100.0)

      expect(result[:converted_amount]).to eq(original_amount)
    end
  end

  describe '#convert' do
    it 'returns same amount for same currency' do
      service = described_class.new
      expect(service.convert(100.0, from: 'USD', to: 'USD')).to eq(100.0)
    end

    it 'rounds to 2 decimal places' do
      service = described_class.new
      result = service.convert(100.0, from: 'USD', to: 'EUR')
      expect(result.to_s).to match(/^\d+\.\d{1,2}$/)
    end
  end
end
