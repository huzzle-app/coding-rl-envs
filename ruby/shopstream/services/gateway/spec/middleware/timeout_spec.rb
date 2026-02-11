# frozen_string_literal: true

require 'rails_helper'

RSpec.describe TimeoutMiddleware do
  

  let(:app) { ->(env) { [200, {}, ['OK']] } }

  describe 'timeout configuration' do
    it 'uses longer timeout for checkout endpoints' do
      middleware = described_class.new(app)

      env = {
        'REQUEST_METHOD' => 'POST',
        'PATH_INFO' => '/api/v1/checkout',
        'rack.input' => StringIO.new
      }

      # Checkout involves: Orders -> Inventory -> Payments -> Shipping
      # Should have a timeout >> 5 seconds
      timeout = middleware.send(:determine_timeout, ActionDispatch::Request.new(env))

      expect(timeout).to be >= 15
    end

    it 'uses longer timeout for order creation endpoints' do
      middleware = described_class.new(app)

      env = {
        'REQUEST_METHOD' => 'POST',
        'PATH_INFO' => '/api/v1/orders',
        'rack.input' => StringIO.new
      }

      timeout = middleware.send(:determine_timeout, ActionDispatch::Request.new(env))

      # Orders endpoint calls multiple downstream services
      expect(timeout).to be >= 10
    end

    it 'uses shorter timeout for read-only endpoints' do
      middleware = described_class.new(app)

      env = {
        'REQUEST_METHOD' => 'GET',
        'PATH_INFO' => '/api/v1/products',
        'rack.input' => StringIO.new
      }

      timeout = middleware.send(:determine_timeout, ActionDispatch::Request.new(env))

      # Read operations should be fast
      expect(timeout).to be <= 10
    end
  end

  describe 'timeout response' do
    it 'returns 504 Gateway Timeout on timeout' do
      slow_app = ->(_env) { sleep 2; [200, {}, ['OK']] }
      middleware = described_class.new(slow_app, timeout: 0.1)

      env = {
        'REQUEST_METHOD' => 'GET',
        'PATH_INFO' => '/api/v1/test',
        'rack.input' => StringIO.new
      }

      status, _headers, _body = middleware.call(env)

      expect(status).to eq(504)
    end

    it 'passes through requests that complete in time' do
      middleware = described_class.new(app, timeout: 5)

      env = {
        'REQUEST_METHOD' => 'GET',
        'PATH_INFO' => '/api/v1/test',
        'rack.input' => StringIO.new
      }

      status, _headers, _body = middleware.call(env)

      expect(status).to eq(200)
    end
  end

  describe 'deadline propagation' do
    it 'sets X-Request-Deadline header for downstream services' do
      captured_env = nil
      deadline_app = ->(env) { captured_env = env; [200, {}, ['OK']] }
      middleware = described_class.new(deadline_app, timeout: 30)

      env = {
        'REQUEST_METHOD' => 'POST',
        'PATH_INFO' => '/api/v1/checkout',
        'rack.input' => StringIO.new
      }

      middleware.call(env)

      # Downstream services should know when the request deadline is
      expect(captured_env['HTTP_X_REQUEST_DEADLINE']).to be_a(String)
    end
  end
end
