# frozen_string_literal: true

require 'rails_helper'

RSpec.describe RateLimiter do
  let(:app) { ->(env) { [200, {}, ['OK']] } }
  let(:redis) { Redis.new }
  let(:middleware) { described_class.new(app, redis: redis, limit: 5, window: 60) }

  before { redis.flushdb }

  describe '#call' do
    
    context 'race condition in rate limiting' do
      it 'accurately counts concurrent requests' do
        threads = 10.times.map do
          Thread.new do
            env = { 'REMOTE_ADDR' => '192.168.1.1' }
            middleware.call(env)
          end
        end

        results = threads.map(&:value)
        successful = results.count { |status, _, _| status == 200 }
        rate_limited = results.count { |status, _, _| status == 429 }

        # Exactly 5 should succeed, 5 should be rate limited
        expect(successful).to eq(5)
        expect(rate_limited).to eq(5)
      end

      it 'uses atomic increment operation' do
        # First 5 requests should succeed
        5.times do
          env = { 'REMOTE_ADDR' => '192.168.1.1' }
          status, _, _ = middleware.call(env)
          expect(status).to eq(200)
        end

        # 6th request should be rate limited
        env = { 'REMOTE_ADDR' => '192.168.1.1' }
        status, _, _ = middleware.call(env)
        expect(status).to eq(429)
      end
    end

    
    context 'X-Forwarded-For header spoofing' do
      it 'does not trust X-Forwarded-For from untrusted sources' do
        # Exhaust rate limit for real IP
        5.times do
          env = { 'REMOTE_ADDR' => '192.168.1.1' }
          middleware.call(env)
        end

        # Try to bypass by spoofing X-Forwarded-For
        env = {
          'REMOTE_ADDR' => '192.168.1.1',
          'HTTP_X_FORWARDED_FOR' => '10.0.0.1'
        }
        status, _, _ = middleware.call(env)

        # Should still be rate limited based on REMOTE_ADDR
        expect(status).to eq(429)
      end

      it 'only trusts X-Forwarded-For from configured trusted proxies' do
        trusted_proxy_middleware = described_class.new(
          app,
          redis: redis,
          limit: 5,
          window: 60,
          trusted_proxies: ['10.0.0.1']
        )

        # Request from trusted proxy
        env = {
          'REMOTE_ADDR' => '10.0.0.1',
          'HTTP_X_FORWARDED_FOR' => '192.168.1.100'
        }

        5.times { trusted_proxy_middleware.call(env) }

        # Should rate limit based on X-Forwarded-For IP
        status, _, _ = trusted_proxy_middleware.call(env)
        expect(status).to eq(429)
      end

      it 'ignores X-Real-Client-ID header' do
        # Exhaust rate limit
        5.times do
          env = { 'REMOTE_ADDR' => '192.168.1.1' }
          middleware.call(env)
        end

        # Try to bypass with custom header
        env = {
          'REMOTE_ADDR' => '192.168.1.1',
          'HTTP_X_REAL_CLIENT_ID' => 'fake-client-id'
        }
        status, _, _ = middleware.call(env)

        expect(status).to eq(429)
      end
    end
  end
end
