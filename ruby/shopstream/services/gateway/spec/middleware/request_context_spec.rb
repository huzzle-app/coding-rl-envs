# frozen_string_literal: true

require 'rails_helper'

RSpec.describe RequestContextMiddleware do
  

  let(:app) { ->(env) { [200, {}, ['OK']] } }

  describe 'request isolation' do
    it 'does not leak request data between concurrent requests' do
      middleware = described_class.new(app)

      results = []
      mutex = Mutex.new

      threads = 5.times.map do |i|
        Thread.new do
          env = {
            'HTTP_AUTHORIZATION' => "Bearer token_#{i}",
            'HTTP_X_CORRELATION_ID' => "corr-#{i}",
            'REMOTE_ADDR' => "10.0.0.#{i}",
            'HTTP_USER_AGENT' => "Agent/#{i}",
            'REQUEST_METHOD' => 'GET',
            'PATH_INFO' => "/test/#{i}",
            'rack.input' => StringIO.new
          }

          middleware.call(env)

          # Each thread should see its own data, not another thread's
          data = described_class.current_data
          mutex.synchronize { results << data }
        end
      end
      threads.each(&:join)

      # Using Thread.current storage, each thread should see its own correlation ID
      # With class variables (bug), data leaks between threads
      correlation_ids = results.compact.map { |d| d[:correlation_id] }.compact.uniq
      expect(correlation_ids.size).to be > 1
    end

    it 'cleans up request context after request completes' do
      middleware = described_class.new(app)

      env = {
        'HTTP_X_CORRELATION_ID' => 'test-corr-123',
        'REMOTE_ADDR' => '127.0.0.1',
        'REQUEST_METHOD' => 'GET',
        'PATH_INFO' => '/test',
        'rack.input' => StringIO.new
      }

      middleware.call(env)

      # After request completes, context should be cleared
      # (Thread.current approach: data cleared in ensure block)
      data = described_class.current_data
      expect(data).to be_empty.or eq({})
    end
  end

  describe 'correlation ID' do
    it 'generates correlation ID if not provided' do
      middleware = described_class.new(app)

      env = {
        'REMOTE_ADDR' => '127.0.0.1',
        'REQUEST_METHOD' => 'GET',
        'PATH_INFO' => '/test',
        'rack.input' => StringIO.new
      }

      _status, headers, _body = middleware.call(env)

      expect(headers['X-Correlation-ID']).to be_a(String)
      expect(headers['X-Correlation-ID']).not_to be_empty
    end

    it 'uses provided correlation ID' do
      middleware = described_class.new(app)

      env = {
        'HTTP_X_CORRELATION_ID' => 'my-custom-id',
        'REMOTE_ADDR' => '127.0.0.1',
        'REQUEST_METHOD' => 'GET',
        'PATH_INFO' => '/test',
        'rack.input' => StringIO.new
      }

      _status, headers, _body = middleware.call(env)

      expect(headers['X-Correlation-ID']).to eq('my-custom-id')
    end
  end
end
