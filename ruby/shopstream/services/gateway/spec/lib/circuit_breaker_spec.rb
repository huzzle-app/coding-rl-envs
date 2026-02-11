# frozen_string_literal: true

require 'rails_helper'

RSpec.describe CircuitBreaker do
  

  describe 'shared state across instances' do
    it 'shares circuit state via Redis, not instance variables' do
      cb1 = described_class.new('orders')
      cb2 = described_class.new('orders')

      # Trip the circuit on instance 1
      5.times do
        cb1.call { raise 'failure' } rescue nil
      end

      # Instance 2 should also see circuit as open
      expect(cb2).to be_open
    end

    it 'all instances agree on failure count' do
      instances = 3.times.map { described_class.new('payments') }

      # Each instance reports one failure
      instances.each do |cb|
        cb.call { raise 'error' } rescue nil
      end

      # Total failures should be 3 across all instances
      instances.each do |cb|
        expect(cb.status[:failure_count]).to eq(3)
      end
    end
  end

  describe 'state transitions' do
    it 'opens circuit after threshold failures' do
      cb = described_class.new('orders', threshold: 3)

      3.times { cb.call { raise 'fail' } rescue nil }

      expect(cb).to be_open
    end

    it 'raises CircuitOpenError when circuit is open' do
      cb = described_class.new('orders', threshold: 1)
      cb.call { raise 'fail' } rescue nil

      expect { cb.call { 'ok' } }.to raise_error(CircuitBreaker::CircuitOpenError)
    end

    it 'transitions to half-open after timeout' do
      cb = described_class.new('orders', threshold: 1, timeout: 1)
      cb.call { raise 'fail' } rescue nil

      expect(cb).to be_open

      sleep 1.5
      # After timeout, should be half-open (not open)
      expect(cb).not_to be_open
    end

    it 'resets failure count on success' do
      cb = described_class.new('orders', threshold: 5)
      2.times { cb.call { raise 'fail' } rescue nil }

      cb.call { 'success' }

      expect(cb.status[:failure_count]).to eq(0)
      expect(cb.status[:state]).to eq(:closed)
    end
  end

  describe '#status' do
    it 'returns service name, state, failure count, and last failure time' do
      cb = described_class.new('orders')
      status = cb.status

      expect(status).to include(:service, :state, :failure_count, :last_failure)
      expect(status[:service]).to eq('orders')
    end
  end
end
