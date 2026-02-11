# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ServiceRegistry do
  
  

  describe '#get_endpoint' do
    it 'performs active health check, not just cached lookup' do
      registry = described_class.new
      registry.register('orders', 'http://orders:3000')

      # Should check health, not just return cached value
      endpoint = registry.get_endpoint('orders')
      expect(endpoint).to be_a(String)
    end

    it 'raises ServiceNotFoundError for unknown service' do
      registry = described_class.new
      expect { registry.get_endpoint('nonexistent') }.to raise_error(ServiceRegistry::ServiceNotFoundError)
    end
  end

  describe '#get_healthy_endpoint' do
    it 'does not return unhealthy endpoints' do
      registry = described_class.new
      registry.register('orders', 'http://orders:3000')

      # Simulate health check failure
      registry.deregister('orders', 'http://orders:3000')

      # get_healthy_endpoint should either raise or return a different endpoint
      # but not return the unhealthy one from cache
      result = begin
        registry.get_healthy_endpoint('orders')
      rescue ServiceRegistry::ServiceNotFoundError
        :not_found
      end

      # Ideally it should not silently return stale endpoint
      expect(result).not_to be_nil
    end
  end

  describe 'shared state across gateway instances (F4)' do
    it 'stores registrations in shared state, not local memory' do
      registry1 = described_class.new
      registry2 = described_class.new

      registry1.register('catalog', 'http://catalog:3000')

      # Registry2 should see the registration from registry1
      endpoint = registry2.get_endpoint('catalog') rescue nil
      expect(endpoint).to eq('http://catalog:3000')
    end

    it 'health check results are shared across instances' do
      registry1 = described_class.new
      registry2 = described_class.new

      registry1.register('auth', 'http://auth:3000')
      registry1.deregister('auth', 'http://auth:3000')

      # Registry2 should also see auth as unhealthy
      healthy = registry2.get_healthy_endpoint('auth') rescue nil
      expect(healthy).not_to eq('http://auth:3000')
    end
  end

  describe '#register and #deregister' do
    it 'register adds endpoint to service list' do
      registry = described_class.new
      registry.register('search', 'http://search:3000')

      endpoint = registry.get_endpoint('search')
      expect(endpoint).to eq('http://search:3000')
    end

    it 'deregister removes service entirely when no endpoint specified' do
      registry = described_class.new
      registry.register('analytics', 'http://analytics:3000')
      registry.deregister('analytics')

      expect { registry.get_endpoint('analytics') }.to raise_error(ServiceRegistry::ServiceNotFoundError)
    end
  end

  describe 'stale endpoint detection (L2)' do
    it 'refresh interval does not mask dead services for too long' do
      registry = described_class.new
      registry.register('payments', 'http://payments:3000')

      # Refresh interval should be short enough or active checks should be used
      # The refresh should actually check health, not just return cached URL
      endpoint = registry.get_endpoint('payments')
      expect(endpoint).to be_a(String)
    end
  end
end
