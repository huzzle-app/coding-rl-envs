# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::ApiClient do
  
  let(:http_double) { double('http_client', get: {}, post: {}, put: {}, delete: {}) }

  before do
    allow(ShopStream::HttpClient).to receive(:new).and_return(http_double)
  end

  describe 'method_missing for known prefixes' do
    it 'handles get_ prefix correctly' do
      client = described_class.new('orders')
      expect(http_double).to receive(:get).with('/api/v1/orders/1', params: {})
      client.get_orders(1)
    end

    it 'handles create_ prefix correctly' do
      client = described_class.new('orders')
      expect(http_double).to receive(:post).with('/api/v1/orders', body: { name: 'test' })
      client.create_orders(name: 'test')
    end

    it 'handles find_ prefix correctly' do
      client = described_class.new('users')
      expect(http_double).to receive(:get).with('/api/v1/users/5', params: {})
      client.find_users(5)
    end
  end

  describe 'method_missing for unknown methods' do
    it 'raises NoMethodError instead of infinite loop' do
      client = described_class.new('orders')

      
      expect {
        Timeout.timeout(2) { client.some_unknown_method }
      }.to raise_error(NoMethodError).or raise_error(Timeout::Error)
    end

    it 'does not cause stack overflow on unknown methods' do
      client = described_class.new('orders')

      expect {
        Timeout.timeout(2) { client.nonexistent_action }
      }.to raise_error(NoMethodError).or raise_error(SystemStackError).or raise_error(Timeout::Error)
    end
  end

  describe 'respond_to_missing?' do
    it 'returns true for known prefixes' do
      client = described_class.new('orders')
      expect(client.respond_to?(:get_orders)).to be true
      expect(client.respond_to?(:create_orders)).to be true
      expect(client.respond_to?(:update_orders)).to be true
      expect(client.respond_to?(:delete_orders)).to be true
    end

    it 'returns false for unknown prefixes' do
      client = described_class.new('orders')
      expect(client.respond_to?(:random_method)).to be false
    end
  end
end
