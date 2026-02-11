# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::RequestLogger do
  
  describe '.log_request' do
    let(:request) do
      double('request',
        method: 'POST',
        path: '/api/v1/auth/login',
        params: { email: 'user@test.com', password: 'secret123', credit_card: '4111111111111111' },
        headers: { 'HTTP_AUTHORIZATION' => 'Bearer token123', 'CONTENT_TYPE' => 'application/json' },
        ip: '127.0.0.1',
        user_agent: 'TestAgent'
      )
    end
    let(:response) { double('response', status: 200, body: '{"token":"secret_jwt"}') }

    before do
      allow(ShopStream::RequestContext).to receive(:user_id).and_return(1)
      allow(ShopStream::RequestContext).to receive(:correlation_id).and_return('corr-1')
    end

    it 'does not log password values' do
      logged_output = nil
      allow(Rails.logger).to receive(:info) { |msg| logged_output = msg }

      described_class.log_request(request, response, 50)

      # Fixed version should filter sensitive fields
      expect(logged_output).not_to include('secret123')
    end

    it 'does not log credit card numbers' do
      logged_output = nil
      allow(Rails.logger).to receive(:info) { |msg| logged_output = msg }

      described_class.log_request(request, response, 50)

      expect(logged_output).not_to include('4111111111111111')
    end

    it 'does not log Authorization header value' do
      logged_output = nil
      allow(Rails.logger).to receive(:info) { |msg| logged_output = msg }

      described_class.log_request(request, response, 50)

      # Fixed version should not include the bearer token
      expect(logged_output).not_to include('Bearer token123')
    end

    it 'still logs non-sensitive request metadata' do
      logged_output = nil
      allow(Rails.logger).to receive(:info) { |msg| logged_output = msg }

      described_class.log_request(request, response, 50)

      expect(logged_output).to include('/api/v1/auth/login')
    end
  end

  describe '.log_error' do
    it 'does not include sensitive params in error logs' do
      request = double('request',
        method: 'POST', path: '/api/v1/payments',
        params: { cvv: '123', ssn: '123-45-6789' },
        headers: {}
      )
      error = StandardError.new('payment failed')
      allow(error).to receive(:backtrace).and_return(['line1', 'line2'])
      allow(ShopStream::RequestContext).to receive(:user_id).and_return(nil)
      allow(ShopStream::RequestContext).to receive(:correlation_id).and_return(nil)

      logged_output = nil
      allow(Rails.logger).to receive(:error) { |msg| logged_output = msg }

      described_class.log_error(request, error)

      expect(logged_output).not_to include('123-45-6789')
    end
  end
end
