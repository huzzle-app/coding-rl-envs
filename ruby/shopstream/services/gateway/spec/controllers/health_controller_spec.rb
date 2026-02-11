# frozen_string_literal: true

require 'rails_helper'

RSpec.describe Api::V1::HealthController, type: :controller do
  

  describe 'GET #show' do
    it 'returns unhealthy when critical services are down' do
      allow_any_instance_of(described_class).to receive(:check_redis)
        .and_return(status: 'unhealthy', error: 'Connection refused')
      allow_any_instance_of(described_class).to receive(:check_database)
        .and_return(status: 'unhealthy', error: 'Connection refused')

      get :show

      body = JSON.parse(response.body)
      expect(body['status']).to eq('unhealthy')
      expect(response.status).to eq(503)
    end

    it 'does not report healthy when only some services are up' do
      # 9/10 services healthy, 1 critical (Redis) down
      allow_any_instance_of(described_class).to receive(:check_redis)
        .and_return(status: 'unhealthy', error: 'Connection refused')
      allow_any_instance_of(described_class).to receive(:check_database)
        .and_return(status: 'healthy')

      get :show

      body = JSON.parse(response.body)
      # Should be unhealthy because Redis is a critical service
      expect(body['status']).to eq('unhealthy')
    end

    it 'reports unhealthy instead of degraded for critical failures' do
      allow_any_instance_of(described_class).to receive(:check_redis)
        .and_return(status: 'unhealthy', error: 'Connection refused')

      get :show

      body = JSON.parse(response.body)
      redis_check = body.dig('checks', 'redis')

      # Should be 'unhealthy', not 'degraded'
      expect(redis_check['status']).to eq('unhealthy')
    end
  end

  describe 'GET #ready' do
    it 'checks database connectivity in readiness probe' do
      allow(ActiveRecord::Base.connection).to receive(:execute)
        .and_raise(PG::ConnectionBad.new('connection failed'))

      get :ready

      # Readiness probe should fail when database is unreachable
      expect(response.status).not_to eq(200)
    end
  end

  describe 'GET #live' do
    it 'returns 200 for liveness probe' do
      get :live

      expect(response.status).to eq(200)
      body = JSON.parse(response.body)
      expect(body['status']).to eq('live')
    end
  end

  describe 'health check performance' do
    it 'runs service checks in parallel, not sequentially' do
      # With 10 services at 5s timeout each, sequential would take 50s
      # Parallel should complete in ~5s
      allow_any_instance_of(described_class).to receive(:check_service) do |_instance, service_name|
        sleep 0.1 # Simulate network call
        { status: 'healthy' }
      end

      allow_any_instance_of(described_class).to receive(:check_redis)
        .and_return(status: 'healthy', latency_ms: 1)
      allow_any_instance_of(described_class).to receive(:check_database)
        .and_return(status: 'healthy')

      start = Time.current
      get :show
      elapsed = Time.current - start

      # Parallel: ~0.1s, Sequential: ~1s (10 services * 0.1s)
      expect(elapsed).to be < 1.0
    end
  end
end
